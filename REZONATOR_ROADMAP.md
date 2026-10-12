# Rezonator Roadmap

## Code-grounded plan, updated 2026-10-10

This roadmap combines the long-range vision in the accompanying strategy note with a review of the repository as it exists today. It treats the current implementation as a research and audit-workbench prototype. Passing unit tests and mathematically defined graph metrics are useful evidence; they do not certify COBOL compatibility, functional equivalence, safety, or production readiness.

Rezonator's direction remains compelling: make legacy software structure inspectable as a graph, use graph and spectral methods to guide investigation, and let a future AI observer explain evidence while humans and independent checks retain decision authority. The fastest credible route is to make one end-to-end analysis trustworthy before expanding to entire portfolios or additional languages.

## 1. Current baseline: what the repository demonstrates

| Area | Present in code | Boundary that the roadmap must respect |
|---|---|---|
| COBOL ingestion | A deterministic, line-oriented Python parser in `rezonator/ast_graph_builder.py`; golden fixtures cover four small example programs. | It is a supported-subset parser, not a complete ANSI-85 or IBM Enterprise COBOL implementation. It recognizes selected verbs and embedded blocks; unsupported syntax can be missed. There is no broad production corpus or complete parser-coverage report yet. |
| Embedded CICS and DB2 SQL | Selected `EXEC CICS` and `EXEC SQL` forms become typed graph nodes and resource/data-flow edges. | Extraction is regex-based and tested on a few representative forms. It does not implement the full CICS command set, DB2 grammar, or precompiler semantics. |
| COPYBOOK | `rezonator/copybooks.py` expands nested copybooks, supports tested `REPLACING` forms, detects cycles, and tracks line origins. | This is a useful preprocessor foundation; production library search rules, dialect edge cases, and large copybook estates still need corpus validation. |
| Mathematical graph | `GraphField` builds adjacency and Laplacian operators; spectral and diffusion modules can also accept sparse matrices. | The end-to-end `GraphField` currently allocates dense NumPy matrices and rejects graphs over `MAX_DENSE_MATRIX_NODES = 2,048`. Sparse math primitives do not yet make the full parser-to-report path sparse. |
| Scale evidence | `tests/test_sparse_scaling.py` checks an eigensolver on a synthetic 200-node graph, diffusion on 1,000 nodes, and directed ranking on 200 nodes. `REZONATOR_BENCHMARKS.md` separately reports larger synthetic runs. | Treat larger timings as benchmark observations, not as a tested end-to-end capacity claim. The current dense graph builder is the operational ceiling for ordinary analysis. |
| Cycle analysis | `rezonator/cycle_detector.py` reports cycles and selected hazards from the CFG. | The implementation calls `networkx.simple_cycles`; it is not Tarjan SCC. A CFG cycle indicates a possible loop, not by itself guaranteed nontermination. Guard analysis is heuristic and cannot prove general program termination. |
| Program slicing | `ProgramSlicer` computes forward graph reachability and BFS rankings; `DiffusionRanker` ranks impact. | This is not yet a bounded, source-mapped LLM context slicer. The H1 benchmark's predeclared Precision@1 improvement criterion was not met, so diffusion should remain an optional ranking signal rather than a claimed accuracy upgrade. |
| AI interface | `LLMSynthesizer` formats analysis values into a deterministic Markdown evidence brief; the UI now describes that behavior without claiming a model call. | No model call, project memory, continuous observer, or code generation exists in this repository. A future Sokół must be a read-only consumer of versioned evidence. |
| Runtime observation | `CobolRuntime` interprets a bounded supported subset, records visited node IDs and final variable state. | It is not a native COBOL/mainframe runtime. It does not yet emit structured per-mutation events or apply a privacy-reviewed trace export policy. |
| Security and provenance | Local mode binds to loopback; the HTTP handler has payload limits, an Origin allowlist, and optional bearer authentication. Results carry source SHA-256, package version, seed metadata, and UTC time. | Remote mode is plain HTTP with a bearer token, so it needs TLS termination on a trusted boundary before network use. CORS is a browser policy, not authentication. Provenance does not yet cover copybook contents, parser options, dependency versions, or a digest of the result. |
| Rust and other languages | `Cargo.toml` and `src/main.rs` provide a Rust package scaffold. | The Rust entry point is a placeholder; graph algorithms and Python bindings are not implemented. There are no non-COBOL frontends or shared language-neutral IR yet. |

