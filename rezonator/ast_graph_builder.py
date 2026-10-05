"""
AST-to-Graph Builder for COBOL Programs.
Constructs formal, typed, directed Control Flow Graphs (CFG) and Data Flow Graphs (DFG)
adhering to IBM Enterprise COBOL and ANSI-85 semantics.
Includes a fully hermetic pure-Python AST parser with optional cobolparser integration.
"""

import re
from typing import Dict, List, Set, Any, Optional, Tuple

try:
    import cobolparser
    from cobolparser.models.statements import (
        IfStatement as _CobolParserIfStatement,
        PerformStatement as _CobolParserPerformStatement,
        StopStatement as _CobolParserStopStatement,
        GobackStatement as _CobolParserGobackStatement,
        MoveStatement as _CobolParserMoveStatement,
        SubtractStatement as _CobolParserSubtractStatement,
        AddStatement as _CobolParserAddStatement,
        ComputeStatement as _CobolParserComputeStatement
    )
    COBOLPARSER_AVAILABLE = True
except (ImportError, Exception):
    COBOLPARSER_AVAILABLE = False


# ============================================================================
# Hermetic Pure-Python AST Data Structures
# ============================================================================

class Location:
    def __init__(self, line: int = 0, column: int = 0):
        self.line = line
        self.column = column


class PictureClause:
    def __init__(self, pattern: str = ""):
        self.pattern = pattern


class DataItem:
    def __init__(self, name: str, level: int = 1, picture: str = "", initial_value: str = ""):
        self.name = name.upper()
        self.level = level
        self.picture_clause = PictureClause(picture)
        self.initial_value = initial_value


class Condition:
    def __init__(self, left: str = "", operator: str = "=", right: str = ""):
        self.left_operand = left
        self.operator = operator
        self.right_operand = right


class ComplexCondition:
    def __init__(self, left_cond: Any, operator: str, right_cond: Any):
        self.left_condition = left_cond
        self.operator = operator
        self.right_condition = right_cond


class Statement:
    def __init__(self, line: int = 0):
        self.location = Location(line=line)


class IfStatement(Statement):
    def __init__(self, condition: Any, then_stmts: Optional[List[Any]] = None, else_stmts: Optional[List[Any]] = None, line: int = 0):
        super().__init__(line)
        self.condition = condition
        self.then_statements = then_stmts or []
        self.else_statements = else_stmts or []


class PerformStatement(Statement):
    def __init__(self, target_paragraph: str, line: int = 0):
        super().__init__(line)
        self.target_paragraph = target_paragraph
        self.operands = [target_paragraph]


class StopStatement(Statement):
    def __init__(self, line: int = 0):
        super().__init__(line)


class GobackStatement(Statement):
    def __init__(self, line: int = 0):
        super().__init__(line)


class MoveStatement(Statement):
    def __init__(self, source: str, targets: Any, line: int = 0):
        super().__init__(line)
        self.source = source
        self.targets = targets if isinstance(targets, list) else [targets]
        self.target = self.targets[0] if self.targets else ""


class SubtractStatement(Statement):
    def __init__(self, operand: str, target: str, line: int = 0):
        super().__init__(line)
        self.operands = [operand]
        self.target = target
        self.targets = [target]
        self.giving: Optional[str] = None


class AddStatement(Statement):
    def __init__(self, operand: str, target: str, line: int = 0):
        super().__init__(line)
        self.operands = [operand]
        self.target = target
        self.targets = [target]
        self.giving: Optional[str] = None


class ComputeStatement(Statement):
    def __init__(self, target: str, expression: str, line: int = 0):
        super().__init__(line)
        self.target = target
        self.targets = [target]
        self.expression = expression


class Paragraph:
    def __init__(self, name: str, statements: Optional[List[Any]] = None):
        self.paragraph_name = name
        self.statements = statements or []


class CobolProgramAST:
    def __init__(self, name: str = "", data_items: Optional[List[DataItem]] = None, procedures: Optional[List[Paragraph]] = None):
        self.program_name = name
        self.data_items = data_items or []
        self.procedures = procedures or []

    def get_data_items(self) -> List[DataItem]:
        return self.data_items

    def get_procedures(self) -> List[Paragraph]:
        return self.procedures


# ============================================================================
# Hermetic Pure-Python COBOL Parser
# ============================================================================

