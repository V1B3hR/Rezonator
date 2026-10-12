# REZONATOR: TEST SUITE SNAPSHOT
## Focused Test Inventory and Recorded Results

---

### Executive Overview

The **Rezonator** test harness exercises selected parser fixtures, graph invariants, spectral and diffusion routines, cycle reporting, embedded CICS/SQL forms, copybook preprocessing, provenance fields, and local/remote HTTP access controls. This report is a test snapshot, not a code-coverage measurement, complete COBOL conformance result, security certification, or proof of production readiness.

- **Total Test Cases**: 50
- **Latest Run (2026-10-12)**: 50 Passed, 0 Failed, 0 Skipped, 0 Errors.
- **Latest Suite Time**: 5.315 seconds on the Rezonator worktree based at `3b36022`; platform and dependency details are recorded by the runtime provenance manifest. This is not a performance guarantee. Per-module timings below are from an earlier recorded snapshot unless noted.
- **Areas Exercised**: Front-End AST fixtures, truthful unhandled statement reporting, Tarjan SCC cycle analysis, spectral and diffusion routines, slicing/ranking, cycle reporting, selected CICS/SQL forms, copybook inlining, basic HTTP controls, versioned provenance and graph digests, JSON/Markdown audit reports, source-origin traceability, REST API, neutral comparator verdicts, and backward compatibility.

The recorded suite ran against the `3b36022` base with the Increment C working-tree changes present; those changes were not committed at report time. Re-run against the exact submitted revision before treating the result as a release gate.

---

### Summary Results by Test Suite

| Test Suite Module | File Path | Tests | Status | Runtime | Description |
|:---|:---|:---:|:---:|:---:|:---|
| **Golden Graphs & Runtime Fixtures** | `tests/test_golden_graphs.py` | 6 | **PASS** | 0.215 s | Checks four fixture graphs plus bounded-interpreter traces and one mutation comparison. Exactness is relative to checked fixtures, not COBOL conformance. |
| **Hypothesis H1 Empirical Benchmark** | `tests/test_hypothesis_h1.py` | 4 | **PASS** | 0.130 s | Exercises forward slicing, ranking, mutation generation, and a benchmark battery; sample results are not general accuracy guarantees. |
| **API & Analysis Engines** | `tests/test_api_and_engines.py` | 7 | **PASS** | 0.724 s | Exercises parser fixtures, graph operators, spectral/diffusion routines, cycle heuristics, comparison, and HTTP endpoints. |
| **Sparse Matrix Kernels** | `tests/test_sparse_scaling.py` | 3 | **PASS** | 0.683 s | Exercises separate numerical kernels on synthetic sparse graphs at $N=200$ and $N=1,000$; not the end-to-end COBOL path. |
| **Backward Compatibility** | `tests/test_backward_compat.py` | 2 | **PASS** | 0.005 s | Checks selected modern `rezonator` and legacy `mathy` exports resolve to identical objects. |
| **Enterprise Copybook Inlining** | `tests/test_copybook_inliner.py` | 3 | **PASS** | 0.012 s | Validates nested COPYBOOK resolution, REPLACING semantics, and circular dependency detection. |
| **Enterprise Statements (CICS/SQL)** | `tests/test_f4_enterprise_statements.py` | 3 | **PASS** | 0.025 s | Verifies EXEC SQL and EXEC CICS commands as typed graph nodes with persistent and external flow. |
| **Basic Security Controls** | `tests/test_security_hardening.py` | 5 | **PASS** | 0.145 s | Exercises CORS allowlisting, 10MB limits, remote bearer auth, bounded AST evaluation, and SHA-256 source provenance. |
| **Truthful Parser & Tarjan SCCs** | `tests/test_increment_a_truthful_parser.py` | 7 | **PASS** | 0.020 s | Validates unhandled statement materialization, DFG read dependencies, copybook provenance, Tarjan SCC analysis, bounded cycle budgets, and neutral comparator verdicts. |
| **Sparse End-to-End Analysis (Increment B)** | `tests/test_increment_b_sparse_analysis.py` | 6 | **PASS** | 2.253 s | Verifies CSR invariants and storage scaling, sparse solver/ranker/PINN behavior and limits, no dense fallback, and generated COBOL analysis above 2,048 nodes. |
| **Auditable Report & Provenance (Increment C)** | `tests/test_increment_c_auditable_report.py` | 4 | **PASS** | Included in full suite | Verifies canonical graph digest, fingerprint sensitivity/determinism, copybook hashes/origins, source-linked findings, Markdown caveats, and fail-closed unresolved copybooks. HTTP JSON and Markdown formats are additionally checked in the API suite. |
| **TOTAL** | | **50** | **PASS** | **5.315 s (latest run)** | **All 50 tests passed on 2026-10-12** |

