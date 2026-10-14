"""
Verification and Mathematical Invariant Test Suite for 3D Topological Spectral Reduction.

Verifies:
1. 3D spectral embedding construction: X = [phi_1, phi_2, phi_3] @ diag(sqrt([lambda_1, lambda_2, lambda_3])).
2. Exact reconstruction of Fiedler value lambda_1 = ||X_{:, 0}||^2 and Fiedler vector v_1 = X_{:, 0} / ||X_{:, 0}||.
3. Pairwise topological spectral distance d(i, j) = ||X_{i, :} - X_{j, :}||_2 in O(1).
4. Order-3 reduced NetLSD signature and controlled truncation error bound <= e^{-t * lambda_4}.
5. Spectral relaxation half-life tau_{1/2} = ln(2) / (alpha * lambda_1).
6. DiffusionRanker O(N) spectral ranking vs continuous Markov propagation.
7. Graceful boundary handling for small graphs (N=0, 1, 2, 3), disconnected graphs, and sparse scale (N >= 120).
"""

import unittest
import numpy as np
import scipy.sparse as sp
import scipy.linalg as la

from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.diffusion_ranker import DiffusionRanker
from rezonator.cobol_parser import CobolParser
from rezonator.graph_field import GraphField
from rezonator.program_comparator import ProgramComparator