def parse_condition_expr(cond_text: str) -> Any:
    """Parses COBOL conditional expressions into Condition or ComplexCondition tree."""
    cond_text = cond_text.strip()
    and_split = re.split(r'\s+AND\s+', cond_text, flags=re.IGNORECASE)
    if len(and_split) > 1:
        left = parse_condition_expr(and_split[0])
        right = parse_condition_expr(" AND ".join(and_split[1:]))
        return ComplexCondition(left, "AND", right)

    or_split = re.split(r'\s+OR\s+', cond_text, flags=re.IGNORECASE)
    if len(or_split) > 1:
        left = parse_condition_expr(or_split[0])
        right = parse_condition_expr(" OR ".join(or_split[1:]))
        return ComplexCondition(left, "OR", right)

    m = re.match(r'(.+?)\s*(<=|>=|!=|<>|=|<|>)\s*(.+)', cond_text)
    if m:
        l_op, op, r_op = m.groups()
        op_norm_map = {"=": "=", "<=": "<=", ">=": ">=", "<": "<", ">": ">", "!=": "!=", "<>": "!="}
        # Keep quotes on string literals if present for eval preservation
        return Condition(l_op.strip(), op_norm_map.get(op, op), r_op.strip())
    
    return Condition(cond_text, "=", "TRUE")


