"""
Static cycle and hazard reporting for parsed COBOL control-flow graphs.
Computes Strongly Connected Components (Tarjan's algorithm, O(V+E)) and
bounded simple-cycle extraction. It reports structural cycles and reachability
hazards under static CFG assumptions without claiming general program termination proofs.
"""

from typing import Dict, List, Set, Any, Optional
import networkx as nx
from rezonator.analysis_config import CYCLE_MAX_PER_SCC, CYCLE_TOTAL_BUDGET


class CycleDetector:
    """
    Reports cycle structure, recursive transfers, and selected heuristic hazards
    in the CFG produced by the supported-subset parser using linear-time SCC analysis
    and bounded cycle extraction.
    """

    def __init__(self, parsed_data: Dict[str, Any]):
        self.program_id = parsed_data.get("program_id", "UNKNOWN")
        self.nodes = parsed_data.get("nodes", [])
        self.edges = parsed_data.get("edges", [])
        self.variables = parsed_data.get("variables", [])

        # Build directed Control Flow Graph (CFG)
        self.cfg = nx.DiGraph()
        self.node_map: Dict[str, Dict[str, Any]] = {}

        for n in self.nodes:
            nid = n["id"]
            self.node_map[nid] = n
            self.cfg.add_node(nid, **n)

        for e in self.edges:
            etype = e.get("edge_type", "")
            # Only include control flow edges (sequential, branch, call, return)
            if etype.startswith("cfg_"):
                self.cfg.add_edge(e["source"], e["target"], edge_type=etype, label=e.get("label", ""))

    def analyze(self) -> Dict[str, Any]:
        """
        Runs comprehensive cycle, recursion, and terminal reachability analysis:
        1. Identifies entry nodes and terminal nodes (STOP RUN / GOBACK).
        2. Computes linear-time Strongly Connected Components (Tarjan's algorithm O(V+E)).
        3. Identifies non-trivial SCCs and trapped SCCs (no static escape path to terminal nodes).
        4. Bounded extraction of representative simple cycles within non-trivial SCCs.
        5. Evaluates data-flow guard invariance on extracted loops.
        """
        terminal_nodes = [
            n["id"] for n in self.nodes
            if n.get("node_type") in ("stop", "goback") or "STOP RUN" in n.get("code", "").upper()
        ]

        entry_node = self.nodes[0]["id"] if self.nodes else None

        # 1. Compute Strongly Connected Components via Tarjan's algorithm (O(V + E))
        all_sccs = list(nx.strongly_connected_components(self.cfg))

        # A non-trivial SCC has > 1 node, or 1 node with a self-loop
        non_trivial_sccs: List[Set[str]] = [
            scc for scc in all_sccs
            if len(scc) > 1 or (len(scc) == 1 and self.cfg.has_edge(next(iter(scc)), next(iter(scc))))
        ]

        def scc_can_reach_terminal(scc_nodes: Set[str]) -> bool:
            if not terminal_nodes:
                return False
            for nid in scc_nodes:
                for term in terminal_nodes:
                    if nx.has_path(self.cfg, nid, term):
                        return True
            return False

        # Check trapped SCCs (SCCs from which no terminal node can ever be reached)
        trapped_sccs = [scc for scc in non_trivial_sccs if not scc_can_reach_terminal(scc)]

        # 2. Bounded cycle extraction within non-trivial SCCs
        raw_cycles: List[List[str]] = []
        budget_exhausted = False

        for scc in non_trivial_sccs:
            if len(raw_cycles) >= CYCLE_TOTAL_BUDGET:
                budget_exhausted = True
                break
            sub = self.cfg.subgraph(scc)
            scc_count = 0
            try:
                for cycle in nx.simple_cycles(sub):
                    raw_cycles.append(cycle)
                    scc_count += 1
                    if scc_count >= CYCLE_MAX_PER_SCC:
                        budget_exhausted = True
                        break
                    if len(raw_cycles) >= CYCLE_TOTAL_BUDGET:
                        budget_exhausted = True
                        break
            except Exception:
                pass

        formatted_cycles = []
        is_recursive = False
        invariant_hazard_cycles = []

        for c in raw_cycles:
            cycle_nodes = [self.node_map[nid] for nid in c if nid in self.node_map]
            cycle_labels = [n.get("label", n.get("code", n.get("id", ""))) for n in cycle_nodes]
            has_perform = any(n.get("node_type") == "perform" for n in cycle_nodes)

            # Check if this cycle contains a recursive PERFORM
            if has_perform:
                is_recursive = True

            # Data-flow invariant check: what variables does the cycle read vs write?
            reads_in_cycle: Set[str] = set()
            writes_in_cycle: Set[str] = set()
            branch_cond_vars: Set[str] = set()

            for n in cycle_nodes:
                reads_in_cycle.update(n.get("reads", []))
                writes_in_cycle.update(n.get("writes", []))
                if n.get("node_type") == "branch":
                    branch_cond_vars.update(n.get("reads", []))

            # If cycle contains a branch condition depending on variables that are NEVER updated inside the cycle
            unmodified_guards = branch_cond_vars - writes_in_cycle
            is_invariant_loop = len(branch_cond_vars) > 0 and len(unmodified_guards) == len(branch_cond_vars)

            cycle_info = {
                "nodes": c,
                "path": cycle_labels,
                "length": len(c),
                "is_recursive_call": has_perform,
                "branch_guard_vars": sorted(list(branch_cond_vars)),
                "unmodified_guard_vars": sorted(list(unmodified_guards)),
                "is_invariant_hazard": is_invariant_loop
            }
            formatted_cycles.append(cycle_info)
            if is_invariant_loop:
                invariant_hazard_cycles.append(cycle_info)

        # 3. Terminal reachability analysis per cycle:
        trapped_cycles = []
        for c in raw_cycles:
            can_escape = False
            for nid in c:
                for term in terminal_nodes:
                    if nx.has_path(self.cfg, nid, term):
                        can_escape = True
                        break
                if can_escape:
                    break
            if not can_escape:
                trapped_cycles.append(c)

        # Reachability from entry to terminals
        can_reach_terminal = False
        if entry_node and terminal_nodes:
            can_reach_terminal = any(nx.has_path(self.cfg, entry_node, term) for term in terminal_nodes)

        # SCC summary objects
        scc_summaries = []
        for idx, scc in enumerate(non_trivial_sccs, 1):
            can_esc = scc_can_reach_terminal(scc)
            scc_summaries.append({
                "scc_id": f"SCC-{idx}",
                "node_count": len(scc),
                "nodes": sorted(list(scc)),
                "can_escape_to_terminal": can_esc,
                "is_trapped": not can_esc,
            })

        # 4. Determine Overall Risk Verdict
        has_cycles = len(non_trivial_sccs) > 0
        if trapped_cycles or trapped_sccs or (is_recursive and invariant_hazard_cycles):
            risk_verdict = "CRITICAL_INFINITE_LOOP"
            risk_description = "Execution path contains strongly connected cyclic sink components or recursive cycles with invariant guard conditions under static CFG reachability."
            has_deadlock = True
        elif is_recursive:
            risk_verdict = "POTENTIAL_RECURSION"
            risk_description = "Recursive control transfer detected within strongly connected component. Verify dynamic base termination condition."
            has_deadlock = False
        elif has_cycles:
            risk_verdict = "ITERATIVE_LOOP"
            risk_description = "Control flow contains standard iterative loops with valid escape paths to exit."
            has_deadlock = False
        else:
            risk_verdict = "DIRECTED_ACYCLIC_FLOW"
            risk_description = "Control flow is strictly acyclic (DAG). Guaranteed finite forward execution under static CFG."
            has_deadlock = False

        return {
            "program_id": self.program_id,
            "has_cycles": has_cycles,
            "has_deadlock": has_deadlock,
            "is_recursive": is_recursive,
            "cycle_count": len(raw_cycles),
            "cycles": formatted_cycles,
            "scc_count": len(non_trivial_sccs),
            "non_trivial_scc_count": len(non_trivial_sccs),
            "trapped_scc_count": len(trapped_sccs),
            "trapped_cycle_count": len(trapped_cycles),
            "invariant_hazard_count": len(invariant_hazard_cycles),
            "cycle_budget_exhausted": budget_exhausted,
            "max_cycles_per_scc": CYCLE_MAX_PER_SCC,
            "total_cycle_budget": CYCLE_TOTAL_BUDGET,
            "sccs": scc_summaries,
            "terminal_nodes": terminal_nodes,
            "reaches_terminal": can_reach_terminal,
            "risk_verdict": risk_verdict,
            "risk_description": risk_description
        }
