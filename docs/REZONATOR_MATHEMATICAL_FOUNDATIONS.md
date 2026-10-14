# MATHEMATICAL FOUNDATIONS OF REZONATOR
## Finite Program Graphs, Spectral Methods, and Static Analysis for Mainframe Code

---

### Abstract & Intuitive Physical Paradigm

Legacy core-banking and insurance systems often contain long-lived COBOL programs with control-flow and shared-data dependencies spread across paragraphs, files, and copybooks. Reconstructing those dependencies from source alone can be labor-intensive.

Text-only inspection or summarization can miss non-local `PERFORM ... THRU` relationships and data dependencies through shared `WORKING-STORAGE`. Rezonator aims to make selected relationships explicit by parsing a supported source subset into a graph; parser coverage limits still apply.

**Rezonator** represents supported program constructs as a **finite graph** and applies discrete graph operators. The following hydraulic picture is only an explanatory analogy:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE HYDRAULIC & PHYSICAL INTUITION                              │
│                                                                                        │
│  In Rezonator, a COBOL program is viewed not as text, but as a hydraulic network:      │
│  • Statements (VERBS) are valves and directional pipes.                                │
│  • Working-Storage Data Items are pressurized fluid reservoirs.                       │
│  • A User Transaction (Deposit/Withdrawal) is a pressure impulse injected at t=0.      │
│  • Control Flow branches (IF/ELSE) are fluid bifurcation junctions.                   │
│  • A reported CFG cycle is a possible loop, not proof of infinite execution.           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

The implemented core represents a parsed program as a finite graph and applies graph operators, spectral methods, and diffusion equations to that representation. The hydraulic and physical language in this document is an explanatory analogy; the current software does not construct a continuous manifold or prove full source-program semantics.

> **Implementation scope:** The parser handles a supported subset of COBOL and explicitly reports selected unsupported statements. GraphField operators are sparse CSR in the normal analysis path. The cycle analyzer uses SCCs and bounded in-component cycle enumeration, but its hazard labels remain heuristics; they do not prove termination. Comparative spectral scores describe parsed graph structure, not behavioral equivalence or migration safety. Consult [REZONATOR_ROADMAP.md](../REZONATOR_ROADMAP.md) for implementation status and remaining validation.

---

### 1. From Source Code to Unified Graph Field

A COBOL program is ingested into an explicit, typed, directed program dependence graph:
$$\mathcal{G} = (V, E)$$

#### 1.1 Vertex Decomposition ($V$)
The vertex set $V = V_{\text{stmt}} \cup V_{\text{var}}$ consists of two distinct topological classes:
1. **Statement Nodes ($V_{\text{stmt}}$)**: Every executable verb (`PERFORM`, `IF`, `MOVE`, `ADD`, `SUBTRACT`, `COMPUTE`, `STOP RUN`, `GOBACK`) forms a basic block node labeled by its paragraph and line number:
   $$v \in V_{\text{stmt}} \iff v = (\text{paragraph}, \text{lineno}, \text{opcode}, \text{reads}, \text{writes})$$
2. **Variable State Hubs ($V_{\text{var}}$)**: Every declared record or field in `WORKING-STORAGE SECTION` forms a persistent state reservoir node:
   $$v \in V_{\text{var}} \iff v = (\text{var\_name}, \text{level}, \text{picture}, \text{initial\_value})$$

#### 1.2 Edge Classes & Physical Weights ($E$)
The edge set $E = E_{\text{cfg}} \cup E_{\text{dfg}}$ contains directed relationships weighted by physical interaction strength:
- **Control Flow Edges ($E_{\text{cfg}}$)**:
  - Sequential transitions: $(u, v) \in E_{\text{seq}}$ with weight $w = 1.0$.
  - Branch conditions: $(u, v) \in E_{\text{branch\_true}}$ and $E_{\text{branch\_false}}$ with weight $w = 1.0$.
  - Inter-procedural calls: $(u, v) \in E_{\text{call}}$ (`PERFORM paragraph`) with weight $w = 1.5$.
  - Call returns: $(u, v) \in E_{\text{return}}$ (from paragraph exits to caller continuation) with weight $w = 1.2$.
  - Paragraph fallthroughs: $(u, v) \in E_{\text{fallthrough}}$ with weight $w = 0.8$.