def parse_cobol_source(source_code: str) -> CobolProgramAST:
    """
    Parses COBOL source code into a CobolProgramAST structure.
    Hermetic, deterministic ANSI-85 and IBM Enterprise COBOL syntax parser.
    """
    lines = source_code.splitlines()
    prog_name = "UNKNOWN"
    data_items: List[DataItem] = []
    procedures: List[Paragraph] = []

    # 1. Parse Program-ID
    for line in lines:
        m = re.search(r'PROGRAM-ID\.\s+([A-Za-z0-9_-]+)', line, re.IGNORECASE)
        if m:
            prog_name = m.group(1).upper()
            break

    # 2. Parse Working-Storage Section
    in_ws = False
    in_proc = False
    proc_lines: List[Tuple[int, str]] = []

    for lineno, raw_line in enumerate(lines, 1):
        clean = raw_line.strip()
        if not clean or clean.startswith("*"):
            continue

        if "WORKING-STORAGE SECTION" in clean.upper():
            in_ws = True
            in_proc = False
            continue
        elif "PROCEDURE DIVISION" in clean.upper():
            in_ws = False
            in_proc = True
            continue

        if in_ws:
            # Handle variable declaration: 01 WS-VAR PIC X(10) VALUE "ABC". or 01 WS-NUM PIC 9(7)V99 VALUE 5000.00.
            m = re.match(r'(\d{2})\s+([A-Za-z0-9_-]+)(?:\s+PIC\s+([A-Za-z0-9()Vv]+))?(?:\s+VALUE\s+(.+?))?\.\s*$', clean, re.IGNORECASE)
            if m:
                lvl, name, pic, val = m.groups()
                data_items.append(DataItem(
                    name=name,
                    level=int(lvl),
                    picture=pic or "",
                    initial_value=(val or "").strip().strip('"').strip("'")
                ))

        if in_proc:
            proc_lines.append((lineno, clean))

    # 3. Parse Procedure Division paragraphs and statements
    current_para: Optional[str] = None
    para_stmts: List[Any] = []

    def flush_para():
        nonlocal current_para, para_stmts
        if current_para:
            procedures.append(Paragraph(current_para, para_stmts))
            current_para = None
            para_stmts = []

    idx = 0
    total = len(proc_lines)
    VERBS = ("PERFORM", "STOP", "GOBACK", "MOVE", "SUBTRACT", "ADD", "COMPUTE", "IF")

    def parse_stmt_from_lines(start_lineno: int, full_text: str) -> Optional[Any]:
        t_up = full_text.upper()
        # PERFORM
        m = re.match(r'^PERFORM\s+([A-Za-z0-9_-]+)', full_text, re.IGNORECASE)
        if m:
            return PerformStatement(m.group(1).upper(), line=start_lineno)
        # STOP RUN
        if t_up.startswith("STOP RUN"):
            return StopStatement(line=start_lineno)
        # GOBACK
        if t_up.startswith("GOBACK"):
            return GobackStatement(line=start_lineno)
        # MOVE
        m = re.match(r'^MOVE\s+(.+?)\s+TO\s+([A-Za-z0-9_,\s-]+)', full_text, re.IGNORECASE | re.DOTALL)
        if m:
            src, dst = m.groups()
            targets = [x.strip().rstrip(".") for x in dst.split(",") if x.strip()]
            return MoveStatement(source=src.strip(), targets=targets, line=start_lineno)
        # SUBTRACT ... FROM ... GIVING ...
        m_giv = re.match(r'^(?:SUBTRACT|SUB)\s+(.+?)\s+FROM\s+(.+?)\s+GIVING\s+([A-Za-z0-9_-]+)', full_text, re.IGNORECASE | re.DOTALL)
        if m_giv:
            src, base, giving = m_giv.groups()
            stmt = SubtractStatement(operand=src.strip(), target=giving.strip().rstrip("."), line=start_lineno)
            stmt.operands = [src.strip(), base.strip()]
            stmt.giving = giving.strip().rstrip(".")
            return stmt

        m = re.match(r'^(?:SUBTRACT|SUB)\s+(.+?)\s+FROM\s+([A-Za-z0-9_-]+)', full_text, re.IGNORECASE | re.DOTALL)
        if m:
            src, dst = m.groups()
            return SubtractStatement(operand=src.strip(), target=dst.strip().rstrip("."), line=start_lineno)
        # ADD ... TO ... GIVING ...
        m_giv = re.match(r'^ADD\s+(.+?)\s+TO\s+(.+?)\s+GIVING\s+([A-Za-z0-9_-]+)', full_text, re.IGNORECASE | re.DOTALL)
        if m_giv:
            src, base, giving = m_giv.groups()
            stmt = AddStatement(operand=src.strip(), target=giving.strip().rstrip("."), line=start_lineno)
            stmt.operands = [src.strip(), base.strip()]
            stmt.giving = giving.strip().rstrip(".")
            return stmt

        m = re.match(r'^ADD\s+(.+?)\s+TO\s+([A-Za-z0-9_-]+)', full_text, re.IGNORECASE | re.DOTALL)
        if m:
            src, dst = m.groups()
            return AddStatement(operand=src.strip(), target=dst.strip().rstrip("."), line=start_lineno)
        # COMPUTE
        m = re.match(r'^COMPUTE\s+([A-Za-z0-9_-]+)\s*=\s*(.+)', full_text, re.IGNORECASE | re.DOTALL)
        if m:
            dst, expr = m.groups()
            return ComputeStatement(target=dst.strip(), expression=expr.strip().rstrip("."), line=start_lineno)

        return None

    def parse_statement_sequence(stop_keywords: List[str]) -> List[Any]:
        nonlocal idx
        stmts: List[Any] = []
        while idx < total:
            lineno, line = proc_lines[idx]
            line_up = line.upper()

            # Check if this line is paragraph header: e.g. "1000-VALIDATE-REQUEST."
            m_para = re.match(r'^([A-Za-z0-9_-]+)\.\s*$', line)
            if m_para and not any(kw in line_up for kw in ["END-IF", "ELSE", "PERFORM", "STOP", "GOBACK"]):
                break

            # Check stop keywords (e.g. ELSE, END-IF)
            first_word = line_up.split()[0].rstrip(".")
            if first_word in stop_keywords:
                break

            if first_word == "IF":
                # Handle IF
                idx += 1
                cond_text = line[len("IF"):].strip()
                # Parse THEN block
                then_stmts = parse_statement_sequence(["ELSE", "END-IF"])
                else_stmts: List[Any] = []
                if idx < total and proc_lines[idx][1].upper().startswith("ELSE"):
                    idx += 1
                    else_stmts = parse_statement_sequence(["END-IF"])
                if idx < total and proc_lines[idx][1].upper().startswith("END-IF"):
                    idx += 1  # Consume END-IF
                
                cond_obj = parse_condition_expr(cond_text)
                if_stmt = IfStatement(condition=cond_obj, then_stmts=then_stmts, else_stmts=else_stmts, line=lineno)
                stmts.append(if_stmt)
            else:
                start_lineno = lineno
                accum_lines = [line]
                idx += 1
                while idx < total:
                    next_lineno, next_line = proc_lines[idx]
                    next_up = next_line.upper().strip()
                    m_p = re.match(r'^([A-Za-z0-9_-]+)\.\s*$', next_line)
                    if m_p and not any(kw in next_up for kw in ["END-IF", "ELSE", "PERFORM", "STOP", "GOBACK"]):
                        break
                    next_first = next_up.split()[0].rstrip(".")
                    if next_first in stop_keywords or next_first in VERBS:
                        break
                    accum_lines.append(next_line)
                    idx += 1
                    if accum_lines[-1].endswith("."):
                        break

                full_stmt_text = " ".join(accum_lines)
                stmt = parse_stmt_from_lines(start_lineno, full_stmt_text)
                if stmt:
                    stmts.append(stmt)

        return stmts

    while idx < total:
        lineno, line = proc_lines[idx]
        m_para = re.match(r'^([A-Za-z0-9_-]+)\.\s*$', line)
        if m_para and not any(kw in line.upper() for kw in ["END-IF", "ELSE", "STOP", "GOBACK"]):
            flush_para()
            current_para = m_para.group(1).upper()
            idx += 1
            para_stmts = parse_statement_sequence([])
        else:
            idx += 1

    flush_para()
    return CobolProgramAST(prog_name, data_items, procedures)


