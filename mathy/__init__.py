"""
Backward-compatibility forwarder for legacy 'mathy' imports.
All active development and core implementations are located in 'rezonator'.
"""

import sys
from rezonator import (
    __version__,
    __author__,
    audit_report_to_markdown,
    build_audit_report,
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
    "audit_report_to_markdown",
    "build_audit_report",
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