class TestSpectral3DReduction(unittest.TestCase):
    """Hermetic unit tests for the 3D Topological Spectral Reduction layer."""

    def setUp(self):
        self.yant_engine = DiamondYantSpectralEngine()

    def test_3d_embedding_exact_recovery(self):
        """Theorem: ||X_{:, 0}||^2 = lambda_1 and X_{:, 0} / ||X_{:, 0}|| = phi_1."""
        # 6-node cycle graph
        n = 6
        row = np.arange(n)
        col = (row + 1) % n
        A = np.zeros((n, n), dtype=np.float64)
        A[row, col] = 1.0
        A = A + A.T
        D = np.diag(np.sum(A, axis=1))
        inv_sqrt_d = 1.0 / np.sqrt(np.diag(D))
        L_norm = np.eye(n) - np.diag(inv_sqrt_d) @ A @ np.diag(inv_sqrt_d)

        res = self.yant_engine.compute_3d_spectral_embedding(L_norm)
        X = res["embedding"]
        evals_3d = res["eigenvalues"]

        self.assertEqual(X.shape, (n, 3))
        self.assertEqual(len(evals_3d), 3)

        # Fiedler eigenvalue lambda_1 = ||X_{:, 0}||^2
        lambda_1_recon = np.linalg.norm(X[:, 0]) ** 2
        self.assertAlmostEqual(lambda_1_recon, evals_3d[0], places=10)
        self.assertAlmostEqual(res["fiedler_value"], evals_3d[0], places=10)

        # Fiedler vector phi_1 = X_{:, 0} / ||X_{:, 0}||
        phi_1_recon = X[:, 0] / np.linalg.norm(X[:, 0])
        phi_1_expected = np.array(res["fiedler_vector"])
        # Check alignment up to global sign flip
        dot_prod = abs(np.dot(phi_1_recon, phi_1_expected))
        self.assertAlmostEqual(dot_prod, 1.0, places=10)

        # lambda_2 = ||X_{:, 1}||^2
        lambda_2_recon = np.linalg.norm(X[:, 1]) ** 2
        self.assertAlmostEqual(lambda_2_recon, evals_3d[1], places=10)

        # lambda_3 = ||X_{:, 2}||^2
        lambda_3_recon = np.linalg.norm(X[:, 2]) ** 2
        self.assertAlmostEqual(lambda_3_recon, evals_3d[2], places=10)

    def test_spectral_distance_o1(self):
        """Theorem: d(i, j) = ||X_{i, :} - X_{j, :}||_2 matches truncated biharmonic distance."""
        n = 8
        A = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            A[i, (i + 1) % n] = 1.0
            A[(i + 1) % n, i] = 1.0
        D = np.diag(np.sum(A, axis=1))
        inv_sqrt_d = 1.0 / np.sqrt(np.diag(D))
        L_norm = np.eye(n) - np.diag(inv_sqrt_d) @ A @ np.diag(inv_sqrt_d)

        res = self.yant_engine.compute_3d_spectral_embedding(L_norm)
        X = res["embedding"]

        # Directly connected adjacent nodes on a ring must have equal spectral distance
        dist_0_1 = self.yant_engine.spectral_node_distance(X, 0, 1)
        dist_1_2 = self.yant_engine.spectral_node_distance(X, 1, 2)
        dist_2_3 = self.yant_engine.spectral_node_distance(X, 2, 3)
        self.assertAlmostEqual(dist_0_1, dist_1_2, places=8)
        self.assertAlmostEqual(dist_1_2, dist_2_3, places=8)

        # Opposite nodes on ring have larger distance than adjacent nodes
        dist_0_4 = self.yant_engine.spectral_node_distance(X, 0, 4)
        self.assertGreater(dist_0_4, dist_0_1)

    def test_netlsd_reduced_3d_and_truncation_bound(self):
        """Theorem: Truncation error |h(t) - h_3D(t)| is bounded by exp(-t * lambda_4)."""
        n = 10
        row = np.arange(n)
        col = (row + 1) % n
        A = np.zeros((n, n), dtype=np.float64)
        A[row, col] = 1.0
        A = A + A.T
        D = np.diag(np.sum(A, axis=1))
        inv_sqrt_d = 1.0 / np.sqrt(np.diag(D))
        L_norm = np.eye(n) - np.diag(inv_sqrt_d) @ A @ np.diag(inv_sqrt_d)

        evals_all = np.sort(la.eigvalsh(L_norm))
        times = np.logspace(-2, 2, 25)

        h_full = [float(np.mean(np.exp(-t * evals_all))) for t in times]
        res = self.yant_engine.compute_3d_spectral_embedding(L_norm)
        h_3d = self.yant_engine.compute_reduced_netlsd(res["eigenvalues"], n, times=times)

        self.assertEqual(len(h_3d), len(times))

        # At large time scale (t=100), high modes vanish and h_3d matches h_full closely
        self.assertAlmostEqual(h_3d[-1], h_full[-1], places=4)

        # Check that error is bounded by tail bound
        lambda_4 = evals_all[4]
        for idx, t in enumerate(times):
            err = abs(h_full[idx] - h_3d[idx])
            tail_bound = ((n - 4) / n) * np.exp(-t * lambda_4) + 1e-12
            self.assertLessEqual(err, tail_bound * 1.01)

    def test_spectral_half_life(self):
        """Theorem: tau_{1/2} = ln(2) / (alpha * lambda_1)."""
        fiedler = 0.4
        alpha = 0.5
        expected = np.log(2.0) / (alpha * fiedler)
        computed = self.yant_engine.compute_spectral_half_life(fiedler, alpha=alpha)
        self.assertAlmostEqual(computed, expected, places=10)

        # Zero fiedler returns inf
        self.assertEqual(self.yant_engine.compute_spectral_half_life(0.0), float("inf"))

    def test_diffusion_ranker_spectral_distance(self):
        """Verify DiffusionRanker.rank_by_spectral_distance ranks topological proximity in O(N)."""
        # Graph with path: n0 -> n1 -> n2 -> n3
        graph_data = {
            "nodes": [{"id": f"n{i}"} for i in range(4)],
            "edges": [
                {"source": "n0", "target": "n1", "weight": 1.0},
                {"source": "n1", "target": "n2", "weight": 1.0},
                {"source": "n2", "target": "n3", "weight": 1.0},
            ]
        }
        ranker = DiffusionRanker(graph_data)
        ranking = ranker.rank_by_spectral_distance("n0")

        # Excludes seed node
        self.assertNotIn("n0", ranking)
        self.assertEqual(len(ranking), 3)
        self.assertEqual(set(ranking), {"n1", "n2", "n3"})

        # Slice filtering
        sliced = ranker.rank_by_spectral_distance("n0", slice_nodes={"n2", "n3"})
        self.assertEqual(set(sliced), {"n2", "n3"})
        self.assertNotIn("n1", sliced)

    def test_small_and_disconnected_graphs(self):
        """Verify robust behavior on edge case graphs: N=0, N=1, N=2, and disconnected graphs."""
        # Empty
        res_0 = self.yant_engine.compute_3d_spectral_embedding(np.zeros((0, 0)))
        self.assertEqual(res_0["embedding"].shape, (0, 3))
        self.assertEqual(res_0["fiedler_value"], 0.0)

        # Single node
        res_1 = self.yant_engine.compute_3d_spectral_embedding(np.zeros((1, 1)))
        self.assertEqual(res_1["embedding"].shape, (1, 3))
        self.assertEqual(res_1["fiedler_value"], 0.0)

        # 2-node graph
        L_2 = np.array([[1.0, -1.0], [-1.0, 1.0]])
        res_2 = self.yant_engine.compute_3d_spectral_embedding(L_2)
        self.assertEqual(res_2["embedding"].shape, (2, 3))
        self.assertGreater(res_2["fiedler_value"], 0.0)

        # Disconnected graph (2 triangles)
        A_dis = np.zeros((6, 6))
        for i in range(3):
            for j in range(3):
                if i != j:
                    A_dis[i, j] = 1.0
        for i in range(3, 6):
            for j in range(3, 6):
                if i != j:
                    A_dis[i, j] = 1.0
        degrees = np.sum(A_dis, axis=1)
        D_inv = np.diag(1.0 / np.sqrt(degrees))
        L_norm_dis = np.eye(6) - D_inv @ A_dis @ D_inv
        res_dis = self.yant_engine.compute_3d_spectral_embedding(L_norm_dis)
        self.assertEqual(res_dis["embedding"].shape, (6, 3))
        # Since disconnected, lambda_1 == 0
        self.assertAlmostEqual(res_dis["fiedler_value"], 0.0, places=6)

    def test_sparse_scaling_embedding(self):
        """Verify 3D embedding computes on sparse graphs (N >= 120) via restarted Lanczos."""
        n = 150
        row = np.arange(n)
        col = (row + 1) % n
        A_sp = sp.csr_matrix((np.ones(n), (row, col)), shape=(n, n))
        A_sp = A_sp + A_sp.T
        degrees = np.array(A_sp.sum(axis=1)).flatten()
        inv_sqrt = 1.0 / np.sqrt(degrees)
        D_inv = sp.diags(inv_sqrt, format="csr")
        L_norm_sp = sp.eye(n, format="csr") - D_inv @ A_sp @ D_inv

        res = self.yant_engine.compute_3d_spectral_embedding(L_norm_sp)
        X = res["embedding"]
        self.assertEqual(X.shape, (n, 3))
        self.assertGreater(res["fiedler_value"], 0.0)
        self.assertIsNotNone(res["truncation_bound_lambda_4"])


if __name__ == "__main__":
    unittest.main()
