"""
Backward-compatibility forwarder for legacy 'mathy' imports.
All active development and core implementations are located in 'rezonator'.
"""

import sys
from rezonator import (
    __version__,
    __author__,
    CobolASTGraphBuilder,
    CobolParser,
    CobolRuntime,
    CycleDetector,
    DiamondYantSpectralEngine,
    DiffusionRanker,
    GraphField,
    LLMSynthesizer,
    MutationBenchmark,
    PINNGraphDiffusionEngine,
    ProgramComparator,
    ProgramSlicer,
)

__all__ = [
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
