"""
COBOL Front-End: Lexer, AST & Unified Graph (CFG + DFG) Builder.
Extracts basic blocks, control transfers, variable definitions, and usage chains.
"""

import re
from typing import Dict, List, Set, Any, Tuple

from rezonator.limits import ResourceLimitError, validate_graph_payload, validate_source_size


class VariableDef:
    def __init__(self, name: str, pic: str = "", initial_value: str = "", level: int = 1):
        self.name = name.strip().upper()
        self.pic = pic.strip()
        self.initial_value = initial_value.strip().strip('"').strip("'")
        self.level = level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "pic": self.pic,
            "initial_value": self.initial_value,
            "level": self.level
        }


class ProgramNode:
    def __init__(self, node_id: str, label: str, node_type: str, paragraph: str, code: str):
        self.id = node_id
        self.label = label
        self.node_type = node_type  # 'entry', 'stmt', 'branch', 'perform', 'stop', 'var'
        self.paragraph = paragraph
        self.code = code.strip()
        self.reads: Set[str] = set()
        self.writes: Set[str] = set()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            "paragraph": self.paragraph,
            "code": self.code,
            "reads": sorted(list(self.reads)),
            "writes": sorted(list(self.writes))
        }


class GraphEdge:
    def __init__(self, source: str, target: str, edge_type: str, weight: float = 1.0, label: str = ""):
        self.source = source
        self.target = target
        self.edge_type = edge_type  # 'cfg_seq', 'cfg_branch', 'cfg_call', 'dfg_read', 'dfg_write'
        self.weight = weight
        self.label = label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "label": self.label
        }


COBOL_RESERVED_KEYWORDS: Set[str] = {
    "IF", "ELSE", "END-IF", "PERFORM", "END-PERFORM",
    "MOVE", "ADD", "SUBTRACT", "COMPUTE", "MULTIPLY", "DIVIDE",
    "STOP", "EXIT", "GOBACK", "CONTINUE", "DISPLAY", "ACCEPT",
    "GO", "GOTO", "READ", "WRITE", "OPEN", "CLOSE", "CALL",
    "EVALUATE", "WHEN", "END-EVALUATE", "SECTION"
}


