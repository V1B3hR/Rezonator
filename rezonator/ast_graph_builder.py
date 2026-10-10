"""
AST-to-Graph Builder for COBOL Programs.
Constructs formal, typed, directed Control Flow Graphs (CFG) and Data Flow Graphs (DFG)
adhering to IBM Enterprise COBOL and ANSI-85 semantics.
Includes a fully hermetic pure-Python AST parser with optional cobolparser integration.
"""

import os
import re
from typing import Dict, List, Set, Any, Optional, Tuple

from rezonator.copybooks import CopybookInliner, SourceOrigin
from rezonator.limits import validate_graph_payload, validate_source_size

COBOLPARSER_AVAILABLE = False

# The pure-Python parser is the deterministic default.  The third-party
# adapter is opt-in because optional parser packages can perform expensive or
# environment-sensitive initialization on import (especially on Windows).
if os.environ.get("REZONATOR_ENABLE_EXTERNAL_COBOLPARSER") == "1":
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
        self.source_origin: Optional[SourceOrigin] = None


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
        self.source_origin: Optional[SourceOrigin] = None


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


class ExecSqlStatement(Statement):
    """Embedded DB2/SQL statement represented as a first-class AST node."""

    READ_OPERATIONS = {"SELECT", "UPDATE", "DELETE", "MERGE"}
    WRITE_OPERATIONS = {"INSERT", "UPDATE", "DELETE", "MERGE"}

    def __init__(self, sql: str, line: int = 0):
        super().__init__(line)
        self.sql = " ".join(sql.split()).strip().rstrip(".")
        self.operation = self._extract_operation(self.sql)
        self.tables = self._extract_tables(self.sql)
        self.host_variables = self._extract_host_variables(self.sql)
        self.host_writes = self._extract_host_writes(self.sql)
        self.host_reads = self.host_variables - self.host_writes

    @staticmethod
    def _extract_operation(sql: str) -> str:
        match = re.match(r"^([A-Za-z]+)", sql.strip())
        return match.group(1).upper() if match else "UNKNOWN"

    @staticmethod
    def _extract_tables(sql: str) -> List[str]:
        """Extract common DB2 table references while ignoring host variables."""
        matches = re.findall(
            r"\b(?:FROM|JOIN|UPDATE|INTO|USING)\s+([A-Za-z][A-Za-z0-9_$#@-]*(?:\.[A-Za-z][A-Za-z0-9_$#@-]*)?)",
            sql,
            flags=re.IGNORECASE,
        )
        tables: List[str] = []
        for table in matches:
            normalized = table.upper().rstrip(".,;")
            if normalized.startswith(":") or normalized not in tables:
                if not normalized.startswith(":"):
                    tables.append(normalized)
        return tables

    @staticmethod
    def _extract_host_variables(sql: str) -> Set[str]:
        return {name.upper() for name in re.findall(r":([A-Za-z][A-Za-z0-9_-]*)", sql)}

    def _extract_host_writes(self, sql: str) -> Set[str]:
        write_vars: Set[str] = set()
        clauses = re.findall(
            r"\b(?:INTO|RETURNING)\b(.*?)(?=\bFROM\b|\bWHERE\b|\bFOR\b|\bEND-EXEC\b|$)",
            sql,
            flags=re.IGNORECASE,
        )
        for clause in clauses:
            write_vars.update(self._extract_host_variables(clause))

        # SELECT/FETCH host variables are output values; other host variables
        # participate as predicates or input values.
        if self.operation == "FETCH":
            write_vars.update(self.host_variables)
        return write_vars


class ExecCicsStatement(Statement):
    """IBM CICS command represented as an external control-flow operation."""

    COMMANDS = ("SEND", "RECEIVE", "SYNCPOINT", "LINK", "XCTL")

    def __init__(self, cics: str, line: int = 0):
        super().__init__(line)
        self.cics = " ".join(cics.split()).strip().rstrip(".")
        self.command = self._extract_command(self.cics)
        self.resource_kind, self.resource_name = self._extract_resource(self.cics)

    @classmethod
    def _extract_command(cls, cics: str) -> str:
        upper = cics.upper()
        for command in cls.COMMANDS:
            if re.search(rf"\b{command}\b", upper):
                if command in {"SEND", "RECEIVE"} and re.search(r"\bMAP\b", upper):
                    return f"{command} MAP"
                return command
        return "UNKNOWN"

    @staticmethod
    def _extract_resource(cics: str) -> Tuple[str, str]:
        upper = cics.upper()
        if "PROGRAM" in upper:
            match = re.search(r"\bPROGRAM\s*\(\s*['\"]?([A-Za-z0-9_-]+)", cics, re.IGNORECASE)
            if match:
                return "PROGRAM", match.group(1).upper()
        if "MAP" in upper:
            match = re.search(r"\bMAP\s*\(\s*['\"]?([A-Za-z0-9_-]+)", cics, re.IGNORECASE)
            if match:
                return "MAP", match.group(1).upper()
        if "SYNCPOINT" in upper:
            return "TRANSACTION", "SYNCPOINT"
        return "COMMAND", ExecCicsStatement._extract_command(cics)


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


def parse_cobol_source(
    source_code: str,
    copybooks: Optional[Dict[str, str]] = None,
    copybook_dirs: Optional[List[str]] = None,
    source_origins: Optional[List[SourceOrigin]] = None,
) -> CobolProgramAST:
    """
    Parses COBOL source code into a CobolProgramAST structure.
    Hermetic, deterministic ANSI-85 and IBM Enterprise COBOL syntax parser.
    """
    validate_source_size(source_code)
    if copybooks is not None or copybook_dirs:
        expanded = CopybookInliner(copybooks, copybook_dirs).inline_with_provenance(source_code)
        source_code = expanded.text
        source_origins = list(expanded.line_origins)
        validate_source_size(source_code)

    def origin_for_line(lineno: int) -> Optional[SourceOrigin]:
        if source_origins and 0 < lineno <= len(source_origins):
            return source_origins[lineno - 1]
        return None

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
                data_item = DataItem(
                    name=name,
                    level=int(lvl),
                    picture=pic or "",
                    initial_value=(val or "").strip().strip('"').strip("'")
                )
                data_item.source_origin = origin_for_line(lineno)
                data_items.append(data_item)

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
    VERBS = ("PERFORM", "STOP", "GOBACK", "MOVE", "SUBTRACT", "ADD", "COMPUTE", "IF", "EXEC")

    def parse_stmt_from_lines(start_lineno: int, full_text: str) -> Optional[Any]:
        t_up = full_text.upper()
        # Embedded Enterprise COBOL subsystems.  Keep the full block intact so
        # multiline SQL/CICS clauses remain a single semantic statement.
        m_exec = re.match(r"^EXEC\s+(SQL|CICS)\s+(.+?)\s+END-EXEC\.?$", full_text, re.IGNORECASE | re.DOTALL)
        if m_exec:
            dialect, body = m_exec.groups()
            if dialect.upper() == "SQL":
                return ExecSqlStatement(body, line=start_lineno)
            return ExecCicsStatement(body, line=start_lineno)

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
                if_stmt.source_origin = origin_for_line(lineno)
                stmts.append(if_stmt)
            elif line_up.startswith(("EXEC SQL", "EXEC CICS")):
                start_lineno = lineno
                block_lines = [line]
                idx += 1
                if not re.search(r"\bEND-EXEC\.?\s*$", line, re.IGNORECASE):
                    while idx < total:
                        block_lines.append(proc_lines[idx][1])
                        end_line = proc_lines[idx][1]
                        idx += 1
                        if re.search(r"\bEND-EXEC\.?\s*$", end_line, re.IGNORECASE):
                            break

                stmt = parse_stmt_from_lines(start_lineno, " ".join(block_lines))
                if stmt:
                    stmt.source_origin = origin_for_line(start_lineno)
                    stmts.append(stmt)
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
                    stmt.source_origin = origin_for_line(start_lineno)
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

    def __init__(
        self,
        copybooks: Optional[Dict[str, str]] = None,
        copybook_dirs: Optional[List[str]] = None,
    ):
        self.program_id = "UNKNOWN-PROGRAM"
        self.variables: Dict[str, Dict[str, Any]] = {}
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.copybook_inliner = (
            CopybookInliner(copybooks, copybook_dirs)
            if copybooks is not None or copybook_dirs
            else None
        )

    @classmethod
    def is_available(cls) -> bool:
        return True

    def build_from_source(
        self,
        source_code: str,
        copybooks: Optional[Dict[str, str]] = None,
        copybook_dirs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Parses COBOL source code and builds the unified graph payload."""
        validate_source_size(source_code)
        source_origins: Optional[List[SourceOrigin]] = None
        if copybooks is not None or copybook_dirs:
            expanded = CopybookInliner(copybooks, copybook_dirs).inline_with_provenance(source_code)
            source_code = expanded.text
            source_origins = list(expanded.line_origins)
            validate_source_size(source_code)
        elif self.copybook_inliner:
            expanded = self.copybook_inliner.inline_with_provenance(source_code)
            source_code = expanded.text
            source_origins = list(expanded.line_origins)
            validate_source_size(source_code)

        ast_obj = None
        if COBOLPARSER_AVAILABLE:
            try:
                res = cobolparser.parse_cobol(source_code)
                if res.success and res.ast is not None:
                    ast_obj = res.ast
            except Exception:
                ast_obj = None

        if ast_obj is None:
            ast_obj = parse_cobol_source(source_code, source_origins=source_origins)

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

            variable = {
                "name": name,
                "pic": str(pic_str),
                "initial_value": init_val_clean,
                "level": getattr(d, "level", 1) or 1
            }
            source_origin = getattr(d, "source_origin", None)
            if source_origin:
                variable["source_origin"] = source_origin.to_dict()
            self.variables[name] = variable

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

        payload = {
            "program_id": self.program_id,
            "variables": list(self.variables.values()),
            "nodes": list(self.nodes.values()),
            "edges": self.edges
        }
        validate_graph_payload(payload, include_variables=True)
        return payload

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

        if isinstance(stmt, ExecSqlStatement):
            reads.update(v for v in stmt.host_reads if v in self.variables)
            writes.update(v for v in stmt.host_writes if v in self.variables)
            return reads, writes

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
        elif isinstance(stmt, ExecSqlStatement):
            node_type = "db_access"
            tables = ", ".join(stmt.tables) if stmt.tables else "UNKNOWN-TABLE"
            label = f"SQL {stmt.operation} {tables}"
            code = f"EXEC SQL {stmt.sql} END-EXEC"
        elif isinstance(stmt, ExecCicsStatement):
            node_type = "external"
            resource = f"{stmt.resource_kind}({stmt.resource_name})"
            label = f"CICS {stmt.command} {resource}"
            code = f"EXEC CICS {stmt.cics} END-EXEC"
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
        if isinstance(stmt, ExecSqlStatement):
            node["sql_operation"] = stmt.operation
            node["tables"] = list(stmt.tables)
            node["host_reads"] = sorted(stmt.host_reads)
            node["host_writes"] = sorted(stmt.host_writes)
        elif isinstance(stmt, ExecCicsStatement):
            node["cics_command"] = stmt.command
            node["resource_kind"] = stmt.resource_kind
            node["resource_name"] = stmt.resource_name
        source_origin = getattr(stmt, "source_origin", None)
        if source_origin:
            node["source_origin"] = source_origin.to_dict()
        self.nodes[node_id] = node
        self._link_external_resources(node, stmt)
        return node

    def _link_external_resources(self, node: Dict[str, Any], stmt: Any):
        """Materializes SQL tables and CICS targets as graph state nodes."""
        if isinstance(stmt, ExecSqlStatement):
            for table in stmt.tables:
                table_id = f"db_table:{table}"
                if table_id not in self.nodes:
                    self.nodes[table_id] = {
                        "id": table_id,
                        "label": f"[DB2:{table}]",
                        "node_type": "db_table",
                        "paragraph": "DATABASE",
                        "code": f"TABLE {table}",
                        "reads": [],
                        "writes": [],
                        "resource": table,
                    }

                if stmt.operation in ExecSqlStatement.READ_OPERATIONS or stmt.operation not in ExecSqlStatement.WRITE_OPERATIONS:
                    self.edges.append({
                        "source": table_id,
                        "target": node["id"],
                        "edge_type": "dfg_db_read",
                        "weight": 1.3,
                        "label": f"read({table})",
                    })
                if stmt.operation in ExecSqlStatement.WRITE_OPERATIONS:
                    self.edges.append({
                        "source": node["id"],
                        "target": table_id,
                        "edge_type": "dfg_db_write",
                        "weight": 1.6,
                        "label": f"write({table})",
                    })

        elif isinstance(stmt, ExecCicsStatement):
            resource_id = f"cics_resource:{stmt.resource_kind}:{stmt.resource_name}"
            if resource_id not in self.nodes:
                self.nodes[resource_id] = {
                    "id": resource_id,
                    "label": f"[CICS:{stmt.resource_kind} {stmt.resource_name}]",
                    "node_type": "cics_resource",
                    "paragraph": "CICS",
                    "code": f"CICS {stmt.command} {stmt.resource_kind}({stmt.resource_name})",
                    "reads": [],
                    "writes": [],
                    "resource": stmt.resource_name,
                }
            self.edges.append({
                "source": node["id"],
                "target": resource_id,
                "edge_type": "cfg_external",
                "weight": 1.4,
                "label": stmt.command,
            })

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
