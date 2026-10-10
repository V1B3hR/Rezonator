# REZONATOR: COMPREHENSIVE TEST SUITE REPORT
## Execution Summary, Invariant Verifications, and Ground-Truth Benchmarks

---

### Executive Overview

The **Rezonator** test harness provides automated, deterministic verification across the entire analytical stack. Every run validates syntactic parsing, AST node generation, Graph Laplacian symmetry, NetLSD spectral traces, forward impact diffusion trajectories, Tarjan Strongly Connected Components (SCC) cycle analysis, enterprise CICS/SQL statements, copybook preprocessing, cryptographic provenance, and zero-trust HTTP hardening.

- **Total Test Cases**: 33
- **Pass Rate**: 100% (33 Passed, 0 Failed, 0 Skipped, 0 Errors)
- **Suite Execution Time**: 1.94 seconds (all tests run hermetically in under 2 seconds)
- **Coverage**: Front-End AST, Spectral Eigensolvers, PINN Diffusion, Slicing & Ranking, Cycle/Deadlock Verification, Enterprise Statements (CICS / SQL), Copybook Inlining, Security Boundaries & Zero-Trust HTTP, Cryptographic Provenance, REST API, Backward Compatibility.

---

### Summary Results by Test Suite

| Test Suite Module | File Path | Tests | Status | Runtime | Description |
|:---|:---|:---:|:---:|:---:|:---|
| **Golden Graph Isomorphism** | `tests/test_golden_graphs.py` | 6 | **PASS** | 0.215 s | Verifies 100% exact isomorphism against ground truth for all 4 canonical COBOL programs. |
| **Hypothesis H1 Empirical Benchmark** | `tests/test_hypothesis_h1.py` | 4 | **PASS** | 0.130 s | Evaluates mutation generation, dynamic slicing, diffusion ranking, and falsification criteria. |
| **API & Physics Engines** | `tests/test_api_and_engines.py` | 7 | **PASS** | 0.724 s | Tests mathematical operators, Laplacians, Chladni cymatics, PINN diffusion, and HTTP endpoints. |
| **Sparse Matrix & Lanczos Scaling** | `tests/test_sparse_scaling.py` | 3 | **PASS** | 0.683 s | Validates shift-invert Lanczos solver and Krylov diffusion scaling on $N=200$ and $N=1,000$ nodes. |
| **Backward Compatibility** | `tests/test_backward_compat.py` | 2 | **PASS** | 0.005 s | Guarantees identical symbol exports between modern `rezonator` and legacy `mathy` imports. |
| **Enterprise Copybook Inlining** | `tests/test_copybook_inliner.py` | 3 | **PASS** | 0.012 s | Validates nested COPYBOOK resolution, REPLACING semantics, and circular dependency detection. |
| **Enterprise Statements (CICS/SQL)** | `tests/test_f4_enterprise_statements.py` | 3 | **PASS** | 0.025 s | Verifies EXEC SQL and EXEC CICS commands as typed graph nodes with persistent and external flow. |
| **Security Hardening & Zero-Trust** | `tests/test_security_hardening.py` | 5 | **PASS** | 0.145 s | Validates CORS allowlisting, 10MB limits, remote bearer auth, AST sandbox (no eval), and SHA-256 provenance. |
| **TOTAL** | | **33** | **PASS** | **1.939 s** | **Deterministic Pass across Entire Codebase** |

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
    - Tarjan cycle count = 0 (acyclic control flow).
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
    - Formally identifies exactly 1 non-trivial SCC cycle ($|SCC| \ge 2$).
    - Flags `has_deadlock = True` and verdict `CRITICAL_INFINITE_LOOP`.
  - **Result**: **PASS**

- `test_04_batch_interest_golden_isomorphism`:
  - **Subject**: `examples/batch_interest.cbl` (18 nodes, 34 edges, 8 variables).
  - **Invariants Checked**:
    - Discovers disconnected components: component count = 2.
    - Discovers isolated variable: `var_WS-MONTHS-ACTIVE`.
    - Algebraic connectivity $\lambda_1 = 0.0$ (reflecting isolated node).
  - **Result**: **PASS**

- `test_05_runtime_state_preservation`:
  - **Subject**: `rezonator/cobol_runtime.py` interpreter on `BANK-DEMO-V1`.
  - **Invariants Checked**:
    - Simulates execution of `01 WS-ACCOUNT-BALANCE = 5000.00` with withdrawal of `500.00`.
    - Asserts resulting balance is exactly `4500.00` and `WS-STATUS-CODE = "OKAY"`.
  - **Result**: **PASS**

- `test_06_deadlock_detection_accuracy`:
  - **Subject**: Comparison between terminating `BANK-DEMO-V1` vs non-terminating `ATM-DEADLOCK`.
  - **Invariants Checked**:
    - Asserts `BANK-DEMO-V1` has 0 cycles and `has_deadlock == False`.
    - Asserts `ATM-DEADLOCK` has 1 cycle and `has_deadlock == True`.
  - **Result**: **PASS**

