"""
Bank-Grade Security Shield: Prompt Injection Defense & PII / Secrets Redaction (Milestone 3).

1. PromptInjectionShield:
   Detects and neutralizes indirect prompt injection attempts embedded in legacy COBOL comments,
   literals, JCL scripts, and copybook streams. Defends against jailbreak patterns, system prompt overrides,
   markdown delimiter breakout, and hidden unicode steganography.

2. PiiSecretsRedactor:
   Identifies and redacts confidential banking data:
   - Primary Account Numbers (PAN / Credit Cards) with Luhn algorithm validation.
   - Polish PESEL (National ID) with official modulo-10 checksum validation.
   - US Social Security Numbers (SSN).
   - International Bank Account Numbers (IBAN).
   - Hardcoded DB2 SQL credentials, passwords, private keys, and API tokens.
"""

from __future__ import annotations

import enum
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class PromptInjectionRisk(str, enum.Enum):
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RedactionMode(str, enum.Enum):
    MASK = "MASK"
    SALTED_HASH = "SALTED_HASH"


class SecurityInjectionError(ValueError):
    """Raised when critical prompt injection is detected under strict security mode."""
    pass


@dataclass
class InjectionFinding:
    pattern_name: str
    risk_level: PromptInjectionRisk
    matched_snippet: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "risk_level": self.risk_level.value,
            "matched_snippet": self.matched_snippet[:64],
            "description": self.description,
        }


@dataclass
class InjectionScanResult:
    is_safe: bool
    highest_risk: PromptInjectionRisk
    findings: List[InjectionFinding] = field(default_factory=list)
    sanitized_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "highest_risk": self.highest_risk.value,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


class PromptInjectionShield:
    """
    Shields external LLM observers from untrusted prompt injections embedded in legacy code.
    Enforces a strict untrusted data boundary and neutralizes jailbreak vectors.
    """

    CRITICAL_PATTERNS = [
        (
            "OVERRIDE_DIRECTIVE",
            re.compile(
                r"(?:ignore|disregard|forget|bypass|override)\s+(?:all\s+)?(?:previous|prior|system|above)\s+(?:instructions|prompts|rules|directives)",
                re.IGNORECASE,
            ),
            PromptInjectionRisk.CRITICAL,
            "Direct attempt to override system instructions.",
        ),
        (
            "SYSTEM_PROMPT_INJECTION",
            re.compile(
                r"\[\s*(?:system|assistant|system\s+directive|developer\s+instruction)\b[^\]]*\]",
                re.IGNORECASE,
            ),
            PromptInjectionRisk.CRITICAL,
            "Simulated system or assistant role delimiter injection.",
        ),
        (
            "JAILBREAK_KEYWORD",
            re.compile(
                r"\b(?:DAN|STAN|DUDE|jailbreak|unfiltered\s+mode|developer\s+mode|uncensored)\b",
                re.IGNORECASE,
            ),
            PromptInjectionRisk.HIGH,
            "Known jailbreak persona or unconstrained prompt activation keyword.",
        ),
        (
            "DELIMITER_BREAKOUT",
            re.compile(r"```(?:json|markdown|python|yaml)?\s*\n\s*(?:stop|end|system|eval)", re.IGNORECASE),
            PromptInjectionRisk.HIGH,
            "Attempted markdown code fence breakout into instruction execution.",
        ),
        (
            "AUTONOMOUS_GATE_FORGERY",
            re.compile(
                r"(?:claim\s+is\s+verified|promote\s+to\s+verified|status\s*[:=]\s*['\"]?VERIFIED['\"]?|certify\s+release)",
                re.IGNORECASE,
            ),
            PromptInjectionRisk.HIGH,
            "Attempt to force automated epistemic promotion from INFERRED to VERIFIED.",
        ),
    ]

    ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200D\uFEFF\u2060\u202A-\u202E]")

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode

    def scan_text(self, text: str) -> InjectionScanResult:
        """Scans input text for known indirect prompt injection and jailbreak signatures."""
        findings: List[InjectionFinding] = []

        # 1. Check for hidden zero-width unicode steganography
        zero_width_matches = self.ZERO_WIDTH_CHARS.findall(text)
        if zero_width_matches:
            findings.append(InjectionFinding(
                pattern_name="ZERO_WIDTH_STEGANOGRAPHY",
                risk_level=PromptInjectionRisk.MEDIUM,
                matched_snippet=f"{len(zero_width_matches)} hidden unicode characters",
                description="Zero-width unicode characters detected, potentially obfuscating malicious instructions.",
            ))

        # 2. Check regex injection signatures
        for name, pattern, risk, desc in self.CRITICAL_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(InjectionFinding(
                    pattern_name=name,
                    risk_level=risk,
                    matched_snippet=match.group(0),
                    description=desc,
                ))

        # 3. Determine highest risk
        risk_priority = [
            PromptInjectionRisk.SAFE,
            PromptInjectionRisk.LOW,
            PromptInjectionRisk.MEDIUM,
            PromptInjectionRisk.HIGH,
            PromptInjectionRisk.CRITICAL,
        ]
        highest = PromptInjectionRisk.SAFE
        for f in findings:
            if risk_priority.index(f.risk_level) > risk_priority.index(highest):
                highest = f.risk_level

        is_safe = (highest in (PromptInjectionRisk.SAFE, PromptInjectionRisk.LOW))
        sanitized = self.sanitize_text(text)

        if self.strict_mode and highest in (PromptInjectionRisk.HIGH, PromptInjectionRisk.CRITICAL):
            raise SecurityInjectionError(
                f"Prompt injection detected under strict mode: {findings[0].description} "
                f"(snippet: '{findings[0].matched_snippet}')"
            )

        return InjectionScanResult(
            is_safe=is_safe,
            highest_risk=highest,
            findings=findings,
            sanitized_text=sanitized,
        )

    def sanitize_text(self, text: str) -> str:
        """
        Sanitizes text by stripping invisible zero-width chars, neutralizing role delimiters,
        and defanging prompt injection escape sequences.
        """
        # Strip zero-width chars
        sanitized = self.ZERO_WIDTH_CHARS.sub("", text)

        # Defang system role delimiters
        sanitized = re.sub(
            r"\[\s*(system|assistant|developer)[^\]]*\]",
            r"[DEFANGED_\1]",
            sanitized,
            flags=re.IGNORECASE,
        )

        # Defang override commands inside comments
        sanitized = re.sub(
            r"\b(ignore|disregard|forget|bypass)\s+(all\s+)?(previous|prior|system)\s+(instructions|prompts|directives|rules)\b",
            r"[BLOCKED_INJECTION_DIRECTIVE]",
            sanitized,
            flags=re.IGNORECASE,
        )

        return sanitized