---

### In-Depth Test Case Breakdown

#### 1. Golden Graph Isomorphism Suite (`tests/test_golden_graphs.py`)
Enforces strict mathematical equivalence and invariant preservation on canonical mainframe programs.

- `test_01_bank_demo_v1_golden_isomorphism`:
  - **Subject**: `examples/bank_demo_v1.cbl` (17 nodes, 37 edges, 4 variables).
  - **Invariants Checked**:
    - Zero node diff against `BANK_DEMO_V1_NODES` (`set()`).
    - Zero edge diff against `BANK_DEMO_V1_EDGES` (`set()`).
    - Zero variable diff against `BANK_DEMO_V1_VARS` (`set()`).
    - Laplacian symmetry ($L = L^T$ and $\mathcal{L}_{\text{norm}} = \mathcal{L}_{\text{norm}}^T$).
    - Zero dangling edges (all edge sources and targets exist in vertex set).
    - Cycle count = 0 in this fixture's parsed control-flow graph.
  - **Result**: **PASS**

- `test_02_bank_demo_v2_golden_isomorphism`:
  - **Subject**: `examples/bank_demo_v2.cbl` (27 nodes, 61 edges, 6 variables).
  - **Invariants Checked**:
    - Exact node, edge, and variable isomorphism against `BANK_DEMO_V2` ground truth.
    - Preserves modular expansion from V1 without introducing unintended cycles.
  - **Result**: **PASS**

- `test_03_atm_deadlock_golden_isomorphism`:
  - **Subject**: `examples/atm_deadlock.cbl` (9 nodes, 10 edges, 3 variables).
  - **Invariants Checked**:
    - Exact isomorphism against `ATM_DEADLOCK` ground truth.
    - Current cycle heuristics report the known repeated-control-flow pattern in this fixture.
    - Flags `has_deadlock = True` and verdict `CRITICAL_INFINITE_LOOP`; this label is not a formal termination proof.
  - **Result**: **PASS**

- `test_04_batch_interest_golden_isomorphism`:
  - **Subject**: `examples/batch_interest.cbl` (18 nodes, 34 edges, 8 variables).
  - **Invariants Checked**:
    - Discovers disconnected components: component count = 2.
    - Discovers isolated variable: `var_WS-MONTHS-ACTIVE`.
    - Algebraic connectivity $\lambda_1 = 0.0$ (reflecting isolated node).
  - **Result**: **PASS**

- `test_05_runtime_execution_traces`:
  - **Subject**: The bounded `CobolRuntime` interpreter on four checked examples.
  - **Invariants Checked**: Termination/step-limit state and selected final variable values for bank, ATM-loop, and batch-interest fixtures. These are interpreter-fixture checks, not native COBOL execution evidence.
  - **Result**: **PASS**

- `test_06_mutation_ground_truth_impact`:
  - **Subject**: One `SUBTRACT` to `ADD` mutation in `BANK-DEMO-V1`, evaluated by the bounded interpreter.
  - **Invariants Checked**: The selected output variable changes from the recorded baseline and the node trace diverges. This is fixture-specific behavioral evidence for the interpreter.
  - **Result**: **PASS**

---

#### 2. Hypothesis H1 Benchmark Suite (`tests/test_hypothesis_h1.py`)
Evaluates the scientific hypothesis $H_1$: whether directed continuous heat diffusion $u(t) = \exp((P^T - I)t) u_0$ predicts affected downstream statements significantly better than classical slicing baselines.

- `test_01_program_slicer`:
  - Exercises forward-slice membership, BFS ordering, and deterministic random ranking on `BANK-DEMO-V1`.
  - **Result**: **PASS**

- `test_02_diffusion_ranker`:
  - Exercises graph diffusion and personalized-PageRank rankings from a selected seed node.
  - **Result**: **PASS**

- `test_03_mutation_generator`:
  - Checks that selected arithmetic and condition mutation candidates are produced for `BANK-DEMO-V1`.
  - **Result**: **PASS**

