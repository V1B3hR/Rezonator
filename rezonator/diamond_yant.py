"""
Diamond Yant Modal Spectral Engine: Graph Eigensolver & 2D Chladni Cymatics.
Extracts spectral harmonic signatures (eigenvalues, Fiedler vector) and projects
graph topology onto continuous 2D Chladni resonant vibration surfaces.
"""

from typing import Dict, List, Any, Tuple, Optional
import numpy as np
import scipy.linalg as la
from rezonator.analysis_config import (
    DIFFUSION_ALPHA,
    NETLSD_HUTCHINSON_SAMPLES,
    NETLSD_TIME_MAX,
    NETLSD_TIME_MIN,
    NETLSD_TIME_SCALES,
    SOLVER_SEED,
    SPARSE_CUTOFF,
    SPARSE_EIGENSOLVER_ITERATIONS_PER_NODE,
    SPARSE_EIGENSOLVER_MIN_ITERATIONS,
    SPARSE_EIGENSOLVER_SHIFT,
    SPARSE_EIGENSOLVER_TOLERANCE,
)


def _to_dense(matrix: Any) -> np.ndarray:
    arr: np.ndarray = np.asarray(matrix.toarray() if hasattr(matrix, "toarray") else matrix)
    return arr


class DiamondYantSpectralEngine:
    """
    Solves the modal spectrum of the Graph Laplacian and generates
    the Diamond Yant Cymatic signature of the program.
    """

    def __init__(self, lattice_size: int = 32):
        self.lattice_size = lattice_size

    def _sparse_eigenpairs(self, matrix, k: int):
        """Solve for the low spectrum without a dense fallback on large graphs."""
        import scipy.sparse.linalg as spla

        n = matrix.shape[0]
        v0 = np.random.default_rng(SOLVER_SEED).standard_normal(n)
        v0 /= np.linalg.norm(v0)
        maxiter = max(SPARSE_EIGENSOLVER_MIN_ITERATIONS, n * SPARSE_EIGENSOLVER_ITERATIONS_PER_NODE)
        try:
            return spla.eigsh(
                matrix, k=k, sigma=SPARSE_EIGENSOLVER_SHIFT, which="LM", v0=v0,
                tol=SPARSE_EIGENSOLVER_TOLERANCE, maxiter=maxiter,
            )
        except Exception as shift_invert_error:
            try:
                return spla.eigsh(
                    matrix, k=k, which="SM", v0=v0,
                    tol=SPARSE_EIGENSOLVER_TOLERANCE, maxiter=maxiter,
                )
            except Exception as iterative_error:
                raise RuntimeError(
                    "Sparse eigensolver did not converge; dense fallback is disabled "
                    "to preserve the graph memory bound"
                ) from iterative_error

    def compute_3d_spectral_embedding(self, L_norm: np.ndarray) -> Dict[str, Any]:
        """
        Computes 3D topological spectral embedding X in R^{N x 3} using truncated
        normalized Laplacian eigen-decomposition:
            X = [phi_1, phi_2, phi_3] @ diag([sqrt(lambda_1), sqrt(lambda_2), sqrt(lambda_3)])
        Where phi_k and lambda_k are the lowest non-trivial eigenpairs of L_norm.

        Reduces full O(N^3) spectral operations to O(N) over low-rank embedding X:
        - Fiedler value lambda_1 = ||X_{:, 0}||_2^2
        - Fiedler vector v_1 = X_{:, 0} / ||X_{:, 0}||_2
        - Pairwise spectral distance d(i, j) = ||X_{i, :} - X_{j, :}||_2 in O(1)
        - Order-3 reduced NetLSD h_3D(t) in O(1)
        - Relaxation half-life tau_1/2 = ln(2) / (alpha * lambda_1) in O(1)
        """
        import scipy.sparse as sp

        n = L_norm.shape[0] if L_norm is not None else 0
        if n == 0:
            return {
                "embedding": np.zeros((0, 3), dtype=np.float64),
                "eigenvalues": [],
                "eigenvectors": [],
                "fiedler_value": 0.0,
                "fiedler_vector": [],
                "spectral_gap": 0.0,
                "lambda_0": 0.0,
                "truncation_bound_lambda_4": None,
            }
        if n == 1:
            return {
                "embedding": np.zeros((1, 3), dtype=np.float64),
                "eigenvalues": [],
                "eigenvectors": [],
                "fiedler_value": 0.0,
                "fiedler_vector": [],
                "spectral_gap": 0.0,
                "lambda_0": 0.0,
                "truncation_bound_lambda_4": None,
            }

        if n < SPARSE_CUTOFF or not sp.issparse(L_norm):
            matrix_dense = _to_dense(L_norm)
            evals_all, evecs_all = la.eigh(matrix_dense)
            idx_sort = np.argsort(evals_all)
            evals = np.clip(evals_all[idx_sort], 0.0, 2.0)
            evecs = evecs_all[:, idx_sort]
        else:
            L_sp = sp.csr_matrix(L_norm, dtype=np.float64)
            k_req = min(5, n - 1)
            evals_sm, evecs_sm = self._sparse_eigenpairs(L_sp, k_req)
            idx_sort = np.argsort(evals_sm)
            evals = np.clip(evals_sm[idx_sort], 0.0, 2.0)
            evecs = evecs_sm[:, idx_sort]

        lambda_0 = float(evals[0]) if len(evals) > 0 else 0.0
        num_non_trivial = min(3, len(evals) - 1)

        X = np.zeros((n, 3), dtype=np.float64)
        evecs_3d = []
        evals_3d = []
        for k in range(num_non_trivial):
            idx = k + 1
            lam = float(evals[idx])
            phi = evecs[:, idx]
            scale = np.sqrt(max(0.0, lam))
            X[:, k] = phi * scale
            evals_3d.append(lam)
            evecs_3d.append(phi)

        fiedler_val = evals_3d[0] if len(evals_3d) > 0 else 0.0
        fiedler_vec = evecs_3d[0].tolist() if len(evecs_3d) > 0 else []
        spectral_gap = (evals_3d[1] - evals_3d[0]) if len(evals_3d) > 1 else 0.0
        lambda_4 = float(evals[4]) if len(evals) > 4 else None

        return {
            "embedding": X,
            "eigenvalues": evals_3d,
            "eigenvectors": [vec.tolist() for vec in evecs_3d],
            "fiedler_value": fiedler_val,
            "fiedler_vector": fiedler_vec,
            "spectral_gap": spectral_gap,
            "lambda_0": lambda_0,
            "truncation_bound_lambda_4": lambda_4,
        }

    def compute_reduced_netlsd(
        self,
        eigenvalues_3d: List[float],
        n: int,
        times: Optional[np.ndarray] = None,
        normalized: bool = True,
        lambda_0: float = 0.0,
    ) -> List[float]:
        """
        Order-3 reduced NetLSD heat trace signature:
            Phi_3D(t) = exp(-t * lambda_0) + sum_{k=1}^3 exp(-t * lambda_k)
        When normalized=True:
            h_3D(t) = Phi_3D(t) / N.
        Evaluated in O(1) per time scale.
        """
        if n == 0:
            return []
        if times is None:
            times = np.logspace(
                np.log10(NETLSD_TIME_MIN), np.log10(NETLSD_TIME_MAX), NETLSD_TIME_SCALES,
            )
        sig = []
        for t in times:
            val = float(np.exp(-t * lambda_0)) + sum(float(np.exp(-t * lam)) for lam in eigenvalues_3d)
            if normalized:
                val = val / n
            sig.append(float(val))
        return sig

    def spectral_node_distance(self, embedding: np.ndarray, i: int, j: int) -> float:
        """
        Returns Euclidean distance between node i and node j in 3D spectral space:
        d(i, j) = ||X_{i, :} - X_{j, :}||_2 in O(1).
        Approximates biharmonic/diffusion distance on the graph.
        """
        if len(embedding) == 0 or i >= len(embedding) or j >= len(embedding):
            return 0.0
        return float(np.linalg.norm(embedding[i] - embedding[j]))

    def compute_spectral_half_life(self, fiedler_val: float, alpha: float = DIFFUSION_ALPHA) -> float:
        """
        Computes relaxation half-life tau_{1/2} = ln(2) / (alpha * lambda_1) in O(1).
        """
        if fiedler_val > 1e-4:
            return float(np.log(2.0) / (alpha * fiedler_val))
        return float("inf")

    def compute_spectrum(self, L: np.ndarray, L_norm: Optional[np.ndarray] = None, num_modes: int = 10) -> Dict[str, Any]:
        """
        Computes exact eigenvalues and eigenvectors of Laplacian L:
        L * v_k = lambda_k * v_k, as well as multi-scale NetLSD heat-kernel signatures
        and 3D topological spectral embedding.
        """
        n = L.shape[0]
        if n == 0:
            return {
                "eigenvalues": [],
                "eigenvectors": [],
                "fiedler_value": 0.0,
                "fiedler_vector": [],
                "spectral_gap": 0.0,
                "algebraic_connectivity": 0.0,
                "netlsd_signature": [],
                "netlsd_stderr": [],
                "netlsd_reduced_3d": [],
                "spectral_embedding_3d": [],
                "spectral_half_life_3d": float("inf"),
                "truncation_bound_lambda_4": None,
                "fiedler_norm": 0.0,
                "total_modes": 0,
            }

        # Sparse Lanczos for large graphs; exact dense eigh is intentionally
        # restricted to small inputs. Never turn an ARPACK failure into an
        # unbounded N-by-N allocation.
        import scipy.sparse as sp
        import scipy.sparse.linalg as spla

        use_sparse = (n >= SPARSE_CUTOFF or sp.issparse(L))
        if use_sparse:
            L_sp = sp.csr_matrix(L, dtype=np.float64)
            k_solve = min(max(num_modes + 2, 6), n - 1)
            if n < SPARSE_CUTOFF:
                evals, evecs = la.eigh(_to_dense(L))
                idx_sort = np.argsort(evals)
                evals = np.clip(evals[idx_sort], a_min=0.0, a_max=None)
                evecs = evecs[:, idx_sort]
            else:
                evals_sm, evecs_sm = self._sparse_eigenpairs(L_sp, k_solve)
                idx_sort = np.argsort(evals_sm)
                evals = np.clip(evals_sm[idx_sort], a_min=0.0, a_max=None)
                evecs = evecs_sm[:, idx_sort]
        else:
            evals, evecs = la.eigh(_to_dense(L))
            idx_sort = np.argsort(evals)
            evals = np.clip(evals[idx_sort], a_min=0.0, a_max=None)
            evecs = evecs[:, idx_sort]

        # Extract algebraic connectivity (Fiedler value = lambda_1)
        fiedler_val = float(evals[1]) if len(evals) > 1 else float(evals[0])
        fiedler_vec = evecs[:, 1].tolist() if evecs.shape[1] > 1 else evecs[:, 0].tolist()

        # Spectral gap: lambda_2 - lambda_1
        spectral_gap = float(evals[2] - evals[1]) if len(evals) > 2 else 0.0

        # Select top-k modes for output
        k = min(len(evals), num_modes)
        top_evals = [float(x) for x in evals[:k]]
        top_evecs = [evecs[:, i].tolist() for i in range(k)]

        # Multi-scale NetLSD signature from Normalized Laplacian & 3D Spectral Embedding
        netlsd_sig: List[float] = []
        netlsd_stderr: List[float] = []
        netlsd_reduced_3d: List[float] = []
        embedding_3d: Optional[np.ndarray] = None
        fiedler_norm = 0.0
        half_life_3d = float("inf")
        truncation_bound_lambda_4 = None

        if L_norm is not None and n > 0:
            times = np.logspace(
                np.log10(NETLSD_TIME_MIN), np.log10(NETLSD_TIME_MAX), NETLSD_TIME_SCALES,
            )
            # Compute 3D spectral embedding and reduced metrics
            emb_res = self.compute_3d_spectral_embedding(L_norm)
            embedding_3d = emb_res["embedding"]
            fiedler_norm = emb_res["fiedler_value"]
            truncation_bound_lambda_4 = emb_res.get("truncation_bound_lambda_4")
            netlsd_reduced_3d = self.compute_reduced_netlsd(
                emb_res["eigenvalues"], n, times=times, normalized=True,
                lambda_0=emb_res.get("lambda_0", 0.0),
            )
            half_life_3d = self.compute_spectral_half_life(fiedler_norm)

            if n < SPARSE_CUTOFF:
                evals_norm = la.eigvalsh(_to_dense(L_norm))
                evals_norm = np.clip(evals_norm, 0.0, 2.0)
                netlsd_sig = [float(np.mean(np.exp(-t * evals_norm))) for t in times]
                netlsd_stderr = [0.0] * len(times)
                fiedler_norm = float(evals_norm[1]) if n > 1 else float(evals_norm[0])
            else:
                L_norm_sp = sp.csr_matrix(L_norm, dtype=np.float64)

                # Fast Hutchinson stochastic trace estimator with Rademacher random vectors
                M_samples = NETLSD_HUTCHINSON_SAMPLES
                rng = np.random.default_rng(SOLVER_SEED)
                # Keep samples as columns so expm_multiply can propagate all
                # probes in one sparse matrix operation per time scale.
                V = rng.choice([-1.0, 1.0], size=(n, M_samples)) / np.sqrt(n)
                for t in times:
                    W = spla.expm_multiply(-t * L_norm_sp, V)
                    probe_estimates = np.sum(V * W, axis=0)
                    tr_mean = float(np.mean(probe_estimates))
                    tr_stderr = (
                        float(np.std(probe_estimates, ddof=1) / np.sqrt(M_samples))
                        if M_samples > 1 else 0.0
                    )
                    netlsd_sig.append(tr_mean)
                    netlsd_stderr.append(tr_stderr)

        return {
            "eigenvalues": top_evals,
            "eigenvectors": top_evecs,
            "fiedler_value": fiedler_val,
            "fiedler_vector": fiedler_vec,
            "spectral_gap": spectral_gap,
            "algebraic_connectivity": fiedler_val,
            "fiedler_norm": fiedler_norm,
            "netlsd_signature": netlsd_sig,
            "netlsd_stderr": netlsd_stderr,
            "netlsd_reduced_3d": netlsd_reduced_3d,
            "spectral_embedding_3d": embedding_3d.tolist() if embedding_3d is not None else [],
            "spectral_half_life_3d": half_life_3d,
            "truncation_bound_lambda_4": truncation_bound_lambda_4,
            "total_modes": n
        }

    def generate_chladni_surface(self, spectrum: Dict[str, Any]) -> Dict[str, Any]:
        """
        Projects graph modal eigenvalues and eigenvectors to a 2D continuous
        Chladni plate resonant pattern using the generalized wave equation:
        w(x, y) = sum_k c_k * [ a_k * sin(n_k * pi * x) * sin(m_k * pi * y) + b_k * sin(m_k * pi * x) * sin(n_k * pi * y) ]
        """
        evals = spectrum.get("eigenvalues", [])
        evecs = spectrum.get("eigenvectors", [])

        size = self.lattice_size
        x = np.linspace(-1.0, 1.0, size)
        y = np.linspace(-1.0, 1.0, size)
        X, Y = np.meshgrid(x, y, indexing="ij")

        W = np.zeros((size, size), dtype=np.float64)

        if not evals:
            return {
                "chladni_matrix": W.tolist(),
                "lattice_size": size,
                "modes_used": 0,
                "nodal_ratio": 0.0
            }

        modes_to_use = min(len(evals), 6)
        active_modes = []

        for k in range(modes_to_use):
            lam = evals[k]
            vec = np.array(evecs[k]) if k < len(evecs) else np.ones(1)

            # Harmonic integers derived from eigenvalue magnitude
            n_k = 1 + int(np.round(lam * 1.5))
            m_k = 2 + int(np.round(lam * 2.0))

            # Amplitude weights: lower modes carry higher global resonant energy
            weight = float(np.exp(-lam / 3.0))

            a_k = float(np.mean(vec)) if len(vec) > 0 else 1.0
            b_k = float(np.std(vec)) if len(vec) > 0 else 0.5
            if abs(a_k) < 1e-4 and abs(b_k) < 1e-4:
                a_k, b_k = 1.0, 0.5

            # Chladni 2D standing plate wave formulation
            mode_surface = (
                a_k * np.sin(n_k * np.pi * X) * np.sin(m_k * np.pi * Y) +
                b_k * np.sin(m_k * np.pi * X) * np.sin(n_k * np.pi * Y)
            )

            W += weight * mode_surface
            active_modes.append({
                "mode_index": k,
                "eigenvalue": float(lam),
                "n": n_k,
                "m": m_k,
                "amplitude": weight
            })

        # Normalize surface to [-1.0, 1.0]
        max_val = np.max(np.abs(W))
        if max_val > 1e-8:
            W = W / max_val

        # Detect nodal points (where |w(x, y)| < threshold, representing sand accumulation lines)
        nodal_mask = np.abs(W) < 0.08
        nodal_ratio = float(np.count_nonzero(nodal_mask) / (size * size))

        return {
            "chladni_matrix": W.tolist(),
            "lattice_size": size,
            "modes_used": modes_to_use,
            "active_modes": active_modes,
            "nodal_ratio": nodal_ratio
        }

    def compute_spectral_distance(self, spec_a: Dict[str, Any], spec_b: Dict[str, Any]) -> float:
        """
        Calculates NetLSD (Network Laplacian Spectral Distance):
        Size-invariant, permutation-invariant heat trace distance across multiple time scales.
        """
        sig_a = np.array(spec_a.get("netlsd_signature", []))
        sig_b = np.array(spec_b.get("netlsd_signature", []))
        if len(sig_a) > 0 and len(sig_b) > 0 and len(sig_a) == len(sig_b):
            return float(np.linalg.norm(sig_a - sig_b))

        # Fallback to normalized Fiedler distance if signatures missing
        fa = spec_a.get("fiedler_norm", spec_a.get("fiedler_value", 0.0))
        fb = spec_b.get("fiedler_norm", spec_b.get("fiedler_value", 0.0))
        return float(abs(fa - fb))

    def compute_reduced_spectral_distance(self, spec_a: Dict[str, Any], spec_b: Dict[str, Any]) -> float:
        """
        Calculates NetLSD distance using order-3 reduced 3D signatures:
        ||h_3D_A - h_3D_B||_2 across multi-scale times in O(1).
        """
        sig_a = np.array(spec_a.get("netlsd_reduced_3d", []))
        sig_b = np.array(spec_b.get("netlsd_reduced_3d", []))
        if len(sig_a) > 0 and len(sig_b) > 0 and len(sig_a) == len(sig_b):
            return float(np.linalg.norm(sig_a - sig_b))

        fa = spec_a.get("fiedler_norm", spec_a.get("fiedler_value", 0.0))
        fb = spec_b.get("fiedler_norm", spec_b.get("fiedler_value", 0.0))
        return float(abs(fa - fb))
