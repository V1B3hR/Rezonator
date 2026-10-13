# Partition Recommendations and Migration Evidence Specification (Filar F6)

🟢 **DELIVERED** · Status: Complete · Scope: Filar F6 (Partition Recommendations and Migration Evidence)

---

## 1. Executive Summary

**Filar F6** addresses modernization decomposition and migration validation for legacy COBOL and mainframe application portfolios. Rather than relying on black-box neural rewrites or treating graph partitioning as an autonomous service generator, Rezonator establishes a mathematically rigorous, auditable evidence pipeline:

1. **Spectral Graph Partitioning (`rezonator/partition_recommender.py`)**:
   - Computes Fiedler-vector sweeps on the sparse graph Laplacian.
   - Evaluates partition candidates against the Cheeger conductance bound ($\frac{\lambda_1}{2} \le \phi \le \sqrt{2 \lambda_1}$).
   - Detects all crossing interaction edges with source-level line anchors.
   - Explicitly penalizes shared DB2 table ownership, distributed file dataset exchange, and sequential JCL batch transaction boundary violations.
   - Quantifies uncertainty introduced by unresolved dynamic `CALL` statements.
   - Mandates human architect review: all decomposition candidates are tagged `PENDING_ARCHITECT_REVIEW`.

2. **Migration Verification & Differential Testing (`rezonator/migration_verifier.py`)**:
   - Executes baseline and candidate programs under bounded operational semantics via `CobolRuntime`.
   - Measures variable state divergences and pinpoint trace branch divergences.
   - Validates domain invariants (e.g. non-negative balance constraints, zero error flags).
   - Gathers structural graph signals (NetLSD heat trace distance, Fiedler eigenvalue shift, Chladni modal surface overlap, and cycle topology preservation).
   - Emits content-addressed, versioned evidence documents (`sokol.migration.v1`).

---

## 2. Mathematical Formulation

### 2.1 Graph Laplacian & Fiedler Vector

Let $G = (V, E)$ be the symmetrized dependency graph derived from an application portfolio or program control/data flow, with node degree $d_i = \sum_{j} A_{ij}$. The diagonal degree matrix is $D = \operatorname{diag}(d_1, \dots, d_n)$, and the unnormalized graph Laplacian is:

$$L = D - A$$

The spectrum of $L$ is ordered as $0 = \lambda_0 \le \lambda_1 \le \lambda_2 \le \dots \le \lambda_{n-1}$. The second smallest eigenvalue $\lambda_1$ is the **algebraic connectivity**, and its corresponding eigenvector $v_2$ is the **Fiedler vector**:

$$v_2 = \arg\min_{\substack{v \perp \mathbf{1} \\ \|v\|_2 = 1}} v^T L v$$

For $N \le 128$, the eigensystem is solved via `scipy.linalg.eigh`. For $N > 128$, the sparse shift-invert eigensolver `scipy.sparse.linalg.eigsh(L, k=2, sigma=1e-5, which="LM")` computes $v_2$ directly on the SciPy CSR representation without any dense matrix allocation.

### 2.2 Conductance & The Cheeger Inequality

For any subset of vertices $S \subset V$, let $\bar{S} = V \setminus S$. The volume of $S$ is $\operatorname{vol}(S) = \sum_{i \in S} d_i$, and the cut weight is:

$$\operatorname{cut}(S, \bar{S}) = \sum_{i \in S, j \in \bar{S}} A_{ij}$$

The **conductance** $\phi(S)$ measures the fraction of edge volume crossing the boundary relative to the smaller partition:

$$\phi(S) = \frac{\operatorname{cut}(S, \bar{S})}{\min(\operatorname{vol}(S), \operatorname{vol}(\bar{S}))}$$

By the discrete Cheeger inequality, the optimal conductance $\phi^* = \min_S \phi(S)$ is tightly bounded by the algebraic connectivity $\lambda_1$:

