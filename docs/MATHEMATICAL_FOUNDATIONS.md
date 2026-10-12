# MATHEMATICAL FOUNDATIONS OF REZONATOR
## Graph Operators, Spectral Analysis, and Static Code Intelligence

---

### Abstract
Legacy COBOL systems have control and data dependencies that are difficult to inspect from source text alone. **Rezonator** maps supported parsed constructs to a finite program-dependence graph containing control-flow and data-flow edges, then derives discrete graph operators.

By applying:
1. **Fan Chung Normalized Laplacian Spectral Analysis** ($\mathcal{L}_{\text{norm}} = I - D^{-1/2} A D^{-1/2}$),
2. **NetLSD Multi-Scale Heat Trace Distance** ($\Phi(t) = \text{Tr}(\exp(-t \mathcal{L}_{\text{norm}}))$),
3. **Directed Forward Impact Diffusion / Blast Radius** ($\dot{u} = (P^T - I)u \implies u(t) = \exp((P^T - I)t) u_0$),
4. **CFG cycle enumeration and heuristic hazard reporting**,

the parsed graph can be analyzed for structural metrics, impact propagation, and possible cycle hazards. Results are deterministic for a given graph and options, but their source-level meaning is limited by parser coverage.

> **Implementation scope:** The parser supports a subset of COBOL. The current analyzer uses NetworkX simple-cycle enumeration, not Tarjan SCC; a graph cycle is not a proof of nontermination. Spectral distance and comparator verdicts are structural heuristics, not behavioral equivalence or safety certificates. See [REZONATOR_ROADMAP.md](../REZONATOR_ROADMAP.md) for code-observed status and validation gates.

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

Computed across 25 logarithmically spaced time scales $t \in [10^{-2}, 10^2]$, $\Phi(t)$ provides a scale-invariant signature of graph topology:
- Small $t \to 0$: captures local neighborhood structure and degree distribution ($\Phi(t) \approx N - t \sum d_i$).
- Intermediate $t$: captures community structure and modular clusters.
- Large $t \to \infty$: converges to the number of connected components ($k$ components $\implies \Phi(t) \to k$).

The **Topological NetLSD Distance** between programs $P_A$ and $P_B$ is:
$$d_{\text{NetLSD}}(P_A, P_B) = \sqrt{\sum_{t \in T} (\Phi_A(t) - \Phi_B(t))^2}$$

---

### 3. Directed Forward Impact Diffusion (Blast Radius)

While symmetric Laplacians evaluate structural cohesion, the directed diffusion operator propagates a model-level perturbation along represented directed edges. This is not a source-level taint analysis or proof of real execution influence. Rezonator models that graph signal via continuous-time Markov transfer:

Let $P \in \mathbb{R}^{N \times N}$ be the row-stochastic transition probability matrix:
$$P_{ij} = \frac{A_{\text{dir}}[i, j]}{\sum_k A_{\text{dir}}[i, k]} \quad (\text{if out-degree } > 0)$$

The forward propagation of an impulse $u_0$ introduced at statement $i$ is governed by the infinitesimal generator $(P^T - I)$:
$$\dot{u}(t) = (P^T - I) u(t) \implies u(t) = \exp((P^T - I) t) u_0$$

This yields model-level impact scores $u_j(t)$ under the selected graph, transition weights, and seed. Whether a ranking predicts real change impact must be evaluated against labeled examples; it is not source-level ground truth by definition.

---

### 4. CFG Cycle and Hazard Analysis

The code reports structural cycles and selected heuristic hazards in the parsed CFG:

1. The current implementation calls NetworkX simple-cycle enumeration; it does not compute Tarjan SCC.
2. A detected cycle means the graph contains a possible repeated path. It does not prove that the path is feasible or that execution repeats forever.
3. The current guard check looks for branch variables that are not written within an enumerated cycle. This is a heuristic signal, not path-sensitive termination analysis.
4. Terminal reachability reports reachability in the modeled graph; it does not establish that every execution path reaches an exit.

---

### 5. Structural Comparison Score (Heuristic)

The current comparator returns several graph metrics. Its base health score is:
$$F_{\text{base}} = \max(0, \min(100, 100(1 - 2.5 d_{\text{NetLSD}})))$$
If Program B receives the heuristic deadlock flag and A does not, the score is zero. If both receive the flag, B's score is capped at 20% of the base; otherwise the base is returned.

This score is not calibrated against behavioral equivalence, expert judgments, or migration outcomes. Verdict strings such as `SAFE_MODULAR_EXTENSION` are labels over graph metrics, not a safety assessment. Use differential execution tests and domain invariants to evaluate behavior.
