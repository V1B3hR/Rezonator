# Sokół Evidence Events v1

This document specifies the first opt-in transport envelope for Rezonator evidence. The implementation is a bounded in-memory JSONL serializer; it does **not** write a file, watch Git, expose an HTTP endpoint, retain project memory, or contact an AI service. Callers choose the opaque `project_id`, any Git commit identifier, when to export, and where (if anywhere) to store the returned text.

## Envelope

Each UTF-8 JSON Lines record is a JSON object with exactly these fields:

```json
{
  "schema_version": "sokol.event.v1",
  "event_id": "sha256:<digest>",
  "event_type": "analysis.completed",
  "project_id": "opaque-project-key",
  "observed_at_utc": "2026-10-12T12:00:00Z",
  "epistemic_status": "OBSERVED",
  "payload": {}
}
```

`event_id` is SHA-256 over canonical JSON of every envelope field except `event_id` (sorted keys, compact UTF-8 JSON, non-finite numbers rejected). `source_snapshot_id` is stable for the same source hashes and sorted copybook name/hash pairs. `analysis_snapshot_id` reuses the audit manifest's deterministic `analysis_fingerprint`, which binds the options, dependency versions, analyzer version, and graph digest. Timestamps are metadata and are not used as snapshot IDs.

The current event types are:

- `source.snapshot`: source hashes, copybook names/hashes, stable `source_snapshot_id`, and optional caller-supplied Git commit. It never contains source text.
- `analysis.completed`: source and analysis snapshot IDs, parser engine/coverage, effective options, dependency versions, graph digests/counts, bounded metric and cycle summaries, finding counts, and at most 250 source anchors. Statement text and source snippets are excluded.
- `runtime.interpreter_run`: an explicitly supplied `CobolRuntime` state summarized as a bounded sequence of node IDs and source anchors. It records step count, outcome, and truncation; variable values and initial overrides are excluded. Its `epistemic_status` is `OBSERVED`, with `observation_scope: bounded_interpreter_only`; it is not evidence from native COBOL execution.

Finding anchors retain only finding kind, up to 16 node IDs, line, paragraph, and whitelisted source-origin fields. Source anchors beyond the cap are represented by counts and `source_anchors_truncated`. Runtime trace exports keep at most 5,000 visited-node entries by default and report the number omitted.

## Bounds and validation

`serialize_jsonl_events` and `parse_jsonl_events` enforce a maximum of 1,024 events and 10 MiB per stream. Parsers reject blank/malformed records, unknown envelope fields, unsupported schema/event types, non-UTC timestamps, and checksum mismatches. Exported project identifiers must be opaque keys, not filesystem paths or customer names.

The digest detects accidental edits when compared with a trusted prior digest, but it is **not** a signature, hash chain, or tamper-proof audit log: anyone able to rewrite a record can recompute it. No persistent storage, retention, encryption, deletion, Git discovery, or remote transfer policy is established by this increment. Those choices remain explicit future work.

## Example

```python
from rezonator import build_analysis_events, serialize_jsonl_events
from rezonator.audit_report import build_audit_report

report = build_audit_report(analysis_result)
events = build_analysis_events(report, project_id="local-fixture")
jsonl = serialize_jsonl_events(events)  # caller decides whether/how to persist
```

The envelope records deterministic core observations only. AI-generated claims and project-memory facts are not event types in v1 and must not be represented as `OBSERVED`.
