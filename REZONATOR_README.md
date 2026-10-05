# ⚡ REZONATOR (Błyskawica Spectral Code Intelligence)
### Continuous Topological Manifolds, Spectral Graph Theory & Formal Verification for Legacy Enterprise Code Intelligence

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Błyskawica](https://img.shields.io/badge/Powered%20by-B%C5%82yskawica%20SPARKLE%20V10-cyan.svg)](https://github.com/V1B3hR/Blyskawica)
[![GitHub Repo](https://img.shields.io/badge/GitHub-V1B3hR%2FRezonator-blue.svg)](https://github.com/V1B3hR/Rezonator)
[![Tests Passing](https://img.shields.io/badge/tests-22%2F22%20passing-brightgreen.svg)]()

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
| **Debugging & Defect Report** | [`REZONATOR_DEBUGGING_REPORT.md`](file:///c:/Projekty/Rezonator/REZONATOR_DEBUGGING_REPORT.md) | Technical audit, root-cause analysis, and proof of remediation across 7 core defects (Smart App Control, decimal parsing, ARPACK shift-invert). |
| **Comprehensive Test Suite** | [`REZONATOR_TEST_SUITE_REPORT.md`](file:///c:/Projekty/Rezonator/REZONATOR_TEST_SUITE_REPORT.md) | Execution summary of all 22 unit & integration tests (100% pass rate in < 1.0s) with invariant proofs. |
| **Performance Benchmarks** | [`REZONATOR_BENCHMARKS.md`](file:///c:/Projekty/Rezonator/REZONATOR_BENCHMARKS.md) | End-to-end parsing throughput (260+ progs/sec), sparse Lanczos scaling up to $N=10,000$ vertices, and Hypothesis $H_1$ mutation battery. |
| **Verification & Validation** | [`REZONATOR_VERIFICATION_AND_VALIDATION.md`](file:///c:/Projekty/Rezonator/REZONATOR_VERIFICATION_AND_VALIDATION.md) | Formal IEEE 1012 / ISO 25010 assessment, ANSI-85 / IBM COBOL compliance, traceability matrix, and hazard mitigations. |
| **Strategic Roadmap** | [`REZONATOR_ROADMAP.md`](file:///c:/Projekty/Rezonator/REZONATOR_ROADMAP.md) | Audit of completed phases (F0–F3) and future milestones (F4 CICS/SQL, F5 JCL hypergraphs, F6 Cheeger spectral monolith cuts). |
| **Development Milestones** | [`REZONATOR_DEVELOPMENT_MILESTONES.md`](file:///c:/Projekty/Rezonator/REZONATOR_DEVELOPMENT_MILESTONES.md) | Chronological evolution of Rezonator from M0 prototype to production v1.0.0. |
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
python main.py --serve --port 8080
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
*(22 tests verify golden AST graph isomorphism, runtime execution, mutation ground-truth, Laplacian symmetry, eigensolver, NetLSD diffusion, cycle/deadlock detection, sparse Lanczos scaling, and backward compatibility).*

### 5. Run the Full Benchmark Suite
```bash
python REZONATOR_run_benchmarks.py
```

---

## 📂 Repository Structure

```text
C:\Projekty\Rezonator\
├── rezonator/                 # Core Production Package
│   ├── __init__.py            # Public API exports (v1.0.0)
│   ├── ast_graph_builder.py   # Hermetic Pure-Python AST & Graph Builder
│   ├── cobol_parser.py        # Front-End Parser Adapter
│   ├── cobol_runtime.py       # Deterministic Operational Semantics
│   ├── cycle_detector.py      # Tarjan SCC Cycle & Recursion Verifier
│   ├── graph_field.py         # Tensorization & Fan Chung Laplacian
│   ├── diamond_yant.py        # Shift-Invert Lanczos & NetLSD Signatures
│   ├── pinn_diffusion.py      # Krylov Matrix Exponential Diffusion
│   ├── diffusion_ranker.py    # Continuous Impact & Blast Radius Ranker
│   ├── program_slicer.py      # Static Forward/Backward Reachability
│   ├── program_comparator.py  # Topological NetLSD & Fidelity Evaluator
│   ├── llm_synthesizer.py     # Cognitive Markdown Prompt Generator
│   ├── mutation_benchmark.py  # Mutation Testing Engine (Hypothesis H1)
│   ├── server.py              # High-Performance HTTP Server & REST API
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
├── tests/                     # Deterministic Test Harness (22 tests)
│   ├── golden_graphs.py       # Immutable Reference Specifications
│   ├── test_golden_graphs.py  # 100% Graph Isomorphism Verification
│   ├── test_hypothesis_h1.py  # Mutation Testing Benchmark Battery
│   ├── test_api_and_engines.py# Physics Engines & REST API Integration
│   ├── test_sparse_scaling.py # Sparse Lanczos & Krylov Scaling Tests
│   └── test_backward_compat.py# Rezonator vs Mathy Namespace Equivalence
├── docs/                      # Scientific Documentation
│   ├── REZONATOR_MATHEMATICAL_FOUNDATIONS.md # Formal Whitepaper
│   └── MATHEMATICAL_FOUNDATIONS.md           # Companion Foundations
├── Cargo.toml                 # Rust Package Definition
├── requirements.txt           # Python Dependency Specification
├── REZONATOR_requirements.txt # Extended Runtime Specification
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