class CobolParser:
    """
    Robust lightweight parser for COBOL business logic and mainframe batch programs.
    Extracts Data Division state variables and Procedure Division Control/Data flow graphs.
    """

    def __init__(self):
        self.variables: Dict[str, VariableDef] = {}
        self.nodes: Dict[str, ProgramNode] = {}
        self.edges: List[GraphEdge] = []
        self.program_id: str = "UNKNOWN-PROGRAM"

    def clean_cobol_text(self, source: str) -> List[str]:
        """Cleans columns 1-6 (sequence numbers) and column 7 (indicator area) if fixed format."""
        lines = []
        for raw_line in source.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue

            # Standard 80-column fixed format check
            if len(line) >= 7 and line[6] in ('*', '/'):
                continue  # Comment line

            # Strip sequence numbers if 6 digits or spaces at start
            if len(line) > 6 and (line[:6].isdigit() or line[:6].isspace()):
                line = line[6:]
                if len(line) > 0 and line[0] in (' ', '-'):
                    line = line[1:]

            # Strip inline comments (e.g., *> )
            if "*>" in line:
                line = line.split("*>")[0]

            line = line.strip()
            if line:
                lines.append(line)
        return lines

    def parse(self, source_code: str) -> Dict[str, Any]:
        validate_source_size(source_code)
        # 1. Primary engine: Compiler-grade AST Graph Builder
        try:
            from rezonator.ast_graph_builder import CobolASTGraphBuilder
            if CobolASTGraphBuilder.is_available():
                return CobolASTGraphBuilder().build_from_source(source_code)
        except ResourceLimitError:
            raise
        except Exception:
            pass

        # 2. Fallback engine: Lightweight regex-based graph parser
        self.variables.clear()
        self.nodes.clear()
        self.edges.clear()

        lines = self.clean_cobol_text(source_code)
        full_text = " ".join(lines)

        # 1. Program ID
        prog_match = re.search(r'PROGRAM-ID\.\s+([A-Za-z0-9_-]+)', full_text, re.IGNORECASE)
        if prog_match:
            self.program_id = prog_match.group(1).upper()

        # 2. Extract Data Division (Working-Storage)
        self._parse_data_division(full_text)

        # 3. Extract Procedure Division
        self._parse_procedure_division(lines)

        # 4. Construct Unified Analytic Graph
        payload = self._build_graph_payload()
        validate_graph_payload(payload, include_variables=True)
        return payload

    def _parse_data_division(self, text: str):
        ws_idx = text.upper().find("WORKING-STORAGE SECTION")
        proc_idx = text.upper().find("PROCEDURE DIVISION")

        if ws_idx != -1:
            end_idx = proc_idx if proc_idx != -1 else len(text)
            ws_text = text[ws_idx:end_idx]

            # Regex for 01-49 level declarations: 01 WS-VAR PIC X(10) VALUE "ABC".
            var_pattern = re.compile(
                r'(\d{2})\s+([A-Za-z0-9_-]+)(?:\s+PIC\s+([A-Za-z0-9()Vv]+))?(?:\s+VALUE\s+([^.]+))?\.',
                re.IGNORECASE
            )
            for match in var_pattern.finditer(ws_text):
                level_str, name, pic, val = match.groups()
                level = int(level_str)
                name_clean = name.upper()
                pic_clean = pic or ""
                val_clean = val or ""
                self.variables[name_clean] = VariableDef(
                    name=name_clean,
                    pic=pic_clean,
                    initial_value=val_clean,
                    level=level
                )

    def _parse_procedure_division(self, lines: List[str]):
        # Locate Procedure Division
        proc_start = False
        raw_paragraphs: Dict[str, List[str]] = {}
        current_para = "GLOBAL-ENTRY"
        raw_paragraphs[current_para] = []

        for line in lines:
            line_up = line.upper().strip()
            if "PROCEDURE DIVISION" in line_up:
                proc_start = True
                continue

            if not proc_start:
                continue

            # Check if this line is a legitimate paragraph header
            para_match = re.match(r'^([A-Za-z0-9_-]+)\.\s*$', line.strip())
            if para_match:
                cand = para_match.group(1).upper()
                if cand not in COBOL_RESERVED_KEYWORDS:
                    current_para = cand
                    if current_para not in raw_paragraphs:
                        raw_paragraphs[current_para] = []
                    continue

            raw_paragraphs[current_para].append(line)

        # Create graph nodes and flow connections
        para_entry_nodes: Dict[str, str] = {}
        para_exit_nodes: Dict[str, str] = {}

        node_counter = 0

        # Step A: Create nodes for statements in paragraphs
        for para_name, para_lines in raw_paragraphs.items():
            if not para_lines and para_name == "GLOBAL-ENTRY":
                continue

            para_text = " ".join(para_lines)
            sentences = [s.strip() for s in re.split(r'\.\s+', para_text) if s.strip()]

            prev_node_id = None
            first_node_id = None

            for s_idx, sentence in enumerate(sentences):
                # Clean up period
                stmt_clean = sentence.rstrip('.')
                if not stmt_clean:
                    continue

                # Handle composite statements (e.g. IF ... ELSE ... END-IF or multiple statements)
                stmts_broken = self._break_statements(stmt_clean)

                for piece in stmts_broken:
                    node_counter += 1
                    node_id = f"node_{node_counter}"
                    node_type, label = self._classify_statement(piece)

                    node = ProgramNode(
                        node_id=node_id,
                        label=label,
                        node_type=node_type,
                        paragraph=para_name,
                        code=piece
                    )

                    # Determine data reads and writes
                    self._annotate_data_flow(node)

                    self.nodes[node_id] = node

                    if first_node_id is None:
                        first_node_id = node_id

                    if prev_node_id and self.nodes[prev_node_id].node_type not in ("stop", "goback"):
                        # Sequential control flow edge
                        self.edges.append(GraphEdge(
                            source=prev_node_id,
                            target=node_id,
                            edge_type="cfg_seq",
                            weight=1.0,
                            label="seq"
                        ))

                    # Do not flow sequentially out of termination statements
                    prev_node_id = None if node_type in ("stop", "goback") else node_id

            if first_node_id:
                para_entry_nodes[para_name] = first_node_id
            if prev_node_id:
                para_exit_nodes[para_name] = prev_node_id

        # Step B: Connect PERFORM calls and branching
        self._link_calls_and_branches(para_entry_nodes, para_exit_nodes)

        # Step C: Connect Data Flow edges (between nodes and variable state)
        self._link_data_dependencies()

    def _break_statements(self, text: str) -> List[str]:
        """Splits IF/ELSE/END-IF and sequential verbs into granular statement nodes."""
        tokens = text.split()
        pieces = []
        curr = []

        delimiters = {
            "PERFORM", "IF", "ELSE", "END-IF", "MOVE", "SUBTRACT",
            "ADD", "COMPUTE", "MULTIPLY", "DIVIDE", "STOP", "GO", "GOBACK", "EXIT"
        }

        for t in tokens:
            up = t.upper().rstrip('.')
            if up in delimiters and curr:
                pieces.append(" ".join(curr))
                curr = [t]
                continue
            curr.append(t)

        if curr:
            pieces.append(" ".join(curr))
        return [p for p in pieces if p.strip()]

    def _classify_statement(self, code: str) -> Tuple[str, str]:
        up = code.upper()
        if up.startswith("IF"):
            cond = code[2:].strip()
            return "branch", f"IF {cond[:24]}"
        elif up.startswith("ELSE"):
            return "branch", "ELSE"
        elif up.startswith("END-IF"):
            return "stmt", "END-IF"
        elif up.startswith("PERFORM"):
            target = code[7:].strip()
            return "perform", f"PERFORM {target[:20]}"
        elif "STOP RUN" in up or up.startswith("STOP"):
            return "stop", "STOP RUN"
        elif up.startswith("GOBACK"):
            return "stop", "GOBACK"
        elif up.startswith("MOVE"):
            return "stmt", f"MOVE {code[4:20].strip()}"
        elif up.startswith("SUBTRACT"):
            return "stmt", f"SUB {code[8:20].strip()}"
        elif up.startswith("ADD"):
            return "stmt", f"ADD {code[3:20].strip()}"
        elif up.startswith("COMPUTE"):
            return "stmt", f"COMPUTE {code[7:20].strip()}"
        elif up.startswith("GO TO") or up.startswith("GOTO"):
            return "branch", f"GOTO {code[4:20].strip()}"
        return "stmt", code[:28]

    def _annotate_data_flow(self, node: ProgramNode):
        """Identifies which variables are read or written by this node."""
        up = node.code.upper()
        var_names = list(self.variables.keys())

        # WRITE Patterns:
        # MOVE <val> TO <var>
        move_to = re.search(r'TO\s+([A-Za-z0-9_-]+)', up)
        if move_to:
            target_var = move_to.group(1)
            if target_var in self.variables:
                node.writes.add(target_var)

        # SUBTRACT <X> FROM <Y>
        sub_match = re.search(r'SUBTRACT\s+([A-Za-z0-9_-]+)\s+FROM\s+([A-Za-z0-9_-]+)', up)
        if sub_match:
            r_var, w_var = sub_match.group(1), sub_match.group(2)
            if r_var in self.variables:
                node.reads.add(r_var)
            if w_var in self.variables:
                node.writes.add(w_var)
                node.reads.add(w_var)

        # ADD <X> TO <Y>
        add_match = re.search(r'ADD\s+([A-Za-z0-9_-]+)\s+TO\s+([A-Za-z0-9_-]+)', up)
        if add_match:
            r_var, w_var = add_match.group(1), add_match.group(2)
            if r_var in self.variables:
                node.reads.add(r_var)
            if w_var in self.variables:
                node.writes.add(w_var)
                node.reads.add(w_var)

        # COMPUTE <Y> = <expr>
        comp_match = re.search(r'COMPUTE\s+([A-Za-z0-9_-]+)\s*=', up)
        if comp_match:
            w_var = comp_match.group(1)
            if w_var in self.variables:
                node.writes.add(w_var)

        # Check all other variable occurrences as reads (ensure full word boundary match)
        for var in var_names:
            if re.search(r'\b' + re.escape(var) + r'\b', up) and var not in node.writes:
                node.reads.add(var)

    def _link_calls_and_branches(self, para_entries: Dict[str, str], para_exits: Dict[str, str]):
        node_keys = list(self.nodes.keys())
        for idx, node_id in enumerate(node_keys):
            node = self.nodes[node_id]
            up = node.code.upper()

            # PERFORM paragraph link
            if node.node_type == "perform":
                tokens = up.split()
                if len(tokens) >= 2:
                    target_para = tokens[1].rstrip('.')
                    if target_para in para_entries:
                        target_entry = para_entries[target_para]
                        # 1. Call edge
                        self.edges.append(GraphEdge(
                            source=node_id,
                            target=target_entry,
                            edge_type="cfg_call",
                            weight=1.5,
                            label="call"
                        ))
                        # 2. Return edge from paragraph exit to next node
                        # (Only if not self-recursion to avoid degenerate return cycles)
                        if target_para in para_exits and target_para != node.paragraph:
                            target_exit = para_exits[target_para]
                            if idx + 1 < len(node_keys):
                                next_node = node_keys[idx + 1]
                                self.edges.append(GraphEdge(
                                    source=target_exit,
                                    target=next_node,
                                    edge_type="cfg_return",
                                    weight=1.2,
                                    label="return"
                                ))

            # IF / ELSE branch link
            elif node.node_type == "branch" and up.startswith("IF"):
                # Search ahead for corresponding ELSE and END-IF
                else_id = None
                endif_id = None
                for fwd_id in node_keys[idx+1:min(idx+16, len(node_keys))]:
                    fwd_up = self.nodes[fwd_id].code.upper()
                    if fwd_up.startswith("ELSE") and else_id is None and endif_id is None:
                        else_id = fwd_id
                    elif fwd_up.startswith("END-IF") and endif_id is None:
                        endif_id = fwd_id
                        break

                if else_id:
                    self.edges.append(GraphEdge(
                        source=node_id,
                        target=else_id,
                        edge_type="cfg_branch",
                        weight=1.0,
                        label="false_branch"
                    ))
                    # Remove sequential edge directly into ELSE from previous statement
                    self.edges = [e for e in self.edges if not (e.target == else_id and e.edge_type == "cfg_seq")]
                    # Connect last statement of THEN block to node after END-IF (skip ELSE block)
                    else_idx = node_keys.index(else_id)
                    if else_idx > 0:
                        then_last_id = node_keys[else_idx - 1]
                        if self.nodes[then_last_id].node_type not in ("stop", "goback"):
                            target_after = endif_id if endif_id else (node_keys[else_idx + 1] if else_idx + 1 < len(node_keys) else None)
                            if target_after:
                                self.edges.append(GraphEdge(
                                    source=then_last_id,
                                    target=target_after,
                                    edge_type="cfg_seq",
                                    weight=1.0,
                                    label="then_skip_else"
                                ))
                elif endif_id:
                    self.edges.append(GraphEdge(
                        source=node_id,
                        target=endif_id,
                        edge_type="cfg_branch",
                        weight=1.0,
                        label="false_branch"
                    ))

            # GOTO target link
            elif "GOTO" in up or "GO TO" in up:
                tokens = up.split()
                for t in tokens:
                    cand = t.rstrip('.')
                    if cand in para_entries:
                        self.edges.append(GraphEdge(
                            source=node_id,
                            target=para_entries[cand],
                            edge_type="cfg_branch",
                            weight=1.2,
                            label="goto"
                        ))

    def _link_data_dependencies(self):
        """Creates DFG edges between statement nodes via def-use data dependencies."""
        var_last_writer: Dict[str, str] = {}

        for node_id, node in self.nodes.items():
            # For variables read, link from the last writer to this reader
            for read_var in node.reads:
                if read_var in var_last_writer:
                    writer_id = var_last_writer[read_var]
                    if writer_id != node_id:
                        self.edges.append(GraphEdge(
                            source=writer_id,
                            target=node_id,
                            edge_type="dfg_read",
                            weight=0.8,
                            label=f"def_use({read_var})"
                        ))

            # Update last writer
            for write_var in node.writes:
                var_last_writer[write_var] = node_id

    def _build_graph_payload(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "variables": [v.to_dict() for v in self.variables.values()],
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }
