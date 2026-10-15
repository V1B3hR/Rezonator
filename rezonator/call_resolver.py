"""
Inter-Program Call and Resource Resolver.
Extracts static/dynamic COBOL CALL statements, CICS LINK/XCTL invocations,
and resolves target programs against an explicit Portfolio Manifest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from rezonator.portfolio_manifest import PortfolioManifest


@dataclass
class ProgramCall:
    caller_program: str
    target_name: str
    call_type: str  # "COBOL_STATIC", "COBOL_DYNAMIC", "CICS_LINK", "CICS_XCTL"
    is_dynamic: bool
    parameters: List[str] = field(default_factory=list)
    line: int = 0
    raw_statement: str = ""
    resolution_status: str = "UNRESOLVED_EXTERNAL"  # "RESOLVED", "UNRESOLVED_EXTERNAL", "DYNAMIC_UNRESOLVED"
    resolved_target: Optional[str] = None

    def __post_init__(self):
        self.caller_program = self.caller_program.strip().upper()
        self.target_name = self.target_name.strip().upper()
        if self.resolved_target:
            self.resolved_target = self.resolved_target.strip().upper()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caller_program": self.caller_program,
            "target_name": self.target_name,
            "call_type": self.call_type,
            "is_dynamic": self.is_dynamic,
            "parameters": list(self.parameters),
            "line": self.line,
            "raw_statement": self.raw_statement,
            "resolution_status": self.resolution_status,
            "resolved_target": self.resolved_target,
        }


@dataclass
class ProgramResourceAccess:
    program_id: str
    resource_type: str  # "DB2_TABLE", "FILE_DATASET"
    resource_name: str
    operation: str  # "SELECT", "INSERT", "UPDATE", "DELETE", "READ", "WRITE", "OPEN_INPUT", "OPEN_OUTPUT"
    access_mode: str  # "READ", "WRITE", "READ_WRITE", "UNKNOWN"
    line: int = 0
    raw_statement: str = ""

    def __post_init__(self):
        self.program_id = self.program_id.strip().upper()
        self.resource_name = self.resource_name.strip().upper()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "operation": self.operation,
            "access_mode": self.access_mode,
            "line": self.line,
            "raw_statement": self.raw_statement,
        }


class CallResolver:
    """
    Extracts and resolves inter-program calls (COBOL CALL, CICS LINK/XCTL)
    and program-to-resource accesses against an explicit Portfolio Manifest.
    """

    def extract_calls_from_source(self, source_text: str, caller_id: str) -> List[ProgramCall]:
        """Extracts all COBOL CALL and CICS LINK/XCTL statements from source code."""
        calls: List[ProgramCall] = []
        lines = source_text.splitlines()

        # 1. Extract COBOL CALL statements
        call_pattern = re.compile(
            r"\bCALL\s+(['\"]?[A-Za-z0-9_-]+['\"]?)(?:\s+USING\s+([^.\n]+?))?(?:\.|\s+END-CALL|\s*$)",
            re.IGNORECASE,
        )

        for lineno, raw_line in enumerate(lines, 1):
            clean = raw_line.strip()
            if not clean or clean.startswith("*"):
                continue

            for match in call_pattern.finditer(clean):
                raw_target = match.group(1).strip()
                using_clause = match.group(2) or ""

                is_literal = (
                    (raw_target.startswith("'") and raw_target.endswith("'"))
                    or (raw_target.startswith('"') and raw_target.endswith('"'))
                )
                target_name = raw_target.strip("'\"").upper()
                is_dynamic = not is_literal
                call_type = "COBOL_DYNAMIC" if is_dynamic else "COBOL_STATIC"

                params = self._extract_call_parameters(using_clause)
                status = "DYNAMIC_UNRESOLVED" if is_dynamic else "UNRESOLVED_EXTERNAL"

                calls.append(ProgramCall(
                    caller_program=caller_id,
                    target_name=target_name,
                    call_type=call_type,
                    is_dynamic=is_dynamic,
                    parameters=params,
                    line=lineno,
                    raw_statement=match.group(0).strip(),
                    resolution_status=status,
                    resolved_target=None,
                ))

        # 2. Extract CICS LINK and XCTL statements
        cics_pattern = re.compile(
            r"EXEC\s+CICS\s+(LINK|XCTL)\s+(.+?)\s+END-EXEC\.?",
            re.IGNORECASE | re.DOTALL,
        )

        full_text = source_text
        for match in cics_pattern.finditer(full_text):
            cmd = match.group(1).upper()
            body = match.group(2)
            lineno = full_text[:match.start()].count("\n") + 1

            prog_match = re.search(r"\bPROGRAM\s*\(\s*(['\"]?[A-Za-z0-9_-]+['\"]?)\s*\)", body, re.IGNORECASE)
            if prog_match:
                raw_target = prog_match.group(1).strip()
                is_literal = (
                    (raw_target.startswith("'") and raw_target.endswith("'"))
                    or (raw_target.startswith('"') and raw_target.endswith('"'))
                )
                target_name = raw_target.strip("'\"").upper()
                is_dynamic = not is_literal

                cics_params: List[str] = []
                commarea_match = re.search(r"\bCOMMAREA\s*\(\s*([A-Za-z0-9_-]+)\s*\)", body, re.IGNORECASE)
                if commarea_match:
                    cics_params.append(commarea_match.group(1).upper())

                call_type = f"CICS_{cmd}"
                status = "DYNAMIC_UNRESOLVED" if is_dynamic else "UNRESOLVED_EXTERNAL"

                calls.append(ProgramCall(
                    caller_program=caller_id,
                    target_name=target_name,
                    call_type=call_type,
                    is_dynamic=is_dynamic,
                    parameters=cics_params,
                    line=lineno,
                    raw_statement=match.group(0).strip(),
                    resolution_status=status,
                    resolved_target=None,
                ))

        return calls

    def _extract_call_parameters(self, using_clause: str) -> List[str]:
        if not using_clause or not using_clause.strip():
            return []
        # Remove BY REFERENCE / BY CONTENT / BY VALUE keywords
        cleaned = re.sub(r"\bBY\s+(?:REFERENCE|CONTENT|VALUE)\b", "", using_clause, flags=re.IGNORECASE)
        tokens = [p.strip().rstrip(".") for p in re.split(r"[,\s]+", cleaned) if p.strip()]
        return [t.upper() for t in tokens if t]

    def extract_resource_accesses_from_source(self, source_text: str, program_id: str) -> List[ProgramResourceAccess]:
        """Extracts DB2 table accesses and COBOL file dataset references."""
        accesses: List[ProgramResourceAccess] = []
        lines = source_text.splitlines()

        # 1. DB2 SQL queries
        sql_pattern = re.compile(r"EXEC\s+SQL\s+(.+?)\s+END-EXEC\.?", re.IGNORECASE | re.DOTALL)
        for match in sql_pattern.finditer(source_text):
            sql = " ".join(match.group(1).split()).strip()
            lineno = source_text[:match.start()].count("\n") + 1

            op_match = re.match(r"^([A-Za-z]+)", sql)
            op = op_match.group(1).upper() if op_match else "UNKNOWN"

            # Extract tables
            table_matches = re.findall(
                r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z][A-Za-z0-9_$#@-]*(?:\.[A-Za-z][A-Za-z0-9_$#@-]*)?)",
                sql,
                flags=re.IGNORECASE,
            )
            for raw_tbl in table_matches:
                tbl = raw_tbl.upper().rstrip(".,;")
                if tbl.startswith(":"):
                    continue

                mode = "READ"
                if op in ("INSERT", "UPDATE", "DELETE", "MERGE"):
                    mode = "WRITE"
                elif op in ("SELECT", "FETCH"):
                    mode = "READ"

                accesses.append(ProgramResourceAccess(
                    program_id=program_id,
                    resource_type="DB2_TABLE",
                    resource_name=tbl,
                    operation=op,
                    access_mode=mode,
                    line=lineno,
                    raw_statement=f"EXEC SQL {sql} END-EXEC",
                ))

        # 2. File Select / Assign statements
        file_map: Dict[str, str] = {}
        for lineno, raw_line in enumerate(lines, 1):
            clean = raw_line.strip()
            m_sel = re.search(r"\bSELECT\s+([A-Za-z0-9_-]+)\s+ASSIGN\s+TO\s+['\"]?([A-Za-z0-9_.-]+)['\"]?", clean, re.IGNORECASE)
            if m_sel:
                internal_name = m_sel.group(1).upper()
                external_dsn = m_sel.group(2).upper()
                file_map[internal_name] = external_dsn

            # File I/O operations
            m_io = re.search(r"\b(OPEN\s+(?:INPUT|OUTPUT|I-O|EXTEND)|READ|WRITE|REWRITE|DELETE)\s+([A-Za-z0-9_-]+)", clean, re.IGNORECASE)
            if m_io:
                verb = m_io.group(1).upper()
                fname = m_io.group(2).upper()
                dsn = file_map.get(fname, fname)

                mode = "READ"
                if "OUTPUT" in verb or "EXTEND" in verb or verb == "WRITE":
                    mode = "WRITE"
                elif "I-O" in verb or verb in ("REWRITE", "DELETE"):
                    mode = "READ_WRITE"
                elif "INPUT" in verb or verb == "READ":
                    mode = "READ"

                accesses.append(ProgramResourceAccess(
                    program_id=program_id,
                    resource_type="FILE_DATASET",
                    resource_name=dsn,
                    operation=verb,
                    access_mode=mode,
                    line=lineno,
                    raw_statement=clean,
                ))

        return accesses

    def resolve_portfolio(
        self, manifest: PortfolioManifest
    ) -> Tuple[Dict[str, List[ProgramCall]], Dict[str, List[ProgramResourceAccess]]]:
        """
        Resolves inter-program calls and resource accesses across all programs in the manifest.
        Dynamic calls and calls to missing programs are preserved as explicit unresolved/unknown edges.
        """
        known_pids: Dict[str, str] = {p.program_id.upper(): p.program_id for p in manifest.programs}
        # Also map filename basenames (without .cbl) for convenient matching
        for p in manifest.programs:
            if p.source_path:
                base = os.path.splitext(os.path.basename(p.source_path))[0].upper()
                known_pids[base] = p.program_id

        all_calls: Dict[str, List[ProgramCall]] = {}
        all_accesses: Dict[str, List[ProgramResourceAccess]] = {}

        for program_entry in manifest.programs:
            pid = program_entry.program_id
            code = program_entry.source_text
            if not code and program_entry.source_path:
                try:
                    with open(program_entry.source_path, "r", encoding="utf-8", errors="replace") as f:
                        code = f.read()
                except Exception:
                    code = ""

            calls = self.extract_calls_from_source(code or "", pid)
            accesses = self.extract_resource_accesses_from_source(code or "", pid)

            # Resolve each call
            for call in calls:
                if call.is_dynamic:
                    call.resolution_status = "DYNAMIC_UNRESOLVED"
                    call.resolved_target = None
                else:
                    target_upper = call.target_name.upper()
                    # Check exact match or prefix/canonical match
                    matched = known_pids.get(target_upper)
                    if not matched:
                        # Try fuzzy prefix: e.g. CBL001 vs CBL001-BATCH-MASTER-FILE
                        for candidate_id in known_pids.values():
                            if candidate_id.startswith(target_upper) or target_upper.startswith(candidate_id):
                                matched = candidate_id
                                break

                    if matched:
                        call.resolution_status = "RESOLVED"
                        call.resolved_target = matched
                    else:
                        call.resolution_status = "UNRESOLVED_EXTERNAL"
                        call.resolved_target = None

            all_calls[pid] = calls
            all_accesses[pid] = accesses

        return all_calls, all_accesses


import os