- **Data Flow Edges ($E_{\text{dfg}}$)**:
  - State read: $(v_{\text{var}}, u_{\text{stmt}}) \in E_{\text{read}}$ with weight $w = 1.2$.
  - State write: $(u_{\text{stmt}}, v_{\text{var}}) \in E_{\text{write}}$ with weight $w = 1.5$.
  - Def-Use chains: direct dependency between earlier writers and downstream readers with weight $w = 1.0$.

---

### 2. Matrix Operators & The Graph Laplacian

Let $N = |V|$ be the total number of vertices ($N = |V_{\text{stmt}}| + |V_{\text{var}}|$).

#### 2.1 Adjacency Matrices
The **Directed Adjacency Matrix** $A_{\text{dir}} \in \mathbb{R}^{N \times N}$ represents asymmetric causal dependencies:
$$A_{\text{dir}}[i, j] = \sum_{e = (v_i, v_j) \in E} w(e)$$

For spectral decomposition, the **Symmetric Adjacency Matrix** $A \in \mathbb{R}^{N \times N}$ represents undirected coupling:
$$A = \frac{1}{2}\left(A_{\text{dir}} + A_{\text{dir}}^T\right)$$

#### 2.2 Degree Matrix
The diagonal **Degree Matrix** $D \in \mathbb{R}^{N \times N}$ is defined by row sums of $A$:
$$D_{ii} = \sum_{j=1}^N A[i, j], \quad D_{ij} = 0 \text{ for } i \neq j$$

#### 2.3 Combinatorial Graph Laplacian
The unnormalized **Combinatorial Laplacian** $L \in \mathbb{R}^{N \times N}$ is:
$$L = D - A$$

For any vector $x \in \mathbb{R}^N$, the associated quadratic form represents the global Dirichlet energy:
$$x^T L x = \frac{1}{2} \sum_{i=1}^N \sum_{j=1}^N A[i, j] \left(x_i - x_j\right)^2 \ge 0$$
Thus, $L$ is symmetric and positive semi-definite ($L \succeq 0$). The row sums satisfy $\sum_{j=1}^N L_{ij} = 0$, meaning the constant vector $\mathbf{1} = (1, 1, \dots, 1)^T$ is always an eigenvector with eigenvalue $\lambda_0 = 0$.

#### 2.4 Fan Chung Symmetric Normalized Laplacian
To eliminate bias from high-degree memory hubs (e.g. widely used status flags), Rezonator implements the **Fan Chung Normalized Laplacian** $\mathcal{L}_{\text{norm}}$:
$$\mathcal{L}_{\text{norm}} = D^{-1/2} L D^{-1/2} = I - D^{-1/2} A D^{-1/2}$$
Explicitly:
$$\mathcal{L}_{\text{norm}}[i, j] = \begin{cases}
1 - \frac{A[i, i]}{D_{ii}}, & \text{if } i = j \text{ and } D_{ii} > 0 \\
-\frac{A[i, j]}{\sqrt{D_{ii} D_{jj}}}, & \text{if } i \neq j \text{ and } D_{ii} D_{jj} > 0 \\
0, & \text{otherwise}
\end{cases}$$

**Fundamental Properties**:
1. **Normalized Spectrum**: All eigenvalues $\lambda_k$ of $\mathcal{L}_{\text{norm}}$ lie strictly in the range:
   $$0 = \lambda_0 \le \lambda_1 \le \lambda_2 \le \dots \le \lambda_{N-1} \le 2$$
2. **Connected Components**: The multiplicity of the zero eigenvalue ($\lambda = 0$) is exactly equal to the number of connected components in the graph.
3. **Algebraic Connectivity (Fiedler Value $\lambda_1$)**: The Fiedler value describes connectivity of the represented graph and can motivate review of candidate cuts. A zero value indicates multiple modeled components under the current operator; it does not by itself identify isolated business logic or unreferenced variables.

