"""
Unit and regression tests for the representative COBOL corpus evaluator.
Verifies parser coverage metrics, copybook resolution, unsupported statement
gap inventory, cycle heuristics, and Sokół evidence event integrity.
"""

from pathlib import Path
import unittest

from rezonator.corpus_evaluator import (
    CorpusEvaluationSummary,
    CorpusEvaluator,
    corpus_evaluation_to_markdown,
    evaluate_corpus,
)


class TestCorpusEvaluator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus_dir = Path("examples/corpus")
        cls.copybooks_dir = Path("examples/corpus/copybooks")
        cls.evaluator = CorpusEvaluator(
            corpus_dir=str(cls.corpus_dir),
            copybooks_dir=str(cls.copybooks_dir),
        )
        cls.summary = cls.evaluator.evaluate_corpus()

    def test_corpus_size_and_files(self):
        self.assertEqual(self.summary.total_files, 6)
        expected_files = {
            "CBL001_BATCH_MASTER_FILE.cbl",
            "CBL002_ACCOUNT_LEDGER_CALC.cbl",
            "CBL003_CUSTOMER_PORTAL_CICS.cbl",
            "CBL004_TRANSACTION_AUDIT_DB2.cbl",
            "CBL005_PAYMENT_CLEARING_CYCLE.cbl",
            "CBL006_POLICY_RULES_TABLE.cbl",
        }
        actual_files = {p.file_name for p in self.summary.programs}
        self.assertEqual(actual_files, expected_files)

    def test_parser_coverage_metrics(self):
        self.assertGreater(self.summary.total_loc, 300)
        self.assertGreater(self.summary.total_statements, 100)
        self.assertGreater(self.summary.total_supported_statements, 100)
        self.assertGreater(self.summary.aggregate_coverage_ratio, 0.80)
        self.assertGreater(self.summary.mean_coverage_ratio, 0.80)

    def test_unsupported_verbs_gap_inventory(self):
        verbs = self.summary.unsupported_verb_frequencies
        self.assertIn("DISPLAY", verbs)
        self.assertIn("OPEN", verbs)
        self.assertIn("CLOSE", verbs)
        self.assertIn("READ", verbs)
        self.assertIn("INITIALIZE", verbs)
        total_unsupported = sum(verbs.values())
        self.assertEqual(total_unsupported, self.summary.total_unsupported_statements)

    def test_sokol_evidence_events_validity(self):
        self.assertTrue(self.summary.all_sokol_events_valid)
        for prog in self.summary.programs:
            self.assertTrue(prog.sokol_valid)
            self.assertGreater(prog.sokol_events_count, 0)
            self.assertEqual(len(prog.source_snapshot_id), 64)
            self.assertEqual(len(prog.analysis_snapshot_id), 64)

    def test_cycle_detection_and_hazard_flagging(self):
        cycle_eval = self.summary.cycle_evaluation
        self.assertEqual(cycle_eval["files_with_cfg_cycles"], 1)
        self.assertIn("CBL005_PAYMENT_CLEARING_CYCLE.cbl", cycle_eval["files_with_cycles_list"])
        cbl005 = next(p for p in self.summary.programs if p.file_name == "CBL005_PAYMENT_CLEARING_CYCLE.cbl")
        self.assertTrue(cbl005.has_deadlock_hazard)
        self.assertGreater(cbl005.cycle_count, 0)

    def test_cics_and_db2_coverage(self):
        cics_prog = next(p for p in self.summary.programs if p.file_name == "CBL003_CUSTOMER_PORTAL_CICS.cbl")
        self.assertEqual(cics_prog.coverage_ratio, 1.0)
        self.assertEqual(cics_prog.unsupported_statements, 0)

        db2_prog = next(p for p in self.summary.programs if p.file_name == "CBL004_TRANSACTION_AUDIT_DB2.cbl")
        self.assertGreaterEqual(db2_prog.coverage_ratio, 0.90)

    def test_markdown_and_json_reports(self):
        md = corpus_evaluation_to_markdown(self.summary)
        self.assertIn("# Rezonator Enterprise COBOL Corpus Evaluation Report", md)
        self.assertIn("## 1. Executive Summary", md)
        self.assertIn("## 2. Program-Level Breakdown", md)
        self.assertIn("## 3. Unsupported Syntax Gap Inventory", md)
        self.assertIn("## 4. Cycle Detection & Semantic Hazard Evaluation", md)
        self.assertIn("## 5. Verification of Pilot Release Gate Criteria", md)

        data = self.summary.to_dict()
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(len(data["programs"]), 6)


if __name__ == "__main__":
    unittest.main()
