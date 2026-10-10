"""
Rezonator: Physics & Spectral Topology Engine for Code Intelligence.
Bridging Legacy COBOL/Mainframe Systems with Graph Laplacians, PINN Diffusion,
Diamond Yant Modal Cymatics, and Directed Impact Analysis.
"""

import importlib

__version__ = "1.0.0"
__author__ = "Błyskawica & Rezonator Team"

# Keep package import lightweight and deterministic.  Scientific and optional
# ML dependencies are loaded only when the corresponding public symbol is
# actually requested.
_LAZY_EXPORTS = {
    "CobolASTGraphBuilder": (".ast_graph_builder", "CobolASTGraphBuilder"),
    "CopybookInliner": (".copybooks", "CopybookInliner"),
    "CopybookResolutionError": (".copybooks", "CopybookResolutionError"),
    "InlinedSource": (".copybooks", "InlinedSource"),
    "SourceOrigin": (".copybooks", "SourceOrigin"),
    "GraphLimitError": (".limits", "GraphLimitError"),
    "ResourceLimitError": (".limits", "ResourceLimitError"),
    "CobolParser": (".cobol_parser", "CobolParser"),
    "CobolRuntime": (".cobol_runtime", "CobolRuntime"),
    "CycleDetector": (".cycle_detector", "CycleDetector"),
    "DiamondYantSpectralEngine": (".diamond_yant", "DiamondYantSpectralEngine"),
    "DiffusionRanker": (".diffusion_ranker", "DiffusionRanker"),
    "GraphField": (".graph_field", "GraphField"),
    "LLMSynthesizer": (".llm_synthesizer", "LLMSynthesizer"),
    "MutationBenchmark": (".mutation_benchmark", "MutationBenchmark"),
    "PINNGraphDiffusionEngine": (".pinn_diffusion", "PINNGraphDiffusionEngine"),
    "ProgramComparator": (".program_comparator", "ProgramComparator"),
    "ProgramSlicer": (".program_slicer", "ProgramSlicer"),
}


def __getattr__(name):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, symbol_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name, __name__)
    symbol = getattr(module, symbol_name)
    globals()[name] = symbol
    return symbol

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