---

### 3. Spectral Decomposition & NetLSD Signatures

#### 3.1 Cheeger's Inequality & Program Modularity
The **conductance** $\phi(S)$ of a set of statements $S \subset V$ measures the ratio of cross-module calls to internal module execution:
$$\phi(S) = \frac{|\partial(S)|}{\min(\text{vol}(S), \text{vol}(\bar{S}))}, \quad \text{where } \text{vol}(S) = \sum_{i \in S} D_{ii}$$
By **Cheeger's Inequality**, the normalized Fiedler value $\lambda_1$ bounds the optimal program partitioning:
$$\frac{\lambda_1}{2} \le \min_{S \subset V} \phi(S) \le \sqrt{2 \lambda_1}$$
A low $\lambda_1$ indicates weak connectivity in this weighted, symmetrized graph model. It can motivate review of candidate partitions, but does not by itself establish clean business modules or viable microservice boundaries.

#### 3.2 NetLSD Multi-Scale Heat Trace
Comparing two programs $A$ and $B$ by zero-padding raw eigenvalue lists creates artificial distance artifacts when $N_A \neq N_B$. 

Rezonator employs **NetLSD (Network Laplacian Spectral Distance)** (Tsitsulin et al., KDD 2018). The heat kernel trace $\Phi(t)$ at time scale $t$ is:
$$\Phi(t) = \text{Tr}\left(\exp(-t \mathcal{L}_{\text{norm}})\right) = \sum_{k=0}^{N-1} \exp(-t \lambda_k)$$
Normalized by vertex count:
$$h(t) = \frac{1}{N} \Phi(t) = \frac{1}{N} \sum_{k=0}^{N-1} \exp(-t \lambda_k)$$
We sample $h(t)$ across 25 logarithmically spaced time scales $t \in [10^{-2}, 10^2]$. 
- Small $t$ ($10^{-2}$): Captures fine-grained local statement structures (e.g. arithmetic blocks).
- Large $t$ ($10^2$): Captures global macro-architecture and inter-procedural flow.

The **NetLSD Topological Distance** between program $\mathcal{G}_A$ and $\mathcal{G}_B$ is:
$$D_{\text{NetLSD}}(\mathcal{G}_A, \mathcal{G}_B) = \left( \sum_{s=1}^{25} \left| h_A(t_s) - h_B(t_s) \right|^2 \right)^{1/2}$$
This distance is:
- **Permutation Invariant**: Renaming paragraphs or reordering variables does not alter the spectrum.
- **Size Adaptive**: Smoothly compares 20-node routines against 500-node monoliths.

#### 3.3 Topologiczny Wzór 3D: Spektralna Redukcja Obliczeń

Trójwymiarowe zanurzenie spektralne oparte na obciętej dekompozycji znormalizowanego laplasjanu Fan-Chunga zastępuje pełne operacje na grafie rzędu $\mathcal{O}(N^3)$ przez operacje na macierzach niskiego rzędu ($\mathcal{O}(N \cdot k^2)$ dla $k=3$), zachowując ścisłą zgodność matematyczną dla kluczowych metryk spektralnych wykorzystywanych w Rezonatorze.

##### 1. Definicja i baza zanurzenia 3D
Dla grafu $\mathcal{G} = (V, E)$, $|V| = N$, ze znormalizowanym laplasjanem symetrycznym $\mathcal{L}_{\text{norm}} = I - D^{-1/2} A D^{-1/2} \in \mathbb{R}^{N \times N}$ i uporządkowanymi parami własnymi $0 = \lambda_0 \le \lambda_1 \le \lambda_2 \dots \le \lambda_{N-1}$, definiujemy macierz zanurzenia $X \in \mathbb{R}^{N \times 3}$:

