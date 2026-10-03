"""
Unit and Integration Tests for Hypothesis H1 & Mutation Benchmark Suite.
Tests slicing, diffusion ranking, mutation discovery, and empirical verification.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mathy.ast_graph_builder import CobolASTGraphBuilder
from mathy.program_slicer import ProgramSlicer
from mathy.diffusion_ranker import DiffusionRanker
from mathy.mutation_benchmark import MutationBenchmark


class TestHypothesisH1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.examples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
        cls.builder = CobolASTGraphBuilder()

        with open(os.path.join(cls.examples_dir, "bank_demo_v1.cbl"), "r", encoding="utf-8") as f:
            cls.code_v1 = f.read()

        cls.graph_v1 = cls.builder.build_from_source(cls.code_v1)

    def test_01_program_slicer(self):
        slicer = ProgramSlicer(self.graph_v1)
        seed_node = "1000-VALIDATE-REQUEST:L23_MOVE"  # MOVE "OKAY" TO WS-STATUS-CODE

        forward_slice = slicer.compute_forward_slice(seed_node)
        self.assertIn(seed_node, forward_slice)
        # Should reach IF condition that reads WS-STATUS-CODE
        self.assertIn("0000-MAIN-LOGIC:L13_IF", forward_slice)

        bfs_rank = slicer.rank_by_bfs(seed_node, forward_slice)
        self.assertNotIn(seed_node, bfs_rank)
        self.assertGreater(len(bfs_rank), 0)

        rand_rank = slicer.rank_by_random(seed_node, forward_slice, seed=42)
        self.assertEqual(len(rand_rank), len(bfs_rank))

    def test_02_diffusion_ranker(self):
        ranker = DiffusionRanker(self.graph_v1)
        seed_node = "1000-VALIDATE-REQUEST:L23_MOVE"

        diff_ranking = ranker.rank_by_diffusion(seed_node, t=1.5)
        self.assertNotIn(seed_node, diff_ranking)
        self.assertGreater(len(diff_ranking), 0)

        ppr_ranking = ranker.rank_by_ppr(seed_node, alpha=0.85)
        self.assertNotIn(seed_node, ppr_ranking)
        self.assertGreater(len(ppr_ranking), 0)

    def test_03_mutation_generator(self):
        bench = MutationBenchmark(self.examples_dir)
        mutations = bench.generate_mutations("bank_demo_v1.cbl", self.code_v1, self.graph_v1)
        self.assertGreater(len(mutations), 0)

        # Check arithmetic and condition mutators were generated
        descs = [m.description for m in mutations]
        self.assertTrue(any("SUBTRACT" in d for d in descs))
        self.assertTrue(any("condition" in d.lower() for d in descs))

    def test_04_hypothesis_h1_benchmark_battery(self):
        bench = MutationBenchmark(self.examples_dir)
        summary = bench.run_full_benchmark()

        self.assertNotIn("error", summary)
        num_exp = summary["valid_behavioral_experiments"]
        self.assertGreaterEqual(num_exp, 30, f"Must evaluate at least 30 experiments; got {num_exp}")

        cmp = summary["comparison"]
        # Diffusion MAP must beat BFS baseline
        self.assertGreater(cmp["map"]["diffusion"], cmp["map"]["bfs"])

        # Diffusion MRR must beat BFS baseline
        self.assertGreater(cmp["mrr"]["diffusion"], cmp["mrr"]["bfs"])

        # Check verdict exists and is well-formed
        verdict = summary["hypothesis_h1_verdict"]
        self.assertIn("hypothesis_h1_confirmed", verdict)
        self.assertIn("delta_precision@1_pp", verdict)


if __name__ == "__main__":
    unittest.main()
