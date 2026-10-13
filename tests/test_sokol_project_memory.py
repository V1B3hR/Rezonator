"""
Regression tests for Sokół Versioned Project Memory (sokol.fact.v1).
Verifies epistemic rules, verification non-transfer, anchor remapping,
staleness invalidation, privacy boundary checks, and JSONL integrity.
"""

from pathlib import Path
import unittest

from rezonator.audit_report import build_audit_report
from rezonator.program_comparator import ProgramComparator
from rezonator.project_memory import (
    FACT_SCHEMA_VERSION,
    NodeAnchor,
    ProjectMemory,
    build_fact_anchor,
    create_fact,
    validate_fact,
)


SOURCE_V1 = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MEMORY-DEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNTER PIC 9(04) VALUE 0.
       01 WS-FLAG    PIC X(01) VALUE 'N'.
       PROCEDURE DIVISION.
       1000-INIT.
           MOVE 0 TO WS-COUNTER.
           MOVE 'Y' TO WS-FLAG.
       2000-PROCESS.
           ADD 1 TO WS-COUNTER.
           STOP RUN.
"""

# Modified source: comments added at top, 2000-PROCESS modified
SOURCE_V2 = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MEMORY-DEMO.
      * Revision 2 with shifted line numbers and modified logic
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNTER PIC 9(04) VALUE 0.
       01 WS-FLAG    PIC X(01) VALUE 'N'.
       PROCEDURE DIVISION.
       1000-INIT.
           MOVE 0 TO WS-COUNTER.
           MOVE 'Y' TO WS-FLAG.
       2000-PROCESS.
           COMPUTE WS-COUNTER = WS-COUNTER + 2.
           STOP RUN.
"""


class TestSokolProjectMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comparator = ProgramComparator()
        cls.analysis_v1 = cls.comparator.analyze_single(SOURCE_V1)
        cls.report_v1 = build_audit_report(cls.analysis_v1)
        cls.source_snap_v1 = cls.report_v1["provenance"]["source_sha256"]

        cls.analysis_v2 = cls.comparator.analyze_single(SOURCE_V2)
        cls.report_v2 = build_audit_report(cls.analysis_v2)
        cls.source_snap_v2 = cls.report_v2["provenance"]["source_sha256"]

    def test_create_and_validate_fact_envelope(self):
        anchor = NodeAnchor(
            paragraph="1000-INIT",
            statement_index=0,
            verb="MOVE",
            signature="MOVE 0 TO WS-COUNTER",
        ).to_dict()

        fact = create_fact(
            claim="WS-COUNTER is initialized to zero at session start",
            status="OBSERVED",
            source_snapshot=self.source_snap_v1,
            node_anchor=anchor,
            evidence_ids=["sha256:" + "a" * 64],
            confidence="high",
            created_at_utc="2026-10-13T08:00:00Z",
        )

        self.assertEqual(fact["schema_version"], FACT_SCHEMA_VERSION)
        self.assertTrue(fact["fact_id"].startswith("fact:sha256:"))
        self.assertEqual(fact["status"], "OBSERVED")
        self.assertFalse(fact["stale"])
        self.assertIsNone(fact["staleness_reason"])

        # Tampering with claim must cause checksum rejection
        tampered = dict(fact)
        tampered["claim"] = "TAMPERED CLAIM"
        with self.assertRaises(ValueError) as ctx:
            validate_fact(tampered)
        self.assertIn("fact_id checksum mismatch", str(ctx.exception))

    def test_epistemic_validation_rules(self):
        anchor = {"paragraph": "1000-INIT", "verb": "MOVE", "signature": "MOVE 0 TO WS-COUNTER"}

        # VERIFIED requires a non-null verification_basis
        with self.assertRaises(ValueError) as ctx:
            create_fact(
                claim="Counter never overflows",
                status="VERIFIED",
                source_snapshot=self.source_snap_v1,
                node_anchor=anchor,
                verification_basis=None,
            )
        self.assertIn("verification_basis", str(ctx.exception))

        # VERIFIED succeeds with compliant basis
        basis = {
            "basis_type": "assertion_test",
            "test_reference": "test_counter_bounds",
            "snapshot_id": self.source_snap_v1,
            "verified_at_utc": "2026-10-13T08:00:00Z",
        }
        verified_fact = create_fact(
            claim="Counter bounded within range 0-9999",
            status="VERIFIED",
            source_snapshot=self.source_snap_v1,
            node_anchor=anchor,
            verification_basis=basis,
        )
        self.assertEqual(verified_fact["status"], "VERIFIED")

        # INFERRED must cite at least one evidence_id
        with self.assertRaises(ValueError) as ctx:
            create_fact(
                claim="Flag may control downstream reporting",
                status="INFERRED",
                source_snapshot=self.source_snap_v1,
                node_anchor=anchor,
                evidence_ids=[],
            )
        self.assertIn("must cite at least one evidence_id", str(ctx.exception))

    def test_privacy_boundary_rejection(self):
        anchor = {"paragraph": "1000-INIT", "verb": "MOVE"}
        with self.assertRaises(ValueError) as ctx:
            create_fact(
                claim="Code in PROCEDURE DIVISION.\nMOVE 0 TO WS-COUNTER.",
                status="OBSERVED",
                source_snapshot=self.source_snap_v1,
                node_anchor=anchor,
            )
        self.assertIn("prohibited raw source division header", str(ctx.exception))

    def test_build_fact_anchor_from_graph_node(self):
        nodes = self.analysis_v1["parsed"]["nodes"]
        move_node = next(n for n in nodes if "MOVE 0 TO WS-COUNTER" in n.get("code", ""))
        anchor = build_fact_anchor(move_node, statement_index=0)

        self.assertEqual(anchor["paragraph"], "1000-INIT")
        self.assertEqual(anchor["verb"], "MOVE")
        self.assertIn("MOVE 0 TO WS-COUNTER", anchor["signature"])
        self.assertIsNotNone(anchor["node_id"])

    def test_reconciliation_and_staleness_invalidation(self):
        memory = ProjectMemory(project_id="audit-pilot")

        # 1. Register fact for 1000-INIT (remains identical in V2)
        fact_init = create_fact(
            claim="WS-FLAG initialized to Y in 1000-INIT",
            status="INFERRED",
            source_snapshot=self.source_snap_v1,
            node_anchor={"paragraph": "1000-INIT", "signature": "MOVE 'Y' TO WS-FLAG", "verb": "MOVE"},
            evidence_ids=["sha256:" + "b" * 64],
        )
        memory.register_fact(fact_init)

        # 2. Register VERIFIED fact on 1000-INIT
        basis = {
            "basis_type": "reviewer_attestation",
            "reviewer": "auditor:senior",
            "snapshot_id": self.source_snap_v1,
        }
        fact_verified = create_fact(
            claim="WS-COUNTER resets to 0 before processing",
            status="VERIFIED",
            source_snapshot=self.source_snap_v1,
            node_anchor={"paragraph": "1000-INIT", "signature": "MOVE 0 TO WS-COUNTER", "verb": "MOVE"},
            verification_basis=basis,
        )
        memory.register_fact(fact_verified)

        # 3. Register fact on 2000-PROCESS statement (modified in V2)
        fact_proc = create_fact(
            claim="WS-COUNTER incremented by 1",
            status="INFERRED",
            source_snapshot=self.source_snap_v1,
            node_anchor={"paragraph": "2000-PROCESS", "signature": "ADD 1 TO WS-COUNTER", "verb": "ADD"},
            evidence_ids=["sha256:" + "c" * 64],
        )
        memory.register_fact(fact_proc)

        # Reconcile against same snapshot V1: all remain active
        recon_v1 = memory.reconcile_with_snapshot(self.analysis_v1)
        self.assertEqual(recon_v1["active_count"], 3)
        self.assertEqual(recon_v1["stale_count"], 0)

        # Reconcile against modified snapshot V2:
        recon_v2 = memory.reconcile_with_snapshot(self.analysis_v2)
        self.assertEqual(recon_v2["reverification_required"], 1)

        # Fact 1 (1000-INIT move flag): code unchanged in V2, so anchor remapped and remains active
        updated_init = memory.get_fact(fact_init["fact_id"])
        self.assertFalse(updated_init["stale"])

        # Fact 2 (VERIFIED): MUST be invalidated to STALE on snapshot change (no silent verification transfer!)
        updated_verified = memory.get_fact(fact_verified["fact_id"])
        self.assertTrue(updated_verified["stale"])
        self.assertEqual(updated_verified["staleness_reason"], "snapshot_changed_reverification_required")

        # Fact 3 (2000-PROCESS add): ADD statement was replaced by COMPUTE in V2, anchor unmappable -> STALE
        updated_proc = memory.get_fact(fact_proc["fact_id"])
        self.assertTrue(updated_proc["stale"])
        self.assertEqual(updated_proc["staleness_reason"], "anchor_unmappable")

        # Query active vs historical facts
        active_facts = memory.list_facts(include_stale=False)
        self.assertEqual(len(active_facts), 1)
        self.assertEqual(active_facts[0]["fact_id"], fact_init["fact_id"])

        all_facts = memory.list_facts(include_stale=True)
        self.assertEqual(len(all_facts), 3)

    def test_json_and_jsonl_serialization_and_report(self):
        memory = ProjectMemory(project_id="test-store")
        fact = create_fact(
            claim="WS-FLAG tested in main loop",
            status="INFERRED",
            source_snapshot=self.source_snap_v1,
            node_anchor={"paragraph": "1000-INIT", "signature": "MOVE 'Y' TO WS-FLAG"},
            evidence_ids=["sha256:" + "1" * 64],
        )
        memory.register_fact(fact)

        # JSON round-trip
        json_data = memory.serialize_json()
        parsed_json_memory = ProjectMemory.parse_json(json_data)
        self.assertEqual(len(parsed_json_memory), 1)
        self.assertEqual(parsed_json_memory.get_fact(fact["fact_id"]), fact)

        # JSONL round-trip
        jsonl_data = memory.serialize_jsonl()
        parsed_jsonl_memory = ProjectMemory.parse_jsonl(jsonl_data, project_id="test-store")
        self.assertEqual(len(parsed_jsonl_memory), 1)

        # Markdown report rendering
        md_report = memory.to_markdown_report()
        self.assertIn("# Sokół Project Memory Report: `test-store`", md_report)
        self.assertIn("## Active Knowledge Base", md_report)
        self.assertIn("WS-FLAG tested in main loop", md_report)


if __name__ == "__main__":
    unittest.main()