$$X = \begin{bmatrix} \phi_1 & \phi_2 & \phi_3 \end{bmatrix} \begin{bmatrix} \sqrt{\lambda_1} & 0 & 0 \\ 0 & \sqrt{\lambda_2} & 0 \\ 0 & 0 & \sqrt{\lambda_3} \end{bmatrix} \in \mathbb{R}^{N \times 3}$$

Wiersz $X_{i, :} \in \mathbb{R}^3$ jest współrzędną węzła $i$ w trójwymiarowej przestrzeni spektralnej. Współrzędne te kodują globalną topologię grafu – odległości euklidesowe w tej przestrzeni aproksymują odległości dyfuzyjne na grafie.

##### 2. Tabela redukcji obliczeniowej

| Metryka | Wzór oryginalny | Wzór zredukowany (3D) | Złożoność |
|:---|:---|:---|:---:|
| **Wartość Fiedlera $\lambda_1$** | $\min_{v \perp 1} \frac{v^T L v}{v^T v}$ | $\lambda_1 = \|X_{:, 0}\|_2^2$ | $\mathcal{O}(N)$ |
| **Wektor Fiedlera $v_1$** | Rozwiązanie problemu własnego | $v_1 = X_{:, 0} / \|X_{:, 0}\|_2$ | $\mathcal{O}(N)$ |
| **NetLSD $\Phi(t)$ / $h(t)$** | $\frac{1}{N}\text{Tr}(\exp(-t \mathcal{L}_{\text{norm}}))$ | $h_{\text{3D}}(t) = \frac{1}{N}\left(1 + \sum_{k=1}^3 \exp(-t \lambda_k)\right)$ | $\mathcal{O}(1)$ |
| **Dystans spektralny $d(i, j)$** | $\|\phi_i - \phi_j\|_2$ | $d(i, j) = \|X_{i, :} - X_{j, :}\|_2$ | $\mathcal{O}(1)$ |
| **Half-life $\tau_{1/2}$** | $\frac{\ln 2}{\alpha \lambda_{\min > 0}}$ | $\tau_{1/2} = \frac{\ln 2}{\alpha \lambda_1} = \frac{\ln 2}{\alpha \|X_{:, 0}\|_2^2}$ | $\mathcal{O}(1)$ |

Całkowity koszt analityczny po wyznaczeniu 3 najmniejszych niezerowych modów przez algorytm Lanczos ($\mathcal{O}(N \cdot m)$) spada z $\mathcal{O}(N^3)$ do $\mathcal{O}(N)$ dla całego grafu i $\mathcal{O}(1)$ dla operacji na parach węzłów.

##### 3. Dowód zgodności i granica błędu aproksymacji (Truncation Bound)
- **Metryki oparte na pierwszych trzech momentach**: Ponieważ wektory własne $\phi_k$ są ortonormalne ($\langle \phi_k, \phi_l \rangle = \delta_{kl}$), dla dowolnej funkcji $g(\lambda_1, \lambda_2, \lambda_3)$ zachodzi $g(\lambda_1, \lambda_2, \lambda_3) = g(\|X_{:, 0}\|_2^2, \|X_{:, 1}\|_2^2, \|X_{:, 2}\|_2^2)$, co gwarantuje 100% zgodności analitycznej.
- **Pełne widmo NetLSD**: Dla sygnatur uwzględniających całe widmo, zanurzenie 3D stanowi kontrolowaną aproksymację rzędu 3. Ponieważ $\lambda_k \ge \lambda_4$ dla wszystkich $k \ge 4$, błąd obcięcia ogona jest ściśle ograniczony przez:
  $$|h(t) - h_{\text{3D}}(t)| = \frac{1}{N} \sum_{k=4}^{N-1} \exp(-t \lambda_k) \le \frac{N - 4}{N} \exp(-t \lambda_4) \le \exp(-t \lambda_4)$$
  Dla czasów dyfuzji makroskopowej ($t \ge 1$), składnik $\exp(-t \lambda_4)$ gwałtownie zanika, dając asymptotyczną zbieżność do pełnego śladu ciepła.

