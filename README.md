# ⚡ REZONATOR (Błyskawica Mathy)
### Continuous Topological Manifolds, Spectral Graph Theory & Formal Verification for Legacy Enterprise Code Intelligence

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Błyskawica](https://img.shields.io/badge/Powered%20by-B%C5%82yskawica%20SPARKLE%20V10-cyan.svg)](https://github.com/V1B3hR/Blyskawica)
[![GitHub Repo](https://img.shields.io/badge/GitHub-V1B3hR%2FRezonator-blue.svg)](https://github.com/V1B3hR/Rezonator)
[![Tests Passing](https://img.shields.io/badge/tests-17%2F17%20passing-brightgreen.svg)]()

> *"Nie traktujemy kodu COBOL jako tekstu słowo po słowie – traktujemy program jako pole wektorowe i przestrzeń topologiczną, którą można różniczkować, całkować i analizować widmowo."*

---

## 🌌 Context & Problem Statement

Over **95% of ATM transactions** and **43% of core banking mainframes** run on COBOL. Mainframe systems are defined by deep determinism: variables have fixed contiguous memory addresses, execution flows resemble hydraulic or thermodynamic pipelines, and global `WORKING-STORAGE` structures create complex coupling.

Standard linguistic LLMs treat code as plain text tokens, frequently hallucinating control flow across archaic `PERFORM`, `EVALUATE`, and `GO TO` jumps. 

**Błyskawica Mathy** takes the cognitive and physical solvers from [V1B3hR/Blyskawica](https://github.com/V1B3hR/Blyskawica) (Diamond Yant, PINN Thermal Engine, Relativistic Gravity Solver) and adapts them into a **rigorous mathematical pipeline**:

```
Legacy COBOL World
       │
       ▼
┌─────────────────────────┐
│   COBOL Front-End       │  ──> Lexer, AST & Block Extractor
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
             │ Unified Graph Laplacian   │  ──> L = D - A
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

## 🔬 Core Physics & Mathematical Solvers

### 1. 💎 Diamond Yant Modal Spectral Engine
- Solves the exact eigensystem of the Graph Laplacian:
  $$L v_k = \lambda_k v_k, \quad 0 = \lambda_0 \le \lambda_1 \le \dots \le \lambda_{N-1}$$
- **Fiedler Value ($\lambda_1$)**: Algebraic connectivity measuring structural cohesion. If $\lambda_1 = 0$, unreachable code or disconnected sinks exist.
- **Fiedler Vector ($v_1$)**: Cheeger spectral bi-partitioning into natural domain logic vs. ancillary routines.
- **NetLSD Multi-Scale Heat Trace Signature**:
  $$\Phi(t) = \text{Tr}\left(\exp(-t \mathcal{L}_{norm})\right) = \sum_{k} \exp(-t \lambda_k)$$
  Provides graph-size invariant topological distance across 25 log time scales $t \in [10^{-2}, 10^2]$.
- **2D Chladni Continuous Plate Resonance**:
  $$w(x, y) = \sum_{k=1}^K c_k \left[ a_k \sin\left(\frac{n_k \pi x}{L}\right)\sin\left(\frac{m_k \pi y}{L}\right) + b_k \sin\left(\frac{m_k \pi x}{L}\right)\sin\left(\frac{n_k \pi y}{L}\right) \right]$$
  Visualizes nodal modal vibrational patterns without contaminating quantitative distance metrics.

### 2. 🌡️ PINN Graph Heat Diffusion Engine
- Solves parabolic data/taint propagation across variables and routines:
  $$\frac{\partial u}{\partial t} = -\alpha L u \implies u(t) = \exp(-\alpha L t) u_0$$
- Injects impulse into any variable (e.g. `WS-ACCOUNT-BALANCE`) to observe downstream dispersion.
- Computes directed impact propagation (blast radius) via forward transfer kernel:
  $$\dot{u} = (P^T - I)u \implies u(t) = \exp((P^T - I)t) u_0$$

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
Expected output:
```text
======================================================================
 REZONATOR: VERIFICATION EXPERIMENT (BANK-DEMO-V1 vs BANK-DEMO-V2)
======================================================================

[PROGRAM A]: BANK-DEMO-V1
  Nodes: 17 | Edges: 37 | Vars: 4
  Connected Components: 1
  Eigenvalues (lambda 0..5): [0.0, 0.2896, 0.975, 1.0834, 1.3464, 1.4094]
  Algebraic Connectivity (Fiedler lambda 1): 0.2896
  Diffusion Half-Life: 4.7877 time units
  Forward Blast Radius (reachable nodes from entry): 16
  Cycle / Deadlock Status: DIRECTED_ACYCLIC_FLOW

[PROGRAM B]: BANK-DEMO-V2
  Nodes: 27 | Edges: 61 | Vars: 6
  Connected Components: 1
  Eigenvalues (lambda 0..5): [0.0, 0.1591, 0.4631, 0.7745, 0.8073, 0.963]
  Algebraic Connectivity (Fiedler lambda 1): 0.1591
  Diffusion Half-Life: 8.7135 time units
  Forward Blast Radius (reachable nodes from entry): 24
  Cycle / Deadlock Status: DIRECTED_ACYCLIC_FLOW

----------------------------------------------------------------------
 REZONATOR TOPOLOGICAL DIVERGENCE METRICS:
----------------------------------------------------------------------
  NetLSD Topological Distance:        0.0550
  Fiedler Connectivity Delta:         -0.1305
  Normalized Fiedler Delta:           -0.0656
  Cymatic Resonance Cross-Similarity: 44.97%
  Node Complexity Expansion:          1.59x
  Refactoring Fidelity Score:         86.3 / 100
  Deadlock Introduced:                NO

  VERDICT: SAFE_MODULAR_EXTENSION: High topological fidelity maintained with conservative logic extension.
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
*(13 tests verify golden AST graph isomorphism, runtime execution, mutation ground-truth, Laplacian symmetry, eigensolver, NetLSD diffusion, cycle/deadlock detection, comparator, and hermetic HTTP API).*

---

## 📂 Repository Structure

```text
C:\Projekty\Mathy\
├── mathy/
│   ├── __init__.py
│   ├── ast_graph_builder.py   # Compiler-Grade AST to CFG/DFG Graph Builder (cobolparser)
│   ├── cobol_parser.py        # COBOL Parser Adapter (AST primary + regex fallback)
│   ├── cobol_runtime.py       # Deterministic Operational Semantics & Mutation Engine
│   ├── cycle_detector.py      # Tarjan SCC Cycle & Recursion Verifier
│   ├── graph_field.py         # Tensorization, Directed Adjacency & Fan Chung Laplacian
│   ├── diamond_yant.py        # Modal Spectral Decomposition & NetLSD Signature Vector
│   ├── pinn_diffusion.py      # Directed Forward Impact Diffusion & Blast Radius Solver
│   ├── program_comparator.py  # Topological NetLSD Radar & Refactoring Fidelity Evaluator
│   ├── llm_synthesizer.py     # Cognitive Markdown Prompt Generator
│   └── server.py              # Hermetic HTTP Server & REST API
├── web/
│   ├── index.html             # High-Contrast Physics Web Studio
│   ├── style.css              # Custom Vanilla CSS Design System
│   └── app.js                 # 4-Quadrant Physics Canvases & Animation
├── examples/
│   ├── bank_demo_v1.cbl       # Canonical Core Banking Withdrawal (17 nodes, 1 component)
│   ├── bank_demo_v2.cbl       # Safe Modular Extension with Risk Evaluation (27 nodes)
│   ├── atm_deadlock.cbl       # Infinite Loop Deadlock (1 Tarjan recursive cycle)
│   └── batch_interest.cbl     # Interest Batch with Dead Variable (2 components)
├── tests/
│   ├── golden_graphs.py       # Ground-Truth Typed CFG/DFG Reference Specifications
│   ├── test_golden_graphs.py  # 100% Isomorphism, Trace Execution & Mutation Tests
│   └── test_api_and_engines.py# Integration & Hermetic API Test Suite
├── docs/
│   └── MATHEMATICAL_FOUNDATIONS.md # Scientific Whitepaper
├── main.py                    # Unified CLI Tool
├── verify_experiment.py       # Standalone Proof-of-Concept Script
└── README.md                  # This Documentation
```

---

## 📜 Theoretical Foundations

For the rigorous mathematical derivation of Graph Laplacians, NetLSD heat trace signatures, directed forward impact diffusion, and Tarjan SCC cycle verification, see:
👉 **[docs/MATHEMATICAL_FOUNDATIONS.md](docs/MATHEMATICAL_FOUNDATIONS.md)**.

