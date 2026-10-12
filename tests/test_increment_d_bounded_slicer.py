"""Increment D regressions: Bounded context-slice beta, budgets & omission disclosure."""

import copy
import json
import unittest

from rezonator.ast_graph_builder import CobolASTGraphBuilder
from rezonator.program_slicer import (
    ContextSliceEvaluator,
    ProgramSlicer,
    context_slice_to_markdown,
    estimate_tokens,
)


BANK_CODE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. BANK-DEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCOUNT-BALANCE PIC 9(6) VALUE 1000.
       01 WS-WITHDRAWAL-AMT  PIC 9(4) VALUE 200.
       01 WS-STATUS-CODE     PIC X(4) VALUE "INIT".
       01 WS-AUTH-CODE       PIC X(4) VALUE "NONE".
       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-VALIDATE.
           IF WS-STATUS-CODE = "OKAY"
               PERFORM 2000-PROCESS
           ELSE
               PERFORM 3000-REJECT.
           STOP RUN.
       1000-VALIDATE.
           IF WS-WITHDRAWAL-AMT <= WS-ACCOUNT-BALANCE
               MOVE "OKAY" TO WS-STATUS-CODE
           ELSE
               MOVE "FAIL" TO WS-STATUS-CODE.
       2000-PROCESS.
           SUBTRACT WS-WITHDRAWAL-AMT FROM WS-ACCOUNT-BALANCE.
           MOVE "APPR" TO WS-AUTH-CODE.
       3000-REJECT.
           MOVE "DENY" TO WS-AUTH-CODE.
"""

COPYBOOK_CODE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SLICE-COPYBOOK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ACC-FIELDS.
       PROCEDURE DIVISION.
       MAIN-PARA.
           COPY SLICE-LOGIC.
           STOP RUN.
"""

COPYBOOKS = {
    "ACC-FIELDS.CPY": "01 WS-BAL PIC 9(5) VALUE 500.",
    "SLICE-LOGIC.CPY": 'COMPUTE WS-BAL = WS-BAL - 50.\n           DISPLAY "UPDATED".',
}


class TestIncrementDBoundedSlicer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        builder = CobolASTGraphBuilder()
        cls.graph = builder.build_from_source(BANK_CODE)
        cls.copybook_graph = CobolASTGraphBuilder(copybooks=COPYBOOKS).build_from_source(COPYBOOK_CODE)

    def test_seed_resolution_by_line_and_variable(self):
        slicer = ProgramSlicer(self.graph)

        # 1. Resolve by direct node ID
        seed_id = slicer.find_seed_node(seed_node_id="1000-VALIDATE:L19_MOVE")
        self.assertEqual(seed_id, "1000-VALIDATE:L19_MOVE")

        # 2. Resolve by source line number (Line 19 is MOVE "OKAY")
        seed_by_line = slicer.find_seed_node(seed_line=19)
        self.assertEqual(seed_by_line, "1000-VALIDATE:L19_MOVE")

        # 3. Resolve by variable (WS-STATUS-CODE is modified at Line 19 & 21)
        seed_by_var = slicer.find_seed_node(seed_variable="WS-STATUS-CODE")
        self.assertIsNotNone(seed_by_var)
        self.assertIn(seed_by_var, slicer.nodes_by_id)

        # 4. Unknown seed raises ValueError in extract_bounded_slice
        with self.assertRaises(ValueError):
            slicer.extract_bounded_slice(seed_node_id="NON-EXISTENT-NODE")

    def test_bounded_slice_respects_line_budget_and_discloses_omissions(self):
        slicer = ProgramSlicer(self.graph)
        seed_node = "1000-VALIDATE:L19_MOVE"

        # Full slice without budget limits
        full_packet = slicer.extract_bounded_slice(
            seed_node_id=seed_node,
            max_lines=100,
            max_tokens=5000,
            max_nodes=100,
        )
        total_slice_nodes = full_packet["slice_scope"]["total_slice_nodes"]
        self.assertGreaterEqual(total_slice_nodes, 4)
        self.assertFalse(full_packet["slice_scope"]["is_truncated"])
        self.assertEqual(len(full_packet["omitted_dependencies"]), 0)

        # Restrict budget to 2 lines
        restricted_packet = slicer.extract_bounded_slice(
            seed_node_id=seed_node,
            max_lines=2,
            max_tokens=5000,
            max_nodes=None,
        )
        scope = restricted_packet["slice_scope"]
        self.assertTrue(scope["is_truncated"])
        self.assertIn("max_lines_exceeded", scope["truncation_reasons"])
        self.assertEqual(scope["included_nodes_count"], 2)
        self.assertEqual(
            scope["included_nodes_count"] + scope["omitted_nodes_count"],
            total_slice_nodes,
        )

        # Verify omitted dependencies contract
        omitted = restricted_packet["omitted_dependencies"]
        self.assertEqual(len(omitted), scope["omitted_nodes_count"])
        for item in omitted:
            self.assertIn("node_id", item)
            self.assertIn("code", item)
            self.assertIn("paragraph", item)
            self.assertIn("hop_distance", item)
            self.assertEqual(item["omission_reason"], "budget_truncation")

    def test_bounded_slice_respects_token_budget(self):
        slicer = ProgramSlicer(self.graph)
        seed_node = "1000-VALIDATE:L19_MOVE"

        # Restrict token budget to a very small count (e.g. 15 tokens)
        token_restricted = slicer.extract_bounded_slice(
            seed_node_id=seed_node,
            max_lines=100,
            max_tokens=15,
            max_nodes=None,
        )
        scope = token_restricted["slice_scope"]
        self.assertTrue(scope["is_truncated"])
        self.assertIn("max_tokens_exceeded", scope["truncation_reasons"])
        self.assertLessEqual(scope["estimated_tokens_used"], 15)
        self.assertGreater(scope["omitted_nodes_count"], 0)

    def test_backward_and_bidirectional_slicing(self):
        slicer = ProgramSlicer(self.graph)
        # Node at 2000-PROCESS: SUBTRACT (Line 23)
        seed_node = "2000-PROCESS:L23_SUBTRACT"

        # Backward slice: what influenced this SUBTRACT?
        backward_packet = slicer.extract_bounded_slice(
            seed_node_id=seed_node,
            direction="backward",
            max_lines=50,
        )
        b_included_ids = {s["node_id"] for s in backward_packet["included_statements"]}
        self.assertIn(seed_node, b_included_ids)

        # Forward slice from same seed
        forward_packet = slicer.extract_bounded_slice(
            seed_node_id=seed_node,
            direction="forward",
            max_lines=50,
        )
        f_included_ids = {s["node_id"] for s in forward_packet["included_statements"]}

        # Bidirectional slice must be superset of both
        bidi_packet = slicer.extract_bounded_slice(
            seed_node_id=seed_node,
            direction="bidirectional",
            max_lines=50,
        )
        bidi_included_ids = {s["node_id"] for s in bidi_packet["included_statements"]}
        self.assertTrue(b_included_ids.issubset(bidi_included_ids))
        self.assertTrue(f_included_ids.issubset(bidi_included_ids))

    def test_source_mapping_and_copybook_origin_preservation(self):
        slicer = ProgramSlicer(self.copybook_graph)
        seed_node = slicer.find_seed_node(seed_variable="WS-BAL")
        self.assertIsNotNone(seed_node)

        packet = slicer.extract_bounded_slice(seed_node_id=seed_node, max_lines=50)
        self.assertEqual(packet["slice_schema_version"], "1.0")
        self.assertIn("WS-BAL", packet["seed"]["code"])

        # Check statement source origins
        origins = [s["source_origin"] for s in packet["included_statements"] if s.get("source_origin")]
        self.assertTrue(any(orig["source"] == "SLICE-LOGIC.CPY" for orig in origins))

    def test_snippet_reconstruction_and_markdown_rendering(self):
        slicer = ProgramSlicer(self.graph)
        seed_node = "1000-VALIDATE:L19_MOVE"

        packet = slicer.extract_bounded_slice(
            seed_node_id=seed_node,
            max_lines=2,
            max_tokens=1000,
        )
        markdown = context_slice_to_markdown(packet)

        self.assertIn("# Rezonator Bounded Context Slice", markdown)
        self.assertIn("## Reconstructed COBOL Slice", markdown)
        self.assertIn("## Included Statements", markdown)
        self.assertIn("## Omitted Dependencies", markdown)
        self.assertIn("## Limitations", markdown)
        self.assertIn("budget limit", packet["reconstructed_snippet"])

    def test_evaluator_metrics_and_budget_sweeps(self):
        slice_nodes = {"A", "B", "C"}
        ground_truth = {"B", "C", "D"}

        metrics = ContextSliceEvaluator.evaluate_slice(slice_nodes, ground_truth)
        self.assertAlmostEqual(metrics["precision"], 2 / 3)
        self.assertAlmostEqual(metrics["recall"], 2 / 3)
        self.assertAlmostEqual(metrics["f1"], 2 / 3)
        self.assertAlmostEqual(metrics["jaccard"], 2 / 4)

        # Budget sweep benchmark across examples
        sweep_report = ContextSliceEvaluator.benchmark_budget_sweeps(budgets=[2, 5, 10])
        self.assertGreater(sweep_report["total_evaluated_mutations"], 0)
        first_exp = sweep_report["experiments"][0]
        self.assertIn("sweep", first_exp)
        self.assertIn("budget_2", first_exp["sweep"])
        self.assertTrue(first_exp["sweep"]["budget_2"]["is_truncated"])


if __name__ == "__main__":
    unittest.main()
