# Rezonator Bounded Context Slice Specification (Increment D)

Increment D turns the static program slicer into an exportable, source-mapped evidence packet under a configurable line and token budget. It is intended for code intelligence, architectural investigation, and LLM context extraction.

Bounded context slices do not promise a fixed 150-line window, and they do not claim mathematical completeness or formal semantic preservation. They are static graph-reachability extractions with explicit disclosure of omitted dependencies when budgets truncate the slice.

## HTTP interface

`POST /api/slice` accepts a JSON object with a required `code` parameter. A seed must be identified via `seed_node` (node ID), `seed_line` (1-indexed source line number), or `seed_variable` (COBOL identifier).

```json
{
  "code": "IDENTIFICATION DIVISION. ...",
  "seed_line": 23,
  "direction": "forward",
  "max_lines": 50,
  "max_tokens": 1000,
  "max_nodes": null,
  "ranking_strategy": "bfs",
  "copybooks": {
    "ACCOUNT-FIELDS.CPY": "01 WS-ACCOUNT PIC 9(5)."
  },
  "format": "json"
}
```

Optional parameters:
- `direction`: `"forward"` (downstream impact), `"backward"` (upstream influencing causes), or `"bidirectional"` / `"both"` (full causal neighborhood). Default is `"forward"`.
- `max_lines`: Maximum lines permitted in the extracted slice (default: 50).
- `max_tokens`: Estimated token budget (default: 1000, approximated via `\w+|[^\w\s]`).
- `max_nodes`: Hard ceiling on the count of statement nodes included.
- `ranking_strategy`: Priority ordering for candidate inclusion when budget is restricted (`"bfs"` hop distance, `"diffusion"` continuous heat propagation, or `"random"`). Default is `"bfs"`.
- `copybooks`: Mapping of copybook filenames to string source text.
- `format`: `"json"` (default) or `"markdown"`.

## Packet Schema 1.0

JSON responses use `slice_schema_version: "1.0"` with the following structure:

- `program_id`: Identifies the analyzed program.
- `seed`: Resolved seed metadata (`node_id`, `line`, `code`, `paragraph`, `direction`).
- `budget`: Declarations of `max_lines`, `max_tokens`, `max_nodes`, and `ranking_strategy`.
- `slice_scope`:
  - `total_slice_nodes`: Total statement nodes in the unconstrained reachability slice.
  - `included_nodes_count`: Count of statement nodes successfully included within budget.
  - `omitted_nodes_count`: Count of statement nodes omitted due to budget truncation.
  - `is_truncated`: Boolean flag (`True` if any dependencies had to be omitted).
  - `truncation_reasons`: List of exceeded budget criteria (`"max_lines_exceeded"`, `"max_tokens_exceeded"`, `"max_nodes_exceeded"`).
  - `estimated_tokens_used`: Approximate token count of included statements.
  - `estimated_lines_used`: Line count of included statements.
- `included_statements`: List of included nodes sorted by natural source line order, retaining:
  - `node_id`, `code`, `node_type`, `paragraph`, `line`;
  - `source_origin`: Inlined copybook provenance (`source`, `line`, `copybook_stack`, `replacements`);
  - `reads` and `writes`: Variable data dependencies;
  - `hop_distance`: Shortest BFS distance from the seed node;
  - `relevance_rank`: Rank position under the chosen ranking strategy.
- `omitted_dependencies`: Complete inventory of omitted statements with node ID, code, line, paragraph, hop distance, and omission reason.
- `reconstructed_snippet`: Reconstructed COBOL code snippet formatted with line numbers and explicit `*> [TRUNCATED DEPENDENCIES]` marker block when truncated.
- `limitations`: Scope caveats that must travel with the slice packet.

## Precision and Recall Evaluation

The `ContextSliceEvaluator` measures precision and recall against behavioral ground truth $G$ established by `MutationBenchmark`:
$$\text{Precision} = \frac{|S \cap G|}{|S|}, \quad \text{Recall} = \frac{|S \cap G|}{|G|}$$

Evaluated on mutation cases across canonical fixtures (`bank_demo_v1.cbl`, `bank_demo_v2.cbl`):
- Unconstrained forward slices achieve high recall ($\ge 85\text{–}100\%$) across tested mutations.
- Under constrained budgets (e.g., $N=3$ or $N=5$), precision increases at the expense of recall, making ranking strategy critical.
- Omission disclosure ensures consumers are informed of excluded dependencies.

## Epistemic Boundaries and Limitations

1. **No Mathematical Completeness Guarantee**: A static PDG slice does not guarantee that all runtime behaviors are captured, especially in the presence of unmodeled COBOL constructs, dynamic `CALL` identifiers, or external CICS/database state.
2. **No Fixed Window Guarantee**: Slices expand dynamically along causal dependencies; lines are not constrained to an arbitrary 150-line contiguous block.
3. **Truncation Visibility**: AI models and human reviewers must inspect `omitted_dependencies` when `is_truncated` is `True` to prevent false confidence in truncated evidence.
