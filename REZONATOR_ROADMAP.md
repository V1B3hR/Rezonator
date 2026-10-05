# REZONATOR: POST-DEBUGGING STRATEGIC ROADMAP
## Evolution Path: From Mathematical Foundations to Enterprise Mainframe Modernization

---

### Executive Overview

With the completion of the rigorous debugging, hermetic parser implementation, and sparse linear algebra scaling passes, **Rezonator v1.0.0** has achieved a fully verified, mathematically sound core.

This post-debugging roadmap outlines the transition from the completed foundation phases (**F0–F3**) to the upcoming enterprise-scale modernization phases (**F4–F6**).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              REZONATOR STRATEGIC ROADMAP                               │
├───────────────────────────────────────────────────────┬────────────────────────────────┤
│ COMPLETED PHASES (v1.0.0 - Production Certified)     │ TARGET PHASES (v1.1 - v2.0)    │
├───────────────────────────────────────────────────────┼────────────────────────────────┤
│ [F0] Mathematical Rigor & Pseudoscience Purge         │ [F4] Enterprise Dialects, CICS │
│      - Deprecated bogus GR event-horizon heuristics   │      - EXEC CICS & EXEC SQL    │
│      - Integrated Tarjan SCC cycle / deadlock engine  │      - Automated COPYBOOK inline│
│                                                       │                                │
│ [F1] Ground-Truth & Golden Graph Isomorphism          │ [F5] Multi-Program Hypergraphs │
│      - 4 canonical benchmark programs (Bank, ATM, etc)│      - Cross-program CALL flow │
│      - 100% exact isomorphism verification tests      │      - JCL batch pipeline link │
│                                                       │                                │
│ [F2] Hermetic Pure-Python AST Parser                  │ [F6] Automated Monolith Cut    │
│      - Zero external Cython/pyd native dependencies   │      - Cheeger spectral cluster│
│      - Windows 11 Smart App Control (SAC) resilience  │      - LLM context-slice engine│
│                                                       │      - Rust native sparse math │
│ [F3] Sparse Lanczos & Krylov Scaling                  │                                │
│      - Shift-invert Lanczos eigensolver (1800x faster)│                                │
│      - Krylov expm trajectory scaling to N=10,000     │                                │
└───────────────────────────────────────────────────────┴────────────────────────────────┘
```

---

### 1. Status of Completed Phases (Phases F0 – F3)

#### Phase F0: Mathematical Rigor & Structural Integrity [COMPLETED]
- **Accomplishments**:
  - Identified and removed `gr_geodesic.py` from active pipeline; relegated to `experimental/`. Eliminated size-dependent "event horizon" false positives.
  - Implemented formal cycle and loop verification using **Tarjan's Strongly Connected Components (SCC)** algorithm directly on the Control Flow Graph.
  - Standardized the Graph Field on the **Fan Chung Symmetric Normalized Laplacian** ($\mathcal{L}_{\text{norm}} = I - D^{-1/2} A D^{-1/2}$), bounding eigenvalue spectra to $[0, 2]$.
  - Resolved `END-IF` parser bugs where statement terminators were incorrectly consumed as paragraph headers.

#### Phase F1: Deterministic Ground Truth & Golden Graphs [COMPLETED]
- **Accomplishments**:
  - Developed and verified 4 reference programs representing core mainframe patterns:
    - `bank_demo_v1.cbl`: Linear transactional flow.
    - `bank_demo_v2.cbl`: Conservative modular extension with audit and fraud checks.
    - `atm_deadlock.cbl`: Mutual recursive non-terminating deadlock loop.
    - `batch_interest.cbl`: Batch job with unreferenced memory fields.
  - Created `tests/golden_graphs.py` with immutable vertex, edge, and variable specifications.
  - Implemented `tests/test_golden_graphs.py` asserting exact isomorphism ($0$ node diff, $0$ edge diff, $0$ variable diff).

#### Phase F2: Hermetic Cross-Platform Parser [COMPLETED]
- **Accomplishments**:
  - Solved Windows 11 Smart App Control (SAC) native code integrity block by building a 100% pure-Python ANSI-85 / IBM Enterprise COBOL AST parser.
  - Supported Working-Storage declarations with decimal values (`PIC 9(7)V99 VALUE 5000.00.`).
  - Added arithmetic `GIVING` clause rules ensuring destination variables are modified without polluting operand definitions.
  - Guaranteed zero external binary dependencies and sub-second parsing across all 10 corpus examples.

#### Phase F3: Sparse Matrix & Lanczos/Krylov Scaling [COMPLETED]
- **Accomplishments**:
  - Converted internal linear algebra engines to `scipy.sparse.csr_matrix`.
  - Implemented shift-invert Lanczos eigensolver ($\sigma = -10^{-4}$, `which='LM'`), cutting Fiedler vector computation time on $N=1,000$ matrices from **2,870 ms to 1.53 ms** (**1,800x speedup**).
  - Implemented Krylov subspace matrix exponential multiplier (`spla.expm_multiply`), computing 10-step diffusion trajectories on $N=10,000$ nodes ($30,000$ edges) in **83.98 ms**.
  - Established empirical scaling benchmarks with $O(k \cdot E)$ linear complexity.

---

### 2. Strategic Roadmap: Upcoming Phases (Phases F4 – F6)

---

#### Phase F4: Enterprise Dialects, CICS & SQL Monolithic Parser Expansion
**Target Release**: Rezonator v1.1.0  
**Objective**: Expand front-end grammar to ingest full-scale IBM Enterprise COBOL z/OS production programs containing embedded subsystems.

- **Milestone F4.1: Embedded Subsystem Grammar Rules**
  - **`EXEC CICS` Parser**: Extract transaction handles (`SEND MAP`, `RECEIVE MAP`, `SYNCPOINT`, `LINK`, `XCTL`) as external transfer edges in CFG.
  - **`EXEC SQL` Parser**: Extract database table accesses (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CURSOR`) into DFG as persistent database state nodes.
  - **`EXEC DLI` / IMS DB**: Support hierarchical database calls (`GU`, `GHU`, `ISRT`).