##### 4. Skalowanie wydajnościowe (do limitu 50 000 węzłów)
Dla grafu o $N = 50\,000$ węzłów:
- Pełna diagonalizacja gęsta $\mathcal{O}(N^3) \approx 1.25 \times 10^{14}$ operacji.
- Z redukcją 3D: $\mathcal{O}(N \cdot m)$ z $m \approx 100$ iteracjami Lanczosa daje $\approx 5 \times 10^6$ operacji.
- Przyspieszenie: ponad 7 rzędów wielkości bez utraty stabilności numerycznej. Warstwa ta jest zintegrowana w modułach [`diamond_yant.py`](../rezonator/diamond_yant.py) (ekstrakcja bazy $X$, $h_{\text{3D}}(t)$) oraz [`diffusion_ranker.py`](../rezonator/diffusion_ranker.py) (`rank_by_spectral_distance`).

---

### 4. Continuous Diffusion Operators: Undirected Heat vs Directed Blast Radius

Rezonator implements two distinct continuous diffusion mechanisms with strict physical conservation laws:

#### 4.1 Undirected Structural Heat Diffusion
Governed by the symmetric Combinatorial Laplacian $L = D - A$:
$$\frac{\partial u}{\partial t} = -\alpha L u \implies u(t) = \exp(-\alpha L t) u_0$$
- **Undirected Physical Dispersion**: Because $L$ is symmetric, heat propagates symmetrically across topological connections regardless of CFG execution flow directions.
- **Strict Mass Conservation**: The row and column sums of $L$ equal zero ($\mathbf{1}^T L = \mathbf{0}^T$), guaranteeing that total signal mass is strictly conserved: $\sum_{i=1}^N u_i(t) = \sum_{i=1}^N u_{0, i}$.
- **Relaxation Half-Life**:
  $$\tau_{1/2} = \frac{\ln 2}{\alpha \lambda_{\min > 0}}$$
  where $\lambda_{\min > 0}$ is the smallest strictly positive eigenvalue above numerical zero tolerance ($10^{-4}$). For a connected graph, this equals the Fiedler value $\lambda_1$. For a disconnected graph with $k$ components ($\lambda_0 = \dots = \lambda_{k-1} = 0$), it correctly identifies the relaxation rate toward component-wise steady state, avoiding false infinite half-lives.

#### 4.2 Directed Forward Blast Radius (Continuous Markov Chain)
To model directed causality—where execution flows strictly forward and outputs depend only on preceding inputs—we define a continuous-time Markov process on the directed graph.

Let $d_{\text{out}}(i) = \sum_{j=1}^N A_{\text{dir}}[i, j]$. The row-stochastic transition probability matrix $P \in \mathbb{R}^{N \times N}$ is:
$$P_{ij} = \begin{cases} \frac{A_{\text{dir}}[i, j]}{d_{\text{out}}(i)}, & \text{if } d_{\text{out}}(i) > 0 \\ 0, & \text{otherwise} \end{cases}$$
Terminal sink nodes (`STOP RUN`, `GOBACK`) receive absorbing self-loops ($P_{ii} = 1.0$), ensuring that probability mass is conserved and absorbed rather than dropped.

The continuous-time Markov generator $Q \in \mathbb{R}^{N \times N}$ governing forward probability flow is:
$$Q = P^T - I$$
Since $P \mathbf{1} = \mathbf{1}$, the columns of $Q$ sum to zero ($\mathbf{1}^T Q = \mathbf{0}^T$), preserving total probability mass $\sum_{i=1}^N u_i(t) = 1.0$.

Given a seed perturbation at statement $v_0$ (represented as impulse $u_0 = e_{v_0}$):
$$\frac{du}{dt} = Q u = (P^T - I) u \implies u(t) = \exp(Q t) u_0 = \exp\left((P^T - I) t\right) u_0$$