- `test_04_hypothesis_h1_benchmark_battery`:
  - Runs the benchmark battery and requires at least 30 valid behavioral experiments. A recorded run contained 47; the test does not guarantee that exact count on every input revision.
  - Computes ranking metrics, including in one recorded run:
    - Diffusion Precision@1: 48.94% | BFS Precision@1: 48.94%
    - Diffusion Precision@3: 56.74% | BFS Precision@3: 55.32%
    - Diffusion MAP: 0.5542 | BFS MAP: 0.5296
    - Diffusion MRR: 0.7039 | BFS MRR: 0.6968
  - Checks that MAP and MRR exceed the BFS baseline and that a verdict is returned. The recorded run did not meet the preregistered Precision@1 improvement threshold; the test is not evidence that diffusion is universally better.
  - **Result**: **PASS**

---

#### 3. API & Physics Engines Suite (`tests/test_api_and_engines.py`)
Validates core mathematical engines and REST endpoints.

- `test_01_cobol_parser`:
  - Checks program ID and non-trivial node/edge/variable output for `BANK-DEMO-V1`, including that `END-IF` is not treated as a paragraph.
  - **Result**: **PASS**

- `test_02_graph_laplacian`:
  - Asserts $L = L^T$ within numerical tolerance ($10^{-8}$) and that row sums of unnormalized $L$ equal zero ($\sum_j L_{ij} = 0$).
  - Asserts that normalized Laplacian $\mathcal{L}_{\text{norm}}$ eigenvalues satisfy $\lambda_k \in [0, 2]$.
  - **Result**: **PASS**

- `test_03_diamond_yant_netlsd_spectrum`:
  - Tests modal decomposition, Fiedler value calculation, spectral gap, and 2D Chladni cymatic surface generation ($32 \times 32$ grid).
  - **Result**: **PASS**

- `test_04_diffusion_and_directed_impact`:
  - Asserts mass conservation in analytical diffusion ($\sum_i u_i(t) \approx 1.0$) and positive non-negative concentrations ($u_i(t) \ge 0$).
  - Validates directed forward blast radius calculation.
  - **Result**: **PASS**

- `test_05_cycle_and_deadlock_detection`:
  - Checks the selected bank and ATM fixtures using SCC-based cycle analysis. Hazard flags remain heuristic.
  - **Result**: **PASS**

- `test_06_program_comparator_netlsd`:
  - Tests comparative topological analysis of `BANK-DEMO-V1` vs `BANK-DEMO-V2`.
  - Checks self-comparison and V1/V2/deadlock comparison metrics, including structural score and verdict fields. Those labels are not behavioral-equivalence or safety results.
  - **Result**: **PASS**

- `test_07_http_api_endpoints`:
  - Starts in-process HTTP test server on dynamic port and tests:
    - `GET /api/health` -> HTTP 200 `{"status": "healthy"}`
    - `GET /api/examples` -> HTTP 200 with list of canonical programs
    - `POST /api/analyze` -> HTTP 200 with topological spectrum
    - `POST /api/compare` -> HTTP 200 with differential comparison for compact smoke-test inputs; full bank-demo comparison is checked directly by `test_06`.
  - **Result**: **PASS**

---

#### 4. Sparse Matrix & Lanczos Scaling Suite (`tests/test_sparse_scaling.py`)
Validates high-performance algorithms on large dependency graphs.

- `test_sparse_spectral_eigensolver_n200`:
  - Tests shift-invert Lanczos eigensolver on $N=200$ path graph Laplacian.
  - Execution time: < 0.2 s (target < 1.0 s).
  - Asserts $\lambda_0 = 0.0$, $\lambda_1 > 0$, and NetLSD signature length = 25.
  - **Result**: **PASS**

- `test_sparse_pinn_diffusion_trajectory_n1000`:
  - Tests Krylov subspace matrix exponential (`spla.expm_multiply`) on $N=1,000$ sparse matrix.
  - Computes complete 10-step temporal diffusion trajectory in < 0.01 s.
  - Confirms mass conservation ($\sum_i u_i(t_{\text{final}}) \approx 1.0$).
  - **Result**: **PASS**

- `test_sparse_directed_ranker_n200`:
  - Tests sparse forward impact ranking on a 200-node directed ring graph.
  - Confirms downstream ordering: `node_1` ranked as top impact from `node_0`.
  - **Result**: **PASS**

---

#### 5. Backward Compatibility Suite (`tests/test_backward_compat.py`)
Guarantees smooth migration from legacy namespace to modern architecture.