@dataclass
class RedactionItem:
    category: str
    original_value_masked: str
    replacement: str
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "original_masked": self.original_value_masked,
            "replacement": self.replacement,
            "line_number": self.line_number,
        }


@dataclass
class RedactionReport:
    total_redactions: int
    categories_found: Dict[str, int] = field(default_factory=dict)
    redaction_items: List[RedactionItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_redactions": self.total_redactions,
            "categories_found": dict(self.categories_found),
            "redaction_items": [i.to_dict() for i in self.redaction_items],
        }


class PiiSecretsRedactor:
    """
    Automated PII, Bank Account, and Credential Redactor.
    Scans legacy COBOL literals, copybooks, and dossiers to prevent leakage of
    confidential banking data to external AI models or unauthorized reviewers.
    """

    # Credit card PAN (13 to 19 digits)
    PAN_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3,4}\d{1,4}\b")

    # Polish PESEL (exactly 11 digits)
    PESEL_REGEX = re.compile(r"\b\d{11}\b")

    # US SSN (3-2-4 digits)
    SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    # Polish IBAN (PL followed by 26 digits) or generic European IBAN
    IBAN_REGEX = re.compile(r"\bPL\d{2}[-\s]?(?:\d{4}[-\s]?){6}\b|\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")

    # DB2 SQL credentials in EXEC SQL or script statements
    DB2_CRED_REGEX = re.compile(
        r"(?:USER\s+['\"][A-Za-z0-9_$-]+['\"]\s+USING\s+['\"])([^'\"]+)(?:['\"])",
        re.IGNORECASE,
    )
    SQL_IDENT_REGEX = re.compile(
        r"(?:IDENTIFIED\s+BY\s+['\"])([^'\"]+)(?:['\"])",
        re.IGNORECASE,
    )

    # Private key blocks
    PRIVATE_KEY_REGEX = re.compile(
        r"-----BEGIN\s+(?:[A-Z0-9_-]+\s+)?PRIVATE\s+KEY-----[\s\S]+?-----END\s+(?:[A-Z0-9_-]+\s+)?PRIVATE\s+KEY-----",
        re.IGNORECASE,
    )

    # API Keys & Hardcoded Passwords
    SECRET_KEY_REGEX = re.compile(
        r"\b(?:api[_-]?key|password|passwd|secret|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"]([A-Za-z0-9_\-+/=]{12,})['\"]",
        re.IGNORECASE,
    )

    def __init__(
        self,
        mode: RedactionMode = RedactionMode.MASK,
        salt: str = "rezonator-audit-salt-2026",
    ):
        self.mode = mode
        self.salt = salt

    @staticmethod
    def _is_luhn_valid(card_number_digits: str) -> bool:
        """Validates credit card PAN using the standard Luhn checksum algorithm."""
        digits = [int(c) for c in card_number_digits if c.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False
        total = 0
        reverse_digits = digits[::-1]
        for i, d in enumerate(reverse_digits):
            if i % 2 == 1:
                doubled = d * 2
                total += doubled - 9 if doubled > 9 else doubled
            else:
                total += d
        return total % 10 == 0

    @staticmethod
    def _is_pesel_valid(pesel_str: str) -> bool:
        """Validates Polish PESEL using official 11-digit modulo-10 weights: 1 3 7 9 1 3 7 9 1 3."""
        if not pesel_str.isdigit() or len(pesel_str) != 11:
            return False
        weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
        digits = [int(c) for c in pesel_str]
        checksum = sum(w * d for w, d in zip(weights, digits[:10])) % 10
        control = (10 - checksum) % 10
        return control == digits[10]

    def _format_replacement(self, category: str, raw_val: str) -> str:
        """Formats the replacement string according to current RedactionMode."""
        if self.mode == RedactionMode.MASK:
            return f"[REDACTED:{category}]"
        else:
            digest = hashlib.sha256(f"{self.salt}:{raw_val}".encode("utf-8")).hexdigest()[:12]
            return f"[HASH:{category}:{digest}]"

    def redact_text(self, text: str) -> Tuple[str, RedactionReport]:
        """Scans and redacts all sensitive PII, account numbers, and secrets from string."""
        categories_count: Dict[str, int] = {}
        items: List[RedactionItem] = []
        result = text

        def record(category: str, raw: str, replacement: str) -> None:
            categories_count[category] = categories_count.get(category, 0) + 1
            masked_sample = raw[:2] + ("*" * max(2, len(raw) - 4)) + raw[-2:] if len(raw) > 4 else "****"
            items.append(RedactionItem(
                category=category,
                original_value_masked=masked_sample,
                replacement=replacement,
            ))

        # 1. Private keys
        for match in self.PRIVATE_KEY_REGEX.finditer(result):
            raw = match.group(0)
            rep = self._format_replacement("PRIVATE_KEY", raw)
            record("PRIVATE_KEY", raw, rep)
            result = result.replace(raw, rep)

        # 2. DB2 SQL Credentials
        for match in self.DB2_CRED_REGEX.finditer(result):
            pwd = match.group(1)
            rep = self._format_replacement("DB2_PASSWORD", pwd)
            record("DB2_PASSWORD", pwd, rep)
            result = result.replace(pwd, rep)

        for match in self.SQL_IDENT_REGEX.finditer(result):
            pwd = match.group(1)
            rep = self._format_replacement("SQL_PASSWORD", pwd)
            record("SQL_PASSWORD", pwd, rep)
            result = result.replace(pwd, rep)

        # 3. API Keys & Hardcoded Secrets
        for match in self.SECRET_KEY_REGEX.finditer(result):
            token = match.group(1)
            rep = self._format_replacement("SECRET_TOKEN", token)
            record("SECRET_TOKEN", token, rep)
            result = result.replace(token, rep)

        # 4. Credit card PAN (validated via Luhn)
        for match in self.PAN_REGEX.finditer(result):
            candidate = match.group(0)
            digits_only = re.sub(r"\D", "", candidate)
            if self._is_luhn_valid(digits_only):
                rep = self._format_replacement("PAN", candidate)
                record("PAN", candidate, rep)
                result = result.replace(candidate, rep)

        # 5. Polish PESEL (validated via weights)
        for match in self.PESEL_REGEX.finditer(result):
            candidate = match.group(0)
            if self._is_pesel_valid(candidate):
                rep = self._format_replacement("PESEL", candidate)
                record("PESEL", candidate, rep)
                result = result.replace(candidate, rep)

        # 6. US SSN
        for match in self.SSN_REGEX.finditer(result):
            candidate = match.group(0)
            rep = self._format_replacement("SSN", candidate)
            record("SSN", candidate, rep)
            result = result.replace(candidate, rep)

        # 7. IBAN Bank Accounts
        for match in self.IBAN_REGEX.finditer(result):
            candidate = match.group(0)
            rep = self._format_replacement("IBAN", candidate)
            record("IBAN", candidate, rep)
            result = result.replace(candidate, rep)

        report = RedactionReport(
            total_redactions=sum(categories_count.values()),
            categories_found=categories_count,
            redaction_items=items,
        )
        return result, report

    def redact_data_structure(self, data: Any) -> Tuple[Any, RedactionReport]:
        """Recursively traverses a JSON-compatible dictionary/list structure and redacts strings."""
        aggregated_items: List[RedactionItem] = []
        aggregated_cats: Dict[str, int] = {}

        def _traverse(val: Any) -> Any:
            if isinstance(val, str):
                redacted, rep = self.redact_text(val)
                aggregated_items.extend(rep.redaction_items)
                for c, n in rep.categories_found.items():
                    aggregated_cats[c] = aggregated_cats.get(c, 0) + n
                return redacted
            elif isinstance(val, dict):
                return {k: _traverse(v) for k, v in val.items()}
            elif isinstance(val, list):
                return [_traverse(item) for item in val]
            else:
                return val

        cleaned = _traverse(data)
        report = RedactionReport(
            total_redactions=sum(aggregated_cats.values()),
            categories_found=aggregated_cats,
            redaction_items=aggregated_items,
        )
        return cleaned, report
