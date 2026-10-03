# MATHEMATICAL FOUNDATIONS OF REZONATOR
## Continuous Topological Manifolds, Spectral Graph Theory, and Formal Verification for Mainframe Code Intelligence

---

### Abstract
Legacy mainframe core banking systems (processing over 95% of worldwide ATM transactions and 43% of core financial institutions) operate on deep deterministic semantics. Rather than treating COBOL source code as unstructured textual tokens—which causes linguistic large language models to hallucinate or misinterpret non-local control transfers (`PERFORM`, `GO TO`, global `WORKING-STORAGE` mutations)—**Rezonator** maps the Program Intermediate Representation (PIR) directly to a formal dependency manifold, discrete Graph Laplacian field, and directed Control Flow / Data Flow Graphs (CFG + DFG).

By applying:
1. **Fan Chung Normalized Laplacian Spectral Analysis** ($\mathcal{L}_{\text{norm}} = I - D^{-1/2} A D^{-1/2}$),
2. **NetLSD Multi-Scale Heat Trace Distance** ($\Phi(t) = \text{Tr}(\exp(-t \mathcal{L}_{\text{norm}}))$),
3. **Directed Forward Impact Diffusion / Blast Radius** ($\dot{u} = (P^T - I)u \implies u(t) = \exp((P^T - I)t) u_0$),
4. **Tarjan SCC Cycle & Termination Invariant Verification**,

the codebase is transformed into a rigorous, verifiable analytical system whose structural resilience, blast radius, cycle hazards, and refactoring divergence are deterministically computed.

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
3. **Algebraic Connectivity ($\lambda_1$)**: The smallest non-zero eigenvalue $\lambda_1$ (the Fiedler value) quantifies global structural cohesion. If $\lambda_1 = 0$, unreachable dead code, isolated variables, or unreferenced logic exists.

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

While symmetric Laplacians evaluate structural cohesion, data/taint perturbations in software flow **strictly downstream** along directed edges. Rezonator models directed impact via continuous-time Markov transfer:

Let $P \in \mathbb{R}^{N \times N}$ be the row-stochastic transition probability matrix:
$$P_{ij} = \frac{A_{\text{dir}}[i, j]}{\sum_k A_{\text{dir}}[i, k]} \quad (\text{if out-degree } > 0)$$

The forward propagation of an impulse $u_0$ introduced at statement $i$ is governed by the infinitesimal generator $(P^T - I)$:
$$\dot{u}(t) = (P^T - I) u(t) \implies u(t) = \exp((P^T - I) t) u_0$$

This yields an exact, monotone, directed impact score $u_j(t) \in [0, 1]$ for every downstream node $j$, ranking the true blast radius of a code modification.

---

### 4. Formal Cycle, Recursion & Deadlock Verification

Rather than heuristic black-hole analogies, Rezonator employs classical, sound computer science algorithms:

1. **Tarjan's Strongly Connected Components (SCC)**:
   Computes all maximal strongly connected subgraphs in $\mathcal{G}_{\text{CFG}}$ in $O(|V| + |E|)$ time.
   - Any non-trivial SCC with $>1$ node or a self-loop indicates a cycle in control flow.
2. **Recursive PERFORM Detection**:
   Distinguishes valid acyclic business workflows from hazardous self-recursion (e.g. `0000-POLL-DISPENSER` calling itself).
3. **Termination Guard Analysis**:
   Inspects loop condition variables. If the loop body contains no statement modifying the condition variables, the loop is flagged as **`CRITICAL_INFINITE_LOOP`** (unconditional deadlock sink).
4. **Terminal Sink Reachability**:
   Checks whether every execution path can reach an exit statement (`STOP RUN` / `GOBACK`).

---

### 5. Refactoring Fidelity & Regression Scoring

To evaluate code refactorings (e.g. $P_A \to P_B$), Rezonator computes:
1. **Topological Similarity**:
   $$\mathcal{S}_{\text{topo}} = \exp\left(-\frac{d_{\text{NetLSD}}(P_A, P_B)}{\sigma}\right)$$
2. **Cohesion Stability**:
   $$\Delta \lambda_1 = \lambda_1^{(B)} - \lambda_1^{(A)}$$
3. **Deadlock Penalty**:
   If $P_A$ is acyclic but $P_B$ introduces an infinite loop / recursive deadlock cycle:
   $$\text{Score}(P_A, P_B) = 0.0, \quad \text{Verdict} = \text{CRITICAL\_REGRESSION}$$
4. **Refactoring Health Score**:
   For safe extensions:
   $$\text{Score} = 100 \cdot \left[ 0.6 \cdot \mathcal{S}_{\text{topo}} + 0.4 \cdot \left(1 - \frac{|\Delta \lambda_1|}{\max(0.1, \lambda_1^{(A)})}\right) \right]$$

This gives architects and auditors a transparent, falsifiable metric backed by compiler AST graphs and continuous spectral mathematics.