The current hard limits are centralized in `rezonator/limits.py`: 10 MiB source/payload, 50,000 graph nodes, 200,000 edges, 2,048 nodes for the dense `GraphField`, and 100,000 runtime steps. The smaller dense-matrix ceiling is the limiting value for the main analysis path.

### Phase status, stated conservatively

- **F0–F1 — mathematical and golden-graph foundations: implemented for the checked fixtures.** This establishes useful invariants on a small corpus, not general COBOL semantic correctness.
- **F2 — hermetic parser: prototype implemented.** Keep the pure-Python default, but describe it as a supported subset until corpus coverage and unsupported-syntax reporting are in place.
- **F3 — sparse solver primitives: implemented in parts.** Sparse algorithms exist, but sparse storage is not connected through the ordinary `GraphField` and comparator path.
- **F4 — enterprise constructs and basic hardening: partial implementation.** Copybook expansion and selected embedded statements exist; full dialect compatibility and deployment-grade remote security do not.
- **F5–F6 — portfolio analysis and decomposition: not implemented.** There is no cross-program CALL/JCL graph, Cheeger partitioner, bounded LLM slicer, or migration verifier today.

### Two-layer architecture: deterministic core and Sokół

The attached Sokół vision fits the project if its boundary is enforced: Layer 1 owns parsing, graph construction, metrics, and controlled traces; Layer 2 consumes evidence read-only and returns explanations or hypotheses. The current evidence brief was corrected in this pass so it no longer presents cycles as formal termination proofs or metrics as business semantics. There is still no AI model, watch service, memory store, JSONL event stream, or spectral regression notifier implemented.

The epistemic labels are adopted with scoped meanings: `OBSERVED` identifies a fact captured from a named artifact or Rezonator output (and says which parsed snapshot it describes); `INFERRED` is an unconfirmed AI hypothesis; `VERIFIED` is claim-specific and must name its test/assertion and exact snapshot or record an explicit reviewer attestation. Human approval is not silently promoted into a formal proof. The detailed evidence, memory, privacy, and delivery contract is in [Sokół Architecture](docs/SOKOL_ARCHITECTURE.md).

## 2. Accelerated delivery path

The sequence below is designed to reach a useful pre-migration audit pilot sooner by avoiding a large parser rewrite, Rust port, or autonomous translator as prerequisites. Estimates are planning ranges for a focused engineering push with access to representative, legally usable COBOL and copybook fixtures; they are not release commitments.

| Increment | Indicative effort | Deliverable and exit evidence |
|---|---:|---|
| **A. Truthful parser and cycle results** | 1–2 focused weeks | Publish a supported-syntax matrix; represent or report every unhandled statement instead of silently omitting it; retain source locations through copybook expansion; replace cycle enumeration with linear-time SCC analysis; report `cycle`, `possible loop`, `hazard under stated assumptions`, or `unknown` without claiming a general termination proof. Rename comparator verdicts such as `SAFE_MODULAR_EXTENSION` to neutral structural descriptions; a graph score is not a safety classification. Golden fixtures cover each supported control-flow construct. |
| **B. Sparse analysis end to end** | 2–4 focused weeks | Move `GraphField` to sparse CSR/array operators and keep the comparator path sparse; avoid dense matrix serialization by default. Preserve current golden graph and numerical invariants. Benchmark generated program graphs through parse → graph → spectrum/diffusion → result, with node/edge, time, and memory limits recorded. |
| **C. Auditable report and provenance** | 1–2 focused weeks, partly parallel after the result schema is stable | Emit a report that includes parser coverage and warnings, graph scope, copybook origins, cycle-analysis assumptions, metric definitions, and source references. Extend the provenance manifest to hash all analysis inputs and options. Keep each automated finding traceable to source and graph evidence. |
| **D. Bounded context-slice beta** | 1–2 focused weeks | Turn the existing static slicer into an exportable, source-mapped evidence packet under a configurable token/line budget. Clearly list omitted dependencies when the budget truncates the slice. Evaluate precision and recall against the existing mutation cases plus an independently reviewed fixture set; do not promise a fixed 150-line slice or call it mathematically complete. |

