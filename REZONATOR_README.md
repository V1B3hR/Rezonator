# ⚡ REZONATOR (Błyskawica Spectral Code Intelligence)
### Continuous Topological Manifolds, Spectral Graph Theory & Formal Verification for Legacy Enterprise Code Intelligence

[![License: Rezonator Commercial](https://img.shields.io/badge/License-Source--Available%20%26%20Commercial-red.svg)](REZONATOR_LICENSE.md)
[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Błyskawica](https://img.shields.io/badge/Powered%20by-B%C5%82yskawica%20SPARKLE%20V10-cyan.svg)](https://github.com/V1B3hR/Blyskawica)
[![GitHub Repo](https://img.shields.io/badge/GitHub-V1B3hR%2FRezonator-blue.svg)](https://github.com/V1B3hR/Rezonator)
[![Tests Passing](https://img.shields.io/badge/tests-33%2F33%20passing-brightgreen.svg)]()

> *"Nie traktujemy kodu COBOL jako tekstu słowo po słowie – traktujemy program jako pole wektorowe i przestrzeń topologiczną, którą można różniczkować, całkować i analizować widmowo."*

---

## 🌌 Context & Problem Statement

Over **95% of ATM transactions** and **43% of core banking mainframes** run on COBOL. Mainframe systems are defined by deep determinism: variables have fixed contiguous memory addresses, execution flows resemble hydraulic or thermodynamic pipelines, and global `WORKING-STORAGE` structures create complex coupling.

Standard linguistic LLMs treat code as plain text tokens, frequently hallucinating control flow across archaic `PERFORM`, `EVALUATE`, and `GO TO` jumps. 

**Rezonator** adapts the cognitive and physical solvers from [V1B3hR/Blyskawica](https://github.com/V1B3hR/Blyskawica) (Diamond Yant, PINN Thermal Engine, Spectral Manifolds) into a **rigorous mathematical pipeline**:

```
Legacy COBOL World
       │
       ▼
┌─────────────────────────┐
│   COBOL Front-End       │  ──> Hermetic AST & Block Extractor
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Program Intermediate    │  ──> Basic blocks, statements, shared memory hubs
│ Representation (PIR)    │
└────────────┬────────────┘
             │
       ┌─────┴──────────────────────┐
       ▼                            ▼
┌────────────────────────┐   ┌────────────────────────┐
│ Control Flow Graph     │   │ Data Flow Graph        │
│ (CFG)                  │   │ (DFG & Def-Use)        │
└────────────┬───────────┘   └────────────┬───────────┘
             │                            │
             └─────────────┬──────────────┘
                           │
                           ▼
             ┌───────────────────────────┐
             │ Unified Graph Laplacian   │  ──> L = D - A, L_norm
             │ Field & Memory Hubs       │
             └─────────────┬─────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ DIAMOND YANT │   │ PINN HEAT    │   │ TARJAN SCC   │
│ Modal Wave   │   │ Diffusion    │   │ Cycle & Loop │
│ Cymatics     │   │ PDE Engine   │   │ Verifier     │
└───────┬──────┘   └──────┬───────┘   └──────┬───────┘
        │                 │                  │
        └─────────────────┼──────────────────┘
                          │
                          ▼
             ┌───────────────────────────┐
             │ AI / LLM COGNITIVE BRIEF  │  ──> Zero Hallucinations, Pure Physics
             │ & Interactive Web Studio  │
             └───────────────────────────┘
```

---

## 📚 Strategic Architecture & Documentation

Rezonator includes an exhaustive, defense-grade documentation suite designed for enterprise architects, scientific researchers, and audit teams:

| Strategic Document | File Location | Key Contents |
|:---|:---|:---|
| **License & Commercial Terms** | [`REZONATOR_LICENSE.md`](file:///c:/Projekty/Rezonator/REZONATOR_LICENSE.md) | Source-available & commercial licensing terms (UK jurisdiction), enterprise bank restrictions, and public healthcare / NHS humanitarian waiver. |
| **Debugging & Defect Report** | [`REZONATOR_DEBUGGING_REPORT.md`](file:///c:/Projekty/Rezonator/REZONATOR_DEBUGGING_REPORT.md) | Technical audit, root-cause analysis, and proof of remediation across 7 core defects (Smart App Control, decimal parsing, ARPACK shift-invert). |
| **Comprehensive Test Suite** | [`REZONATOR_TEST_SUITE_REPORT.md`](file:///c:/Projekty/Rezonator/REZONATOR_TEST_SUITE_REPORT.md) | Execution summary of all 33 unit & integration tests (100% pass rate in < 2.0s) covering dialects, security boundaries, and invariant proofs. |
| **Performance Benchmarks** | [`REZONATOR_BENCHMARKS.md`](file:///c:/Projekty/Rezonator/REZONATOR_BENCHMARKS.md) | End-to-end parsing throughput (260+ progs/sec), sparse Lanczos scaling up to $N=10,000$ vertices, and Hypothesis $H_1$ mutation battery. |
| **Verification & Validation** | [`REZONATOR_VERIFICATION_AND_VALIDATION.md`](file:///c:/Projekty/Rezonator/REZONATOR_VERIFICATION_AND_VALIDATION.md) | Formal IEEE 1012 / ISO 25010 assessment, ANSI-85 / IBM COBOL compliance, traceability matrix, and hazard mitigations. |
| **Strategic Roadmap** | [`REZONATOR_ROADMAP.md`](file:///c:/Projekty/Rezonator/REZONATOR_ROADMAP.md) | Audit of completed phases (F0–F4) and future milestones (F4.3 hybrid bridge, F5 JCL hypergraphs, F6 Cheeger spectral cuts). |
| **Development Milestones** | [`REZONATOR_DEVELOPMENT_MILESTONES.md`](file:///c:/Projekty/Rezonator/REZONATOR_DEVELOPMENT_MILESTONES.md) | Chronological evolution of Rezonator from M0 prototype to production v1.0.0 and hardened M7 state. |
| **Mathematical Foundations** | [`docs/REZONATOR_MATHEMATICAL_FOUNDATIONS.md`](file:///c:/Projekty/Rezonator/docs/REZONATOR_MATHEMATICAL_FOUNDATIONS.md) | Exhaustive scientific whitepaper: Fan Chung Laplacians, NetLSD heat trace kernels, continuous Markov generators, and Cheeger bounds. |

---

## 🔬 Core Physics & Mathematical Solvers

### 1. 💎 Diamond Yant Modal Spectral Engine
- Solves the exact eigensystem of the Graph Laplacian:
  $$L v_k = \lambda_k v_k, \quad 0 = \lambda_0 \le \lambda_1 \le \dots \le \lambda_{N-1}$$
- **Fiedler Value ($\lambda_1$)**: Algebraic connectivity measuring structural cohesion. If $\lambda_1 = 0$, unreachable code or disconnected sinks exist.
- **Fiedler Vector ($v_1$)**: Cheeger spectral bi-partitioning into natural domain logic vs. ancillary routines.
- **NetLSD Multi-Scale Heat Trace Signature**:
  $$\Phi(t) = \text{Tr}\left(\exp(-t \mathcal{L}_{\text{norm}})\right) = \sum_{k} \exp(-t \lambda_k)$$
  Provides graph-size invariant topological distance across 25 log time scales $t \in [10^{-2}, 10^2]$.
- **Sparse Shift-Invert Lanczos Scaling**:
  Uses negative spectral shift $\sigma = -10^{-4}$ with `scipy.sparse.linalg.eigsh`, achieving an **1,800x speedup** on large matrices ($N \ge 1,000$).

### 2. 🌡️ PINN Graph Heat Diffusion Engine
- Solves parabolic data/taint propagation across variables and routines:
  $$\frac{\partial u}{\partial t} = -\alpha L u \implies u(t) = \exp(-\alpha L t) u_0$$
- Injects impulse into any variable (e.g. `WS-ACCOUNT-BALANCE`) to observe downstream dispersion.
- Computes directed forward blast radius via continuous Markov generator $Q = P^T - I$:
  $$u(t) = \exp((P^T - I)t) u_0$$
- Scales to $N = 10,000$ vertices in **83 ms** using Krylov subspace `expm_multiply`.

### 3. 🛡️ Formal Cycle, Recursion & Deadlock Verifier (Tarjan SCC)
- Computes Strongly Connected Components (SCC) on the directed Control Flow Graph $\mathcal{G}_{\text{CFG}}$.
- Distinguishes valid acyclic business logic from hazardous recursive `PERFORM` cycles.
- Analyzes loop termination guards and invariants to mathematically guarantee exit reachability (`STOP RUN` / `GOBACK`).
- Flags infinite recursion traps with 100% precision (e.g. `ATM-DEADLOCK` correctly identified as `CRITICAL_INFINITE_LOOP`).

---

## 🚀 Quickstart

### 1. Run the Empirical Verification Experiment (V1 vs V2)
```bash
python verify_experiment.py
```

### 2. Launch the Interactive Web Studio
```bash
# Default: Secure local diagnostic mode (127.0.0.1, no auth needed)
python main.py --serve --port 8080

# Hardened Remote Mode: Requires bearer token authentication
python main.py --serve --remote --token YOUR_SECURE_TOKEN --port 8080
```
Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)** in any modern browser to access:
- **Interactive Graph Topology Canvas (CFG + DFG)** with dynamic heat glowing.
- **Diamond Yant 2D Chladni Cymatics Oscilloscope** running 60 FPS standing wave simulations.
- **PINN Heat Diffusion Timeline Scrubber** with variable impulse injection.
- **Tarjan SCC Cycle & Deadlock Radar** with formal termination verification.
- **Side-by-Side Differential Anomaly Scorecard** (V1 vs V2).
- **One-Click LLM Cognitive Brief Generation**.

### 3. Compare Custom COBOL Files
```bash
python main.py --compare examples/bank_demo_v1.cbl examples/bank_demo_v2.cbl
```

### 4. Run Automated Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py"
```
*(33 tests verify golden AST graph isomorphism, runtime execution, mutation ground-truth, Laplacian symmetry, eigensolver, NetLSD diffusion, cycle/deadlock detection, sparse Lanczos scaling, copybook expansion, embedded CICS/SQL statements, zero-trust HTTP hardening, and backward compatibility).*

### 5. Run the Full Benchmark Suite
```bash
python REZONATOR_run_benchmarks.py
```

---

## 🔒 Security Hardening & Zero-Trust Architecture

Rezonator adheres to a defensive, zero-trust posture designed for sensitive enterprise codebases:

1. **Local-by-Default Binding**: Binds strictly to loopback interface `127.0.0.1`. Remote binding (`--remote`) requires an explicit secret token (`--token <TOKEN>`). Unauthenticated requests fail closed with `HTTP 401 Unauthorized`.
2. **Explicit HTTP/1.0 & Connection Termination**: Emits explicit `HTTP/1.0` with mandatory `Connection: close`, preventing connection reuse attacks, smuggling, and lingering socket leaks.
3. **Payload & Resource Limits**:
   - `MAX_PAYLOAD_BYTES = 10 MB`: Requests exceeding 10 MB are rejected immediately with `HTTP 413 Payload Too Large`.
   - `MAX_SOURCE_BYTES = 10 MB`: Source files exceeding 10 MB raise `ResourceLimitError`.
   - `MAX_DENSE_MATRIX_NODES = 1,000`: Dense matrix representations reject allocations $> 1,000$ nodes with `GraphLimitError`, requiring sparse Lanczos solvers.
   - `MAX_GRAPH_NODES = 50,000`: Hard ceiling on graph size to prevent memory exhaustion.
   - `MAX_RUNTIME_STEPS = 10,000`: Execution step limit in simulation runtime.
4. **CORS Allowlist & Preflight Protection**: Replaces permissive wildcard CORS (`*`) with configurable origin allowlisting (`ALLOWED_ORIGINS`) and preflight `OPTIONS` handling. Unauthorized origins receive `HTTP 403 Forbidden`.
5. **Hermetic AST Expression Evaluator (Zero `eval()`)**: Evaluates expressions in runtime conditions strictly via an Abstract Syntax Tree whitelist (basic arithmetic and boolean operators). Escapes attempting arbitrary code execution (e.g. `__import__`, `os.system`) fail closed safely.
6. **Cryptographic Provenance Envelope**: Every analysis result includes a provenance block:
   - `source_sha256`: Cryptographic digest of the analyzed source code.
   - `solver_seed`: Fixed deterministic solver seed (`42`).
   - `rezonator_version`: Package semantic version (`1.0.0`).
   - `timestamp_utc`: ISO 8601 UTC timestamp.

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
│   ├── ast_graph_builder.py   # Pure-Python AST, CICS/SQL dialect & Graph Builder
│   ├── cobol_parser.py        # Front-End Parser Adapter
│   ├── cobol_runtime.py       # Deterministic Operational Semantics (AST Evaluator)
│   ├── copybooks.py           # Nested COPYBOOK inlining & REPLACING preprocessor
│   ├── cycle_detector.py      # Tarjan SCC Cycle & Recursion Verifier
│   ├── diamond_yant.py        # Shift-Invert Lanczos & NetLSD Signatures
│   ├── diffusion_ranker.py    # Continuous Impact & Blast Radius Ranker
│   ├── graph_field.py         # Tensorization & Fan Chung Laplacian
│   ├── limits.py              # Defense-in-depth resource & size limits
│   ├── llm_synthesizer.py     # Cognitive Markdown Prompt Generator
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
├── tests/                     # Deterministic Test Harness (33 tests)
│   ├── golden_graphs.py       # Immutable Reference Specifications
│   ├── test_golden_graphs.py  # 100% Graph Isomorphism Verification (6 tests)
│   ├── test_hypothesis_h1.py  # Mutation Testing Benchmark Battery (4 tests)
│   ├── test_api_and_engines.py# Physics Engines & REST API Integration (7 tests)
│   ├── test_sparse_scaling.py # Sparse Lanczos & Krylov Scaling Tests (3 tests)
│   ├── test_backward_compat.py# Rezonator vs Mathy Namespace Equivalence (2 tests)
│   ├── test_copybook_inliner.py# Nested COPYBOOK expansion & REPLACING (3 tests)
│   ├── test_f4_enterprise_statements.py # Embedded CICS & DB2 SQL Dialects (3 tests)
│   └── test_security_hardening.py# HTTP, AST sandbox, limits, provenance (5 tests)
├── docs/                      # Scientific Documentation
│   ├── REZONATOR_MATHEMATICAL_FOUNDATIONS.md # Formal Whitepaper
│   └── MATHEMATICAL_FOUNDATIONS.md           # Companion Foundations
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
  title = {Rezonator: Continuous Topological Manifolds, Spectral Graph Theory, and Formal Verification for Mainframe Code Intelligence},
  year = {2026},
  url = {https://github.com/V1B3hR/Rezonator}
}
```
