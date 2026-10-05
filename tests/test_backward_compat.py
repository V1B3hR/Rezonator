"""
Backward Compatibility Verification Test.
Ensures legacy imports from `mathy` export identical symbols to `rezonator`.
"""

import unittest


class TestBackwardCompat(unittest.TestCase):

    def test_package_exports(self):
        import rezonator
        import mathy

        self.assertEqual(rezonator.__version__, mathy.__version__)

        symbols = [
            "CobolASTGraphBuilder",
            "CobolParser",
            "CobolRuntime",
            "CycleDetector",
            "DiamondYantSpectralEngine",
            "DiffusionRanker",
            "GraphField",
            "LLMSynthesizer",
            "MutationBenchmark",
            "PINNGraphDiffusionEngine",
            "ProgramComparator",
            "ProgramSlicer",
        ]

        for sym in symbols:
            self.assertTrue(hasattr(rezonator, sym), f"rezonator missing {sym}")
            self.assertTrue(hasattr(mathy, sym), f"mathy missing {sym}")
            self.assertIs(getattr(rezonator, sym), getattr(mathy, sym), f"Symbol {sym} mismatch")

    def test_legacy_submodule_imports(self):
        from mathy.ast_graph_builder import CobolASTGraphBuilder as LegacyBuilder
        from rezonator.ast_graph_builder import CobolASTGraphBuilder as ModernBuilder
        self.assertIs(LegacyBuilder, ModernBuilder)

        from mathy.diamond_yant import DiamondYantSpectralEngine as LegacySpectral
        from rezonator.diamond_yant import DiamondYantSpectralEngine as ModernSpectral
        self.assertIs(LegacySpectral, ModernSpectral)

        from mathy.server import MathyRequestHandler as LegacyHandler
        from rezonator.server import MathyRequestHandler as ModernHandler
        self.assertIs(LegacyHandler, ModernHandler)


if __name__ == "__main__":
    unittest.main()