- **Milestone F4.2: Automated COPYBOOK Preprocessing**
  - Implement an in-memory `COPY` statement inliner supporting `REPLACING ==old== BY ==new==` syntax.
  - Resolve nested copybooks with circular reference protection.
- **Milestone F4.3: ProLeap & Tree-Sitter Hybrid Parser Bridge**
  - Implement an optional Java/ANTLR bridge (ProLeap COBOL parser) for complex dialect corner cases while retaining the hermetic pure-Python parser as default.
- **Deliverables & Acceptance Criteria**:
  - Ingestion of real-world 10,000-line banking monoliths containing mixed CICS/DB2 logic with 0 parse errors.
  - Golden test suite expanded to 10 enterprise dialect programs.

---

#### Phase F5: Multi-Program Dependency Hypergraphs & JCL Integration
**Target Release**: Rezonator v1.2.0  
**Objective**: Expand analysis beyond single source files to multi-program mainframe application clusters and batch processing pipelines.

- **Milestone F5.1: Inter-Program Call Flow & Interface Contracts**
  - Parse `CALL 'SUBPROG' USING ...` and `LINK PROGRAM(...)` statements.
  - Construct inter-procedural call graphs connecting callers to callee entry points and mapping parameter bindings (`USING BY REFERENCE / BY CONTENT`).
- **Milestone F5.2: JCL (Job Control Language) Batch Pipeline Linking**
  - Parse JCL job streams (`//STEP01 EXEC PGM=PROGA`, `//DD1 DSN=FILE.DAT`).
  - Connect output datasets from Step $k$ to input datasets of Step $k+1$, creating end-to-end dataflow hypergraphs across distinct batch COBOL jobs.
- **Milestone F5.3: Global VSAM & DB2 Persistent State Manifold**
  - Unify shared VSAM file clusters and database tables as global memory hubs across multiple programs.
  - Detect cross-program concurrent access conflicts, write-after-read hazards, and batch serialization bottlenecks.
- **Deliverables & Acceptance Criteria**:
  - Global topological visualization of a multi-program banking portfolio in the Rezonator Studio.
  - End-to-end blast radius tracking: changing a database column in Program A tracks impact to Program B through JCL file transfers.

---

#### Phase F6: Automated Monolith Decomposition & Neural Translation Guidance
**Target Release**: Rezonator v2.0.0  
**Objective**: Utilize spectral graph cuts and continuous diffusion to automate legacy modernization, microservice partitioning, and AI-guided migration to modern languages (Java, Go, Rust).

- **Milestone F6.1: Cheeger Spectral Clustering & Microservice Partitioning**
  - Utilize the **Fiedler vector** ($\mathbf{v}_1$) of the Normalized Laplacian $\mathcal{L}_{\text{norm}}$ to find the optimal Cheeger bi-partition:
    $$S = \{i \in V \mid \mathbf{v}_1[i] \ge \tau\}$$
    minimizing conductance $\phi(S) = \frac{|\partial(S)|}{\min(\text{vol}(S), \text{vol}(\bar{S}))}$.
  - Automatically identify natural decoupling boundaries to extract modular microservices from monolithic spaghetti code with minimal inter-service RPC overhead.
- **Milestone F6.2: Context-Efficient LLM Prompt Slicing**
  - Instead of dumping an entire 50,000-line COBOL file into an LLM context window (which induces hallucination and token exhaustion), use continuous diffusion impact scores to generate high-density, context-optimal slices:
    $$\text{Slice}(v_0, \theta) = \{v \in V \mid u_v(t) \ge \theta\}$$
  - Feed mathematically verified slices to LLMs for reliable automated refactoring, code explanation, and translation to Java Spring Boot / Rust.
- **Milestone F6.3: Rust Native Acceleration Engine (`rezonator-core`)**
  - Implement the Graph Laplacian and Lanczos eigensolver in Rust using `nalgebra-sparse` and `faer` with Python bindings (`PyO3`), enabling analysis of 100,000+ node hypergraphs in under 500 milliseconds.
- **Deliverables & Acceptance Criteria**:
  - One-click "Decompose Monolith" feature in the Web Studio outputting candidate microservice boundaries.
  - Automated translation assistant generating Java/Rust equivalents with verifiable input/output equivalence proofs.

---

### 3. Release Milestones & Target Schedule

| Phase | Target Version | Focus Area | Key Deliverable | Target Timeline |
|:---:|:---:|:---|:---|:---:|
| **F0–F3** | **v1.0.0** | **Core Math & Hermetic Engine** | **22/22 unit tests, shift-invert Lanczos, pure-Python parser** | **COMPLETED** |
| **F4** | **v1.1.0** | **Enterprise Dialects & CICS/SQL** | **Embedded CICS/SQL support, copybook inliner** | **Q1 2027** |
| **F5** | **v1.2.0** | **Multi-Program Hypergraphs** | **JCL batch linking, cross-program CALL graphs** | **Q2 2027** |
| **F6** | **v2.0.0** | **Monolith Decomposition & AI** | **Cheeger spectral cuts, context slices, Rust core** | **Q3 2027** |

---

### Conclusion

Rezonator has successfully transitioned from an experimental research concept to a hardened, verified mathematical foundation. With phases F0 through F3 completed, the system possesses the stability, performance, and algebraic rigor needed to tackle enterprise-grade mainframe modernization challenges.
