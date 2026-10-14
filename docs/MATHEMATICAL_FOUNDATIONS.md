# MATHEMATICAL FOUNDATIONS OF REZONATOR
## Graph Operators, Spectral Analysis, and Static Code Intelligence

---

### Abstract
Legacy COBOL systems have control and data dependencies that are difficult to inspect from source text alone. **Rezonator** maps supported parsed constructs to a finite program-dependence graph containing control-flow and data-flow edges, then derives discrete graph operators.

By applying:
1. **Fan Chung Normalized Laplacian Spectral Analysis** ($\mathcal{L}_{\text{norm}} = I - D^{-1/2} A D^{-1/2}$),
2. **NetLSD Multi-Scale Normalized Heat Trace Distance** ($h(t) = \frac{1}{N}\text{Tr}(\exp(-t \mathcal{L}_{\text{norm}}))$),
3. **Directed Forward Impact Diffusion / Blast Radius** ($\dot{u} = (P^T - I)u \implies u(t) = \exp((P^T - I)t) u_0$),
4. **CFG cycle enumeration and heuristic hazard reporting**,

the parsed graph can be analyzed for structural metrics, impact propagation, and possible cycle hazards. Results are deterministic for a given graph and options, but their source-level meaning is limited by parser coverage.

> **Implementation scope:** The parser supports a subset of COBOL and reports selected unsupported statements explicitly. GraphField operators use SciPy CSR in the ordinary path; only explicit dense export and experimental PINN training are size-limited. Cycle analysis groups the modeled graph into SCCs and applies bounded in-component enumeration. A graph cycle is not a proof of nontermination; spectral distance and comparator verdicts are structural heuristics, not behavioral equivalence or safety certificates. See [REZONATOR_ROADMAP.md](../REZONATOR_ROADMAP.md) for remaining validation gates.

---

### 1. From Imperative Code to Graph Laplacian Field

A COBOL program is parsed into a directed, typed multi-layer graph $\mathcal{G} = (V, E)$ where:
- $V = V_{\text{stmt}} \cup V_{\text{var}}$: Vertices representing basic block instructions and shared `WORKING-STORAGE` memory hubs.
- $E = E_{\text{cfg}} \cup E_{\text{dfg}}$:
  - $E_{\text{cfg}} = E_{\text{seq}} \cup E_{\text{branch\_true}} \cup E_{\text{branch\_false}} \cup E_{\text{call}} \cup E_{\text{return}} \cup E_{\text{fallthrough}}$
  - $E_{\text{dfg}} = E_{\text{def-use}} \cup E_{\text{var\_read}} \cup E_{\text{var\_write}}$

The directed adjacency matrix $A_{\text{dir}} \in \mathbb{R}^{N \times N}$ encodes the directional flow of control and data:
$$A_{\text{dir}}[u, v] = \sum_{e = (u, v)} w(e)$$

For spectral graph analysis and Cheeger bi-partitioning, the symmetric adjacency matrix is:
$$A_{\text{sym}} = \frac{1}{2}(A_{\text{dir}} + A_{\text{dir}}^T)$$

The diagonal degree matrix $D \in \mathbb{R}^{N \times N}$ is defined by:
$$D_{ii} = \sum_{j=1}^N A_{\text{sym}}[i, j]$$

The **Combinatorial Graph Laplacian** $L$ is:
$$L = D - A_{\text{sym}}$$

And the **Fan Chung Symmetric Normalized Laplacian** $\mathcal{L}_{\text{norm}}$ is:
$$\mathcal{L}_{\text{norm}}[i, j] = \begin{cases} 
1 - \frac{A_{\text{sym}}[i, i]}{D_{ii}}, & \text{if } i = j \text{ and } D_{ii} > 0 \\
-\frac{A_{\text{sym}}[i, j]}{\sqrt{D_{ii} D_{jj}}}, & \text{if } i \neq j \text{ and } D_{ii} D_{jj} > 0 \\
0, & \text{otherwise}
\end{cases}$$

