"""
Hermetic JCL Parser for Mainframe Job Streams.
Parses Job, Step (EXEC PGM/PROC), DD statements, dataset dispositions,
conditional step logic (COND), and dataflow directions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class JclCondition:
    code: Optional[int] = None
    operator: Optional[str] = None  # LT, LE, EQ, NE, GE, GT
    reference_step: Optional[str] = None
    special: Optional[str] = None  # EVEN, ONLY
    raw_text: str = ""

    def evaluates_true(self, step_rc: int) -> bool:
        """
        In JCL semantics, if COND evaluates to TRUE, the step is BYPASSED (skipped).
        E.g. COND=(4,LT) means: if 4 < step_rc, bypass step.
        """
        if self.special == "EVEN":
            return False  # Execute even if prior steps abended
        if self.special == "ONLY":
            return False
        if self.code is None or self.operator is None:
            return False

        op = self.operator.upper()
        if op == "LT":
            return self.code < step_rc
        if op == "LE":
            return self.code <= step_rc
        if op == "EQ":
            return self.code == step_rc
        if op == "NE":
            return self.code != step_rc
        if op == "GE":
            return self.code >= step_rc
        if op == "GT":
            return self.code > step_rc
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "operator": self.operator,
            "reference_step": self.reference_step,
            "special": self.special,
            "raw_text": self.raw_text,
        }


@dataclass
class JclDd:
    dd_name: str
    dsn: Optional[str] = None
    disp: Optional[str] = None
    access_intent: str = "UNKNOWN"  # READ, WRITE, READ_WRITE, UNKNOWN
    is_temporary: bool = False
    is_dummy: bool = False
    is_sysout: bool = False
    line: int = 0
    raw_parameters: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.dd_name = self.dd_name.strip().upper()
        if self.dsn:
            self.dsn = self.dsn.strip().upper()
            if self.dsn.startswith("&&"):
                self.is_temporary = True
            elif self.dsn == "NULLFILE":
                self.is_dummy = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dd_name": self.dd_name,
            "dsn": self.dsn,
            "disp": self.disp,
            "access_intent": self.access_intent,
            "is_temporary": self.is_temporary,
            "is_dummy": self.is_dummy,
            "is_sysout": self.is_sysout,
            "line": self.line,
            "raw_parameters": dict(self.raw_parameters),
        }


@dataclass
class JclStep:
    step_name: str
    program_name: Optional[str] = None
    proc_name: Optional[str] = None
    exec_type: str = "PGM"  # "PGM" or "PROC"
    conditions: List[JclCondition] = field(default_factory=list)
    dds: List[JclDd] = field(default_factory=list)
    line: int = 0
    raw_parameters: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.step_name = self.step_name.strip().upper()
        if self.program_name:
            self.program_name = self.program_name.strip().upper()
        if self.proc_name:
            self.proc_name = self.proc_name.strip().upper()

    def get_dd(self, dd_name: str) -> Optional[JclDd]:
        target = dd_name.strip().upper()
        for dd in self.dds:
            if dd.dd_name == target:
                return dd
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "program_name": self.program_name,
            "proc_name": self.proc_name,
            "exec_type": self.exec_type,
            "conditions": [c.to_dict() for c in self.conditions],
            "dds": [dd.to_dict() for dd in self.dds],
            "line": self.line,
            "raw_parameters": dict(self.raw_parameters),
        }


@dataclass
class JclJob:
    job_name: str
    steps: List[JclStep] = field(default_factory=list)
    accounting: Optional[str] = None
    job_class: Optional[str] = None
    msgclass: Optional[str] = None
    line: int = 0
    raw_parameters: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.job_name = self.job_name.strip().upper()

    def get_step(self, step_name: str) -> Optional[JclStep]:
        target = step_name.strip().upper()
        for step in self.steps:
            if step.step_name == target:
                return step
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_name": self.job_name,
            "accounting": self.accounting,
            "job_class": self.job_class,
            "msgclass": self.msgclass,
            "steps": [s.to_dict() for s in self.steps],
            "line": self.line,
            "raw_parameters": dict(self.raw_parameters),
        }


class JclParser:
    """
    Deterministic JCL Lexer & Parser.
    Extracts Jobs, Steps, and DD datasets from mainframe JCL text.
    """

    def parse(self, text: str) -> List[JclJob]:
        """Parses JCL text stream into structured JclJob objects."""
        logical_lines = self._merge_continuation_lines(text)
        jobs: List[JclJob] = []
        current_job: Optional[JclJob] = None
        current_step: Optional[JclStep] = None

        for lineno, raw_line in logical_lines:
            # Check comment: //*
            if raw_line.startswith("//*"):
                continue

            if not raw_line.startswith("//"):
                continue

            line = raw_line[2:].strip()
            if not line:
                continue

            tokens = line.split(None, 2)
            if not tokens:
                continue

            name = tokens[0].upper()
            verb = tokens[1].upper() if len(tokens) > 1 else ""
            params_str = tokens[2] if len(tokens) > 2 else ""

            if verb == "JOB":
                current_job = self._parse_job(name, params_str, lineno)
                jobs.append(current_job)
                current_step = None

            elif verb == "EXEC":
                if current_job is None:
                    # Implicit anonymous job if no JOB card preceded
                    current_job = JclJob(job_name="ANONJOB", line=lineno)
                    jobs.append(current_job)
                current_step = self._parse_step(name, params_str, lineno)
                current_job.steps.append(current_step)

            elif verb == "DD":
                if current_step is not None:
                    dd_card = self._parse_dd(name, params_str, lineno)
                    current_step.dds.append(dd_card)

        return jobs

    def _merge_continuation_lines(self, text: str) -> List[Tuple[int, str]]:
        """
        Merges JCL continuation lines. In JCL, if a line ends with a comma (outside quotes)
        or has whitespace after a comma, the next line starting with // continues it.
        """
        lines = text.splitlines()
        merged: List[Tuple[int, str]] = []
        idx = 0
        n = len(lines)

        while idx < n:
            raw = lines[idx]
            lineno = idx + 1
            idx += 1

            if not raw.startswith("//") or raw.startswith("//*"):
                merged.append((lineno, raw))
                continue

            current_text = raw
            while idx < n:
                stripped = current_text.rstrip()
                # Check if it ends with a comma
                if stripped.endswith(","):
                    next_line = lines[idx]
                    if next_line.startswith("//"):
                        # Continuation line: strip leading '//' and spaces
                        continuation_body = next_line[2:].strip()
                        current_text = stripped + " " + continuation_body
                        idx += 1
                        continue
                break

            merged.append((lineno, current_text))

        return merged

    def _parse_key_values(self, params_str: str) -> Dict[str, str]:
        """Parses parameter string preserving parenthesis groups and quotes."""
        kvs: Dict[str, str] = {}
        tokens = self._tokenize_parameters(params_str)
        for token in tokens:
            if "=" in token:
                k, v = token.split("=", 1)
                kvs[k.strip().upper()] = v.strip()
            else:
                kvs[token.strip().upper()] = "TRUE"
        return kvs

    def _tokenize_parameters(self, text: str) -> List[str]:
        tokens: List[str] = []
        cur: List[str] = []
        paren_depth = 0
        in_quote = False
        quote_char = ""

        for char in text:
            if in_quote:
                cur.append(char)
                if char == quote_char:
                    in_quote = False
            elif char in ("'", '"'):
                in_quote = True
                quote_char = char
                cur.append(char)
            elif char == "(":
                paren_depth += 1
                cur.append(char)
            elif char == ")":
                if paren_depth > 0:
                    paren_depth -= 1
                cur.append(char)
            elif char == "," and paren_depth == 0 and not in_quote:
                tok = "".join(cur).strip()
                if tok:
                    tokens.append(tok)
                cur = []
            elif char.isspace() and paren_depth == 0 and not in_quote and not cur:
                continue
            else:
                cur.append(char)

        if cur:
            tok = "".join(cur).strip()
            if tok:
                tokens.append(tok)
        return tokens

    def _parse_job(self, name: str, params_str: str, lineno: int) -> JclJob:
        kvs = self._parse_key_values(params_str)
        job_class = kvs.get("CLASS")
        msgclass = kvs.get("MSGCLASS")
        accounting = None

        tokens = self._tokenize_parameters(params_str)
        if tokens and not tokens[0].startswith("CLASS=") and not tokens[0].startswith("MSGCLASS="):
            accounting = tokens[0].strip("()'\"")

        return JclJob(
            job_name=name,
            accounting=accounting,
            job_class=job_class,
            msgclass=msgclass,
            line=lineno,
            raw_parameters=kvs,
        )

    def _parse_step(self, name: str, params_str: str, lineno: int) -> JclStep:
        kvs = self._parse_key_values(params_str)
        pgm = kvs.get("PGM")
        proc = kvs.get("PROC")
        exec_type = "PGM"

        if not pgm and not proc:
            # Positional format: //STEP01 EXEC MYPROC
            tokens = self._tokenize_parameters(params_str)
            if tokens and "=" not in tokens[0]:
                proc = tokens[0].strip()
                exec_type = "PROC"

        if proc and not pgm:
            exec_type = "PROC"

        conditions: List[JclCondition] = []
        cond_raw = kvs.get("COND")
        if cond_raw:
            conditions = self._parse_conditions(cond_raw)

        return JclStep(
            step_name=name,
            program_name=pgm,
            proc_name=proc,
            exec_type=exec_type,
            conditions=conditions,
            line=lineno,
            raw_parameters=kvs,
        )

    def _parse_conditions(self, cond_str: str) -> List[JclCondition]:
        cond_clean = cond_str.strip()
        if cond_clean.upper() in ("EVEN", "ONLY"):
            return [JclCondition(special=cond_clean.upper(), raw_text=cond_clean)]

        conds: List[JclCondition] = []
        # Matches (code, operator[, stepname])
        tuples = re.findall(r"\(\s*(\d+)\s*,\s*([A-Za-z]+)(?:\s*,\s*([A-Za-z0-9_-]+))?\s*\)", cond_clean)
        for t in tuples:
            code = int(t[0])
            op = t[1].upper()
            ref_step = t[2].upper() if t[2] else None
            conds.append(JclCondition(code=code, operator=op, reference_step=ref_step, raw_text=f"({t[0]},{t[1]})"))

        if not conds and cond_clean:
            conds.append(JclCondition(raw_text=cond_clean))
        return conds

    def _parse_dd(self, name: str, params_str: str, lineno: int) -> JclDd:
        kvs = self._parse_key_values(params_str)
        dsn = kvs.get("DSN")
        disp = kvs.get("DISP")
        is_dummy = "DUMMY" in kvs or (dsn is not None and dsn.upper() == "NULLFILE")
        is_sysout = "SYSOUT" in kvs

        # Classify access intent from DISP
        access_intent = "UNKNOWN"
        if is_dummy:
            access_intent = "READ"
        elif is_sysout:
            access_intent = "WRITE"
        elif disp:
            disp_up = disp.upper().strip("()")
            parts = [p.strip() for p in disp_up.split(",")]
            status = parts[0] if parts else ""
            if status in ("SHR", "SHARE"):
                access_intent = "READ"
            elif status == "NEW":
                access_intent = "WRITE"
            elif status == "MOD":
                access_intent = "WRITE"
            elif status == "OLD":
                # OLD can be read or update
                access_intent = "READ_WRITE"
            else:
                access_intent = "UNKNOWN"
        elif dsn:
            # In JCL, default DISP is (NEW,DELETE)
            access_intent = "WRITE"

        return JclDd(
            dd_name=name,
            dsn=dsn,
            disp=disp,
            access_intent=access_intent,
            is_dummy=is_dummy,
            is_sysout=is_sysout,
            line=lineno,
            raw_parameters=kvs,
        )
