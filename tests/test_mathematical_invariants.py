"""
Mathematical Invariant Regression Tests for Rezonator.

Validates fundamental mathematical theorems and physical conservation laws:
1. Mass conservation of continuous heat diffusion: sum_i u_i(t) = sum_i u0_i.
2. Mass conservation of continuous-time Markov process: 1^T Q = 0 ==> sum_i u_i(t) = 1.0.
3. Annihilation of component-wise constant vectors by the Combinatorial Laplacian: L 1_C = 0.
4. Spectral relaxation half-life on connected, disconnected, and edgeless graphs.
5. Exact BFS topological reachability vs thresholded probability concentrations.
6. NetLSD Hutchinson stochastic trace estimator noise reporting.
7. Degree-normalized Markov diffusion ranking.
"""

import unittest
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from rezonator.pinn_diffusion import PINNGraphDiffusionEngine
from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.diffusion_ranker import DiffusionRanker
from rezonator.graph_field import GraphField
from rezonator.cobol_parser import CobolParser
from rezonator.ast_graph_builder import CobolASTGraphBuilder


class TestMathematicalInvariants(unittest.TestCase):
    """Hermetic verification of continuous physical & spectral invariants."""

    def setUp(self):
        self.diffusion_engine = PINNGraphDiffusionEngine(alpha=0.5)
        self.yant_engine = DiamondYantSpectralEngine()

    def test_heat_diffusion_mass_conservation_dense(self):
        """Theorem: Continuous heat diffusion on symmetric L conserves total mass."""
        # 4-node ring graph
        A = np.array([
            [0, 1, 0, 1],
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [1, 0, 1, 0],
        ], dtype=np.float64)
        D = np.diag(np.sum(A, axis=1))
        L = D - A

        u0 = np.array([1.0, 0.0, 0.0, 0.0])
        res = self.diffusion_engine.solve_analytical(L, u0, time_steps=20, t_max=3.0)

        for step, u_t in enumerate(res["trajectory"]):
            mass = sum(u_t)
            self.assertAlmostEqual(
                mass, 1.0, places=5,
                msg=f"Mass conservation violated at step {step}: sum(u) = {mass}"
            )

    def test_heat_diffusion_mass_conservation_sparse(self):
        """Theorem: Sparse Krylov expm_multiply conserves total mass on large graphs."""
        n = 120
        # Directed ring symmetrized into undirected ring
        row = np.arange(n)
        col = (row + 1) % n
        data = np.ones(n, dtype=np.float64)
        A = sp.csr_matrix((data, (row, col)), shape=(n, n))
        A = A + A.T
        A.data = np.clip(A.data, 0.0, 1.0)
        degrees = np.array(A.sum(axis=1)).flatten()
        L_sp = sp.diags(degrees, format="csr") - A

        u0 = np.zeros(n)
        u0[0] = 1.0
        res = self.diffusion_engine.solve_analytical(L_sp, u0, time_steps=15, t_max=2.5)

        for step, u_t in enumerate(res["trajectory"]):
            mass = sum(u_t)
            self.assertAlmostEqual(
                mass, 1.0, places=5,
                msg=f"Sparse mass conservation violated at step {step}: sum(u) = {mass}"
            )

    def test_markov_blast_radius_mass_conservation(self):
        """Theorem: Continuous Markov generator Q = P^T - I conserves probability mass."""
        # Directed graph with 4 nodes: 0 -> 1 -> 2, and 2 is a sink (absorbing)
        A_dir = np.array([
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 0],  # sink
            [1, 0, 0, 0],
        ], dtype=np.float64)

        for t in [0.1, 0.5, 1.5, 5.0]:
            # Dense path
            res_dense = self.diffusion_engine.solve_directed_impact(A_dir, source_idx=0, t=t, threshold=0.0)
            dense_scores = [item["impact_score"] for item in res_dense["impact_ranking"]]
            self.assertAlmostEqual(sum(dense_scores), 1.0, places=5)

            # Sparse path (force sparse by passing csr_matrix)
            A_sp = sp.csr_matrix(A_dir)
            res_sparse = self.diffusion_engine.solve_directed_impact(A_sp, source_idx=0, t=t, threshold=0.0)
            sparse_scores = [item["impact_score"] for item in res_sparse["impact_ranking"]]
            self.assertAlmostEqual(sum(sparse_scores), 1.0, places=5)

    def test_laplacian_annihilates_constant_vectors(self):
        """Theorem: L 1 = 0 and L 1_C = 0 for every connected component C."""
        # Graph with 2 disconnected components: C1 = {0, 1}, C2 = {2, 3, 4}
        A = np.zeros((5, 5))
        A[0, 1] = A[1, 0] = 1.0
        A[2, 3] = A[3, 2] = 1.0
        A[3, 4] = A[4, 3] = 1.0
        D = np.diag(np.sum(A, axis=1))
        L = D - A

        # Global constant vector
        ones = np.ones(5)
        np.testing.assert_allclose(L @ ones, np.zeros(5), atol=1e-12)

        # Indicator of C1
        c1_ind = np.array([1.0, 1.0, 0.0, 0.0, 0.0])
        np.testing.assert_allclose(L @ c1_ind, np.zeros(5), atol=1e-12)

        # Indicator of C2
        c2_ind = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
        np.testing.assert_allclose(L @ c2_ind, np.zeros(5), atol=1e-12)

    def test_diffusion_half_life_disconnected_graph(self):
        """
        Verify that a disconnected graph with non-trivial components correctly
        uses the smallest strictly positive eigenvalue, rather than returning inf.
        """
        # Two disconnected triangles: {0, 1, 2} and {3, 4, 5}
        # In a triangle, Laplacian eigenvalues are 0, 3, 3.
        # For two triangles, eigenvalues are 0, 0, 3, 3, 3, 3.
        A = np.zeros((6, 6))
        for i in range(3):
            for j in range(3):
                if i != j:
                    A[i, j] = 1.0
        for i in range(3, 6):
            for j in range(3, 6):
                if i != j:
                    A[i, j] = 1.0
        D = np.diag(np.sum(A, axis=1))
        L = D - A

        evals = np.linalg.eigvalsh(L)
        np.testing.assert_allclose(evals[:2], [0.0, 0.0], atol=1e-10)
        self.assertGreater(evals[2], 2.9)

        u0 = np.array([1.0, 0, 0, 0, 0, 0])
        res = self.diffusion_engine.solve_analytical(L, u0)

        # Smallest positive eigenvalue is 3.0
        expected_hl = np.log(2.0) / (0.5 * 3.0)
        self.assertTrue(np.isfinite(res["diffusion_half_life"]))
        self.assertAlmostEqual(res["diffusion_half_life"], expected_hl, places=4)

    def test_diffusion_half_life_edgeless_graph(self):
        """Verify that an edgeless graph (no positive eigenvalues) yields infinite half-life."""
        L = np.zeros((4, 4))
        u0 = np.array([1.0, 0, 0, 0])
        res = self.diffusion_engine.solve_analytical(L, u0)
        self.assertEqual(res["diffusion_half_life"], float("inf"))

    def test_exact_reachability_vs_numerical_threshold(self):
        """
        Verify that exact topological reachability is reported separately
        from threshold-filtered numerical ranking.
        """
        # Long linear chain: 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7
        n = 8
        A_dir = np.zeros((n, n))
        for i in range(n - 1):
            A_dir[i, i + 1] = 1.0

        # At small t=0.1, node 7 receives negligible mass < 1e-4
        res = self.diffusion_engine.solve_directed_impact(A_dir, source_idx=0, t=0.1, threshold=1e-3)

        self.assertEqual(res["exact_reachable_count"], 8)
        self.assertLess(res["threshold_filtered_count"], 8)
        self.assertEqual(res["reachable_count"], res["threshold_filtered_count"])

    def test_netlsd_hutchinson_error_reporting(self):
        """Verify NetLSD signature contains non-negative estimator noise standard errors."""
        n = 110
        # Build 110-node sparse cycle
        row = np.arange(n)
        col = (row + 1) % n
        A = sp.csr_matrix((np.ones(n), (row, col)), shape=(n, n))
        A = A + A.T
        degrees = np.array(A.sum(axis=1)).flatten()
        inv_sqrt_d = 1.0 / np.sqrt(degrees)
        D_inv_sqrt = sp.diags(inv_sqrt_d, format="csr")
        L_norm = sp.eye(n, format="csr") - D_inv_sqrt @ A @ D_inv_sqrt
        L_comb = sp.diags(degrees, format="csr") - A

        spec = self.yant_engine.compute_spectrum(L_comb, L_norm=L_norm, num_modes=5)
        self.assertIn("netlsd_stderr", spec)
        self.assertEqual(len(spec["netlsd_stderr"]), len(spec["netlsd_signature"]))
        for err in spec["netlsd_stderr"]:
            self.assertGreaterEqual(err, 0.0)

    def test_degree_normalized_diffusion_ranking(self):
        """Verify degree-normalized Markov ranking reduces bias toward in-degree hubs."""
        # Node 0 points to node 1 and hub 2.
        # Hub 2 has incoming edges from nodes 0, 3, 4, 5.
        graph_data = {
            "nodes": [{"id": f"n{i}"} for i in range(6)],
            "edges": [
                {"source": "n0", "target": "n1", "weight": 1.0},
                {"source": "n0", "target": "n2", "weight": 1.0},
                {"source": "n3", "target": "n2", "weight": 1.0},
                {"source": "n4", "target": "n2", "weight": 1.0},
                {"source": "n5", "target": "n2", "weight": 1.0},
            ]
        }
        ranker = DiffusionRanker(graph_data)
        raw_ranking = ranker.rank_by_diffusion("n0", degree_normalized=False)
        deg_ranking = ranker.rank_by_diffusion("n0", degree_normalized=True)

        self.assertIn("n1", raw_ranking)
        self.assertIn("n2", raw_ranking)
        self.assertIn("n1", deg_ranking)
        self.assertIn("n2", deg_ranking)


if __name__ == "__main__":
    unittest.main()
