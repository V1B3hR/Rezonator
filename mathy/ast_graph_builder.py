"""
AST-to-Graph Builder for COBOL Programs.
Constructs formal, typed, directed Control Flow Graphs (CFG) and Data Flow Graphs (DFG)
from the cobolparser AST, adhering to IBM Enterprise COBOL and ANSI-85 semantics.
"""

import re
from typing import Dict, List, Set, Any, Optional, Tuple

try:
    import cobolparser
    from cobolparser.models.statements import (
        IfStatement, PerformStatement, StopStatement, GobackStatement,
        MoveStatement, SubtractStatement, AddStatement, ComputeStatement
    )
    COBOLPARSER_AVAILABLE = True
except ImportError:
    COBOLPARSER_AVAILABLE = False


class CobolASTGraphBuilder:
    """
    Constructs high-fidelity program dependence graphs (CFG + DFG) from COBOL AST.
    """

    def __init__(self):
        self.program_id = "UNKNOWN-PROGRAM"
        self.variables: Dict[str, Dict[str, Any]] = {}
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    @classmethod
    def is_available(cls) -> bool:
        return COBOLPARSER_AVAILABLE

    def build_from_source(self, source_code: str) -> Dict[str, Any]:
        """Parses COBOL source code and builds the unified graph payload."""
        if not COBOLPARSER_AVAILABLE:
            raise RuntimeError("cobolparser package is not installed.")

        res = cobolparser.parse_cobol(source_code)
        if not res.success or res.ast is None:
            err_msg = "; ".join(str(e) for e in res.errors) if res.errors else "Unknown parse failure"
            raise SyntaxError(f"COBOL parse error: {err_msg}")

        return self.build_from_ast(res.ast)

    def build_from_ast(self, ast_program: Any) -> Dict[str, Any]:
        """Builds CFG and DFG from a parsed CobolProgram AST instance."""
        self.program_id = getattr(ast_program, "program_name", "UNKNOWN-PROGRAM")
        self.variables.clear()
        self.nodes.clear()
        self.edges.clear()

        # 1. Extract Working-Storage variables
        data_items = ast_program.get_data_items() if hasattr(ast_program, "get_data_items") else []
        for d in data_items:
            name = d.name.upper()
            pic_str = ""
            if hasattr(d, "picture_clause") and d.picture_clause:
                pic_str = getattr(d.picture_clause, "pattern", "") or ""
            elif hasattr(d, "picture"):
                pic_str = getattr(d, "picture", "") or ""

            init_val = getattr(d, "initial_value", None) or getattr(d, "value_clause", None) or getattr(d, "value", "")
            init_val_clean = str(init_val or "").strip().strip('"').strip("'")

            self.variables[name] = {
                "name": name,
                "pic": str(pic_str),
                "initial_value": init_val_clean,
                "level": getattr(d, "level", 1) or 1
            }

        # 2. Extract Procedures & Statements
        procedures = ast_program.get_procedures() if hasattr(ast_program, "get_procedures") else []
        
        # Maps for inter-procedural linking
        para_entries: Dict[str, str] = {}
        para_exits: Dict[str, List[str]] = {}

        # First pass: Create statement nodes for each paragraph
        for proc in procedures:
            para_name = proc.paragraph_name
            para_exits[para_name] = []
            para_stmts = proc.statements

            if not para_stmts:
                continue

            entry_id, exits = self._process_statement_block(para_stmts, para_name, continuation_id=None)
            if entry_id:
                para_entries[para_name] = entry_id
            para_exits[para_name].extend(exits)

        # Second pass: Connect PERFORM call and return edges
        self._link_perform_calls(para_entries, para_exits)

        # Third pass: Connect paragraph fallthrough edges where applicable
        self._link_fallthroughs(procedures, para_entries, para_exits)

        # Fourth pass: Build direct Def-Use DFG edges
        self._link_def_use_chains()

        return {
            "program_id": self.program_id,
            "variables": list(self.variables.values()),
            "nodes": list(self.nodes.values()),
            "edges": self.edges
        }

    def _extract_vars_from_expr(self, obj: Any) -> Set[str]:
        """Recursively extracts declared variable names from an AST expression or string."""
        found = set()
        if obj is None:
            return found

        if isinstance(obj, str):
            for v in self.variables:
                if re.search(r'\b' + re.escape(v) + r'\b', obj):
                    found.add(v)
            return found

        if hasattr(obj, "children") and obj.children:
            for child in obj.children:
                found.update(self._extract_vars_from_expr(child))

        for attr in ["left_operand", "right_operand", "left_condition", "right_condition", "source", "expression"]:
            if hasattr(obj, attr):
                val = getattr(obj, attr)
                if isinstance(val, str):
                    for v in self.variables:
                        if re.search(r'\b' + re.escape(v) + r'\b', val):
                            found.add(v)
                elif val is not None:
                    found.update(self._extract_vars_from_expr(val))

        return found

    def _analyze_statement_io(self, stmt: Any) -> Tuple[Set[str], Set[str]]:
        """Identifies exact (reads, writes) variable sets for a given statement."""
        reads: Set[str] = set()
        writes: Set[str] = set()
        stype = type(stmt).__name__

        # 1. Writes
        targets = getattr(stmt, "targets", None)
        if targets:
            for t in targets:
                t_up = str(t).upper()
                if t_up in self.variables:
                    writes.add(t_up)
        target = getattr(stmt, "target", None)
        if target:
            t_up = str(target).upper()
            if t_up in self.variables:
                writes.add(t_up)

        # 2. Reads from Condition
        if hasattr(stmt, "condition") and stmt.condition:
            reads.update(self._extract_vars_from_expr(stmt.condition))

        # 3. Reads from Expression
        if hasattr(stmt, "expression") and stmt.expression:
            reads.update(self._extract_vars_from_expr(stmt.expression))

        # 4. Reads from Source
        if hasattr(stmt, "source") and stmt.source:
            reads.update(self._extract_vars_from_expr(stmt.source))

        # 5. Operands (Subtract / Add / Move)
        if hasattr(stmt, "operands") and stmt.operands:
            for op in stmt.operands:
                op_up = str(op).upper()
                if op_up in self.variables and op_up not in writes:
                    reads.add(op_up)

        # In-place arithmetic without GIVING: SUBTRACT A FROM B -> reads A and B, writes B
        if stype in ("SubtractStatement", "AddStatement") and not getattr(stmt, "giving", None):
            if target and str(target).upper() in self.variables:
                reads.add(str(target).upper())
            elif targets:
                for t in targets:
                    t_up = str(t).upper()
                    if t_up in self.variables:
                        reads.add(t_up)

        return reads, writes

    def _format_condition(self, cond: Any) -> str:
        """Reconstructs clean, standard conditional expression string from AST condition."""
        if cond is None:
            return "TRUE"
        if hasattr(cond, "left_condition") and hasattr(cond, "right_condition") and cond.left_condition:
            op = str(getattr(cond, "operator", "AND")).upper()
            return f"({self._format_condition(cond.left_condition)} {op} {self._format_condition(cond.right_condition)})"
        if hasattr(cond, "children") and len(cond.children) == 2:
            op = str(getattr(cond, "operator", "AND")).upper()
            return f"({self._format_condition(cond.children[0])} {op} {self._format_condition(cond.children[1])})"

        left = getattr(cond, "left_operand", "")
        op = str(getattr(cond, "operator", "=")).upper()
        right = getattr(cond, "right_operand", "")
        op_map = {
            "EQUAL": "=", "EQUALS": "=",
            "NOT_EQUAL": "!=",
            "LESS": "<", "LESS_THAN": "<",
            "LESS_OR_EQUAL": "<=",
            "GREATER": ">", "GREATER_THAN": ">",
            "GREATER_OR_EQUAL": ">="
        }
        op_sym = op_map.get(op, op)
        return f"{left} {op_sym} {right}".strip()

    def _create_node(self, stmt: Any, para_name: str) -> Dict[str, Any]:
        """Creates a standardized ProgramNode dictionary from an AST statement."""
        stype_name = type(stmt).__name__.replace("Statement", "").upper()
        line = stmt.location.line if getattr(stmt, "location", None) else 0
        node_id = f"{para_name}:L{line}_{stype_name}"

        # Classify node type and reconstruct human-readable code
        if isinstance(stmt, IfStatement):
            node_type = "branch"
            cond_str = self._format_condition(stmt.condition)
            label = f"IF {cond_str[:24]}"
            code = f"IF {cond_str}"
        elif isinstance(stmt, PerformStatement):
            node_type = "perform"
            target_p = getattr(stmt, "target_paragraph", "") or (stmt.operands[0] if getattr(stmt, "operands", None) else "")
            label = f"PERFORM {target_p}"
            code = f"PERFORM {target_p}"
        elif isinstance(stmt, (StopStatement, GobackStatement)):
            node_type = "stop"
            label = "STOP RUN" if isinstance(stmt, StopStatement) else "GOBACK"
            code = label
        elif isinstance(stmt, MoveStatement):
            node_type = "stmt"
            dest = ", ".join(stmt.targets) if getattr(stmt, "targets", None) else getattr(stmt, "target", "")
            label = f"MOVE {dest}"
            code = f"MOVE {getattr(stmt, 'source', '')} TO {dest}"
        elif isinstance(stmt, SubtractStatement):
            node_type = "stmt"
            src = stmt.operands[0] if getattr(stmt, "operands", None) else ""
            dest = getattr(stmt, "target", "") or (stmt.targets[0] if getattr(stmt, "targets", None) else "")
            label = f"SUB {dest}"
            code = f"SUBTRACT {src} FROM {dest}"
        elif isinstance(stmt, AddStatement):
            node_type = "stmt"
            src = stmt.operands[0] if getattr(stmt, "operands", None) else ""
            dest = getattr(stmt, "target", "") or (stmt.targets[0] if getattr(stmt, "targets", None) else "")
            label = f"ADD {dest}"
            code = f"ADD {src} TO {dest}"
        elif isinstance(stmt, ComputeStatement):
            node_type = "stmt"
            dest = ", ".join(stmt.targets) if getattr(stmt, "targets", None) else getattr(stmt, "target", "")
            expr = getattr(stmt, "expression", "")
            label = f"COMPUTE {dest}"
            code = f"COMPUTE {dest} = {expr}"
        else:
            node_type = "stmt"
            target_var = getattr(stmt, "target", "") or (stmt.targets[0] if getattr(stmt, "targets", None) else "")
            label = f"{stype_name} {target_var}".strip()
            code = label

        reads, writes = self._analyze_statement_io(stmt)

        node = {
            "id": node_id,
            "label": label,
            "node_type": node_type,
            "paragraph": para_name,
            "code": code,
            "reads": sorted(list(reads)),
            "writes": sorted(list(writes)),
            "location": {"line": line, "column": getattr(stmt.location, "column", 0) if getattr(stmt, "location", None) else 0},
            "_ast_stmt": stmt
        }
        self.nodes[node_id] = node
        return node

    def _process_statement_block(self, stmts: List[Any], para_name: str, continuation_id: Optional[str]) -> Tuple[Optional[str], List[str]]:
        """
        Recursively processes a sequential block of statements.
        Returns: (entry_node_id, list_of_exit_node_ids)
        """
        if not stmts:
            return None, []

        created_nodes = [self._create_node(s, para_name) for s in stmts]
        entry_node_id = created_nodes[0]["id"]
        exits: List[str] = []

        for i, curr_node in enumerate(created_nodes):
            curr_id = curr_node["id"]
            curr_stmt = curr_node["_ast_stmt"]
            is_terminal = curr_node["node_type"] == "stop"

            # Determine next sequential statement in this block
            next_in_block = created_nodes[i + 1]["id"] if i + 1 < len(created_nodes) else continuation_id

            if isinstance(curr_stmt, IfStatement):
                # Branch TRUE
                then_stmts = getattr(curr_stmt, "then_statements", []) or []
                then_entry, then_exits = self._process_statement_block(then_stmts, para_name, next_in_block)
                if then_entry:
                    self.edges.append({
                        "source": curr_id,
                        "target": then_entry,
                        "edge_type": "cfg_branch_true",
                        "weight": 1.0,
                        "label": "true"
                    })

                # Branch FALSE
                else_stmts = getattr(curr_stmt, "else_statements", []) or []
                if else_stmts:
                    else_entry, else_exits = self._process_statement_block(else_stmts, para_name, next_in_block)
                    if else_entry:
                        self.edges.append({
                            "source": curr_id,
                            "target": else_entry,
                            "edge_type": "cfg_branch_false",
                            "weight": 1.0,
                            "label": "false"
                        })
                else:
                    # No ELSE branch: falls directly to next statement
                    else_exits = [curr_id]
                    if next_in_block:
                        self.edges.append({
                            "source": curr_id,
                            "target": next_in_block,
                            "edge_type": "cfg_branch_false",
                            "weight": 1.0,
                            "label": "false"
                        })

                # If this IF is the last statement in the block, its exits become block exits
                if i == len(created_nodes) - 1:
                    exits.extend(then_exits)
                    exits.extend(else_exits)

            else:
                # Regular non-branch statement
                if not is_terminal and next_in_block:
                    self.edges.append({
                        "source": curr_id,
                        "target": next_in_block,
                        "edge_type": "cfg_seq",
                        "weight": 1.0,
                        "label": "seq"
                    })

                if i == len(created_nodes) - 1 and not is_terminal:
                    exits.append(curr_id)

        return entry_node_id, exits

    def _link_perform_calls(self, para_entries: Dict[str, str], para_exits: Dict[str, List[str]]):
        """Creates cfg_call and cfg_return edges for PERFORM statements."""
        for nid, node in list(self.nodes.items()):
            stmt = node.get("_ast_stmt")
            if not isinstance(stmt, PerformStatement):
                continue

            target_p = getattr(stmt, "target_paragraph", "") or (stmt.operands[0] if getattr(stmt, "operands", None) else "")
            target_p = target_p.upper().rstrip(".")

            if target_p not in para_entries:
                continue

            target_entry = para_entries[target_p]

            # 1. Call edge
            self.edges.append({
                "source": nid,
                "target": target_entry,
                "edge_type": "cfg_call",
                "weight": 1.5,
                "label": "call"
            })

            # 2. Return edge (from target exits to continuation after PERFORM)
            # Only if not calling self
            if target_p != node["paragraph"]:
                # Find sequential successor of PERFORM
                seq_succs = [e["target"] for e in self.edges if e["source"] == nid and e["edge_type"] in ("cfg_seq", "cfg_branch_true", "cfg_branch_false")]
                continuation = seq_succs[0] if seq_succs else None

                if continuation:
                    for exit_node in para_exits.get(target_p, []):
                        if exit_node != nid:
                            self.edges.append({
                                "source": exit_node,
                                "target": continuation,
                                "edge_type": "cfg_return",
                                "weight": 1.2,
                                "label": "return"
                            })

    def _link_fallthroughs(self, procedures: List[Any], para_entries: Dict[str, str], para_exits: Dict[str, List[str]]):
        """Creates cfg_fallthrough edges between consecutive paragraphs if no terminal barrier exists."""
        for i in range(len(procedures) - 1):
            curr_proc = procedures[i]
            next_proc = procedures[i + 1]

            curr_name = curr_proc.paragraph_name
            next_name = next_proc.paragraph_name

            if next_name not in para_entries:
                continue

            next_entry = para_entries[next_name]

            # In COBOL, fallthrough occurs from the exits of paragraph i to entry of paragraph i+1
            for exit_node in para_exits.get(curr_name, []):
                # Don't add redundant fallthrough if it's already connected to next_entry
                already_connected = any(e["source"] == exit_node and e["target"] == next_entry for e in self.edges)
                if not already_connected:
                    self.edges.append({
                        "source": exit_node,
                        "target": next_entry,
                        "edge_type": "cfg_fallthrough",
                        "weight": 0.8,
                        "label": "fallthrough"
                    })

    def _link_def_use_chains(self):
        """Creates direct dfg_def_use data dependency edges from writers to readers."""
        # Simple reaching definition tracking across CFG
        for r_nid, r_node in self.nodes.items():
            for read_var in r_node.get("reads", []):
                for w_nid, w_node in self.nodes.items():
                    if w_nid != r_nid and read_var in w_node.get("writes", []):
                        self.edges.append({
                            "source": w_nid,
                            "target": r_nid,
                            "edge_type": "dfg_def_use",
                            "weight": 1.0,
                            "label": f"def_use({read_var})"
                        })

        # Strip internal temporary AST object reference before returning payload
        for n in self.nodes.values():
            n.pop("_ast_stmt", None)
