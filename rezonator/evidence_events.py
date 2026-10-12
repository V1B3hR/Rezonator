"""Opt-in, bounded, versioned Sokół evidence-event envelopes.

This module defines an export format only. It does not persist events, watch a
repository, send data over the network, or call an AI model.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from rezonator import __version__
from rezonator.limits import MAX_SOURCE_BYTES


EVENT_SCHEMA_VERSION = "sokol.event.v1"
MAX_EVENTS_PER_STREAM = 1024
MAX_EVENT_STREAM_BYTES = MAX_SOURCE_BYTES
MAX_SOURCE_ANCHORS = 250
MAX_RUNTIME_TRACE_NODES = 5000
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_EVENT_TYPES = frozenset({
    "source.snapshot",
    "analysis.completed",
    "runtime.interpreter_run",
})
_EVENT_FIELDS = frozenset({
    "schema_version", "event_id", "event_type", "project_id",
    "observed_at_utc", "epistemic_status", "payload",
})


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("event data must be finite, JSON-serializable values") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _timestamp(value: Optional[str]) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    else:
        if not isinstance(value, str):
            raise TypeError("observed_at_utc must be an ISO-8601 string")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at_utc must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("observed_at_utc must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _project_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("project_id must be a non-empty opaque project identifier")
    normalized = value.strip()
    if len(normalized) > 256:
        raise ValueError("project_id cannot exceed 256 characters")
    if "/" in normalized or "\\" in normalized or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError("project_id must be opaque and cannot be a filesystem path")
    return normalized


def _hash_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ValueError(f"{field} must be a 64-character lowercase SHA-256 hex digest")
    return value


def _make_event(
    event_type: str,
    project_id: str,
    payload: Mapping[str, Any],
    *,
    observed_at_utc: Optional[str] = None,
    epistemic_status: str = "OBSERVED",
) -> Dict[str, Any]:
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"unsupported event_type: {event_type!r}")
    if epistemic_status != "OBSERVED":
        raise ValueError("unsupported epistemic_status")
    body = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_type": event_type,
        "project_id": _project_id(project_id),
        "observed_at_utc": _timestamp(observed_at_utc),
        "epistemic_status": epistemic_status,
        "payload": dict(payload),
    }
    event = {**body, "event_id": f"sha256:{_sha256(body)}"}
    _validate_event(event)
    return event


def _validate_event(event: Mapping[str, Any]) -> None:
    if not isinstance(event, Mapping) or set(event) != _EVENT_FIELDS:
        raise ValueError("event has missing or unknown envelope fields")
    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        raise ValueError("unsupported evidence event schema_version")
    if event.get("event_type") not in _EVENT_TYPES:
        raise ValueError("unsupported evidence event_type")
    if event.get("epistemic_status") != "OBSERVED":
        raise ValueError("unsupported evidence epistemic_status")
    if not isinstance(event.get("payload"), Mapping):
        raise ValueError("event payload must be an object")
    _project_id(event.get("project_id"))
    normalized_timestamp = _timestamp(event.get("observed_at_utc"))
    if normalized_timestamp != event.get("observed_at_utc"):
        raise ValueError("observed_at_utc must be normalized to UTC with a Z suffix")
    expected_id = f"sha256:{_sha256({key: value for key, value in event.items() if key != 'event_id'})}"
    if not isinstance(event.get("event_id"), str) or event["event_id"] != expected_id:
        raise ValueError("event_id checksum does not match the event contents")


def _copybook_entries(provenance: Mapping[str, Any]) -> list:
    entries = provenance.get("copybooks", [])
    if not isinstance(entries, list):
        raise ValueError("provenance.copybooks must be a list")
    safe_entries = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("each copybook provenance entry must be an object")
        name = entry.get("name")
        digest = entry.get("sha256")
        if not isinstance(name, str) or not name:
            raise ValueError("copybook provenance entry requires a name")
        _hash_id(digest, "copybook sha256")
        safe_entries.append({"name": name, "sha256": digest})
    return sorted(safe_entries, key=lambda entry: entry["name"])


def _source_hashes(provenance: Mapping[str, Any]) -> Dict[str, str]:
    hashes = provenance.get("source_hashes")
    if not isinstance(hashes, Mapping) or not hashes:
        source_sha256 = provenance.get("source_sha256")
        hashes = {"source": source_sha256} if source_sha256 else {}
    if not hashes:
        raise ValueError("provenance must contain source SHA-256 hashes")
    result = {}
    for name, digest in hashes.items():
        if not isinstance(name, str) or not name:
            raise ValueError("source hash names must be non-empty strings")
        result[name] = _hash_id(digest, f"source hash {name}")
    return dict(sorted(result.items()))


def _safe_source_origin(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    origin = {}
    for key in ("source", "line", "copybook_stack"):
        if key in value:
            item = value[key]
            if key == "copybook_stack" and isinstance(item, Sequence) and not isinstance(item, str):
                origin[key] = [str(part) for part in item[:32]]
            elif item is None or isinstance(item, (str, int)):
                origin[key] = item
    return origin or None


def build_analysis_events(
    audit_report: Mapping[str, Any],
    project_id: str,
    *,
    git_commit: Optional[str] = None,
    observed_at_utc: Optional[str] = None,
) -> list:
    """Create source-snapshot and analysis-result events from an audit report.

    Source text and statement text are deliberately excluded. The supplied
    project ID should be opaque and must not be a filesystem path.
    """
    if not isinstance(audit_report, Mapping):
        raise TypeError("audit_report must be a mapping")
    provenance = audit_report.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("audit report has no provenance object")
    sources = _source_hashes(provenance)
    copybooks = _copybook_entries(provenance)
    source_snapshot = _sha256({"source_hashes": sources, "copybooks": copybooks})
    analysis_fingerprint = _hash_id(
        provenance.get("analysis_fingerprint"), "analysis_fingerprint",
    )
    if git_commit is not None:
        if not isinstance(git_commit, str) or not re.fullmatch(r"[0-9a-fA-F]{7,64}", git_commit):
            raise ValueError("git_commit must be a 7–64 character hexadecimal commit ID")
        git_commit = git_commit.lower()

    source_payload = {
        "source_snapshot_id": source_snapshot,
        "source_hashes": sources,
        "copybooks": copybooks,
        "git_commit": git_commit,
    }
    source_event = _make_event(
        "source.snapshot", project_id, source_payload,
        observed_at_utc=observed_at_utc,
    )

    parser = audit_report.get("parser") or {}
    coverage = parser.get("coverage") or {}
    graph = audit_report.get("graph") or {}
    cycle = (audit_report.get("cycle_analysis") or {}).get("summary") or {}
    dependency_versions = provenance.get("dependency_versions") or {}
    analysis_options = provenance.get("analysis_options") or {}
    metrics = []
    for metric in audit_report.get("metrics", []):
        if not isinstance(metric, Mapping):
            continue
        value = metric.get("value")
        if isinstance(value, float) and not math.isfinite(value):
            value = None
        if value is None or isinstance(value, (str, int, float, bool)):
            metrics.append({
                "name": str(metric.get("name", "unknown")),
                "value": value,
                "value_status": metric.get("value_status", "unavailable"),
            })

    finding_counts: Dict[str, int] = {}
    anchors = []
    for finding in audit_report.get("findings", []):
        if not isinstance(finding, Mapping):
            continue
        kind = str(finding.get("kind", "unknown"))
        finding_counts[kind] = finding_counts.get(kind, 0) + 1
        if len(anchors) >= MAX_SOURCE_ANCHORS:
            continue
        source_node_ids = finding.get("source_node_ids") or []
        anchors.append({
            "kind": kind,
            "node_ids": [str(node_id) for node_id in source_node_ids[:16]],
            "line": finding.get("source_line"),
            "paragraph": finding.get("paragraph"),
            "source_origin": _safe_source_origin(finding.get("source_origin")),
        })

    graph_digests = {
        key: value for key, value in provenance.items()
        if key == "graph_digest" or key.startswith("graph_digest_")
    }
    if graph.get("graph_digest"):
        graph_digests.setdefault("graph_digest", graph["graph_digest"])
    analysis_payload = {
        "source_snapshot_id": source_snapshot,
        "analysis_snapshot_id": analysis_fingerprint,
        "audit_report_schema_version": audit_report.get("audit_report_schema_version"),
        "manifest_schema_version": provenance.get("manifest_schema_version"),
        "analyzer_version": provenance.get("rezonator_version", __version__),
        "parser": {
            "engine": parser.get("engine"),
            "coverage": {
                key: coverage.get(key)
                for key in (
                    "total_statements", "supported_statements",
                    "unsupported_statements", "coverage_ratio",
                ) if key in coverage
            },
        },
        "analysis_options": analysis_options,
        "dependency_versions": dependency_versions,
        "graph_digests": graph_digests,
        "graph_counts": {
            key: graph.get(key)
            for key in ("node_count", "edge_count", "parsed_node_count", "parsed_edge_count", "variable_count")
            if key in graph
        },
        "cycle_summary": {
            key: value for key, value in cycle.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        },
        "metrics": metrics,
        "finding_counts": dict(sorted(finding_counts.items())),
        "source_anchors": anchors,
        "source_anchors_truncated": sum(finding_counts.values()) > len(anchors),
    }
    analysis_event = _make_event(
        "analysis.completed", project_id, analysis_payload,
        observed_at_utc=observed_at_utc,
    )
    return [source_event, analysis_event]


def build_interpreter_run_event(
    execution_state: Any,
    project_id: str,
    *,
    run_id: str,
    source_snapshot_id: str,
    analysis_snapshot_id: str,
    graph_data: Optional[Mapping[str, Any]] = None,
    observed_at_utc: Optional[str] = None,
    max_trace_nodes: int = MAX_RUNTIME_TRACE_NODES,
) -> Dict[str, Any]:
    """Create a value-free summary of one explicitly requested local interpreter run."""
    if not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 256:
        raise ValueError("run_id must be a non-empty identifier no longer than 256 characters")
    source_snapshot_id = _hash_id(source_snapshot_id, "source_snapshot_id")
    analysis_snapshot_id = _hash_id(analysis_snapshot_id, "analysis_snapshot_id")
    if not isinstance(max_trace_nodes, int) or isinstance(max_trace_nodes, bool) or max_trace_nodes < 0:
        raise ValueError("max_trace_nodes must be a non-negative integer")

    trace = getattr(execution_state, "trace", None)
    if not isinstance(trace, list) or not all(isinstance(node_id, str) for node_id in trace):
        raise ValueError("execution_state.trace must be a list of node IDs")
    nodes_by_id = {}
    if graph_data is not None:
        nodes_by_id = {
            str(node.get("id")): node for node in graph_data.get("nodes", [])
            if isinstance(node, Mapping) and node.get("id") is not None
        }

    visited = []
    for node_id in trace[:max_trace_nodes]:
        node = nodes_by_id.get(node_id, {})
        location = node.get("location") or {}
        origin = node.get("source_origin") or {}
        line = origin.get("line", location.get("line", node.get("line")))
        visited.append({
            "node_id": node_id,
            "line": line,
            "paragraph": node.get("paragraph"),
            "source_origin": _safe_source_origin(origin),
        })

    timed_out = bool(getattr(execution_state, "timed_out", False))
    terminated = bool(getattr(execution_state, "terminated", False))
    steps = getattr(execution_state, "steps", len(trace))
    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 0:
        raise ValueError("execution_state.steps must be a non-negative integer")
    payload = {
        "run_id": run_id.strip(),
        "source_snapshot_id": source_snapshot_id,
        "analysis_snapshot_id": analysis_snapshot_id,
        "runtime": "CobolRuntime",
        "analyzer_version": __version__,
        "observation_scope": "bounded_interpreter_only",
        "outcome": "step_limit" if timed_out else "terminated" if terminated else "ended_without_terminal",
        "steps": steps,
        "trace_length": len(trace),
        "visited_nodes": visited,
        "visited_nodes_omitted": max(0, len(trace) - len(visited)),
        "raw_variable_values_included": False,
        "initial_overrides_included": False,
    }
    return _make_event(
        "runtime.interpreter_run", project_id, payload,
        observed_at_utc=observed_at_utc,
        epistemic_status="OBSERVED",
    )


def serialize_jsonl_events(events: Iterable[Mapping[str, Any]]) -> str:
    """Serialize validated events as a bounded UTF-8 JSON Lines string."""
    lines = []
    total_bytes = 0
    for event in events:
        if len(lines) >= MAX_EVENTS_PER_STREAM:
            raise ValueError(f"event stream exceeds {MAX_EVENTS_PER_STREAM} events")
        _validate_event(event)
        line = _canonical_json(dict(event)) + b"\n"
        total_bytes += len(line)
        if total_bytes > MAX_EVENT_STREAM_BYTES:
            raise ValueError(f"event stream exceeds {MAX_EVENT_STREAM_BYTES} bytes")
        lines.append(line.decode("utf-8"))
    return "".join(lines)


def parse_jsonl_events(stream: str) -> list:
    """Parse and validate a bounded JSONL event stream; reject blank/bad lines."""
    if not isinstance(stream, str):
        raise TypeError("JSONL event stream must be a string")
    encoded = stream.encode("utf-8")
    if len(encoded) > MAX_EVENT_STREAM_BYTES:
        raise ValueError(f"event stream exceeds {MAX_EVENT_STREAM_BYTES} bytes")
    if not stream:
        return []
    lines = stream.splitlines()
    if len(lines) > MAX_EVENTS_PER_STREAM:
        raise ValueError(f"event stream exceeds {MAX_EVENTS_PER_STREAM} events")
    events = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ValueError(f"blank JSONL record at line {line_number}")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL record at line {line_number}") from exc
        _validate_event(event)
        events.append(event)
    return events

