"""
Sokół Versioned Project Memory (sokol.fact.v1) & Anchor Invalidation Engine.

Implements read-only epistemic fact envelopes, deterministic node anchors,
snapshot binding, staleness invalidation, and strict non-transfer of verified
claims across changed code revisions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from rezonator.limits import MAX_SOURCE_BYTES


FACT_SCHEMA_VERSION = "sokol.fact.v1"
MAX_FACTS_IN_MEMORY = 2048
MAX_FACT_STREAM_BYTES = MAX_SOURCE_BYTES
MAX_CLAIM_CHARS = 1000
MAX_SIGNATURE_CHARS = 256

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_FACT_STATUSES = frozenset({"OBSERVED", "INFERRED", "VERIFIED"})
_FACT_FIELDS = frozenset({
    "schema_version",
    "fact_id",
    "status",
    "claim",
    "evidence_ids",
    "source_snapshot",
    "git_commit",
    "graph_snapshot",
    "node_anchor",
    "confidence",
    "verification_basis",
    "created_at_utc",
    "stale",
    "staleness_reason",
})


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("fact data must be finite, JSON-serializable values") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _normalize_timestamp(value: Optional[str]) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    else:
        if not isinstance(value, str):
            raise TypeError("timestamp must be an ISO-8601 string")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be an ISO-8601 string") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_hash_id(digest: Any, label: str) -> str:
    if not isinstance(digest, str):
        raise ValueError(f"{label} must be a 64-character hexadecimal SHA-256 string")
    clean = digest.lower()
    if clean.startswith("sha256:"):
        clean = clean[7:]
    if not _HASH_RE.fullmatch(clean):
        raise ValueError(f"{label} must be a 64-character hexadecimal SHA-256 string")
    return clean


@dataclass(frozen=True)
class NodeAnchor:
    """
    Source anchor for a graph node or statement that can be remapped across
    revisions even when line numbers shift or nodes are re-indexed.
    """

    paragraph: str
    statement_index: int = 0
    verb: str = "UNKNOWN"
    signature: str = ""
    node_id: Optional[str] = None
    line: Optional[int] = None
    copybook: Optional[str] = None
    copybook_line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paragraph": self.paragraph,
            "statement_index": self.statement_index,
            "verb": self.verb.upper(),
            "signature": self.signature[:MAX_SIGNATURE_CHARS],
            "node_id": self.node_id,
            "line": self.line,
            "copybook": self.copybook,
            "copybook_line": self.copybook_line,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NodeAnchor":
        return cls(
            paragraph=str(data.get("paragraph", "")).upper(),
            statement_index=int(data.get("statement_index", 0)),
            verb=str(data.get("verb", "UNKNOWN")).upper(),
            signature=str(data.get("signature", ""))[:MAX_SIGNATURE_CHARS],
            node_id=str(data["node_id"]) if data.get("node_id") is not None else None,
            line=int(data["line"]) if data.get("line") is not None else None,
            copybook=str(data["copybook"]) if data.get("copybook") is not None else None,
            copybook_line=int(data["copybook_line"]) if data.get("copybook_line") is not None else None,
        )


def build_fact_anchor(node: Mapping[str, Any], statement_index: int = 0) -> Dict[str, Any]:
    """Extract a normalized NodeAnchor dictionary from a graph node mapping."""
    origin = node.get("source_origin") or {}
    loc = node.get("location") or {}
    code = node.get("code", "").strip()
    verb = code.split()[0].rstrip(".").upper() if code else "UNKNOWN"
    line = origin.get("line", loc.get("line", node.get("line")))
    
    anchor = NodeAnchor(
        paragraph=str(node.get("paragraph", "UNKNOWN")).upper(),
        statement_index=statement_index,
        verb=verb,
        signature=" ".join(code.split())[:MAX_SIGNATURE_CHARS],
        node_id=str(node.get("id")) if node.get("id") is not None else None,
        line=line,
        copybook=origin.get("file") or origin.get("source"),
        copybook_line=origin.get("line"),
    )
    return anchor.to_dict()


def validate_fact(fact: Mapping[str, Any]) -> None:
    """
    Validates a fact against the sokol.fact.v1 specification.
    Enforces epistemic status constraints, evidence requirements, and checksums.
    """
    if not isinstance(fact, Mapping):
        raise TypeError("fact must be a dictionary or mapping")
    
    extra = set(fact.keys()) - _FACT_FIELDS
    if extra:
        raise ValueError(f"fact contains unknown fields: {sorted(extra)}")
    
    missing = {
        "schema_version", "fact_id", "status", "claim", "evidence_ids",
        "source_snapshot", "node_anchor", "confidence", "created_at_utc", "stale",
    } - set(fact.keys())
    if missing:
        raise ValueError(f"fact is missing required fields: {sorted(missing)}")

    if fact.get("schema_version") != FACT_SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version; expected {FACT_SCHEMA_VERSION}")

    status = fact.get("status")
    if status not in _FACT_STATUSES:
        raise ValueError(f"invalid status {status!r}; expected one of {sorted(_FACT_STATUSES)}")

    claim = fact.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be a non-empty string")
    if len(claim) > MAX_CLAIM_CHARS:
        raise ValueError(f"claim exceeds maximum length of {MAX_CLAIM_CHARS} characters")
    # Privacy check: reject raw COBOL source code dumps in claims
    if any(header in claim.upper() for header in ["IDENTIFICATION DIVISION", "PROCEDURE DIVISION", "WORKING-STORAGE SECTION"]):
        raise ValueError("claim contains prohibited raw source division header")

    evidence_ids = fact.get("evidence_ids")
    if not isinstance(evidence_ids, Sequence) or isinstance(evidence_ids, str):
        raise ValueError("evidence_ids must be a sequence of evidence event IDs")
    
    # INFERRED facts MUST cite at least one evidence event ID
    if status == "INFERRED" and len(evidence_ids) == 0:
        raise ValueError("INFERRED fact must cite at least one evidence_id")

    _validate_hash_id(fact.get("source_snapshot"), "source_snapshot")

    if fact.get("graph_snapshot") is not None:
        _validate_hash_id(fact.get("graph_snapshot"), "graph_snapshot")

    git_commit = fact.get("git_commit")
    if git_commit is not None:
        if not isinstance(git_commit, str) or not re.fullmatch(r"[0-9a-fA-F]{7,64}", git_commit):
            raise ValueError("git_commit must be a 7-64 character hexadecimal commit ID")

    node_anchor = fact.get("node_anchor")
    if not isinstance(node_anchor, Mapping):
        raise ValueError("node_anchor must be an object")

    # VERIFIED status MUST have a non-null verification_basis specifying basis_type and snapshot_id
    verification_basis = fact.get("verification_basis")
    if status == "VERIFIED":
        if not isinstance(verification_basis, Mapping):
            raise ValueError("VERIFIED fact requires a non-null verification_basis object")
        b_type = verification_basis.get("basis_type")
        if b_type not in ("assertion_test", "reviewer_attestation"):
            raise ValueError("verification_basis.basis_type must be 'assertion_test' or 'reviewer_attestation'")
        if not verification_basis.get("snapshot_id"):
            raise ValueError("verification_basis requires a snapshot_id")
    elif verification_basis is not None and not isinstance(verification_basis, Mapping):
        raise ValueError("verification_basis must be null or an object")

    normalized_ts = _normalize_timestamp(fact.get("created_at_utc"))
    if normalized_ts != fact.get("created_at_utc"):
        raise ValueError("created_at_utc must be formatted as UTC ISO-8601 with trailing 'Z'")

    if not isinstance(fact.get("stale"), bool):
        raise ValueError("stale must be a boolean")

    # Validate immutable content-based fact_id checksum
    # fact_id covers all fields EXCEPT fact_id, stale, and staleness_reason
    body = {
        k: v for k, v in fact.items()
        if k not in ("fact_id", "stale", "staleness_reason")
    }
    expected_id = f"fact:sha256:{_sha256(body)}"
    if fact.get("fact_id") != expected_id:
        raise ValueError(
            f"fact_id checksum mismatch; expected {expected_id}, got {fact.get('fact_id')}"
        )


def create_fact(
    claim: str,
    status: str,
    source_snapshot: str,
    node_anchor: Mapping[str, Any],
    *,
    evidence_ids: Optional[Sequence[str]] = None,
    graph_snapshot: Optional[str] = None,
    git_commit: Optional[str] = None,
    confidence: str = "unscored",
    verification_basis: Optional[Mapping[str, Any]] = None,
    created_at_utc: Optional[str] = None,
    stale: bool = False,
    staleness_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper factory that constructs and validates a compliant sokol.fact.v1 envelope."""
    clean_source_snap = _validate_hash_id(source_snapshot, "source_snapshot")
    clean_graph_snap = _validate_hash_id(graph_snapshot, "graph_snapshot") if graph_snapshot else None
    
    timestamp = _normalize_timestamp(created_at_utc)
    ev_ids = list(evidence_ids or [])
    clean_git = git_commit.lower() if git_commit else None

    body = {
        "schema_version": FACT_SCHEMA_VERSION,
        "status": status,
        "claim": claim.strip(),
        "evidence_ids": ev_ids,
        "source_snapshot": clean_source_snap,
        "git_commit": clean_git,
        "graph_snapshot": clean_graph_snap,
        "node_anchor": dict(node_anchor),
        "confidence": confidence,
        "verification_basis": dict(verification_basis) if verification_basis else None,
        "created_at_utc": timestamp,
    }
    fact_id = f"fact:sha256:{_sha256(body)}"
    fact = {
        **body,
        "fact_id": fact_id,
        "stale": stale,
        "staleness_reason": staleness_reason,
    }
    validate_fact(fact)
    return fact


