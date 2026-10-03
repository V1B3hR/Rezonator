"""
Deterministic COBOL Runtime & Mutation Simulator.
Provides hermetic operational semantics for canonical COBOL programs.
Executes CFG/AST statements, maintains WORKING-STORAGE state, and records execution traces.
Enables verifiable ground-truth mutation testing for Phase F1/F2.
"""

import re
from typing import Dict, List, Any, Optional, Set, Tuple


class ExecutionState:
    def __init__(self, initial_vars: Dict[str, Any]):
        self.variables: Dict[str, Any] = dict(initial_vars)
        self.call_stack: List[str] = []
        self.trace: List[str] = []
        self.steps: int = 0
        self.terminated: bool = False
        self.timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variables": self.variables,
            "steps": self.steps,
            "terminated": self.terminated,
            "timed_out": self.timed_out,
            "trace_length": len(self.trace),
            "trace": self.trace
        }


class CobolRuntime:
    """
    Hermetic interpreter for canonical COBOL programs.
    Executes statement nodes from CobolASTGraphBuilder or raw source code.
    """

    def __init__(self):
        from mathy.ast_graph_builder import CobolASTGraphBuilder
        self.builder = CobolASTGraphBuilder()

    def _parse_val(self, raw_val: str) -> Any:
        """Parses a string or numeric literal into Python type."""
        s = str(raw_val).strip().strip('"').strip("'")
        if not s:
            return 0
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    def _eval_expr(self, expr_str: str, variables: Dict[str, Any]) -> Any:
        """Safely evaluates a COBOL arithmetic or boolean expression using variable values."""
        s = expr_str.strip()
        # 1. Substitute variable names by length-descending order
        for k in sorted(variables.keys(), key=len, reverse=True):
            val = variables[k]
            val_repr = repr(val) if isinstance(val, str) else str(val)
            s = re.sub(r'\b' + re.escape(k) + r'\b', val_repr, s, flags=re.IGNORECASE)

        # 2. Map COBOL keywords to Python equivalents
        s = re.sub(r'\bAND\b', ' and ', s, flags=re.IGNORECASE)
        s = re.sub(r'\bOR\b', ' or ', s, flags=re.IGNORECASE)
        s = re.sub(r'\bNOT\b', ' not ', s, flags=re.IGNORECASE)

        # 3. Map comparison operators: single '=' to '=='
        s = re.sub(r'(?<![<>=!])=(?![=])', '==', s)

        try:
            return eval(s, {"__builtins__": {}}, {})
        except Exception:
            return 0

    def run(self, source_code: str, initial_overrides: Optional[Dict[str, Any]] = None, max_steps: int = 500) -> ExecutionState:
        """Executes the COBOL source code and returns the full execution trace and variable state."""
        graph_data = self.builder.build_from_source(source_code)
        return self.run_graph(graph_data, initial_overrides=initial_overrides, max_steps=max_steps)

    def run_graph(self, graph_data: Dict[str, Any], initial_overrides: Optional[Dict[str, Any]] = None, max_steps: int = 500) -> ExecutionState:
        """Executes a pre-constructed AST graph payload."""
        # 1. Initialize variables from Working-Storage
        init_vars = {}
        for v in graph_data.get("variables", []):
            name = v["name"]
            raw_val = v.get("initial_value", "")
            init_vars[name] = self._parse_val(raw_val)

        if initial_overrides:
            for k, val in initial_overrides.items():
                init_vars[k.upper()] = val

        state = ExecutionState(init_vars)

        # 2. Build index of nodes and edges
        nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}
        cfg_edges = [e for e in graph_data.get("edges", []) if e["edge_type"].startswith("cfg_")]

        # Determine procedure structure
        paragraphs: Dict[str, List[str]] = {}
        for n in graph_data.get("nodes", []):
            para = n["paragraph"]
            if para not in paragraphs:
                paragraphs[para] = []
            paragraphs[para].append(n["id"])

        if not nodes_by_id:
            state.terminated = True
            return state

        # Execution starts at the first node of the first paragraph
        current_node_id = list(nodes_by_id.keys())[0]

        while current_node_id and state.steps < max_steps and not state.terminated:
            state.steps += 1
            state.trace.append(current_node_id)
            node = nodes_by_id[current_node_id]
            node_type = node["node_type"]
            label = node["label"]

            # Handle statement types
            if node_type == "stop":
                state.terminated = True
                break

            elif node_type == "perform":
                # Find call edge and continuation edge
                call_edges = [e for e in cfg_edges if e["source"] == current_node_id and e["edge_type"] == "cfg_call"]
                seq_edges = [e for e in cfg_edges if e["source"] == current_node_id and e["edge_type"] == "cfg_seq"]

                continuation = seq_edges[0]["target"] if seq_edges else None
                if call_edges:
                    target_entry = call_edges[0]["target"]
                    # If not self-recursive, push continuation to call stack
                    if target_entry != current_node_id and continuation:
                        state.call_stack.append(continuation)
                    current_node_id = target_entry
                    continue

            elif node_type == "branch":
                # Evaluate branch condition
                # Look at outgoing true and false edges
                true_edges = [e for e in cfg_edges if e["source"] == current_node_id and e["edge_type"] == "cfg_branch_true"]
                false_edges = [e for e in cfg_edges if e["source"] == current_node_id and e["edge_type"] == "cfg_branch_false"]

                # Extract condition from node code / label
                cond_code = node.get("code", "")
                if cond_code.upper().startswith("IF "):
                    cond_code = cond_code[3:].strip()
                cond_val = bool(self._eval_expr(cond_code, state.variables))

                if cond_val and true_edges:
                    current_node_id = true_edges[0]["target"]
                    continue
                elif not cond_val and false_edges:
                    current_node_id = false_edges[0]["target"]
                    continue

            elif node_type == "stmt":
                # Execute data mutation
                code = " ".join(node.get("code", node.get("label", "")).split())
                up = code.upper()

                if up.startswith("MOVE "):
                    # MOVE <val> TO <var>
                    m = re.match(r'MOVE\s+(.+?)\s+TO\s+([A-Za-z0-9_-]+)', code, re.IGNORECASE)
                    if m:
                        val_src, dest = m.group(1).strip(), m.group(2).strip().upper()
                        val = self._eval_expr(val_src, state.variables)
                        state.variables[dest] = val

                elif up.startswith("SUBTRACT ") or up.startswith("SUB "):
                    # SUBTRACT <val> FROM <var>
                    m = re.match(r'(?:SUBTRACT|SUB)\s+(.+?)\s+FROM\s+([A-Za-z0-9_-]+)', code, re.IGNORECASE)
                    if m:
                        val_src, dest = m.group(1).strip(), m.group(2).strip().upper()
                        sub_amt = self._eval_expr(val_src, state.variables)
                        current_dest_val = state.variables.get(dest, 0)
                        state.variables[dest] = current_dest_val - sub_amt

                elif up.startswith("ADD "):
                    # ADD <val> TO <var>
                    m = re.match(r'ADD\s+(.+?)\s+TO\s+([A-Za-z0-9_-]+)', code, re.IGNORECASE)
                    if m:
                        val_src, dest = m.group(1).strip(), m.group(2).strip().upper()
                        add_amt = self._eval_expr(val_src, state.variables)
                        current_dest_val = state.variables.get(dest, 0)
                        state.variables[dest] = current_dest_val + add_amt

                elif up.startswith("COMPUTE "):
                    # COMPUTE <var> = <expr>
                    m = re.match(r'COMPUTE\s+([A-Za-z0-9_-]+)\s*=\s*(.+)', code, re.IGNORECASE)
                    if m:
                        dest, expr = m.group(1).strip().upper(), m.group(2).strip().rstrip(".")
                        val = self._eval_expr(expr, state.variables)
                        state.variables[dest] = val

            # Advance to next sequential statement or return from call
            seq_edges = [e for e in cfg_edges if e["source"] == current_node_id and e["edge_type"] == "cfg_seq"]
            if seq_edges:
                current_node_id = seq_edges[0]["target"]
            elif state.call_stack:
                # Return from PERFORM
                current_node_id = state.call_stack.pop()
            else:
                # Check fallthrough to next paragraph
                fall_edges = [e for e in cfg_edges if e["source"] == current_node_id and e["edge_type"] == "cfg_fallthrough"]
                if fall_edges:
                    current_node_id = fall_edges[0]["target"]
                else:
                    state.terminated = True
                    break

        if state.steps >= max_steps:
            state.timed_out = True

        return state

    def mutate_and_compare(self, source_code: str, mutation_edits: List[Tuple[str, str]], initial_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Applies line-level text mutations to source_code, runs both baseline and mutated code,
        and computes the exact behavioral ground-truth impact (affected variables & trace delta).
        """
        # Baseline execution
        baseline_state = self.run(source_code, initial_overrides=initial_overrides)

        # Apply mutations
        mutated_code = source_code
        for old_txt, new_txt in mutation_edits:
            mutated_code = mutated_code.replace(old_txt, new_txt, 1)

        mutated_state = self.run(mutated_code, initial_overrides=initial_overrides)

        # Compare outputs
        affected_vars = {}
        all_var_names = set(baseline_state.variables.keys()) | set(mutated_state.variables.keys())
        for v in sorted(list(all_var_names)):
            b_val = baseline_state.variables.get(v)
            m_val = mutated_state.variables.get(v)
            if b_val != m_val:
                affected_vars[v] = {"baseline": b_val, "mutated": m_val}

        # Compare execution trace
        trace_diverged_at = None
        min_len = min(len(baseline_state.trace), len(mutated_state.trace))
        for step_i in range(min_len):
            if baseline_state.trace[step_i] != mutated_state.trace[step_i]:
                trace_diverged_at = step_i
                break
        if trace_diverged_at is None and len(baseline_state.trace) != len(mutated_state.trace):
            trace_diverged_at = min_len

        return {
            "baseline": baseline_state.to_dict(),
            "mutated": mutated_state.to_dict(),
            "affected_variables": affected_vars,
            "has_behavioral_change": len(affected_vars) > 0 or trace_diverged_at is not None,
            "trace_diverged_at_step": trace_diverged_at
        }
