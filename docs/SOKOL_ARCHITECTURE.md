# Sokół: AI Observer and Project Memory

## Purpose and status

Sokół is the proposed second layer of Rezonator: a read-only observer that helps engineers interpret the deterministic core's results in the context of a particular codebase and its history. It is not currently implemented. The existing `LLMSynthesizer` only formats a local Markdown brief; it does not call a model, maintain project memory, watch Git, or observe native COBOL execution.

The architecture keeps the boundary explicit:

```text
source / Git ─┐
core analysis ├─> versioned evidence events ─> project memory ─> optional AI observer
controlled run┘                                                    │
                                                explanations / hypotheses / questions
                                                                    │
                                                        human review; no core mutation
```

The mathematical core remains authoritative for what it computed. Sokół may explain or correlate evidence, but it cannot change parser output, graph construction, metric values, runtime inputs, or release decisions.

## Evidence and epistemic labels

Every future observation or claim should carry its scope, source, and provenance. Use the three requested labels with narrow definitions:

- **`OBSERVED`** — directly captured from a named artifact or tool output: for example, a source hash, a Git diff, a graph emitted by a particular parser version, or a trace from a named controlled run. A graph fact means “present in this parsed model,” not “complete truth about the COBOL program.”
- **`INFERRED`** — a hypothesis proposed by Sokół. It must cite the evidence IDs it used, state uncertainty, and remain visibly unconfirmed.
- **`VERIFIED`** — a specific, scoped claim checked against an identified test/assertion and exact input snapshot, or explicitly attested by a named reviewer. Store `verification_basis` separately: human review is an approval/attestation, not automatically a formal proof of program behavior.

Suggested fact envelope (field names are a design proposal, not a current API):

```json
{
  "schema_version": "sokol.fact.v1",
  "fact_id": "fact:...",
  "status": "INFERRED",
  "claim": "WS-RISK-FLAG may guard the settlement retry path",
  "evidence_ids": ["event:...", "event:..."],
  "source_snapshot": "sha256:...",
  "git_commit": "...",
  "graph_snapshot": "sha256:...",
  "node_anchor": "...",
  "confidence": "unscored",
  "verification_basis": null,
  "created_at_utc": "...",
  "stale": false
}
```

Do not present model confidence as a calibrated probability unless calibration has been measured. A human's name, decision, and timestamp belong in review metadata and should be recorded only under the project's identity and retention policy.

## Versioning, node identity, and invalidation

The current provenance records source SHA-256, Rezonator version, seed, and UTC time; it does not yet record the Git commit, copybook set, parser options, dependency versions, or graph digest. Current statement IDs are based on paragraph, line, and statement type (for example `PARA:L42_STMT`), so they can shift or collide as code changes. They are not yet safe long-lived memory keys.

Before persistent project memory:

1. Define a complete analysis snapshot covering the source and resolved copybooks, parser/options, analyzer version, and graph serialization.
2. Introduce source anchors that retain copybook origin and can be remapped across revisions with an explicit match quality. A line-number or text-fingerprint match alone must not silently transfer a verified claim.
3. Bind every memory fact to the exact source and graph snapshots it describes.
4. On a new commit, mark affected or unmappable facts `STALE`; keep historical facts for audit but exclude them from current answers unless clearly labeled historical.
5. Never carry `VERIFIED` across snapshots without rerunning its scoped check or recording a new reviewer attestation.

An append-only JSONL event log is a reasonable first transport because it is inspectable and easy to replay. It should be versioned, bounded, project-scoped, and opt-in for persistence. Append-only application behavior is not tamper-proof storage; if the log is audit evidence, add a defined integrity mechanism (for example, chained event hashes or signed snapshots) and document its key-management limits. The storage location, retention, encryption, and deletion behavior must be explicit before implementation; a source repository should not silently become the memory database.

## Runtime traces and privacy boundary

The current `CobolRuntime` is a bounded interpreter for a supported subset, not a native COBOL runtime or production instrumentation agent. It records visited graph node IDs and final variable state; it does not currently emit a complete structured event stream of each mutation. Such traces are observations of this interpreter on a specific fixture and input, not proof of behavior on a mainframe.

Future tracing should run only in a controlled local/test harness and should emit structured, source-linked events with run ID, input snapshot, runtime version, step/node, event kind, and outcome. Default events should omit raw variable values. If a test needs values, use a field allowlist and synthetic data wherever possible. Unknown fields are excluded by default.

Deterministic masking can reduce exposure but cannot guarantee detection of all personal data or secrets. Therefore:

- do not send production data or traces to an AI provider;
- do not claim “PII-free” based only on regular expressions;
- redact or omit before persistence/export, not only before model submission;
- require explicit local policy and user approval before any remote model transfer;
- retain hashes and evidence references where they suffice instead of copying source or values.

COBOL source, comments, copybooks, logs, and runtime values are untrusted data. Instructions embedded in them must never be treated as trusted system or developer instructions by the model.

## Spectral change radar and project idioms

The spectral radar should report **metric deltas**, not semantic diagnoses. Compare only analyses with compatible parser versions, graph definitions, options, and coverage. A change in a Fiedler value or heat-trace signature can nominate a review target; it does not by itself mean a module was broken, logic disconnected, or a regression introduced. Reports should show the before/after values, graph/source evidence, unsupported-syntax counts, and the reason for the alert. Thresholds need evaluation on representative change histories before they trigger high-severity alerts.

Project idioms should first appear as `INFERRED` candidates with the number of examples, counterexamples, source anchors, and snapshot. A human may accept, edit, or reject them. Do not silently promote a frequent pattern to a rule or a `VERIFIED` fact.

## Context packets and model integration

The existing `ProgramSlicer` provides a forward graph slice and BFS ranking. It is not a source-mapped, bounded LLM packet, and it does not establish complete dependencies. A future packet should include only necessary source spans and evidence IDs, plus parser coverage, unresolved/opaque constructs, snapshot IDs, and an explicit truncation list. Budgets should be measured in tokens or bytes rather than promising a fixed number of source lines.

The first model adapter should be optional, read-only, and disabled by default. The deterministic API must work without model credentials or network access. The model receives a packet only after local policy checks; every generated claim must cite packet evidence or be marked `INFERRED`. Rezonator should validate evidence references and output schema, not pretend that schema validation proves semantic correctness. No autonomous edits, command execution, production access, or deployment authority are in scope.

“Near real time” means processing committed or explicitly watched local events asynchronously with bounded queues. It must not block or perturb core analysis and must expose dropped, delayed, or stale events rather than silently losing them.

## Delivery gates

1. **Evidence contract** — versioned event and fact schemas, reproducible snapshot IDs, parser coverage fields, and a clear distinction between core output and model claims.
2. **Core readiness** — unsupported syntax is surfaced; graph storage and analysis are sparse end to end and benchmarked on generated plus permissioned representative inputs.
3. **Controlled trace** — structured events from the bounded interpreter are labeled as interpreter observations, values are omitted by default, and redaction/allowlist behavior is independently reviewed.
4. **Memory prototype** — local opt-in storage, snapshot binding, stale invalidation, review metadata, and replay/deletion behavior are defined.
5. **Observer pilot** — model adapter is read-only and opt-in; evidence references are checked; usefulness, unsupported claims, data exposure, and latency are evaluated before continuous watching is enabled.

No delivery gate is passed by a persuasive demo alone. The current roadmap is the schedule and source of implementation status: [REZONATOR_ROADMAP.md](../REZONATOR_ROADMAP.md).
