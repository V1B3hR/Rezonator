# ⚡ REZONATOR (Błyskawica Spectral Code Intelligence)
### Spectral Graph Analysis & Static Code Intelligence for Legacy Enterprise Systems

[![License: Rezonator Commercial](https://img.shields.io/badge/License-Source--Available%20%26%20Commercial-red.svg)](REZONATOR_LICENSE.md)
[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Błyskawica](https://img.shields.io/badge/Powered%20by-B%C5%82yskawica%20SPARKLE%20V10-cyan.svg)](https://github.com/V1B3hR/Blyskawica)
[![GitHub Repo](https://img.shields.io/badge/GitHub-V1B3hR%2FRezonator-blue.svg)](https://github.com/V1B3hR/Rezonator)
[![Focused Test Inventory](https://img.shields.io/badge/focused%20tests-62%20listed-blue.svg)]()

> *"Rezonator maps selected COBOL constructs into a finite program graph, making structural relationships easier to inspect."*

---

## 🌌 Context & Problem Statement

Long-lived COBOL systems can contain non-local control flow, shared `WORKING-STORAGE`, and dependencies spread across paragraphs and copybooks. Reconstructing those relationships is difficult; a graph view can help navigate them, provided parser coverage and uncertainty are visible.

Rezonator is a research-oriented static-analysis prototype. Its line-oriented parser recognizes a supported subset of COBOL, then computes graph and spectral metrics, diffusion rankings, and heuristic cycle signals. It does not model all COBOL semantics or prove program behavior.

The ordinary source-to-result path uses sparse CSR graph operators. The declared graph-input ceiling is 50,000 nodes and 200,000 edges; this is a resource limit, not a throughput guarantee:

```
COBOL source
    │
    ▼
[Supported-subset, line-oriented parser]
    │  unsupported syntax may be missed
    ▼
[Parsed statements and source relationships]
    ├──> CFG (control-flow edges)
    └──> DFG (selected data-flow edges)
             │
             ▼
[Sparse CSR GraphField: adjacency and Laplacians]
             │
             ├──> Spectral graph metrics
             ├──> Diffusion-based impact rankings
             └──> Cycle enumeration and heuristic hazard signals
                         │
                         ▼
                 [API / Web Studio results]
```

---

## 📚 Strategic Architecture & Documentation

Rezonator includes project documentation for architecture, experiments, implementation history, and the current roadmap:

| Strategic Document | File Location | Key Contents |
|:---|:---|:---|
| **License & Commercial Terms** | [`REZONATOR_LICENSE.md`](file:///c:/Projekty/Rezonator/REZONATOR_LICENSE.md) | Source-available & commercial licensing terms (UK jurisdiction), enterprise bank restrictions, and public healthcare / NHS humanitarian waiver. |
| **Debugging & Defect Report** | [`REZONATOR_DEBUGGING_REPORT.md`](file:///c:/Projekty/Rezonator/REZONATOR_DEBUGGING_REPORT.md) | Historical technical audit and root-cause notes for reported defects; not an independent proof or current certification. |
| **Test Suite Report** | [`REZONATOR_TEST_SUITE_REPORT.md`](file:///c:/Projekty/Rezonator/REZONATOR_TEST_SUITE_REPORT.md) | Snapshot of 75 focused unit and integration tests; not a statement of code coverage or certification. |
| **Audit Report & Provenance** | [`docs/AUDIT_REPORT.md`](file:///c:/Projekty/Rezonator/docs/AUDIT_REPORT.md) | Contract for auditable JSON/Markdown reports, SHA-256 graph digest, deterministic analysis fingerprint, and source anchors (Increment C). |
| **Context Slice Specification** | [`docs/CONTEXT_SLICE_SPEC.md`](file:///c:/Projekty/Rezonator/docs/CONTEXT_SLICE_SPEC.md) | Contract for bounded context slices under line/token budgets with explicit disclosure of omitted dependencies (Increment D). |
| **Sokół Evidence Events** | [`docs/SOKOL_EVIDENCE_EVENTS.md`](file:///c:/Projekty/Rezonator/docs/SOKOL_EVIDENCE_EVENTS.md) | Versioned, bounded JSONL export contract for source snapshots, deterministic analyses, and value-free interpreter summaries; no persistence or AI transfer. |
| **Sokół Project Memory** | [`docs/SOKOL_PROJECT_MEMORY.md`](file:///c:/Projekty/Rezonator/docs/SOKOL_PROJECT_MEMORY.md) | Specification of `sokol.fact.v1`, immutable content-addressed fact envelopes (`fact:sha256:...`), structural node anchors, and staleness invalidation on edit. |
| **Corpus Evaluation Report** | [`docs/CORPUS_EVALUATION_REPORT.md`](file:///c:/Projekty/Rezonator/docs/CORPUS_EVALUATION_REPORT.md) | Empirical evaluation of 6 representative enterprise COBOL programs (339 LOC, 88.24% coverage, copybooks, CICS/DB2, cycle analysis, Sokół event validation). |
| **Performance Benchmarks** | [`REZONATOR_BENCHMARKS.md`](file:///c:/Projekty/Rezonator/REZONATOR_BENCHMARKS.md) | Recorded parser and synthetic sparse-kernel measurements plus the Hypothesis $H_1$ experiment. See the roadmap for end-to-end scaling limits. |
| **Verification & Validation Notes** | [`REZONATOR_VERIFICATION_AND_VALIDATION.md`](file:///c:/Projekty/Rezonator/REZONATOR_VERIFICATION_AND_VALIDATION.md) | Project checks inspired by V&V practices; not an IEEE/ISO conformity assessment or independent certification. |
| **Strategic Roadmap** | [`REZONATOR_ROADMAP.md`](file:///c:/Projekty/Rezonator/REZONATOR_ROADMAP.md) | Code-grounded baseline, delivery gates, and 2027/2028/2031 strategic horizons. |
| **Sokół Architecture** | [`docs/SOKOL_ARCHITECTURE.md`](file:///c:/Projekty/Rezonator/docs/SOKOL_ARCHITECTURE.md) | Read-only AI observer design, evidence labels, memory, controlled traces, and privacy gates; event export is implemented, while persistent memory and model integration are not. |
| **Development Milestones** | [`REZONATOR_DEVELOPMENT_MILESTONES.md`](file:///c:/Projekty/Rezonator/REZONATOR_DEVELOPMENT_MILESTONES.md) | Historical implementation notes; read alongside the current code-grounded roadmap. |
| **Mathematical Foundations** | [`docs/REZONATOR_MATHEMATICAL_FOUNDATIONS.md`](file:///c:/Projekty/Rezonator/docs/REZONATOR_MATHEMATICAL_FOUNDATIONS.md) | Mathematical reference for graph operators and spectral methods, with explicit implementation-scope caveats. |

---

## 🔬 Core Physics & Mathematical Solvers

### 1. 💎 Diamond Yant Modal Spectral Engine
- Computes graph modes with dense eigensolvers for small inputs and sparse shift-invert methods for larger sparse inputs:
  $$L v_k = \lambda_k v_k, \quad 0 = \lambda_0 \le \lambda_1 \le \dots \le \lambda_{N-1}$$
- **Fiedler Value ($\lambda_1$)**: A structural connectivity metric for the modeled graph. A zero value warrants checking component and isolated-node counts; it does not prove that code is unreachable.
- **Fiedler Vector ($v_1$)**: a mathematical input for future partition analysis; the application does not yet produce or validate service boundaries.
- **NetLSD Multi-Scale Heat Trace Signature**:
  $$\Phi(t) = \text{Tr}\left(\exp(-t \mathcal{L}_{\text{norm}})\right) = \sum_{k} \exp(-t \lambda_k)$$
  Provides graph-size invariant topological distance across 25 log time scales $t \in [10^{-2}, 10^2]$.
- **Sparse Shift-Invert Lanczos**:
  Uses a negative spectral shift with `scipy.sparse.linalg.eigsh`. The benchmark report records a speedup against a historical dense baseline; results depend on the graph, hardware, and comparison method.

### 2. 🌡️ Graph Heat Diffusion Engine
- Computes graph diffusion over the modeled adjacency/Laplacian operators; this is not a source-level taint proof:
  - **Undirected Structural Dispersion**: Continuous heat diffusion on the symmetric Laplacian $L$ propagates bidirectionally across topological neighbors:
    $$\frac{\partial u}{\partial t} = -\alpha L u \implies u(t) = \exp(-\alpha L t) u_0$$
    Injects an impulse into any statement or variable (e.g. `WS-ACCOUNT-BALANCE`) to observe structural connectivity and modal equilibration. Total mass $\sum u_i(t) = \sum u_{0, i}$ is strictly conserved; the relaxation half-life $\tau_{1/2} = \ln(2)/(\alpha \lambda_{\min > 0})$ captures the decay rate of the slowest non-trivial eigenmode toward component-wise steady state.
  - **Directed Forward Blast Radius**: Forward impact propagation along directed CFG and DFG edges is governed strictly by the continuous-time Markov generator $Q = P^T - I$ (with absorbing sink states):
    $$u(t) = \exp((P^T - I)t) u_0$$
    Total probability mass is conserved ($\sum u_i(t) = 1.0$). Structural reachability is exact via graph traversal, while continuous diffusion mass ranks downstream impact and supports degree normalization to reduce in-degree hub bias.
- The ordinary `GraphField` and comparator path use CSR operators. A generated COBOL benchmark exercises the full analyzer at 2,050 and 5,001 graph nodes; see [`REZONATOR_BENCHMARKS.md`](REZONATOR_BENCHMARKS.md). These are bounded synthetic observations, not production-corpus or 50,000-node capacity claims.

### 3. Cycle and Control-Flow Analysis
- Enumerates control-flow cycles with NetworkX and reports selected trapped-cycle and unmodified-guard hazards.
- A cycle is evidence of a possible repeated execution path; it does not, by itself, prove nontermination. The current analysis does not formally prove general COBOL termination.
- The canonical `ATM-DEADLOCK` fixture is detected by current heuristics. Results should be reviewed as analysis signals with stated assumptions.

---

## 🚀 Quickstart

### 1. Run the Empirical Verification Experiment (V1 vs V2)
```bash
python verify_experiment.py
```

### 2. Launch the Interactive Web Studio
```bash
# Default: local diagnostic mode bound to 127.0.0.1
python main.py --serve --port 8080

# Remote mode: bearer token over HTTP; deploy behind a trusted TLS boundary
python main.py --serve --remote --token YOUR_SECURE_TOKEN --port 8080
```
Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)** in any modern browser to access:
- **Interactive Graph Topology Canvas (CFG + DFG)** with dynamic heat glowing.
- **Diamond Yant 2D Chladni Cymatics Oscilloscope** running 60 FPS standing wave simulations.
- **PINN Heat Diffusion Timeline Scrubber** with variable impulse injection.
- **Control-flow cycle and hazard summary** based on the current static heuristics.
- **Side-by-Side Differential Anomaly Scorecard** (V1 vs V2).
- **Deterministic Markdown analysis brief**; the current implementation does not call an LLM.

### 3. Compare Custom COBOL Files
```bash
python main.py --compare examples/bank_demo_v1.cbl examples/bank_demo_v2.cbl
```

### 4. Run Automated Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py"
```
*(The 62 focused tests exercise golden graphs, runtime examples, mutation experiments, selected numerical invariants, cycle analysis, sparse kernels, copybook expansion, selected CICS/SQL forms, HTTP access controls, auditable provenance fields, JSON/Markdown reports, bounded context slices with line/token budgets and omission disclosures, versioned Sokół event envelopes, and compatibility shims. They are not exhaustive COBOL conformance or production certification.)*

### 5. Run the Full Benchmark Suite
```bash
python REZONATOR_run_benchmarks.py
```

---

## 🔒 Local API Safeguards

Rezonator currently provides basic local API safeguards. They are not a zero-trust architecture or a security certification:

1. **Local-by-Default Binding**: Binds strictly to loopback interface `127.0.0.1`. Remote binding (`--remote`) requires an explicit secret token (`--token <TOKEN>`). Unauthenticated requests fail closed with `HTTP 401 Unauthorized`.
2. **Request/response isolation**: Uses `HTTP/1.0` and `Connection: close` for a simple connection lifecycle. Winsock `SO_LINGER` and chunked stream delivery prevent connection resets on large responses.
3. **Payload & Resource Limits**:
   - `MAX_PAYLOAD_BYTES = 10 MB`: Requests exceeding 10 MB are rejected immediately with `HTTP 413 Payload Too Large`.
   - `MAX_SOURCE_BYTES = 10 MB`: Source files exceeding 10 MB raise `ResourceLimitError`.
   - `MAX_GRAPH_NODES = 50,000` and `MAX_GRAPH_EDGES = 200,000`: hard input graph budgets; actual runtime and result size depend on graph structure.
   - `MAX_DENSE_MATRIX_NODES = 2,048`: applies only to explicit legacy dense export via `GraphField.to_dict(..., matrix_format="dense")`; normal operators and default serialization do not materialize dense matrices.
   - `MAX_PINN_NODES = 2,048`: caps experimental PINN training, whose neural output is dense; use the sparse analytical solver for larger graphs.
   - `MAX_RUNTIME_STEPS = 100,000`: Upper bound for simulation steps.
4. **CORS Origin Allowlist**: Uses an origin allowlist and handles browser preflight requests. CORS is not authentication and does not restrict non-browser clients.
5. **Hermetic AST Expression Evaluator (Zero `eval()`)**: Evaluates expressions in runtime conditions strictly via an Abstract Syntax Tree whitelist (basic arithmetic and boolean operators). Escapes attempting arbitrary code execution (e.g. `__import__`, `os.system`) fail closed safely.
6. **Auditable Provenance Manifest & Graph Digest (Increment C)**: Analyze, compare, and `/api/audit` results include versioned provenance metadata (`manifest_schema_version: "1.0"`):
   - `analysis_fingerprint`: Deterministic SHA-256 digest over canonical source hashes, sorted copybooks, effective analysis options, dependency versions, Rezonator version, and graph digests.
   - `graph_digest`: Order-independent SHA-256 digest over canonical graph topology (nodes, types, edges, weights, and DFG variable expansions).
   - `source_sha256`: Cryptographic digest of the analyzed source code.
   - `copybooks`: Inlined copybook names and content SHA-256 hashes.
   - `dependency_versions`: Exact runtime versions (`numpy`, `scipy`, `networkx`, `torch`, `python`, `platform`).
   - `solver_seed`: Fixed deterministic solver seed (`42`).
   - `timestamp_utc`: ISO 8601 UTC timestamp.
   The `/api/audit` endpoint emits structured JSON or Markdown reports linking findings directly to source line numbers, paragraphs, and copybook origins.
7. **Bounded Context Slices (Increment D)**: The `/api/slice` endpoint extracts source-mapped, bounded evidence packets under caller-supplied line and token budgets (`max_lines`, `max_tokens`, `max_nodes`) with explicit disclosure of omitted dependencies when budgets truncate the slice. Emits JSON or reviewer-oriented Markdown.
8. **Sokół Event Export (opt-in local library API)**: `build_analysis_events` and `build_interpreter_run_event` create bounded `sokol.event.v1` envelopes; `serialize_jsonl_events` returns validated JSONL text in memory. No event file, API route, Git watcher, or AI transfer is started automatically.

Remote mode accepts a bearer token over plain HTTP. Use it only behind a trusted TLS-terminating boundary until encrypted transport is provided by deployment infrastructure.

---

## ⚖️ Licensing, Commercial Terms & Public Healthcare Waiver

Rezonator is distributed under the **Rezonator Source-Available & Commercial License (Version 1.0)**.
**Jurisdiction**: England and Wales, United Kingdom.

### Licensing Tiers:

- **1. Academic, Research & Evaluation Tier (Free)**:
  - Free for personal learning, academic study, scientific research, and peer review.
  - Free for security audits, mathematical validation, and provenance verification.
- **2. Commercial Enterprise Tier (Mandatory Paid License)**:
  - **Financial Institutions & Banking**: Any deployment, execution, or automated analysis by or on behalf of commercial banks, clearing houses, credit unions, hedge funds, investment firms, insurance corporations, or fintech providers **strictly requires a paid commercial license**.
  - **Consulting & Systems Integrators**: Any commercial consultancy (including IBM, Kyndryl, Accenture, AWS, Microsoft, DXC, or Big 4 advisory firms) analyzing client legacy codebases with Rezonator must hold an active commercial enterprise license.
  - **Hosting & SaaS**: Hosting Rezonator as a cloud service, shared API, or internal multi-tenant tool for commercial users is prohibited under the free tier.
- **3. Public Healthcare & Life-Saving Humanitarian Exemption**:
  - Accredited public non-profit healthcare institutions, national health services (including **NHS Trusts in the United Kingdom**), public university medical hospitals, emergency major trauma centres, and intensive care units (ICU) may request and receive a **100% royalty-free, perpetual commercial use waiver** directly from the author for direct patient care, clinical operations, and life-critical hospital infrastructure upon written application.
  - *For-profit medical technology corporations, private hospital chains, and commercial EHR/EMR vendors are strictly excluded from this waiver and must acquire an enterprise license.*

For full legal terms, see [`REZONATOR_LICENSE.md`](file:///c:/Projekty/Rezonator/REZONATOR_LICENSE.md) and [`LICENSE`](file:///c:/Projekty/Rezonator/LICENSE).
Commercial inquiries: **[https://github.com/V1B3hR/Rezonator](https://github.com/V1B3hR/Rezonator)**

---

## 📂 Repository Structure

```text
C:\Projekty\Rezonator\
├── rezonator/                 # Core Production Package
│   ├── __init__.py            # Public API exports (v1.0.0)
│   ├── analysis_config.py     # Deterministic pipeline parameters & solver options
│   ├── ast_graph_builder.py   # Pure-Python AST, CICS/SQL dialect & Graph Builder
│   ├── audit_report.py        # Auditable report generator & Markdown exporter
│   ├── evidence_events.py     # Bounded Sokół v1 evidence-event/JSONL contract
│   ├── cobol_parser.py        # Front-End Parser Adapter
│   ├── cobol_runtime.py       # Deterministic Operational Semantics (AST Evaluator)
│   ├── copybooks.py           # Nested COPYBOOK inlining & REPLACING preprocessor
│   ├── cycle_detector.py      # CFG cycle enumeration and heuristic hazard analysis
│   ├── diamond_yant.py        # Shift-Invert Lanczos & NetLSD Signatures
│   ├── diffusion_ranker.py    # Continuous Impact & Blast Radius Ranker
│   ├── graph_field.py         # Tensorization & Fan Chung Laplacian
│   ├── limits.py              # Defense-in-depth resource & size limits
│   ├── llm_synthesizer.py     # Deterministic analysis brief (legacy module name)
│   ├── mutation_benchmark.py  # Mutation Testing Engine (Hypothesis H1)
│   ├── pinn_diffusion.py      # Krylov Matrix Exponential Diffusion
│   ├── program_comparator.py  # Topological NetLSD & Fidelity Evaluator
│   ├── program_slicer.py      # Static Forward/Backward Reachability
│   ├── provenance.py          # Cryptographic SHA-256 provenance tracking
│   ├── server.py              # Hardened HTTP Server & REST API
│   └── experimental/          # Deprecated & experimental heuristics
├── mathy/                     # Backward-Compatibility Facade
│   └── *.py                   # Shims forwarding all imports to rezonator.*
├── web/                       # High-Contrast Physics Web Studio
│   ├── index.html             # Web Studio Interface
│   ├── style.css              # Vanilla CSS Dark-Mode & Glassmorphic System
│   └── app.js                 # 4-Quadrant Physics Canvases & Animation
├── examples/                  # 10 Canonical COBOL Banking Programs
│   ├── bank_demo_v1.cbl       # Core Banking Withdrawal (17 nodes)
│   ├── bank_demo_v2.cbl       # Modular Extension with Risk Checks (27 nodes)
│   ├── atm_deadlock.cbl       # Mutual Recursive Deadlock Loop (1 cycle)
│   └── batch_interest.cbl     # Batch with Dead Variable (2 components)
├── tests/                     # Deterministic Test Harness (62 tests)
│   ├── golden_graphs.py       # Immutable Reference Specifications
│   ├── test_golden_graphs.py  # 100% Graph Isomorphism Verification (6 tests)
│   ├── test_hypothesis_h1.py  # Mutation Testing Benchmark Battery (4 tests)
│   ├── test_api_and_engines.py# Physics Engines & REST API Integration (7 tests)
│   ├── test_sparse_scaling.py # Sparse Lanczos & Krylov Scaling Tests (3 tests)
│   ├── test_backward_compat.py# Rezonator vs Mathy Namespace Equivalence (2 tests)
│   ├── test_copybook_inliner.py# Nested COPYBOOK expansion & REPLACING (3 tests)
│   ├── test_f4_enterprise_statements.py # Embedded CICS & DB2 SQL Dialects (3 tests)
│   ├── test_security_hardening.py# HTTP, AST sandbox, limits, provenance (5 tests)
│   ├── test_increment_a_truthful_parser.py # Truthful parser & Tarjan SCCs (7 tests)
│   ├── test_increment_b_sparse_analysis.py # Sparse end-to-end & scaling (6 tests)
│   ├── test_increment_c_auditable_report.py # Auditable report & provenance (4 tests)
│   ├── test_increment_d_bounded_slicer.py # Bounded context slices & budgets (7 tests)
│   └── test_sokol_evidence_events.py # Event envelopes, JSONL and value exclusion
├── docs/                      # Scientific Documentation
│   ├── AUDIT_REPORT.md        # Audit report & provenance contract (Increment C)
│   ├── CONTEXT_SLICE_SPEC.md  # Bounded context slice specification (Increment D)
│   ├── SOKOL_EVIDENCE_EVENTS.md # Versioned bounded Sokół event export contract
│   ├── MATHEMATICAL_FOUNDATIONS.md           # Companion Foundations
│   ├── REZONATOR_MATHEMATICAL_FOUNDATIONS.md # Graph-math reference and implementation scope
│   ├── SOKOL_ARCHITECTURE.md  # Sokół observer, memory & privacy specifications
│   └── SUPPORTED_SYNTAX.md    # COBOL parser supported/unsupported syntax matrix
├── Cargo.toml                 # Rust Package Definition
├── requirements.txt           # Python Dependency Specification
├── REZONATOR_requirements.txt # Extended Runtime Specification
├── LICENSE                    # Plaintext Rezonator License (UK Jurisdiction)
├── REZONATOR_LICENSE.md       # Formatted License & Healthcare Terms
├── REZONATOR_DEBUGGING_REPORT.md
├── REZONATOR_TEST_SUITE_REPORT.md
├── REZONATOR_BENCHMARKS.md
├── REZONATOR_VERIFICATION_AND_VALIDATION.md
├── REZONATOR_ROADMAP.md
├── REZONATOR_DEVELOPMENT_MILESTONES.md
├── REZONATOR_run_benchmarks.py# One-Click Benchmark Suite
├── main.py                    # Unified CLI Tool
└── README.md                  # Primary Repository Documentation
```

---

## 📜 Scientific Citation

If you use Rezonator in your research or enterprise modernization work, please cite:
```bibtex
@software{rezonator2026,
  author = {Błyskawica & Rezonator Team},
  title = {Rezonator: Finite Program Graphs, Spectral Methods, and Static Analysis for Mainframe Code},
  year = {2026},
  url = {https://github.com/V1B3hR/Rezonator}
}
```