class ProjectMemory:
    """
    In-memory, versioned project memory store for Sokół fact envelopes.
    Binds observations and hypotheses to specific code and graph snapshots,
    and reconciles staleness across codebase revisions.
    """

    def __init__(self, project_id: str = "default-project", max_facts: int = MAX_FACTS_IN_MEMORY):
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("project_id must be a non-empty string")
        if "/" in project_id or "\\" in project_id:
            raise ValueError("project_id must be an opaque identifier, not a filesystem path")
        self.project_id = project_id
        self.max_facts = max_facts
        self._facts: Dict[str, Dict[str, Any]] = {}

    def __len__(self) -> int:
        return len(self._facts)

    def register_fact(self, fact: Mapping[str, Any]) -> str:
        """Register a validated fact. Rejects duplicate IDs or capacity overflow."""
        validate_fact(fact)
        fact_id: str = str(fact["fact_id"])
        if fact_id not in self._facts and len(self._facts) >= self.max_facts:
            raise ValueError(f"Project memory capacity limit reached ({self.max_facts} facts)")
        self._facts[fact_id] = dict(fact)
        return fact_id

    def get_fact(self, fact_id: str) -> Optional[Dict[str, Any]]:
        return dict(self._facts[fact_id]) if fact_id in self._facts else None

    def list_facts(
        self,
        *,
        include_stale: bool = True,
        status: Optional[str] = None,
        paragraph: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query stored facts with optional status, paragraph, and staleness filtering."""
        results = []
        for fact in self._facts.values():
            if not include_stale and fact["stale"]:
                continue
            if status is not None and fact["status"] != status:
                continue
            if paragraph is not None:
                anchor = fact.get("node_anchor") or {}
                if anchor.get("paragraph", "").upper() != paragraph.upper():
                    continue
            results.append(dict(fact))
        return results

    def reconcile_with_snapshot(
        self,
        analysis_or_report: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """
        Reconciles all active facts in memory against a new analysis snapshot.
        Enforces Sokół memory invariants:
        1. If source_snapshot matches, fact remains active.
        2. If source_snapshot changed:
           - VERIFIED facts are marked STALE (staleness_reason="snapshot_changed_reverification_required").
           - INFERRED/OBSERVED facts attempt anchor remapping against new graph nodes.
           - If anchor cannot be cleanly matched, fact is marked STALE (staleness_reason="anchor_unmappable").
        """
        # Extract new snapshot IDs and nodes
        provenance = analysis_or_report.get("provenance") or {}
        new_source_snap = ""
        if "analysis_fingerprint" in provenance:
            # Audit report format
            sources = provenance.get("source_hashes") or {}
            source_sha = provenance.get("source_sha256") or (next(iter(sources.values())) if sources else "")
            new_source_snap = source_sha.lower()
        else:
            # Raw comparator format
            new_source_snap = str(provenance.get("source_sha256", "")).lower()

        parsed = analysis_or_report.get("parsed") or {}
        new_nodes = parsed.get("nodes", [])
        
        # Build node index for remapping: paragraph -> list of nodes
        nodes_by_para: Dict[str, List[Dict[str, Any]]] = {}
        for n in new_nodes:
            para = str(n.get("paragraph", "")).upper()
            nodes_by_para.setdefault(para, []).append(n)

        total_checked = 0
        newly_invalidated = 0
        reverification_required = 0
        active_count = 0

        for fact_id, fact in list(self._facts.items()):
            total_checked += 1
            old_source = fact["source_snapshot"].lower()

            if old_source == new_source_snap:
                # Same source snapshot: fact remains active unless already marked stale
                if not fact["stale"]:
                    active_count += 1
                continue

            # Source snapshot has changed!
            if fact["status"] == "VERIFIED":
                # Strict invariant: never carry VERIFIED across snapshots without re-verification
                fact["stale"] = True
                fact["staleness_reason"] = "snapshot_changed_reverification_required"
                newly_invalidated += 1
                reverification_required += 1
                continue

            # For INFERRED and OBSERVED facts, evaluate anchor remappability
            anchor = fact.get("node_anchor") or {}
            para = anchor.get("paragraph", "").upper()
            sig = anchor.get("signature", "").strip()

            candidate_nodes = nodes_by_para.get(para, [])
            match_found = False

            for cand in candidate_nodes:
                cand_code = " ".join(cand.get("code", "").split())
                if sig and cand_code and (sig in cand_code or cand_code in sig):
                    match_found = True
                    break

            if match_found:
                # Anchor found in new revision: remains active with anchor remapped
                fact["stale"] = False
                fact["staleness_reason"] = None
                active_count += 1
            else:
                # Anchor unmappable or statement altered: mark stale
                fact["stale"] = True
                fact["staleness_reason"] = "anchor_unmappable"
                newly_invalidated += 1

        return {
            "total_facts": len(self._facts),
            "reconciled_facts": total_checked,
            "active_count": active_count,
            "stale_count": len(self._facts) - active_count,
            "newly_invalidated": newly_invalidated,
            "reverification_required": reverification_required,
        }

    def serialize_json(self, indent: Optional[int] = 2) -> str:
        """Serializes project memory into a validated JSON string."""
        payload = {
            "schema_version": FACT_SCHEMA_VERSION,
            "project_id": self.project_id,
            "facts_count": len(self._facts),
            "facts": list(self._facts.values()),
        }
        raw = json.dumps(payload, indent=indent, sort_keys=True, ensure_ascii=False)
        if len(raw.encode("utf-8")) > MAX_FACT_STREAM_BYTES:
            raise ValueError(f"Serialized memory exceeds maximum byte limit of {MAX_FACT_STREAM_BYTES}")
        return raw

    @classmethod
    def parse_json(cls, json_str: str) -> "ProjectMemory":
        """Parses and validates a JSON string into a ProjectMemory store."""
        if len(json_str.encode("utf-8")) > MAX_FACT_STREAM_BYTES:
            raise ValueError("JSON string exceeds memory payload size limit")
        data = json.loads(json_str)
        if not isinstance(data, Mapping):
            raise ValueError("memory JSON must be an object")
        if data.get("schema_version") != FACT_SCHEMA_VERSION:
            raise ValueError("unsupported schema_version")
        
        project_id = data.get("project_id", "default-project")
        memory = cls(project_id=project_id)
        for fact in data.get("facts", []):
            memory.register_fact(fact)
        return memory

    def serialize_jsonl(self) -> str:
        """Serializes all facts as one validated JSONL line per fact."""
        lines = []
        for fact in self._facts.values():
            validate_fact(fact)
            lines.append(json.dumps(fact, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return "\n".join(lines) + ("\n" if lines else "")

    @classmethod
    def parse_jsonl(cls, jsonl_str: str, project_id: str = "default-project") -> "ProjectMemory":
        """Parses a stream of newline-delimited JSON fact lines into ProjectMemory."""
        if len(jsonl_str.encode("utf-8")) > MAX_FACT_STREAM_BYTES:
            raise ValueError("JSONL string exceeds memory stream byte limit")
        memory = cls(project_id=project_id)
        for line_num, line in enumerate(jsonl_str.splitlines(), start=1):
            clean = line.strip()
            if not clean:
                continue
            try:
                fact = json.loads(clean)
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed JSON on line {line_num}") from exc
            memory.register_fact(fact)
        return memory

    def to_markdown_report(self) -> str:
        """Renders the memory contents into an inspectable Markdown summary table."""
        active_facts = [f for f in self._facts.values() if not f["stale"]]
        stale_facts = [f for f in self._facts.values() if f["stale"]]

        lines = [
            f"# Sokół Project Memory Report: `{self.project_id}`",
            "",
            "## Summary",
            "",
            f"- **Schema Version:** `{FACT_SCHEMA_VERSION}`",
            f"- **Total Registered Facts:** {len(self._facts)}",
            f"- **Active Facts:** {len(active_facts)}",
            f"- **Stale (Invalidated) Facts:** {len(stale_facts)}",
            "",
            "---",
            "",
            "## Active Knowledge Base",
            "",
            "| Status | Claim | Anchor Paragraph | Snapshot | Confidence | Basis |",
            "|:---:|---|---|:---:|:---:|---|",
        ]

        for f in active_facts:
            basis_str = f["verification_basis"]["basis_type"] if f.get("verification_basis") else "none"
            para = (f.get("node_anchor") or {}).get("paragraph", "-")
            snap_short = f["source_snapshot"][:8]
            lines.append(
                f"| `{f['status']}` | {f['claim']} | `{para}` | `{snap_short}` | {f['confidence']} | {basis_str} |"
            )

        if stale_facts:
            lines.extend([
                "",
                "---",
                "",
                "## Stale (Invalidated / Historical) Facts",
                "",
                "| Status | Claim | Reason for Invalidation | Original Snapshot |",
                "|:---:|---|---|:---:|",
            ])
            for f in stale_facts:
                reason = f.get("staleness_reason") or "unspecified"
                snap_short = f["source_snapshot"][:8]
                lines.append(
                    f"| `{f['status']}` | {f['claim']} | `{reason}` | `{snap_short}` |"
                )

        return "\n".join(lines) + "\n"
