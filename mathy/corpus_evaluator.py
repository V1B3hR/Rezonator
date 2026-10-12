"""Compatibility shim redirecting mathy.corpus_evaluator to rezonator.corpus_evaluator."""

from rezonator.corpus_evaluator import (
    CorpusEvaluationSummary,
    CorpusEvaluator,
    EVALUATOR_SCHEMA_VERSION,
    ProgramEvaluationResult,
    corpus_evaluation_to_markdown,
    evaluate_corpus,
)

__all__ = [
    "CorpusEvaluationSummary",
    "CorpusEvaluator",
    "EVALUATOR_SCHEMA_VERSION",
    "ProgramEvaluationResult",
    "corpus_evaluation_to_markdown",
    "evaluate_corpus",
]