This focused 5–10 week estimate covers A–D only; it does not include implementation or evaluation of Sokół's persistent memory, runtime event stream, or model adapter. The current brief/UI wording correction is a documentation and presentation cleanup, not a completed AI integration.

Parser coverage work and corpus curation can proceed while the sparse graph path is being built, once the graph/result contract is fixed. The audit report and context-slice consumer can follow that contract. This gives early parallel progress without coupling each feature to a different graph representation.

### Near-term release gate: pre-migration audit pilot

The first meaningful external-facing milestone is a pilot that can analyze a bounded, documented COBOL subset and explain its own limits. Exit criteria:

1. Every parsed and unsupported construct has an explicit status and source location; no silent drop is treated as a complete graph.
2. The source-to-graph path runs sparsely at the declared pilot scale, with reproducible time and memory measurements.
3. Cycle results distinguish graph facts from semantic conclusions and do not label a mere cycle as a proof of deadlock.
4. A reviewer can trace each report finding to source lines, graph edges, and the analysis version/options.
5. Context slices remain within a caller-supplied budget and disclose truncation.
6. The pilot is evaluated on a representative, permissioned corpus, with false positives, false negatives, and unsupported syntax recorded.
7. The deterministic analysis brief has a direct regression check for provenance and scope caveats; API compatibility does not mislabel it as AI/model output.

### Sokół delivery sequence (after the evidence contract stabilizes)

1. **Versioned evidence events:** define JSONL or an equivalent versioned event envelope for source/Git snapshots, analysis results, and controlled runs. Include copybook resolution, parser options, graph digest, and analyzer version; current provenance is not yet complete enough for persistent memory.
2. **Core readiness and scale:** complete parser coverage reporting and sparse analysis end to end before treating graph output as a comprehensive view. CSR storage is necessary for sparse scale but does not itself establish 10,000–50,000-line throughput; record end-to-end time, peak memory, graph density, and unsupported syntax on specified inputs.
3. **Controlled runtime trace:** emit structured, source-linked events only from an explicit test harness. The current interpreter is subset-only; label traces as interpreter observations. Omit values by default and use field allowlists/synthetic data. Deterministic redaction is defense-in-depth, not a guarantee that all PII or secrets are removed.
4. **Versioned project memory:** add facts only after snapshot IDs and remappable source anchors are defined. Current paragraph/line/type node IDs can shift across edits. Bind each fact to source and graph snapshots, mark stale facts on change, and never carry verification to a new snapshot without rerunning the check or recording a new scoped attestation.
5. **Radar, idioms, and optional model:** first report compatible-metric deltas as review candidates, not claims of broken logic. Keep mined idioms as `INFERRED` until reviewed. Enable a read-only model adapter only after bounded context packets disclose truncation, source coverage, and data-transfer policy; it stays off by default and cannot mutate the core or run commands.

The spectral radar must not label a Fiedler-value drop as a business-logic failure: it is a metric change in a specific parsed graph. Compare like-for-like parser/configuration snapshots and show the affected source/graph evidence. Likewise, an interpreter trace is not automatically a trace of native COBOL execution.

## 3. Multi-program analysis and modernization guidance

### F5 — application portfolio graph (target horizon: 2027)

Build a cross-program dependency model incrementally, starting from an explicit project manifest rather than assuming that one repository contains the whole mainframe estate.

1. Resolve static COBOL `CALL`, CICS `LINK`/`XCTL`, program identifiers, and parameter bindings where available; preserve unresolved or dynamic calls as explicit unknown edges.
2. Add JCL job, step, `PGM`, and DD dataset relationships. Model conditional execution, procedures, overrides, and dataset identity only as their semantics are implemented and tested.
3. Join shared DB2 table and VSAM/file resources across programs. Distinguish observed names from proven read/write semantics; represent missing catalog information as unknown.
4. Produce an application-level dependency map and blast-radius report with source evidence and coverage counts.