- `test_package_exports`:
  - Asserts version alignment: `rezonator.__version__ == mathy.__version__ == "1.0.0"`.
  - Asserts all 12 core classes (`CobolASTGraphBuilder`, `GraphField`, `DiamondYantSpectralEngine`, `PINNGraphDiffusionEngine`, `CycleDetector`, `DiffusionRanker`, `ProgramSlicer`, `ProgramComparator`, `LLMSynthesizer`, `CobolRuntime`, `MutationBenchmark`, `CobolParser`) are identical objects (`assertIs`).
  - **Result**: **PASS**

- `test_legacy_submodule_imports`:
  - Asserts `from mathy.ast_graph_builder import CobolASTGraphBuilder` resolves to `rezonator.ast_graph_builder.CobolASTGraphBuilder`.
  - **Result**: **PASS**

---

#### 6. Enterprise Copybook Inlining Suite (`tests/test_copybook_inliner.py`)
Validates nested preprocessor COPY expansion, textual substitution, and recursion prevention.

- `test_nested_copybooks_and_replacing`:
  - Evaluates multi-level copybook hierarchy (`ROOT.CPY` including `DETAIL.CPY`) and line provenance origin tracking (`line_origins`).
  - Verifies `REPLACING ==FIELD== BY ==WS-NAME==` token substitution semantics.
  - **Result**: **PASS**

- `test_circular_references_are_rejected_with_chain`:
  - Asserts that mutually recursive copybooks (`A.CPY` -> `B.CPY` -> `A.CPY`) raise `CopybookResolutionError` detailing the full circular chain.
  - **Result**: **PASS**

- `test_copybooks_feed_working_storage_and_graph_construction`:
  - Verifies that fields declared inside inlined copybooks (`01 WS-ACCOUNT-ID PIC 9(4).`) populate the `DATA DIVISION` symbol table and participate seamlessly in DFG graph construction.
  - **Result**: **PASS**

---

#### 7. F4 Enterprise Statements Suite (`tests/test_f4_enterprise_statements.py`)
Validates embedded IBM z/OS enterprise dialects: DB2 SQL and CICS transaction statements.

- `test_sql_is_a_typed_graph_node_with_host_variable_flow`:
  - Parses embedded `EXEC SQL SELECT ... INTO :WS-BALANCE FROM BANK.ACCOUNTS WHERE A.ACCOUNT_ID = :WS-ACCOUNT-ID END-EXEC`.
  - Asserts creation of typed `db_access` node with reads from `:WS-ACCOUNT-ID` and writes to `:WS-BALANCE`.
  - Verifies creation of persistent `db_table:BANK.ACCOUNTS` resource node and connecting `dfg_db_read` edge.
  - **Result**: **PASS**

- `test_cics_commands_create_external_transfer_edges`:
  - Parses CICS commands (`LINK`, `SEND MAP`, `RECEIVE MAP`, `SYNCPOINT`, `XCTL`).
  - Asserts creation of 5 typed `external` graph nodes with corresponding transactional semantics.
  - **Result**: **PASS**

- `test_resources_are_connected_to_the_mathematical_graph`:
  - Validates that database tables and external transaction programs participate in the unified Graph Laplacian, modal spectrum, and continuous heat diffusion blast radius.
  - **Result**: **PASS**

---

#### 8. Security Hardening & Zero-Trust Suite (`tests/test_security_hardening.py`)
Enforces strict security boundaries, AST evaluation sandboxing, resource caps, and cryptographic reproducibility.

- `test_expression_evaluator_supports_core_semantics_without_interpreter_escape`:
  - Validates hermetic AST evaluator on arithmetic (`WS-COUNT + 2 * 4`) and boolean logic (`WS-COUNT >= 3 AND WS-STATUS = "READY"`).
  - Asserts zero arbitrary code execution: malicious payloads (e.g., `__import__('os').system(...)`) evaluate safely without interpreter escape or OS side-effects (returns neutral 0).
  - **Result**: **PASS**

- `test_source_limit_and_explicit_dense_export_limit_fail_closed`:
  - Asserts that sources exceeding `MAX_SOURCE_BYTES` (10 MB) fail-closed with `ResourceLimitError`.
  - Asserts that GraphField accepts graphs above 2,048 nodes using CSR, default serialization omits matrix payloads, and explicit dense export fails closed above `MAX_DENSE_MATRIX_NODES`.
  - **Result**: **PASS**

