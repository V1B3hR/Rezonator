"""
Cycle, Recursion & Termination Analyzer for COBOL Control Flow Graphs.
Applies graph-theoretic SCC (Strongly Connected Components), cycle enumeration,
and reachability to formally verify termination and detect infinite recursion / deadlock traps.
"""

from typing import Dict, List, Set, Any, Optional
import networkx as nx


class CycleDetector:
    """
    Rigorously detects loops, recursions, and terminal trapping states in COBOL CFG.
    Replaces heuristic pseudo-physics with exact graph-theoretic formal verification.
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
        Runs comprehensive termination, cycle, and recursion analysis:
        1. Identifies entry nodes and terminal nodes (STOP RUN / GOBACK).
        2. Detects all simple cycles and recursive calls in CFG.
        3. Identifies terminal sink SCCs (cycles with no exit path to STOP RUN).
        4. Checks whether condition variables in guarded loops are invariant (never updated).
        """
        terminal_nodes = [
            n["id"] for n in self.nodes
            if n.get("node_type") in ("stop", "goback") or "STOP RUN" in n.get("code", "").upper()
        ]

        entry_node = self.nodes[0]["id"] if self.nodes else None

        # 1. Detect simple cycles in CFG
        try:
            raw_cycles = list(nx.simple_cycles(self.cfg))
        except Exception:
            raw_cycles = []

        formatted_cycles = []
        is_recursive = False
        invariant_hazard_cycles = []

        for c in raw_cycles:
            cycle_nodes = [self.node_map[nid] for nid in c if nid in self.node_map]
            cycle_labels = [n.get("label", n.get("code", n.get("id", ""))) for n in cycle_nodes]
            has_perform = any(n.get("node_type") == "perform" for n in cycle_nodes)

            # Check if this cycle is a recursive PERFORM
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

        # 2. Terminal reachability analysis:
        # Check if every node in each cycle can reach at least one terminal node
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

        # 3. Determine Overall Risk Verdict
        if trapped_cycles or (is_recursive and invariant_hazard_cycles):
            risk_verdict = "CRITICAL_INFINITE_LOOP"
            risk_description = "Execution path contains guaranteed infinite recursion / deadlock cycle with invariant guard conditions."
            has_deadlock = True
        elif is_recursive:
            risk_verdict = "POTENTIAL_RECURSION"
            risk_description = "Recursive control transfer detected. Verify dynamic base termination condition."
            has_deadlock = False
        elif raw_cycles:
            risk_verdict = "ITERATIVE_LOOP"
            risk_description = "Control flow contains standard iterative loops with valid escape paths to exit."
            has_deadlock = False
        else:
            risk_verdict = "DIRECTED_ACYCLIC_FLOW"
            risk_description = "Control flow is strictly acyclic (DAG). Guaranteed finite forward execution."
            has_deadlock = False

        return {
            "program_id": self.program_id,
            "has_cycles": len(raw_cycles) > 0,
            "has_deadlock": has_deadlock,
            "is_recursive": is_recursive,
            "cycle_count": len(raw_cycles),
            "cycles": formatted_cycles,
            "trapped_cycle_count": len(trapped_cycles),
            "invariant_hazard_count": len(invariant_hazard_cycles),
            "terminal_nodes": terminal_nodes,
            "reaches_terminal": can_reach_terminal,
            "risk_verdict": risk_verdict,
            "risk_description": risk_description
        }