#### Fundamental Properties:
1. **Positive Semi-Definiteness**: $L$ and $\mathcal{L}_{\text{norm}}$ are symmetric positive semi-definite; all eigenvalues satisfy $\lambda_k \ge 0$, and for $\mathcal{L}_{\text{norm}}$, $\lambda_k \in [0, 2]$.
2. **Multiplicity of Zero Eigenvalues**: The multiplicity of eigenvalue $\lambda = 0$ equals the exact number of connected components in the program graph.
3. **Algebraic Connectivity ($\lambda_1$)**: The Fiedler value describes connectivity of the represented graph. A zero eigenvalue beyond the first indicates multiple modeled components (isolated-node handling also matters); it does not by itself identify unreachable code or unreferenced business logic.

---

### 2. Modal Spectral Analysis & NetLSD Signatures

The spectral decomposition of the Normalized Laplacian yields the modal frequencies and vibrational eigenstates:
$$\mathcal{L}_{\text{norm}} v_k = \lambda_k v_k, \quad 0 = \lambda_0 \le \lambda_1 \le \lambda_2 \le \dots \le \lambda_{N-1} \le 2$$

#### NetLSD Multi-Scale Heat Trace:
Comparing raw unnormalized eigenvalue spectra across graphs of different sizes $N_A \neq N_B$ via zero-padding introduces artificial distance artifacts. Rezonator uses **NetLSD (Network Laplacian Spectral Distance)** (Tsitsulin et al., KDD 2018):
$$\Phi(t) = \text{Tr}\left(\exp(-t \mathcal{L}_{\text{norm}})\right) = \sum_{k=0}^{N-1} \exp(-t \lambda_k)$$

Computed across 25 logarithmically spaced time scales $t \in [10^{-2}, 10^2]$, the normalized trace $h(t)=\Phi(t)/N$ provides a size-normalized signature of represented graph topology. For $N<100$ the code uses the exact eigenvalue trace; for $N\ge100$ it uses a seeded 15-probe Hutchinson estimate:
$$h(t) = \frac{1}{N}\operatorname{Tr}\left(\exp(-t\mathcal{L}_{\text{norm}})\right) \approx \frac{1}{M}\sum_{m=1}^{M}v_m^T\exp(-t\mathcal{L}_{\text{norm}})v_m,$$
where each Rademacher vector has entries scaled by $1/\sqrt{N}$. The engine reports the sample standard error across the $M$ probes ($\sigma / \sqrt{M}$), providing an explicit stochastic noise floor for topological comparisons.
- Small $t \to 0$: approaches 1, with its initial slope determined by $-\operatorname{Tr}(\mathcal{L}_{\text{norm}})/N$.
- Intermediate $t$: captures community structure and modular clusters.
- Large $t \to \infty$: the normalized trace approaches the component-related nullity divided by $N$ (subject to isolated-node handling).

The **Topological NetLSD Distance** between programs $P_A$ and $P_B$ is:
$$d_{\text{NetLSD}}(P_A, P_B) = \sqrt{\sum_{t \in T} (\Phi_A(t) - \Phi_B(t))^2}$$

#### 2.1 3D Topological Spectral Reduction:
To avoid $\mathcal{O}(N^3)$ dense operations or multiple iterative solves on graphs up to $N = 50\,000$, Rezonator provides a **3D Topological Spectral Embedding** layer based on the three lowest non-trivial eigenpairs of $\mathcal{L}_{\text{norm}}$:
$$X = \begin{bmatrix} \phi_1 & \phi_2 & \phi_3 \end{bmatrix} \operatorname{diag}\left(\sqrt{\lambda_1}, \sqrt{\lambda_2}, \sqrt{\lambda_3}\right) \in \mathbb{R}^{N \times 3}$$

- **Fiedler Value & Vector in $\mathcal{O}(N)$**: $\lambda_1 = \|X_{:, 0}\|_2^2$ and $v_1 = X_{:, 0} / \|X_{:, 0}\|_2$, exact to machine precision without re-solving.
- **Topological Spectral Distance in $\mathcal{O}(1)$**: $d(i, j) = \|X_{i, :} - X_{j, :}\|_2$, approximating continuous diffusion coupling between nodes.
- **Reduced NetLSD Signature in $\mathcal{O}(1)$**: $h_{\text{3D}}(t) = \frac{1}{N}\left(1 + \sum_{k=1}^3 \exp(-t \lambda_k)\right)$, with truncation tail error bounded by $|h(t) - h_{\text{3D}}(t)| \le \exp(-t \lambda_4)$.
- **Relaxation Half-Life in $\mathcal{O}(1)$**: $\tau_{1/2} = \ln 2 / (\alpha \lambda_1)$.