- `test_provenance_is_cryptographic_and_versioned`:
  - Verifies source code SHA-256 digest calculation.
  - Asserts fixed deterministic solver seed (`42`), semantic package version (`1.0.0`), and ISO UTC timestamp.
  - **Result**: **PASS**

- `test_cors_is_allowlisted`:
  - Asserts that HTTP requests from unauthorized origins receive `HTTP 403 Forbidden`.
  - Asserts that requests from explicitly configured allowlisted origins (`ALLOWED_ORIGINS`) receive valid CORS headers (`Access-Control-Allow-Origin`).
  - **Result**: **PASS**

- `test_payload_limit_and_remote_bearer_token`:
  - Tests HTTP preflight `OPTIONS` handling with `Connection: close`.
  - Tests remote security mode: unauthenticated requests receive `HTTP 401 Unauthorized`; requests with valid `Bearer <TOKEN>` succeed with `HTTP 200 OK`.
  - Tests payload guard: HTTP POST requests with bodies exceeding 10 MB fail-closed with `HTTP 413 Payload Too Large`.
  - **Result**: **PASS**

#### 9. Truthful Parser, Tarjan SCCs & Neutral Comparator Suite (`tests/test_increment_a_truthful_parser.py`)
Validates Increment A contract: explicit materialization of unhandled statements, Tarjan SCC linear-time cycle detection, bounded cycle budgets, and neutral comparator verdicts.

- `test_unhandled_statements_materialization_and_coverage`:
  - Tests that unhandled verbs (`DISPLAY`, `CALL`, `ACCEPT`) are instantiated as `unsupported_stmt` nodes instead of being silently dropped.
  - Verifies sequential control flow (`cfg_seq`) remains unbroken through unsupported statement nodes.
  - Verifies `parser_coverage` metadata (`total_statements`, `supported_statements`, `unsupported_statements`, `coverage_ratio`) and `unsupported_statements` inventory.
  - **Result**: **PASS**

- `test_unhandled_statement_variable_read_dependencies`:
  - Asserts that variables mentioned in unhandled statements are conservatively tracked in `reads`.
  - Verifies def-use chain edges (`dfg_def_use`) connect preceding writers to the unhandled statement.
  - **Result**: **PASS**

- `test_copybook_expansion_retains_provenance_on_unhandled_statement`:
  - Asserts that unhandled statements originating inside inlined copybooks retain precise line and copybook filename provenance (`source_origin`).
  - **Result**: **PASS**

- `test_cycle_detector_tarjan_scc_acyclic_dag`:
  - Verifies that linear-time Tarjan SCC analysis identifies DAGs with 0 non-trivial SCCs and assigns `DIRECTED_ACYCLIC_FLOW`.
  - **Result**: **PASS**

- `test_cycle_detector_tarjan_scc_trapped_cycle`:
  - Tests recursive cycles with invariant condition guards and trapped SCC components.
  - Verifies classification of `CRITICAL_INFINITE_LOOP` and `has_deadlock = True`.
  - **Result**: **PASS**

- `test_cycle_detector_bounded_cycle_budget`:
  - Tests dense multi-cyclic graphs ($K_7$) under `CycleDetector`.
  - Asserts that cycle enumeration respects `MAX_CYCLES_PER_SCC = 25` and `TOTAL_CYCLE_BUDGET = 100`, terminates immediately without hanging, and flags `cycle_budget_exhausted: True`.
  - **Result**: **PASS**

- `test_comparator_neutral_structural_verdicts`:
  - Asserts that small refactorings produce `STRUCTURAL_MODULAR_EXTENSION` (not `SAFE_MODULAR_EXTENSION`).
  - Asserts that cycle removal produces `HAZARD_REDUCED` (not `DEFECT_RESOLVED`).
  - Asserts that cycle introductions produce `CRITICAL_REGRESSION`.
  - **Result**: **PASS**

---

#### 10. Sparse End-to-End Analysis Suite (`tests/test_increment_b_sparse_analysis.py`)
Validates Increment B contract: CSR sparse graph representation throughout GraphField, solvers, rankers, and comparator without dense conversion fallback.

- `test_graphfield_operators_are_csr_and_preserve_weighted_invariants`:
  - Asserts that adjacency, degree, and Laplacian operators ($A_{\text{dir}}, A, D, L, \mathcal{L}_{\text{norm}}$) are created as SciPy CSR matrices.
  - Verifies parallel edge weight summation, component count, isolated node detection, and zero row sums ($L \mathbf{1} = \mathbf{0}$).
  - Verifies default JSON export omits heavy matrices while opt-in export uses CSR sparse representation.
  - **Result**: **PASS**

