"""
Diamond Yant Modal Spectral Engine: Graph Eigensolver & 2D Chladni Cymatics.
Extracts spectral harmonic signatures (eigenvalues, Fiedler vector) and projects
graph topology onto continuous 2D Chladni resonant vibration surfaces.
"""

from typing import Dict, List, Any, Tuple, Optional
import numpy as np
import scipy.linalg as la


class DiamondYantSpectralEngine:
    """
    Solves the modal spectrum of the Graph Laplacian and generates
    the Diamond Yant Cymatic signature of the program.
    """

    def __init__(self, lattice_size: int = 32):
        self.lattice_size = lattice_size

    def compute_spectrum(self, L: np.ndarray, L_norm: Optional[np.ndarray] = None, num_modes: int = 10) -> Dict[str, Any]:
        """
        Computes exact eigenvalues and eigenvectors of Laplacian L:
        L * v_k = lambda_k * v_k, as well as multi-scale NetLSD heat-kernel signatures.
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
                "fiedler_norm": 0.0
            }

        # Dual solver: Sparse Arnoldi/Lanczos for n >= 100, exact dense eigh for small graphs
        import scipy.sparse as sp
        import scipy.sparse.linalg as spla

        use_sparse = (n >= 100 or sp.issparse(L))
        if use_sparse:
            L_sp = sp.csr_matrix(L, dtype=np.float64)
            k_solve = min(max(num_modes + 2, 6), n - 1)
            try:
                evals_sm, evecs_sm = spla.eigsh(L_sp, k=k_solve, sigma=-1e-4, which='LM')
                idx_sort = np.argsort(evals_sm)
                evals = np.clip(evals_sm[idx_sort], a_min=0.0, a_max=None)
                evecs = evecs_sm[:, idx_sort]
            except Exception:
                evals, evecs = la.eigh(L if not sp.issparse(L) else L.toarray())
                idx_sort = np.argsort(evals)
                evals = np.clip(evals[idx_sort], a_min=0.0, a_max=None)
                evecs = evecs[:, idx_sort]
        else:
            evals, evecs = la.eigh(L if not sp.issparse(L) else L.toarray())
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

        # Multi-scale NetLSD signature from Normalized Laplacian
        netlsd_sig: List[float] = []
        fiedler_norm = 0.0
        if L_norm is not None and n > 0:
            times = np.logspace(-2, 2, 25)
            if n < 100:
                evals_norm = la.eigvalsh(L_norm if not sp.issparse(L_norm) else L_norm.toarray())
                evals_norm = np.clip(evals_norm, 0.0, 2.0)
                netlsd_sig = [float(np.mean(np.exp(-t * evals_norm))) for t in times]
                fiedler_norm = float(evals_norm[1]) if n > 1 else float(evals_norm[0])
            else:
                L_norm_sp = sp.csr_matrix(L_norm, dtype=np.float64)
                try:
                    norm_evals_sm, _ = spla.eigsh(L_norm_sp, k=min(4, n - 1), sigma=-1e-4, which='LM')
                    norm_evals_sm = np.sort(np.clip(norm_evals_sm, 0.0, 2.0))
                    fiedler_norm = float(norm_evals_sm[1]) if len(norm_evals_sm) > 1 else float(norm_evals_sm[0])
                except Exception:
                    fiedler_norm = 0.0

                # Fast Hutchinson stochastic trace estimator with Rademacher random vectors
                M_samples = 15
                rng = np.random.default_rng(42)
                # Keep samples as columns so expm_multiply can propagate all
                # probes in one sparse matrix operation per time scale.
                V = rng.choice([-1.0, 1.0], size=(n, M_samples)) / np.sqrt(n)
                for t in times:
                    W = spla.expm_multiply(-t * L_norm_sp, V)
                    tr_est = float(np.sum(V * W))
                    netlsd_sig.append(tr_est / M_samples)

        return {
            "eigenvalues": top_evals,
            "eigenvectors": top_evecs,
            "fiedler_value": fiedler_val,
            "fiedler_vector": fiedler_vec,
            "spectral_gap": spectral_gap,
            "algebraic_connectivity": fiedler_val,
            "fiedler_norm": fiedler_norm,
            "netlsd_signature": netlsd_sig,
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