$$\frac{\lambda_1}{2} \le \phi^* \le \sqrt{2 \lambda_1}$$

The Fiedler sweep algorithm orders vertices according to the sorted entries of $v_2$:

$$\pi(1), \pi(2), \dots, \pi(n) \quad \text{such that} \quad v_2[\pi(1)] \le v_2[\pi(2)] \le \dots \le v_2[\pi(n)]$$

Sweeping split indices $k \in \{1, \dots, n-1\}$ where $S_k = \{\pi(1), \dots, \pi(k)\}$ produces candidate cuts guaranteed to satisfy the Cheeger upper bound.

### 2.3 Domain Friction & Multi-Objective Scoring

A pure spectral cut minimizes graph conductance but ignores mainframe architectural realities. Rezonator incorporates domain friction penalties into candidate evaluation:

$$\operatorname{Score}(S) = w_{\phi} \cdot \phi(S) + w_{\text{tbl}} \cdot N_{\text{shared\_tables}}(S) + w_{\text{dsn}} \cdot N_{\text{shared\_dsns}}(S) + w_{\text{tx}} \cdot N_{\text{tx\_violations}}(S)$$

- **Shared Relational Tables ($N_{\text{shared\_tables}}$)**: Detects DB2 tables accessed by programs on both sides of the cut ($S$ and $\bar{S}$). Splitting database ownership requires distributed transactions (2PC) or event sourcing.
- **Shared Datasets ($N_{\text{shared\_dsns}}$)**: Detects VSAM or sequential files read/written across partitions.
- **Transaction Boundary Violations ($N_{\text{tx\_violations}}$)**: Detects sequential JCL step chains (`STEP_SEQUENCE`) broken across partitions.
- **Uncertainty Score ($\mu$):**

$$\mu = \frac{N_{\text{dynamic\_crossings}}}{N_{\text{total\_crossings}}}$$

Unresolved dynamic calls (`CALL WS-VAR`) directly increase the candidate's uncertainty score.

---

## 3. Migration Verification Engine (`rezonator/migration_verifier.py`)

### 3.1 Differential Execution Workflow

To validate migrated, refactored, or translated code, Rezonator executes baseline and candidate implementations against shared test cases:

```
[Baseline COBOL]   --> CobolRuntime.run() --> State A: {Variables, Trace, Steps}
                                                              |
                                                              v  Differential Comparator
                                                              |  - Affected Variable Diffs
                                                              |  - Trace Divergence Step
                                                              v
[Candidate Code]  --> CobolRuntime.run() --> State B: {Variables, Trace, Steps}
                                                              |
                                                              v
                                                    Domain Invariant Evaluator
                                                    - Balance >= 0
                                                    - Return Code == 0
```

### 3.2 Dual Structural and Semantic Signals

| Category | Metric / Signal | Formula / Origin | Meaning |
| :--- | :--- | :--- | :--- |
| **Semantic** | Equivalence Rate | $P_{\text{passed}} / P_{\text{total}}$ | Fraction of input test cases with zero output variable divergence |
| **Semantic** | Variable State Diff | $V_A[k] \neq V_B[k]$ | Exact values of diverged variables upon program termination |
| **Semantic** | Trace Divergence Step | $\min \{i : \text{trace}_A[i] \neq \text{trace}_B[i]\}$ | Exact execution step where control flow paths split |
| **Semantic** | Domain Invariants | $\operatorname{eval}(\text{expr}, V_B) == \text{True}$ | Business invariants asserted over candidate terminal states |
| **Structural** | NetLSD Distance | $\| \Phi(A) - \Phi(B) \|_2$ | Heat trace signature distance across normalized graph spectra |
| **Structural** | Fiedler Shift | $\lambda_{1}(B) - \lambda_{1}(A)$ | Shift in algebraic connectivity and graph bottleneck structure |
| **Structural** | Cymatic Overlap | $\frac{w_A \cdot w_B}{\|w_A\| \|w_B\|}$ | Cosine correlation between 2D Chladni modal surfaces |
| **Structural** | Cycle Preservation | $\operatorname{deadlock}(A) == \operatorname{deadlock}(B)$ | Detection of introduced or eliminated circular dependencies |