**2027 outcome:** a credible pre-migration audit pilot for a bounded application portfolio, with copybook-aware source references, selected CICS/DB2 support, parser coverage, and reviewable context slices. A Topological Coupling Score (TCS) may be researched during this period, but it becomes a published metric only after its definition is stable and its relationship to expert assessments or observed migration effort has been evaluated on a held-out corpus.

### F6 — partition recommendations and migration evidence (target horizon: 2028)

1. Add candidate cuts using Fiedler-vector sweeps and conductance, then incorporate shared state, transaction boundaries, call traffic, and data ownership. A spectral cut is a structural suggestion; it does not by itself produce a valid service boundary or minimize real RPC cost.
2. Explain each candidate boundary, including crossing edges, shared resources, uncertainty, and the source statements that create the coupling. Keep an architect in the approval loop.
3. For translated code, compare observable behavior with differential tests, workload traces, and domain invariants. NetLSD similarity and absence of detected cycles are structural signals, not proof of functional equivalence.
4. Consider a Rust `rezonator-core` only after profiling identifies Python or sparse-kernel overhead as the bottleneck. First define a stable graph interchange format and benchmark the Python baseline. The proposed 10-million-node / sub-500-ms target remains a research hypothesis until measured on a specified workload and machine.

**2028 outcome:** ranked, explainable decomposition candidates and a migration-validation workflow for selected COBOL portfolios. Rezonator recommends and gathers evidence; it does not autonomously rewrite or certify production systems.

## 4. Longer-range direction (target horizon: 2031)

Add language frontends one at a time behind a versioned intermediate graph model. Start with one adjacent representation (for example, a compiler IR or a second language frontend) and require conformance fixtures for control flow, data dependencies, calls, and source mapping before claiming language independence.

The broad vision is reusable structural analysis for banking, aerospace, automotive, and medical software. Graph topology can help find coupling, reachability, and propagation paths; it cannot by itself establish safety compliance or prove the absence of harmful behavior. Any safety-critical use needs language-specific semantics, independent verification, domain hazard analysis, and the applicable certification process. The five-year ambition is therefore a research direction, not a promise of a universal safety gate or “compiler of compilers.”

## 5. Design rules for shortening the path without weakening evidence

- **Build one vertical slice at a time:** real source → parser diagnostics → graph → metric → source-linked report.
- **Prefer explicit unknowns to guessed semantics:** unsupported syntax and dynamic dependencies must lower a coverage measure, not disappear silently.
- **Keep the graph model sparse before scaling claims:** test the application path, not only isolated numerical kernels.
- **Separate findings from recommendations:** expose measured graph facts, assumptions, uncertainty, and human decisions distinctly.
- **Validate metrics before naming standards:** TCS and any “migration safety” score need empirical baselines and sensitivity analysis.
- **Use AI as an analyst:** AI may summarize evidence or propose a patch; deterministic checks and human review decide what is accepted.
- **Keep Sokół read-only:** stream versioned, minimized evidence to it asynchronously; source and trace contents are untrusted data, and any remote model transfer requires explicit policy and consent.
- **Delay expensive platform work until justified:** no full grammar bridge, Rust port, or multi-language engine until coverage gaps, profiling, and pilot feedback identify the need.

## 6. Documentation alignment notes

The current-facing README, web brief, math references, and roadmap have been aligned to the code observed in this review. Historical milestones, test inventories, and debugging notes intentionally preserve some original terminology under explicit snapshot/scope caveats. Continue to treat those records as historical rather than current guarantees, especially where they mention:

- references to Tarjan SCC, formal termination guarantees, 100% deadlock precision, and production certification;
- parser claims implying complete ANSI-85 / IBM dialect support;
- sparse scalability claims that do not distinguish synthetic solver benchmarks from the dense end-to-end graph path;
- stale resource-limit values (some documents say 1,000 dense nodes and 10,000 runtime steps; the current code says 2,048 and 100,000);
- “zero-trust” remote HTTP and AI/LLM descriptions that overstate what the current bearer-token server and deterministic brief template provide.

Those distinctions are prerequisites for an audit product that earns trust through inspectable evidence rather than confident labels.
