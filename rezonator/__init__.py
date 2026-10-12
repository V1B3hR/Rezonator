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
    "audit_report_to_markdown": (".audit_report", "audit_report_to_markdown"),
    "build_audit_report": (".audit_report", "build_audit_report"),
    "build_analysis_events": (".evidence_events", "build_analysis_events"),
    "build_interpreter_run_event": (".evidence_events", "build_interpreter_run_event"),
    "serialize_jsonl_events": (".evidence_events", "serialize_jsonl_events"),
    "parse_jsonl_events": (".evidence_events", "parse_jsonl_events"),
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
    "context_slice_to_markdown": (".program_slicer", "context_slice_to_markdown"),
    "ContextSliceEvaluator": (".program_slicer", "ContextSliceEvaluator"),
    "CorpusEvaluator": (".corpus_evaluator", "CorpusEvaluator"),
    "evaluate_corpus": (".corpus_evaluator", "evaluate_corpus"),
    "corpus_evaluation_to_markdown": (".corpus_evaluator", "corpus_evaluation_to_markdown"),
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
    "audit_report_to_markdown",
    "build_audit_report",
    "build_analysis_events",
    "build_interpreter_run_event",
    "serialize_jsonl_events",
    "parse_jsonl_events",
    "CobolASTGraphBuilder",
    "CobolParser",
    "CobolRuntime",
    "ContextSliceEvaluator",
    "context_slice_to_markdown",
    "CorpusEvaluator",
    "corpus_evaluation_to_markdown",
    "CycleDetector",
    "DiamondYantSpectralEngine",
    "DiffusionRanker",
    "evaluate_corpus",
    "GraphField",
    "LLMSynthesizer",
    "MutationBenchmark",
    "PINNGraphDiffusionEngine",
    "ProgramComparator",
    "ProgramSlicer",
]