# ============================================================================
# CobolASTGraphBuilder Class
# ============================================================================

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
        return True

    def build_from_source(self, source_code: str) -> Dict[str, Any]:
        """Parses COBOL source code and builds the unified graph payload."""
        ast_obj = None
        if COBOLPARSER_AVAILABLE:
            try:
                res = cobolparser.parse_cobol(source_code)
                if res.success and res.ast is not None:
                    ast_obj = res.ast
            except Exception:
                ast_obj = None

        if ast_obj is None:
            ast_obj = parse_cobol_source(source_code)

        return self.build_from_ast(ast_obj)

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
        if isinstance(stmt, (IfStatement, _CobolParserIfStatement if COBOLPARSER_AVAILABLE else IfStatement)):
            node_type = "branch"
            cond_str = self._format_condition(stmt.condition)
            label = f"IF {cond_str[:24]}"
            code = f"IF {cond_str}"
        elif isinstance(stmt, (PerformStatement, _CobolParserPerformStatement if COBOLPARSER_AVAILABLE else PerformStatement)):
            node_type = "perform"
            target_p = getattr(stmt, "target_paragraph", "") or (stmt.operands[0] if getattr(stmt, "operands", None) else "")
            label = f"PERFORM {target_p}"
            code = f"PERFORM {target_p}"
        elif isinstance(stmt, (StopStatement, GobackStatement, _CobolParserStopStatement if COBOLPARSER_AVAILABLE else StopStatement, _CobolParserGobackStatement if COBOLPARSER_AVAILABLE else GobackStatement)):
            node_type = "stop"
            label = "STOP RUN" if type(stmt).__name__.startswith("Stop") else "GOBACK"
            code = label
        elif isinstance(stmt, (MoveStatement, _CobolParserMoveStatement if COBOLPARSER_AVAILABLE else MoveStatement)):
            node_type = "stmt"
            dest = ", ".join(stmt.targets) if getattr(stmt, "targets", None) else getattr(stmt, "target", "")
            label = f"MOVE {dest}"
            code = f"MOVE {getattr(stmt, 'source', '')} TO {dest}"
        elif isinstance(stmt, (SubtractStatement, _CobolParserSubtractStatement if COBOLPARSER_AVAILABLE else SubtractStatement)):
            node_type = "stmt"
            src = stmt.operands[0] if getattr(stmt, "operands", None) else ""
            dest = getattr(stmt, "target", "") or (stmt.targets[0] if getattr(stmt, "targets", None) else "")
            label = f"SUB {dest}"
            code = f"SUBTRACT {src} FROM {dest}"
        elif isinstance(stmt, (AddStatement, _CobolParserAddStatement if COBOLPARSER_AVAILABLE else AddStatement)):
            node_type = "stmt"
            src = stmt.operands[0] if getattr(stmt, "operands", None) else ""
            dest = getattr(stmt, "target", "") or (stmt.targets[0] if getattr(stmt, "targets", None) else "")
            label = f"ADD {dest}"
            code = f"ADD {src} TO {dest}"
        elif isinstance(stmt, (ComputeStatement, _CobolParserComputeStatement if COBOLPARSER_AVAILABLE else ComputeStatement)):
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

            if isinstance(curr_stmt, (IfStatement, _CobolParserIfStatement if COBOLPARSER_AVAILABLE else IfStatement)):
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
            if not isinstance(stmt, (PerformStatement, _CobolParserPerformStatement if COBOLPARSER_AVAILABLE else PerformStatement)):
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

        for n in self.nodes.values():
            n.pop("_ast_stmt", None)