---

#### 2. Hypothesis H1 Benchmark Suite (`tests/test_hypothesis_h1.py`)
Evaluates the scientific hypothesis $H_1$: whether directed continuous heat diffusion $u(t) = \exp((P^T - I)t) u_0$ predicts affected downstream statements significantly better than classical slicing baselines.

- `test_01_corpus_loading`:
  - Asserts that all 10 COBOL benchmark programs in `examples/` load and parse into valid ASTs.
  - **Result**: **PASS**

- `test_02_mutation_generation`:
  - Asserts that the mutation engine discovers valid statement mutation candidates across arithmetic (`SUBTRACT`, `ADD`, `COMPUTE`) and logic (`IF`, `MOVE`).
  - Generates 68 mutations total.
  - **Result**: **PASS**

- `test_03_forward_slicing_and_ranking`:
  - Validates `ProgramSlicer` forward reachability and compares rank order against `DiffusionRanker` and BFS hop distance.
  - **Result**: **PASS**

- `test_04_full_benchmark_execution`:
  - Executes all 47 behavioral ground-truth experiments and computes statistical ranking metrics:
    - Diffusion Precision@1: 48.94% | BFS Precision@1: 48.94%
    - Diffusion Precision@3: 56.74% | BFS Precision@3: 55.32%
    - Diffusion MAP: 0.5542 | BFS MAP: 0.5296
    - Diffusion MRR: 0.7039 | BFS MRR: 0.6968
  - Verifies that the falsification decision matches the pre-set scientific criterion ($\Delta \ge 10$ percentage points).
  - **Result**: **PASS**

---

#### 3. API & Physics Engines Suite (`tests/test_api_and_engines.py`)
Validates core mathematical engines and REST endpoints.

- `test_01_graph_field_laplacian_symmetry`:
  - Asserts $L = L^T$ within numerical tolerance ($10^{-8}$) and that row sums of unnormalized $L$ equal zero ($\sum_j L_{ij} = 0$).
  - Asserts that normalized Laplacian $\mathcal{L}_{\text{norm}}$ eigenvalues satisfy $\lambda_k \in [0, 2]$.
  - **Result**: **PASS**

- `test_02_spectral_engine_modes`:
  - Tests modal decomposition, Fiedler value calculation, spectral gap, and 2D Chladni cymatic surface generation ($32 \times 32$ grid).
  - **Result**: **PASS**

- `test_03_pinn_diffusion_stability`:
  - Asserts mass conservation in analytical diffusion ($\sum_i u_i(t) \approx 1.0$) and positive non-negative concentrations ($u_i(t) \ge 0$).
  - Validates directed forward blast radius calculation.
  - **Result**: **PASS**

- `test_04_cycle_detector_tarjan`:
  - Validates Tarjan's Strongly Connected Components algorithm on synthetic DAGs and cyclic graphs.
  - **Result**: **PASS**

- `test_05_program_comparator_metrics`:
  - Tests comparative topological analysis of `BANK-DEMO-V1` vs `BANK-DEMO-V2`.
  - Asserts NetLSD distance $\approx 0.055$, Refactoring Fidelity Score $\approx 86.3/100$, and verdict `SAFE_MODULAR_EXTENSION`.
  - **Result**: **PASS**

- `test_06_llm_synthesizer_brief`:
  - Asserts that `LLMSynthesizer` produces structured Markdown briefs containing vertices, spectral gaps, blast radii, and formal deadlock guarantees.
  - **Result**: **PASS**

- `test_07_http_api_endpoints`:
  - Starts in-process HTTP test server on dynamic port and tests:
    - `GET /api/health` -> HTTP 200 `{"status": "healthy"}`
    - `GET /api/examples` -> HTTP 200 with list of canonical programs
    - `POST /api/analyze` -> HTTP 200 with topological spectrum
    - `POST /api/compare` -> HTTP 200 with differential comparison
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

- `test_source_and_dense_graph_limits_fail_closed`:
  - Asserts that sources exceeding `MAX_SOURCE_BYTES` (10 MB) fail-closed with `ResourceLimitError`.
  - Asserts that graph structures exceeding `MAX_DENSE_MATRIX_NODES` (1,000 nodes for dense representations) fail-closed with `GraphLimitError`, requiring sparse Lanczos solvers.
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

---

### Conclusion & Quality Sign-Off

The Rezonator test suite provides **100% green coverage** over all critical theoretical, enterprise dialect, and security components across **33 deterministic tests**. The suite is fully self-contained, hermetic, requires zero external binary `.pyd` dependencies, and executes in ~1.94 seconds on Windows, Linux, and macOS.
