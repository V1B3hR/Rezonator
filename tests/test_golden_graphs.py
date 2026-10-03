"""
Golden Graph Verification Suite (Phase F1).
Enforces 100% exact graph isomorphism against the ground-truth specification
for all 4 canonical COBOL programs.
"""

import os
import sys
import unittest
from typing import Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mathy.ast_graph_builder import CobolASTGraphBuilder
from mathy.graph_field import GraphField
from mathy.cycle_detector import CycleDetector
from tests.golden_graphs import (
    BANK_DEMO_V1_NODES, BANK_DEMO_V1_EDGES, BANK_DEMO_V1_VARS,
    BANK_DEMO_V2_NODES, BANK_DEMO_V2_EDGES, BANK_DEMO_V2_VARS,
    ATM_DEADLOCK_NODES, ATM_DEADLOCK_EDGES, ATM_DEADLOCK_VARS,
    BATCH_INTEREST_NODES, BATCH_INTEREST_EDGES, BATCH_INTEREST_VARS,
)


class TestGoldenGraphs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.examples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
        cls.builder = CobolASTGraphBuilder()

    def _load_code(self, filename: str) -> str:
        filepath = os.path.join(self.examples_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def _extract_edge_tuples(self, edges: list) -> Set[Tuple[str, str, str]]:
        return {(e["source"], e["target"], e["edge_type"]) for e in edges}

    def _assert_graph_invariants(self, data: dict, field: GraphField):
        # 1. No dangling edges: all source and target nodes must exist in nodes list
        node_ids = {n["id"] for n in data["nodes"]}
        for e in data["edges"]:
            self.assertIn(e["source"], node_ids, f"Dangling edge source: {e['source']}")
            self.assertIn(e["target"], node_ids, f"Dangling edge target: {e['target']}")

        # 2. Laplacian symmetry: L == L.T
        import numpy as np
        self.assertTrue(np.allclose(field.L, field.L.T, atol=1e-8), "Laplacian L must be symmetric")
        self.assertTrue(np.allclose(field.L_norm, field.L_norm.T, atol=1e-8), "Normalized Laplacian L_norm must be symmetric")

    def test_01_bank_demo_v1_golden_isomorphism(self):
        code = self._load_code("bank_demo_v1.cbl")
        data = self.builder.build_from_source(code)
        field = GraphField(data, symmetrize=True, include_variables=True)
        cycles = CycleDetector(data).analyze()

        # Exact Node Isomorphism
        actual_nodes = {n["id"] for n in data["nodes"]}
        expected_nodes = set(BANK_DEMO_V1_NODES)
        self.assertEqual(actual_nodes, expected_nodes, f"Node mismatch in BANK-DEMO-V1: {actual_nodes ^ expected_nodes}")

        # Exact Edge Isomorphism
        actual_edges = self._extract_edge_tuples(data["edges"])
        expected_edges = set(BANK_DEMO_V1_EDGES)
        self.assertEqual(actual_edges, expected_edges, f"Edge mismatch in BANK-DEMO-V1: {actual_edges ^ expected_edges}")

        # Variables Check
        actual_vars = {v["name"] for v in data["variables"]}
        expected_vars = set(BANK_DEMO_V1_VARS)
        self.assertEqual(actual_vars, expected_vars)

        # Graph Field Invariants
        self._assert_graph_invariants(data, field)
        self.assertEqual(field.num_components, 1, "V1 must have exactly 1 connected component")
        self.assertEqual(len(field.isolated_nodes), 0, "V1 must have 0 isolated nodes")

        # Cycle / Deadlock Invariants
        self.assertEqual(cycles["cycle_count"], 0, "V1 must have 0 cycles")
        self.assertFalse(cycles["has_deadlock"])
        self.assertEqual(cycles["risk_verdict"], "DIRECTED_ACYCLIC_FLOW")

    def test_02_bank_demo_v2_golden_isomorphism(self):
        code = self._load_code("bank_demo_v2.cbl")
        data = self.builder.build_from_source(code)
        field = GraphField(data, symmetrize=True, include_variables=True)
        cycles = CycleDetector(data).analyze()

        actual_nodes = {n["id"] for n in data["nodes"]}
        expected_nodes = set(BANK_DEMO_V2_NODES)
        self.assertEqual(actual_nodes, expected_nodes, f"Node mismatch in BANK-DEMO-V2: {actual_nodes ^ expected_nodes}")

        actual_edges = self._extract_edge_tuples(data["edges"])
        expected_edges = set(BANK_DEMO_V2_EDGES)
        self.assertEqual(actual_edges, expected_edges, f"Edge mismatch in BANK-DEMO-V2: {actual_edges ^ expected_edges}")

        actual_vars = {v["name"] for v in data["variables"]}
        expected_vars = set(BANK_DEMO_V2_VARS)
        self.assertEqual(actual_vars, expected_vars)

        self._assert_graph_invariants(data, field)
        self.assertEqual(field.num_components, 1, "V2 must have exactly 1 connected component")
        self.assertEqual(len(field.isolated_nodes), 0, "V2 must have 0 isolated nodes")

        self.assertEqual(cycles["cycle_count"], 0)
        self.assertFalse(cycles["has_deadlock"])
        self.assertEqual(cycles["risk_verdict"], "DIRECTED_ACYCLIC_FLOW")

    def test_03_atm_deadlock_golden_isomorphism(self):
        code = self._load_code("atm_deadlock.cbl")
        data = self.builder.build_from_source(code)
        field = GraphField(data, symmetrize=True, include_variables=True)
        cycles = CycleDetector(data).analyze()

        actual_nodes = {n["id"] for n in data["nodes"]}
        expected_nodes = set(ATM_DEADLOCK_NODES)
        self.assertEqual(actual_nodes, expected_nodes, f"Node mismatch in ATM-DEADLOCK: {actual_nodes ^ expected_nodes}")

        actual_edges = self._extract_edge_tuples(data["edges"])
        expected_edges = set(ATM_DEADLOCK_EDGES)
        self.assertEqual(actual_edges, expected_edges, f"Edge mismatch in ATM-DEADLOCK: {actual_edges ^ expected_edges}")

        actual_vars = {v["name"] for v in data["variables"]}
        expected_vars = set(ATM_DEADLOCK_VARS)
        self.assertEqual(actual_vars, expected_vars)

        self._assert_graph_invariants(data, field)

        # ATM-DEADLOCK must trigger critical cycle detection
        self.assertEqual(cycles["cycle_count"], 1, "ATM-DEADLOCK must have exactly 1 recursive cycle")
        self.assertTrue(cycles["has_deadlock"])
        self.assertTrue(cycles["is_recursive"])
        self.assertEqual(cycles["risk_verdict"], "CRITICAL_INFINITE_LOOP")

    def test_04_batch_interest_golden_isomorphism(self):
        code = self._load_code("batch_interest.cbl")
        data = self.builder.build_from_source(code)
        field = GraphField(data, symmetrize=True, include_variables=True)
        cycles = CycleDetector(data).analyze()

        actual_nodes = {n["id"] for n in data["nodes"]}
        expected_nodes = set(BATCH_INTEREST_NODES)
        self.assertEqual(actual_nodes, expected_nodes, f"Node mismatch in BATCH-INTEREST: {actual_nodes ^ expected_nodes}")

        actual_edges = self._extract_edge_tuples(data["edges"])
        expected_edges = set(BATCH_INTEREST_EDGES)
        self.assertEqual(actual_edges, expected_edges, f"Edge mismatch in BATCH-INTEREST: {actual_edges ^ expected_edges}")

        actual_vars = {v["name"] for v in data["variables"]}
        expected_vars = set(BATCH_INTEREST_VARS)
        self.assertEqual(actual_vars, expected_vars)

        self._assert_graph_invariants(data, field)

        # BATCH-INTEREST must have exactly 2 connected components due to dead variable WS-MONTHS-ACTIVE
        self.assertEqual(field.num_components, 2, "BATCH-INTEREST must have 2 components (program + dead variable)")
        self.assertEqual(field.isolated_nodes, ["var_WS-MONTHS-ACTIVE"], "Isolated node must be var_WS-MONTHS-ACTIVE")

        self.assertEqual(cycles["cycle_count"], 0)
        self.assertFalse(cycles["has_deadlock"])
        self.assertEqual(cycles["risk_verdict"], "DIRECTED_ACYCLIC_FLOW")

    def test_05_runtime_execution_traces(self):
        from mathy.cobol_runtime import CobolRuntime
        runtime = CobolRuntime()

        # 1. Bank Demo V1
        c1 = self._load_code("bank_demo_v1.cbl")
        s1 = runtime.run(c1)
        self.assertTrue(s1.terminated)
        self.assertFalse(s1.timed_out)
        self.assertEqual(s1.variables["WS-ACCOUNT-BALANCE"], 3800.00)
        self.assertEqual(s1.variables["WS-STATUS-CODE"], "DONE")
        self.assertEqual(s1.variables["WS-AUDIT-FLAG"], 1)

        # 2. Bank Demo V2
        c2 = self._load_code("bank_demo_v2.cbl")
        s2 = runtime.run(c2)
        self.assertTrue(s2.terminated)
        self.assertFalse(s2.timed_out)
        self.assertEqual(s2.variables["WS-ACCOUNT-BALANCE"], 3800.00)
        self.assertEqual(s2.variables["WS-STATUS-CODE"], "DONE")
        self.assertEqual(s2.variables["WS-AUDIT-FLAG"], 2)
        self.assertEqual(s2.variables["WS-FRAUD-ALERT"], 0)

        # 3. ATM Deadlock (Infinite loop)
        cd = self._load_code("atm_deadlock.cbl")
        sd = runtime.run(cd, max_steps=40)
        self.assertFalse(sd.terminated)
        self.assertTrue(sd.timed_out)
        self.assertGreater(sd.variables["WS-RETRY-COUNT"], 10)

        # 4. Batch Interest
        cb = self._load_code("batch_interest.cbl")
        sb = runtime.run(cb)
        self.assertTrue(sb.terminated)
        self.assertFalse(sb.timed_out)
        self.assertAlmostEqual(sb.variables["WS-TOTAL-ACCRUAL"], 251145.83, places=1)
        self.assertAlmostEqual(sb.variables["WS-COMPOUND-INTEREST"], 1145.83, places=1)
        self.assertAlmostEqual(sb.variables["WS-NET-PAYOUT"], 250928.13, places=1)
        # Dead variable WS-MONTHS-ACTIVE must remain completely unchanged
        self.assertEqual(sb.variables["WS-MONTHS-ACTIVE"], 36)

    def test_06_mutation_ground_truth_impact(self):
        from mathy.cobol_runtime import CobolRuntime
        runtime = CobolRuntime()

        c1 = self._load_code("bank_demo_v1.cbl")
        # Mutate line 29: SUBTRACT -> ADD
        mut_res = runtime.mutate_and_compare(c1, [
            ("SUBTRACT WS-WITHDRAW-AMOUNT FROM WS-ACCOUNT-BALANCE.",
             "ADD WS-WITHDRAW-AMOUNT TO WS-ACCOUNT-BALANCE.")
        ])

        self.assertTrue(mut_res["has_behavioral_change"])
        self.assertIn("WS-ACCOUNT-BALANCE", mut_res["affected_variables"])
        diff = mut_res["affected_variables"]["WS-ACCOUNT-BALANCE"]
        self.assertEqual(diff["baseline"], 3800.0)
        self.assertEqual(diff["mutated"], 6200.0)
        self.assertIsNotNone(mut_res["trace_diverged_at_step"])


if __name__ == "__main__":
    unittest.main()