#### 4.3 Physical Interpretation & Reachability:
- **Topological Reachability vs Ranking**: For any $t > 0$, every topologically reachable node in the continuous chain receives strictly positive probability mass. The analyzer reports exact reachability via graph traversal (`exact_reachable_count`), while numerical thresholding ($u_i(t) \ge 10^{-4}$) filters negligible numerical tails for impact ranking.
- **In-Degree Normalization**: Raw $\exp(Q t) u_0$ mass naturally accumulates at high in-degree structural hubs. Degree normalization ($u_i(t) / d_{\text{in}}(i)$) is supported to isolate genuine perturbation flow from topological convergence.
- **Model Bound**: Diffusion scores are structural graph signals, not formal source-level taint proofs or execution guarantees.

---

### 5. Sparse Operators and Numerical Solvers (Increment B)

#### 5.1 Shift-Invert Lanczos Eigensolver
For large symmetric sparse Laplacians, Rezonator uses ARPACK's shift-invert eigensolver to obtain low modes. The negative shift moves the target near-zero eigenvalues away from a singular factorization:
$$(L - \sigma I)^{-1} v = \mu v, \quad \text{with } \sigma = -10^{-4} < 0$$
Since $L \succeq 0$, choosing $\sigma < 0$ guarantees that $(L - \sigma I)$ is strictly positive definite and non-singular. Under the Cayley mapping:
$$\mu_k = \frac{1}{\lambda_k - \sigma}$$
The transformation maps the smallest $\lambda_k$ to large-magnitude transformed eigenvalues. Rezonator first tries `eigsh(..., sigma=-10^{-4}, which='LM')`, then retries with `which='SM'` if needed. If sparse solving still fails on a large graph, the analyzer raises an explicit error; it does not fall back to a dense $N \times N$ allocation. Runtime depends on graph structure, conditioning, SciPy/ARPACK, and machine. The measurements in [REZONATOR_BENCHMARKS.md](../REZONATOR_BENCHMARKS.md) are observations, not asymptotic guarantees.

#### 5.2 Krylov Subspace Matrix Exponential Multipliers
To compute $u(t) = \exp(Q t) u_0$ without materializing dense $N \times N$ matrix exponentials, Rezonator projects the operator into a small $m$-dimensional Krylov subspace:
$$\mathcal{K}_m(Q, u_0) = \text{span}\{u_0, Q u_0, Q^2 u_0, \dots, Q^{m-1} u_0\}$$
Using the Arnoldi iteration, $Q V_m = V_m H_m + h_{m+1, m} v_{m+1} e_m^T$, the matrix exponential is approximated by:
$$\exp(Q t) u_0 \approx \|u_0\|_2 V_m \exp(H_m t) e_1$$
On the recorded environment, the isolated synthetic $N=10{,}000$ sparse kernel produced a 10-point diffusion trajectory in **77.57 ms**. A separate end-to-end generated COBOL measurement covers 5,001 graph nodes; neither timing establishes production-corpus throughput or operation at the 50,000-node hard limit.

#### 5.3 Hutchinson Stochastic Trace Estimator
For graphs with $N \ge 100$, computing the exact NetLSD heat trace is replaced with a 15-probe Hutchinson estimate of its normalized trace:
$$h(t) = \frac{1}{N}\text{Tr}\left(\exp(-t \mathcal{L}_{\text{norm}})\right) \approx \frac{1}{M} \sum_{m=1}^M v_m^T \exp\left(-t \mathcal{L}_{\text{norm}}\right) v_m$$
where each entry of $v_m$ is an independent Rademacher sign scaled by $1/\sqrt{N}$, so $\mathbb{E}[v_m v_m^T] = I/N$. The implementation fixes the random seed for repeatable probes. The estimator is unbiased for the normalized trace; the engine additionally computes and exposes the sample standard error across the $M$ probes ($\sigma / \sqrt{M}$) to quantify the stochastic noise floor.

---

### 6. CFG Cycles and Static Hazard Signals

Let $\mathcal{G}_{\text{cfg}} = (V_{\text{stmt}}, E_{\text{cfg}})$ be the directed Control Flow Graph.