Integrated in `diamond_yant.py` and `diffusion_ranker.py` (`rank_by_spectral_distance`).

---

### 3. Continuous Diffusion: Undirected Heat vs. Directed Markov Blast Radius

Rezonator provides two mathematically distinct continuous diffusion operators:

#### 3.1 Undirected Structural Heat Diffusion
Governed by the symmetric Combinatorial Laplacian $L = D - A_{\text{sym}}$:
$$\frac{\partial u}{\partial t} = -\alpha L u \implies u(t) = \exp(-\alpha L t) u_0$$
- **Undirected Dispersion**: Because $L$ is symmetric, heat propagates bidirectionally across all connections regardless of CFG arrow directions.
- **Mass Conservation**: Since $\mathbf{1}^T L = \mathbf{0}^T$, total mass is strictly conserved: $\sum_{i=1}^N u_i(t) = \sum_{i=1}^N u_{0, i}$.
- **Relaxation Half-Life**: Measures the decay rate of the slowest non-trivial eigenmode amplitude toward component-wise steady state:
  $$\tau_{1/2} = \frac{\ln 2}{\alpha \lambda_{\min > 0}}$$
  where $\lambda_{\min > 0}$ is the smallest strictly positive eigenvalue above numerical zero tolerance (for $k$ disconnected components, $\lambda_0 = \dots = \lambda_{k-1} = 0$).

#### 3.2 Directed Forward Impact Diffusion (Blast Radius)
While symmetric Laplacians evaluate undirected structural cohesion, directed forward impact propagates strictly along CFG and DFG dependencies via a continuous-time Markov process:

Let $P \in \mathbb{R}^{N \times N}$ be the row-stochastic transition probability matrix:
$$P_{ij} = \frac{A_{\text{dir}}[i, j]}{\sum_k A_{\text{dir}}[i, k]} \quad (\text{if out-degree } > 0)$$
Terminal sink nodes (`STOP RUN`, `GOBACK`) receive absorbing self-loops ($P_{ii} = 1.0$), ensuring probability mass is strictly conserved.

The forward propagation of an impulse $u_0$ introduced at statement $i$ is governed by the infinitesimal generator $Q = P^T - I$:
$$\dot{u}(t) = (P^T - I) u(t) \implies u(t) = \exp((P^T - I) t) u_0$$

- **Exact Reachability vs Ranking**: For any $t > 0$, every topologically reachable node in the continuous chain receives strictly positive mass. Exact reachability is computed via BFS graph search, while continuous diffusion mass ranks relative impact and can be degree-normalized ($u_j / d_{\text{in}}(j)$) to mitigate hub bias.
- **Physical Interpretation**: This yields model-level impact scores $u_j(t)$ under the selected graph, transition weights, and seed. Whether a ranking predicts real change impact must be evaluated against labeled examples; it is not a formal taint proof or source-level ground truth.

---

### 4. CFG Cycle and Hazard Analysis

The code reports structural cycles and selected heuristic hazards in the parsed CFG:

1. The implementation obtains strongly connected components through NetworkX and bounds simple-cycle enumeration within each component; cycle-budget exhaustion is reported.
2. A detected cycle means the graph contains a possible repeated path. It does not prove that the path is feasible or that execution repeats forever.
3. The current guard check looks for branch variables that are not written within an enumerated cycle. This is a heuristic signal, not path-sensitive termination analysis.
4. Terminal reachability reports reachability in the modeled graph; it does not establish that every execution path reaches an exit.

---

### 5. Structural Comparison Score (Heuristic)

The current comparator returns several graph metrics. Its base health score is:
$$F_{\text{base}} = \max(0, \min(100, 100(1 - 2.5 d_{\text{NetLSD}})))$$
If Program B receives the heuristic deadlock flag and A does not, the score is zero. If both receive the flag, B's score is capped at 20% of the base; otherwise the base is returned.

This score is not calibrated against behavioral equivalence, expert judgments, or migration outcomes. Verdict strings such as `STRUCTURAL_MODULAR_EXTENSION` are labels over graph metrics, not a safety assessment. Use differential execution tests and domain invariants to evaluate behavior.
