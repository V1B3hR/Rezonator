"""
Verification Test for F3 Sparse Matrix & Lanczos Scaling.
Tests DiamondYantSpectralEngine and PINNGraphDiffusionEngine on large sparse graphs (N=200, N=1,000).
"""

import unittest
import time
import numpy as np
import scipy.sparse as sp
from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.pinn_diffusion import PINNGraphDiffusionEngine
from rezonator.diffusion_ranker import DiffusionRanker


class TestSparseScaling(unittest.TestCase):

    def _build_synthetic_tridiagonal_laplacian(self, n: int) -> sp.csr_matrix:
        """Constructs 1D path graph Laplacian of size n (known spectrum: lambda_k = 2 - 2*cos(k*pi/n))."""
        main_diag = 2.0 * np.ones(n)
        main_diag[0] = 1.0
        main_diag[-1] = 1.0
        off_diag = -1.0 * np.ones(n - 1)
        return sp.diags([off_diag, main_diag, off_diag], [-1, 0, 1], shape=(n, n), format="csr")

    def test_sparse_spectral_eigensolver_n200(self):
        engine = DiamondYantSpectralEngine(lattice_size=16)
        n = 200
        L_sp = self._build_synthetic_tridiagonal_laplacian(n)

        t0 = time.perf_counter()
        spec = engine.compute_spectrum(L_sp, L_norm=L_sp, num_modes=6)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 1.0, f"Sparse eigensolver took too long: {elapsed:.3f}s")
        self.assertEqual(len(spec["eigenvalues"]), 6)
        # For path graph, lambda_0 == 0.0, lambda_1 > 0
        self.assertAlmostEqual(spec["eigenvalues"][0], 0.0, places=4)
        self.assertGreater(spec["fiedler_value"], 0.0)
        self.assertEqual(len(spec["fiedler_vector"]), n)
        self.assertEqual(len(spec["netlsd_signature"]), 25)

    def test_sparse_pinn_diffusion_trajectory_n1000(self):
        engine = PINNGraphDiffusionEngine(alpha=0.5)
        n = 1000
        L_sp = self._build_synthetic_tridiagonal_laplacian(n)
        u0 = np.zeros(n)
        u0[0] = 1.0

        t0 = time.perf_counter()
        res = engine.solve_analytical(L_sp, u0, time_steps=10, t_max=1.0)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 1.5, f"Sparse diffusion trajectory took too long: {elapsed:.3f}s")
        self.assertEqual(len(res["trajectory"]), 10)
        self.assertEqual(len(res["final_state"]), n)
        # Mass conservation: sum should remain ~ 1.0
        self.assertAlmostEqual(sum(res["final_state"]), 1.0, delta=0.05)

    def test_sparse_directed_ranker_n200(self):
        # Directed ring with 200 nodes
        n = 200
        nodes = [{"id": f"node_{i}", "label": f"N{i}"} for i in range(n)]
        edges = [{"source": f"node_{i}", "target": f"node_{(i+1)%n}", "weight": 1.0} for i in range(n)]
        graph_data = {"nodes": nodes, "edges": edges}

        ranker = DiffusionRanker(graph_data)
        t0 = time.perf_counter()
        ranked = ranker.rank_by_diffusion("node_0", t=1.0)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 1.0, f"Sparse diffusion ranking took too long: {elapsed:.3f}s")
        self.assertEqual(len(ranked), n - 1)
        # node_1 should be the top ranked downstream node from node_0 in a directed ring
        self.assertEqual(ranked[0], "node_1")


if __name__ == "__main__":
    unittest.main()
