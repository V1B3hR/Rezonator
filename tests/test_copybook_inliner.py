"""F4.2 regression tests for nested COPYBOOK expansion."""

import unittest

from rezonator import CopybookInliner, CopybookResolutionError
from rezonator.ast_graph_builder import CobolASTGraphBuilder


class TestCopybookInliner(unittest.TestCase):
    def test_nested_copybooks_and_replacing(self):
        inliner = CopybookInliner(
            {
                "ROOT.CPY": "01 CUSTOMER-ID PIC X(10).\nCOPY DETAIL.CPY.",
                "DETAIL.CPY": "01 CUSTOMER-BALANCE PIC 9(7)V99.",
                "RENAMED.CPY": "01 ==FIELD== PIC X(8).\n01 ==COUNT== PIC 9(2).",
            }
        )

        nested_result = inliner.inline_with_provenance("       COPY ROOT.\n")
        self.assertIn("CUSTOMER-ID", nested_result.text)
        self.assertIn("CUSTOMER-BALANCE", nested_result.text)
        self.assertEqual(nested_result.line_origins[0].source, "ROOT.CPY")
        self.assertEqual(nested_result.line_origins[1].source, "DETAIL.CPY")
        self.assertEqual(nested_result.line_origins[1].copybook_stack, ("ROOT.CPY", "DETAIL.CPY"))

        replaced = inliner.inline(
            "       COPY RENAMED REPLACING ==FIELD== BY ==WS-NAME== ==COUNT== BY ==WS-COUNT==.\n"
        )
        self.assertIn("WS-NAME", replaced)
        self.assertIn("WS-COUNT", replaced)
        self.assertNotIn("==FIELD==", replaced)

    def test_circular_references_are_rejected_with_chain(self):
        inliner = CopybookInliner(
            {
                "A.CPY": "COPY B.",
                "B.CPY": "COPY A.",
            }
        )
        with self.assertRaisesRegex(CopybookResolutionError, r"A\.CPY -> B\.CPY -> A\.CPY"):
            inliner.inline("COPY A.\n")

    def test_copybooks_feed_working_storage_and_graph_construction(self):
        source = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. COPYBOOK-DEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ACCOUNT-FIELDS.
       PROCEDURE DIVISION.
       MAIN.
           MOVE 42 TO WS-ACCOUNT-ID.
           STOP RUN.
"""
        builder = CobolASTGraphBuilder(
            copybooks={"ACCOUNT-FIELDS.CPY": "01 WS-ACCOUNT-ID PIC 9(4)."}
        )
        data = builder.build_from_source(source)

        self.assertEqual(data["program_id"], "COPYBOOK-DEMO")
        account_var = next(item for item in data["variables"] if item["name"] == "WS-ACCOUNT-ID")
        self.assertEqual(account_var["source_origin"]["source"], "ACCOUNT-FIELDS.CPY")
        self.assertEqual(account_var["source_origin"]["line"], 1)
        move_node = next(node for node in data["nodes"] if node["code"].startswith("MOVE"))
        self.assertEqual(move_node["source_origin"]["source"], "main")


if __name__ == "__main__":
    unittest.main()