---

## 4. REST API Endpoints

### 4.1 `POST /api/partition`
Computes explainable decomposition candidates from a portfolio manifest or the default enterprise corpus.

- **Request**:
  ```json
  {
    "top_k": 3,
    "format": "json"
  }
  ```
- **Response (`sokol.partition.v1`)**:
  ```json
  {
    "schema_version": "sokol.partition.v1",
    "manifest_id": "man-CorpusEnterprisePortfolio-...",
    "candidate_count": 3,
    "candidates": [
      {
        "candidate_id": "cand-01-...",
        "name": "Candidate Boundary 1 (phi=0.125)",
        "partition_a": ["PGM:CBL001", "PGM:CBL002"],
        "partition_b": ["PGM:CBL003", "PGM:CBL004", "PGM:CBL005", "PGM:CBL006"],
        "conductance": 0.125,
        "cheeger_bound_lower": 0.045,
        "cheeger_bound_upper": 0.424,
        "crossing_edges": [...],
        "shared_tables": ["ACCOUNTS"],
        "transaction_boundaries_violated": 1,
        "uncertainty_score": 0.0,
        "architect_review_status": "PENDING_ARCHITECT_REVIEW",
        "rationale": "Spectral Cheeger partition with conductance phi = 0.125..."
      }
    ]
  }
  ```

### 4.2 `POST /api/migration`
Executes differential tests and domain invariant validations across baseline and modernized programs.

- **Request**:
  ```json
  {
    "baseline_source": "...",
    "candidate_source": "...",
    "test_cases": [
      {
        "test_id": "tc-standard",
        "input_overrides": {"WS-TRANSACTION-AMOUNT": 500},
        "invariants": ["NO_NEGATIVE_BALANCE"]
      }
    ],
    "invariants": [
      {
        "name": "NO_NEGATIVE_BALANCE",
        "expression": "WS-BALANCE >= 0",
        "severity": "CRITICAL"
      }
    ],
    "format": "json"
  }
  ```
- **Response (`sokol.migration.v1`)**:
  ```json
  {
    "schema_version": "sokol.migration.v1",
    "evidence_id": "migeve-...",
    "epistemic_status": "OBSERVED_VERIFIED",
    "architect_review_status": "PENDING_ARCHITECT_REVIEW",
    "total_tests": 1,
    "passed_tests": 1,
    "equivalence_rate": 1.0,
    "structural_signals": {
      "netlsd_distance": 0.0,
      "fiedler_delta": 0.0,
      "cymatic_similarity": 1.0,
      "cycle_topology_preserved": true
    },
    "test_runs": [...],
    "domain_invariants_evaluated": 1,
    "domain_invariants_violated": []
  }
  ```

---

## 5. Epistemic Invariants & Governance Rules

> [!IMPORTANT]
> **Rule 1: A spectral cut is a topological heuristic, not an autonomous microservice rewrite.**
> Spectral graph partitioning minimizes edge cuts; it cannot foresee distributed latency, network partitions, or organizational Conway boundaries. Every partition recommendation remains `PENDING_ARCHITECT_REVIEW`. Rezonator suggests and explains; human architects decide.

> [!WARNING]
> **Rule 2: Structural signals are not formal proofs of semantic equivalence.**
> A NetLSD distance of zero or the absence of detected cycles indicates identical graph topology; it does **not** prove functional correctness. Functional equivalence requires comprehensive differential testing across all production workload spaces.

> [!NOTE]
> **Rule 3: Deterministic Hermetic Execution.**
> All matrix calculations, differential runs, and JSONL evidence serialization execute locally in sub-5 seconds without external model APIs or network access.
