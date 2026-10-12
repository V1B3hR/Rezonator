"""
Tests for Increment A: Truthful Parser, Tarjan SCC Cycle Detection, and Neutral Comparator Verdicts.
"""

import unittest
from rezonator.cobol_parser import CobolParser
from rezonator.ast_graph_builder import (
    CobolASTGraphBuilder,
    parse_cobol_source,
    UnhandledStatement,
)
from rezonator.cycle_detector import CycleDetector
from rezonator.program_comparator import ProgramComparator


class TestIncrementATruthfulParser(unittest.TestCase):

    def setUp(self):
        self.code_with_unhandled = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO-UNHANDLED.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-USER-ID PIC X(10) VALUE "USR001".
       01 WS-BALANCE PIC 9(7)V99 VALUE 2500.50.
       PROCEDURE DIVISION.
       0000-MAIN.
           DISPLAY "STARTING BATCH JOB FOR " WS-USER-ID.
           MOVE 3000.00 TO WS-BALANCE.
           CALL "AUDIT-SERVICE" USING WS-USER-ID WS-BALANCE.
           ACCEPT WS-USER-ID.
           STOP RUN.
        """.strip()

        self.code_pure_supported = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO-SUPPORTED.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(5) VALUE 10.
       01 WS-B PIC 9(5) VALUE 20.
       PROCEDURE DIVISION.
       0000-MAIN.
           MOVE 10 TO WS-A.
           ADD WS-A TO WS-B.
           STOP RUN.
        """.strip()

    def test_unhandled_statements_materialization_and_coverage(self):
        builder = CobolASTGraphBuilder()
        payload = builder.build_from_source(self.code_with_unhandled)

        # 1. Verify coverage metadata
        cov = payload.get("parser_coverage")
        self.assertIsNotNone(cov)
        self.assertEqual(cov["unsupported_statements"], 3)  # DISPLAY, CALL, ACCEPT
        self.assertEqual(cov["supported_statements"], 2)    # MOVE, STOP RUN
        self.assertEqual(cov["total_statements"], 5)
        self.assertAlmostEqual(cov["coverage_ratio"], 0.40, places=2)

        # 2. Verify unhandled statements list
        unsupported = payload.get("unsupported_statements", [])
        self.assertEqual(len(unsupported), 3)
        verbs = [item["verb"] for item in unsupported]
        self.assertIn("DISPLAY", verbs)
        self.assertIn("CALL", verbs)
        self.assertIn("ACCEPT", verbs)

        # 3. Verify graph nodes exist for unhandled statements
        node_types = {n["id"]: n["node_type"] for n in payload["nodes"]}
        unsupported_nodes = [n for n in payload["nodes"] if n["node_type"] == "unsupported_stmt"]
        self.assertEqual(len(unsupported_nodes), 3)

        # 4. Verify sequential control flow reaches through unsupported nodes
        seq_edges = [e for e in payload["edges"] if e.get("edge_type") == "cfg_seq"]
        self.assertGreaterEqual(len(seq_edges), 3)

    def test_unhandled_statement_variable_read_dependencies(self):
        builder = CobolASTGraphBuilder()
        payload = builder.build_from_source(self.code_with_unhandled)

        # The CALL statement references WS-USER-ID and WS-BALANCE
        call_nodes = [n for n in payload["nodes"] if "CALL" in n["label"]]
        self.assertEqual(len(call_nodes), 1)
        call_node = call_nodes[0]
        self.assertIn("WS-USER-ID", call_node["reads"])
        self.assertIn("WS-BALANCE", call_node["reads"])

        # Data-flow edge must link the writer of WS-BALANCE (MOVE 3000.00 TO WS-BALANCE) to the CALL node
        def_use_edges = [
            e for e in payload["edges"]
            if e.get("edge_type") == "dfg_def_use" and e.get("target") == call_node["id"]
        ]
        self.assertTrue(len(def_use_edges) > 0)

    def test_copybook_expansion_retains_provenance_on_unhandled_statement(self):
        copybooks = {
            "LOGGING.CPY": "DISPLAY \"LOG EVENT RECORDED\"."
        }
        source_with_copy = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COPY-PROV.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-FLAG PIC X VALUE "Y".
       PROCEDURE DIVISION.
       0000-MAIN.
           COPY LOGGING.CPY.
           STOP RUN.
        """.strip()

        builder = CobolASTGraphBuilder(copybooks=copybooks)
        payload = builder.build_from_source(source_with_copy)

        unsupported = payload.get("unsupported_statements", [])
        self.assertEqual(len(unsupported), 1)
        self.assertEqual(unsupported[0]["verb"], "DISPLAY")

        # Must retain copybook source provenance
        origin = unsupported[0].get("source_origin")
        self.assertIsNotNone(origin)
        self.assertEqual(origin.get("source"), "LOGGING.CPY")
        self.assertEqual(origin.get("line"), 1)

    def test_cycle_detector_tarjan_scc_acyclic_dag(self):
        builder = CobolASTGraphBuilder()
        payload = builder.build_from_source(self.code_pure_supported)

        detector = CycleDetector(payload)
        analysis = detector.analyze()

        self.assertFalse(analysis["has_cycles"])
        self.assertFalse(analysis["has_deadlock"])
        self.assertFalse(analysis["is_recursive"])
        self.assertEqual(analysis["scc_count"], 0)
        self.assertEqual(analysis["trapped_scc_count"], 0)
        self.assertEqual(analysis["risk_verdict"], "DIRECTED_ACYCLIC_FLOW")
        self.assertTrue(analysis["reaches_terminal"])

    def test_cycle_detector_tarjan_scc_trapped_cycle(self):
        trapped_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRAPPED-LOOP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNT PIC 9(4) VALUE 0.
       01 WS-DEVICE-READY PIC X VALUE "N".
       PROCEDURE DIVISION.
       0000-MAIN.
           ADD 1 TO WS-COUNT.
           IF WS-DEVICE-READY = "Y"
               STOP RUN
           ELSE
               PERFORM 0000-MAIN
           END-IF.
        """.strip()

        builder = CobolASTGraphBuilder()
        payload = builder.build_from_source(trapped_code)

        detector = CycleDetector(payload)
        analysis = detector.analyze()

        self.assertTrue(analysis["has_cycles"])
        self.assertTrue(analysis["has_deadlock"])
        self.assertTrue(analysis["is_recursive"])
        self.assertGreaterEqual(analysis["scc_count"], 1)
        self.assertEqual(analysis["risk_verdict"], "CRITICAL_INFINITE_LOOP")
        self.assertTrue(len(analysis["sccs"]) >= 1)

    def test_cycle_detector_bounded_cycle_budget(self):
        # Construct a synthetic multi-cyclic CFG payload
        # Complete directed graph K_7 has many simple cycles
        nodes = [{"id": f"N{i}", "node_type": "stmt", "label": f"STMT_{i}", "paragraph": "P", "code": f"C{i}"} for i in range(7)]
        edges = []
        for i in range(7):
            for j in range(7):
                if i != j:
                    edges.append({"source": f"N{i}", "target": f"N{j}", "edge_type": "cfg_seq"})

        synthetic_payload = {
            "program_id": "SYNTH-DENSE",
            "nodes": nodes,
            "edges": edges,
            "variables": []
        }

        detector = CycleDetector(synthetic_payload)
        analysis = detector.analyze()

        self.assertTrue(analysis["has_cycles"])
        self.assertTrue(analysis["cycle_budget_exhausted"])
        self.assertLessEqual(analysis["cycle_count"], 100)
        self.assertEqual(analysis["scc_count"], 1)

    def test_comparator_neutral_structural_verdicts(self):
        comparator = ProgramComparator(lattice_size=16)

        with open("examples/bank_demo_v1.cbl", "r") as f:
            code_v1 = f.read()
        with open("examples/bank_demo_v2.cbl", "r") as f:
            code_v2 = f.read()
        with open("examples/atm_deadlock.cbl", "r") as f:
            code_deadlock = f.read()

        # 1. Modular extension
        res_ext = comparator.compare(code_v1, code_v2)
        self.assertIn("STRUCTURAL_MODULAR_EXTENSION", res_ext["verdict"])
        self.assertNotIn("SAFE_MODULAR_EXTENSION", res_ext["verdict"])

        # 2. Hazard reduced
        res_fixed = comparator.compare(code_deadlock, code_v1)
        self.assertIn("HAZARD_REDUCED", res_fixed["verdict"])
        self.assertNotIn("DEFECT_RESOLVED", res_fixed["verdict"])

        # 3. Critical regression
        res_reg = comparator.compare(code_v1, code_deadlock)
        self.assertIn("CRITICAL_REGRESSION", res_reg["verdict"])


if __name__ == "__main__":
    unittest.main()
