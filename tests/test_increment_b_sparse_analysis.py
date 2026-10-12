"""Regression tests for sparse end-to-end graph operators and solvers."""

import unittest
from unittest.mock import patch

import numpy as np
import scipy.sparse as sp

from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.diffusion_ranker import DiffusionRanker
from rezonator.graph_field import GraphField
from rezonator.pinn_diffusion import PINNGraphDiffusionEngine
from rezonator.program_comparator import ProgramComparator
from rezonator.limits import MAX_PINN_NODES, GraphLimitError


def _generated_cobol(statement_count: int) -> str:
    lines = [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. SPARSE-SCALE.",
        "       PROCEDURE DIVISION.",
        "       MAIN-PARA.",
    ]
    lines.extend(f'           DISPLAY "SPARSE-{i:06d}".' for i in range(statement_count))
    lines.append("           STOP RUN.")
    return "\n".join(lines)


class TestIncrementBSparseAnalysis(unittest.TestCase):
    def test_graphfield_operators_are_csr_and_preserve_weighted_invariants(self):
        payload = {
            "program_id": "CSR-INVARIANTS",
            "nodes": [{"id": f"N{i}", "reads": [], "writes": []} for i in range(4)],
            "edges": [
                {"source": "N0", "target": "N1", "weight": 2.0},
                {"source": "N0", "target": "N1", "weight": 1.0},
                {"source": "N1", "target": "N2", "weight": 2.0},
            ],
            "variables": [],
        }
        field = GraphField(payload)
        self.assertTrue(all(sp.isspmatrix_csr(getattr(field, name)) for name in ("A_dir", "A", "D", "L", "L_norm")))
        self.assertEqual(field.A_dir[0, 1], 3.0)
        self.assertEqual(field.num_components, 2)
        self.assertEqual(field.isolated_nodes, ["N3"])
        np.testing.assert_allclose(np.asarray(field.L.sum(axis=1)).ravel(), 0.0, atol=1e-12)
        self.assertEqual(field.L_norm[3, 3], 0.0)

        default_export = field.to_dict()
        self.assertNotIn("adjacency_matrix", default_export)
        csr_export = field.to_dict(include_matrices=True)
        self.assertEqual(csr_export["matrix_format"], "csr")
        self.assertEqual(csr_export["adjacency_matrix"]["shape"], [4, 4])

    def test_graphfield_storage_scales_with_edges_beyond_old_dense_ceiling(self):
        n = 3_000
        payload = {
            "nodes": [{"id": f"N{i}", "reads": [], "writes": []} for i in range(n)],
            "edges": [
                {"source": f"N{i}", "target": f"N{i + 1}", "weight": 1.0}
                for i in range(n - 1)
            ],
            "variables": [],
        }
        field = GraphField(payload)
        self.assertEqual(field.num_nodes, n)
        self.assertLess(field.L.nnz, 3 * n)
        self.assertLess(field.get_operator_storage_bytes(), 3_000_000)
        self.assertLess(field.get_operator_storage_bytes(), 5 * n * n * 8)

    def test_sparse_spectral_failure_never_densifies_as_fallback(self):
        n = 200
        laplacian = sp.diags(
            [-np.ones(n - 1), np.r_[1.0, np.full(n - 2, 2.0), 1.0], -np.ones(n - 1)],
            [-1, 0, 1], shape=(n, n), format="csr",
        )
        with patch("scipy.sparse.linalg.eigsh", side_effect=RuntimeError("forced solver failure")):
            with patch.object(sp.csr_matrix, "toarray", side_effect=AssertionError("unexpected dense conversion")):
                with self.assertRaisesRegex(RuntimeError, "dense fallback is disabled"):
                    DiamondYantSpectralEngine().compute_spectrum(laplacian, laplacian, num_modes=4)

    def test_sparse_analytical_diffusion_and_rankers_accept_large_csr(self):
        n = 300
        laplacian = sp.diags(
            [-np.ones(n - 1), np.r_[1.0, np.full(n - 2, 2.0), 1.0], -np.ones(n - 1)],
            [-1, 0, 1], shape=(n, n), format="csr",
        )
        u0 = np.zeros(n)
        u0[0] = 1.0
        diffusion = PINNGraphDiffusionEngine().solve_analytical(laplacian, u0, time_steps=4, t_max=0.5)
        self.assertEqual(len(diffusion["trajectory"]), 4)
        self.assertAlmostEqual(sum(diffusion["final_state"]), 1.0, delta=0.05)

        graph = {
            "nodes": [{"id": f"N{i}"} for i in range(n)],
            "edges": [{"source": f"N{i}", "target": f"N{i+1}"} for i in range(n - 1)],
        }
        ranker = DiffusionRanker(graph)
        self.assertTrue(sp.isspmatrix_csr(ranker.A_dir))
        self.assertTrue(sp.isspmatrix_csr(ranker.P))
        self.assertEqual(ranker.rank_by_diffusion("N0", t=0.5)[0], "N1")
        self.assertEqual(ranker.rank_by_ppr("N0")[0], "N1")

    def test_sparse_pinn_residual_uses_sparse_operator_and_respects_training_cap(self):
        n = 4
        laplacian = sp.diags(
            [-np.ones(n - 1), np.r_[1.0, np.full(n - 2, 2.0), 1.0], -np.ones(n - 1)],
            [-1, 0, 1], shape=(n, n), format="csr",
        )
        result = PINNGraphDiffusionEngine().train_pinn_residual(
            laplacian, np.array([1.0, 0.0, 0.0, 0.0]), epochs=1
        )
        self.assertTrue(np.isfinite(result["final_loss"]))

        large_laplacian = sp.eye(MAX_PINN_NODES + 1, format="csr")
        with self.assertRaisesRegex(GraphLimitError, "PINN training node limit"):
            PINNGraphDiffusionEngine().train_pinn_residual(
                large_laplacian, np.zeros(MAX_PINN_NODES + 1), epochs=1
            )

    def test_comparator_analyzes_generated_cobol_above_old_dense_limit(self):
        result = ProgramComparator(lattice_size=8).analyze_single(_generated_cobol(2_050))
        self.assertGreater(result["stats"]["num_nodes"], 2_048)
        self.assertGreater(result["stats"]["num_edges"], 2_000)
        self.assertGreater(result["stats"]["density"], 0.0)
        self.assertTrue(result["spectrum"]["eigenvalues"])
        self.assertEqual(len(result["diffusion"]["trajectory"]), 20)
        self.assertEqual(result["parsed"]["parser_coverage"]["unsupported_statements"], 2_050)


if __name__ == "__main__":
    unittest.main()