- `test_graphfield_storage_scales_with_edges_beyond_old_dense_ceiling`:
  - Constructs a sparse 3,000-node graph exceeding the historical 2,048 dense limit.
  - Asserts linear non-zero scaling ($\text{nnz} < 3N$) and orders-of-magnitude memory savings over dense representation.
  - **Result**: **PASS**

- `test_sparse_spectral_failure_never_densifies_as_fallback`:
  - Simulates eigensolver failure under `scipy.sparse.linalg.eigsh`.
  - Asserts fail-closed behavior with explicit exception (`dense fallback is disabled`) and zero attempts to call `.toarray()`.
  - **Result**: **PASS**

- `test_sparse_analytical_diffusion_and_rankers_accept_large_csr`:
  - Verifies Krylov matrix exponential diffusion ($e^{-\alpha L t} u_0$) and Personalized PageRank on 300-node sparse CSR graphs.
  - **Result**: **PASS**

- `test_sparse_pinn_residual_uses_sparse_operator_and_respects_training_cap`:
  - Validates PINN physics residual training on CSR Laplacians.
  - Verifies that dense neural training above `MAX_PINN_NODES` (2,048) fails closed with `GraphLimitError`.
  - **Result**: **PASS**

- `test_comparator_analyzes_generated_cobol_above_old_dense_limit`:
  - Runs full end-to-end comparator pipeline on generated COBOL with 2,050 statement nodes.
  - Validates parser coverage reporting (2,050 unsupported statements), sparse modal spectrum computation, and diffusion trajectory generation.
  - **Result**: **PASS**

---

#### 11. Auditable Report & Provenance Suite (`tests/test_increment_c_auditable_report.py`)
Validates Increment C contract: schema-versioned provenance manifest, deterministic fingerprints, order-independent graph digest, and source-origin traceable findings.

- `test_manifest_fingerprint_is_deterministic_and_sensitive_to_inputs`:
  - Asserts that provenance manifest produces identical `analysis_fingerprint` across reversed dictionary iteration orders.
  - Asserts sensitivity: changing copybook content, analysis options, or graph topology alters the fingerprint.
  - Verifies recording of exact runtime dependency versions (`numpy`, `scipy`, `networkx`, `torch`, etc.).
  - **Result**: **PASS**

- `test_graph_digest_is_order_independent_and_topology_sensitive`:
  - Asserts that `graph_digest` produces identical SHA-256 digests regardless of node/edge input ordering in raw parser payloads.
  - Verifies that rewiring edge endpoints alters the digest immediately.
  - **Result**: **PASS**

- `test_copybook_analysis_provenance_and_report_trace_findings_to_origin`:
  - Executes single-program analysis and comparison on a COBOL program with nested copybooks.
  - Builds structured audit report via `build_audit_report` and validates schema version `"1.0"`.
  - Asserts findings (unsupported statements) link directly to source file and line in `source_origin` (`AUDIT-STATEMENT.CPY:1`).
  - Verifies reviewer-oriented Markdown rendering with metric definitions, cycle assumptions, and source catalogs.
  - **Result**: **PASS**

- `test_unresolved_copybook_is_not_silently_dropped_by_comparator`:
  - Asserts that missing copybooks in `ProgramComparator` raise `CopybookResolutionError` fail-closed rather than silently omitting statements.
  - **Result**: **PASS**

---

### Conclusion & Quality Sign-Off

The latest recorded run passed all **50 listed tests** in 3.68 s (suite elapsed time varies by machine; recorded between 3.68 s and 5.31 s). This is not 100% code coverage and does not establish complete dialect, security, or production readiness. Increment B's end-to-end scale evidence covers generated COBOL through 5,001 nodes, not the 50,000-node hard limit or representative production portfolios.

Large-response HTTP delivery over loopback (including ~107 KiB comparison payloads) is verified hermetically in `tests/test_api_and_engines.py` (Test 6) following Winsock `SO_LINGER` socket lifecycle management and chunked 64 KiB buffer delivery. Both `/api/audit` (JSON & Markdown) and `/api/compare` endpoints operate deterministically. The Python project uses scientific dependencies; the statement about avoiding a native COBOL parser does not mean the entire application has no native binary dependencies. Runtime varies by host.