Strongly connected components (SCCs) group mutually reachable nodes; the current implementation obtains SCCs with NetworkX's linear-time SCC routine and bounds simple-cycle enumeration within each component.

A directed cycle in the parsed CFG establishes that the graph model contains a possible repeated path. It does not establish that the path is feasible for program data, that its guards remain true, or that execution repeats forever. Likewise, an acyclic parsed CFG only establishes absence of cycles in the represented graph; unsupported syntax and unresolved external calls limit any conclusion about the full program.

The analyzer reports trapped SCCs and selected cycle/guard hazards. Its cycle search is budgeted, and exhaustion is recorded explicitly. These are structural observations and heuristic hazard signals, not termination proofs.

---

### 7. Comparative Refactoring Divergence Metrics

When comparing Program A (original) with Program B (refactored), the API reports structural metrics including NetLSD distance, Fiedler-value differences, Chladni-surface similarity, diffusion half-life difference, node growth, and the current cycle-hazard flags. These values describe the parsed graph model.

#### 7.1 Current Structural Score and Its Limits
The current comparator calculates a base score from NetLSD distance:
$$F_{\text{base}} = \max(0, \min(100, 100(1 - 2.5 D_{\text{NetLSD}})))$$
It sets the score to zero if Program B receives the heuristic deadlock flag while A does not; if B has that flag in both inputs, it caps the score at 20% of the base. Otherwise it returns the base score. The implemented formula does not include the Fiedler delta or cymatic similarity.

The API emits labels including `STRUCTURAL_MODULAR_EXTENSION`, `HAZARD_REDUCED`, and `CRITICAL_REGRESSION`. These are heuristic structural labels, not calibrated confidence, functional-equivalence results, or safety certificates. Differential tests and domain invariants are required to assess behavioral preservation.

---

### Summary Table of Mathematical Operators

| Mathematical Concept | Formal Notation | Operational Role in Rezonator |
|:---|:---:|:---|
| **Normalized Laplacian** | $\mathcal{L}_{\text{norm}} = I - D^{-1/2} A D^{-1/2}$ | Invariant spectral field; bounded spectrum $[0, 2]$. |
| **Algebraic Connectivity** | $\lambda_1(\mathcal{L}_{\text{norm}})$ | Measures connectivity in the modeled graph; it does not by itself prove code is dead or unreachable. |
| **NetLSD Signature** | $h(t) = \frac{1}{N}\text{Tr}(\exp(-t \mathcal{L}_{\text{norm}}))$ | Multiscale topological fingerprint; invariant to size & reordering. |
| **Directed Markov Generator**| $Q = P^T - I$ | Continuous causal operator for forward impact tracking. |
| **Blast Radius Trajectory**| $u(t) = \exp(Q t) u_0$ | Pinpoints affected downstream code following a mutation. |
| **Shift-Invert Lanczos** | $(L - \sigma I)^{-1} v = \mu v, \; \sigma < 0$ | High-speed ($1.5\text{ ms}$) sparse modal solver for $N \ge 1,000$. |
| **3D Spectral Embedding** | $X = [\phi_1, \phi_2, \phi_3] \operatorname{diag}(\sqrt{\lambda_1}, \sqrt{\lambda_2}, \sqrt{\lambda_3})$ | Low-rank coordinates reducing $\mathcal{O}(N^3)$ spectral analysis to $\mathcal{O}(N)$. |
| **3D Reduced NetLSD** | $h_{\text{3D}}(t) = \frac{1}{N}(1 + \sum_{k=1}^3 e^{-t \lambda_k})$ | $\mathcal{O}(1)$ heat trace approximation with controlled error $\le e^{-t \lambda_4}$. |
| **3D Spectral Distance** | $d(i, j) = \|X_{i, :} - X_{j, :}\|_2$ | $\mathcal{O}(1)$ pairwise topological distance approximating continuous diffusion coupling. |
| **CFG cycle analysis** | Directed cycles in the parsed CFG | Reports possible recurring paths and heuristic hazards; does not prove general program termination. |
