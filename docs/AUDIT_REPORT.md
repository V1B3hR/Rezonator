# Rezonator audit report and provenance contract

Increment C adds a report over one deterministic Rezonator analysis snapshot. It is intended to help a reviewer inspect the parser's modeled scope, graph signals, assumptions, and source evidence. It is not a native COBOL execution record, proof of termination, behavioral-equivalence result, or safety certificate.

## HTTP interface

`POST /api/audit` accepts a JSON object with a required source string. An optional `copybooks` object maps copybook names to their complete source text. The default `format` is `json`; use `"format": "markdown"` for an auditable Markdown rendering.

```json
{
  "code": "IDENTIFICATION DIVISION. ...",
  "copybooks": {
    "ACCOUNT-FIELDS.CPY": "01 WS-ACCOUNT PIC 9(5)."
  },
  "format": "json"
}
```

JSON responses use `audit_report_schema_version: "1.0"`. The report contains:

- `provenance`: source and copybook hashes, effective analysis options, installed dependency versions, deterministic `analysis_fingerprint`, generation time, and graph digest;
- `graph`: digest algorithm and scope plus parsed/expanded graph counts;
- `parser`: parser engine selected, statement coverage, and the complete `unsupported_statements` list;
- `cycle_analysis`: current CFG findings and explicit assumptions;
- `metrics`: each metric's value, definition, and limitation;
- `findings`: unsupported statements, enumerated cycles, trapped SCCs, and heuristic cycle warnings, linked by snapshot-local node IDs;
- `source_references`: source line, paragraph, and `source_origin` (including copybook stack and replacements when present);
- `limitations`: scope caveats that must travel with the report.

The `/api/analyze`, `/api/compare`, and `/api/brief` requests also accept the optional `copybooks` mapping. Comparisons apply that same mapping to both source inputs and report separate graph digests for A and B. Copybook directories are deliberately not accepted over HTTP; callers provide explicit contents, avoiding hidden filesystem inputs.

## Provenance and digest definitions

The manifest hashes source text as UTF-8. Copybooks are normalized by trimming quote wrappers and uppercasing their names; each normalized name and UTF-8 content SHA-256 is included in the manifest. Duplicate names after normalization are rejected. The manifest also records the effective parser, graph, spectral, diffusion, and cycle-analysis settings, Rezonator version, Python/platform versions, and installed NumPy, SciPy, NetworkX, Torch, and optional `cobolparser` versions (an unavailable distribution is recorded as `null`).

`analysis_fingerprint` is SHA-256 over canonical UTF-8 JSON (sorted keys, compact separators) containing the schema version, source hashes, sorted copybook entries, effective options, dependency/runtime versions, Rezonator version, and graph digest(s). `timestamp_utc` is intentionally excluded, so repeated runs of the same declared inputs/configuration on the same dependency/runtime versions have the same fingerprint.

`graph_digest` is SHA-256 over canonical, sorted parsed graph topology: node IDs and node types; edge source, target, edge type, and weight; plus declared-variable nodes and their read/write dependency edges matching the comparator's `GraphField` expansion. Labels, source text, locations, and paragraph names are excluded from this topology digest; source/copybook hashes and source-origin references cover the input evidence. Consequently, the graph digest is not a digest of the full report or source artifact. The source and graph identifiers describe one analysis snapshot and can change after edits.

## Metric and interpretation boundaries

| Metric | Definition in this implementation | Boundary |
|---|---|---|
| `parser_coverage_ratio` | Supported modeled statement nodes divided by total modeled statement nodes; `1.0` if there are none. | Statement classification coverage, not dialect completeness or semantic fidelity. |
| `unsupported_statement_count` | Materialized statement nodes outside the modeled subset. | Does not count constructs the parser fails to recognize as statements at all. |
| `graph_node_count` / `graph_edge_count` | Parsed statement graph plus declared-variable nodes and generated read/write edges. | Edge count preserves parallel relations; sparse matrix assembly can sum edges with matching endpoints. |
| `fiedler_value` | Second-smallest eigenvalue reported for the symmetric Laplacian. | Structural property of this graph snapshot, not business correctness. |
| `diffusion_half_life` | `ln(2) / (alpha * Fiedler value)` under the solver's threshold rule. | Model-derived value, not measured execution time. An infinite value is represented by `value: null` and `value_status: "positive_infinity"`. |
| `enumerated_cycle_count` | Simple cycles returned by the bounded SCC-local enumerator. | Not necessarily the total cycle count; consult `cycle_budget_exhausted`. |
| `trapped_scc_count` | Non-trivial SCCs with no static CFG path to a recognized terminal. | No path in this parsed graph is not proof of runtime nontermination. |
| `reaches_terminal` | Whether the selected entry node has a CFG path to a recognized `STOP RUN`/`GOBACK` node. | A path's existence does not mean every execution reaches it. |

Cycle enumeration is bounded to 25 cycles per SCC and 100 total. Guard-invariance heuristics compare parsed branch reads with writes found inside each enumerated cycle. Data-flow findings come from the parser's modeled def-use/read/write graph, not runtime observation. Unsupported statements are explicit coverage gaps but their full COBOL semantics are not modeled.

Source node IDs are snapshot-local. A finding's `source_node_ids` refer to entries in `source_references`; an unsupported statement also includes its code and direct source origin. For a copybook statement, use the origin's `source`, `line`, and `copybook_stack`, not the expanded-source parser line alone.

## Change control

The schema version changes when the report contract changes incompatibly. New metrics should be added with their mathematical definition, implementation scope, and known limitations. Never interpret parser coverage, graph similarity, SCC reachability, or a deterministic report as a certification claim.
