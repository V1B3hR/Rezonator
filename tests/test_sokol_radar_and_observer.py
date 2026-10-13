"""
Tests for Sokół Step 5: Spectral Change Radar, Idiom Miner, and Read-Only Observer.

Verifies:
1. SokolRadar: Compatibility checks, metric deltas, and review candidates without diagnosing failure.
2. IdiomMiner: Mined idioms strictly tagged as INFERRED, supporting node anchors, and fact creation.
3. DataTransferPolicy: Rejection of unredacted variables, undeclared truncation, and unauthorized remote transfer.
4. ObserverContextPacket: Content-addressed packets, untrusted code boundary shielding.
5. SokolObserver: Deterministic offline mode and epistemic gate (downgrading VERIFIED to INFERRED, checking evidence citations).
6. Backward compatibility between rezonator and mathy exports.
"""

import unittest
from rezonator.cobol_parser import CobolParser
from rezonator.program_comparator import ProgramComparator
from rezonator.project_memory import ProjectMemory, NodeAnchor
from rezonator.sokol_radar import SokolRadar, build_radar_report, radar_report_to_markdown
from rezonator.idiom_miner import IdiomMiner, mined_idiom_to_fact
from rezonator.sokol_observer import (
    DataTransferPolicy,
    ObserverContextPacket,
    PolicyViolationError,
    SokolObserver,
)
import mathy


SAMPLE_COBOL_BASELINE = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RADAR-BASE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-FLAG        PIC X(1) VALUE 'N'.
       01  WS-COUNT       PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
       0000-MAIN.
           MOVE 'Y' TO WS-FLAG.
           PERFORM 1000-PROCESS.
           STOP RUN.
       1000-PROCESS.
           ADD 1 TO WS-COUNT.
           IF WS-COUNT > 10
               MOVE 'N' TO WS-FLAG
           END-IF.
"""

SAMPLE_COBOL_CANDIDATE = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RADAR-CAND.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-FLAG        PIC X(1) VALUE 'N'.
       01  WS-COUNT       PIC 9(4) VALUE 0.
       01  WS-UNUSED-1    PIC X(10) VALUE 'DEAD'.
       01  WS-UNUSED-2    PIC X(10) VALUE 'ISOLATED'.
       PROCEDURE DIVISION.
       0000-MAIN.
           MOVE 'Y' TO WS-FLAG.
           PERFORM 1000-PROCESS.
           STOP RUN.
       1000-PROCESS.
           ADD 1 TO WS-COUNT.
"""

SAMPLE_COBOL_DEFENSIVE = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEF-IDIOM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-STATUS      PIC 9(2) VALUE 0.
       PROCEDURE DIVISION.
       0000-ENTRY.
           MOVE 0 TO WS-STATUS.
           MOVE 1 TO WS-STATUS.
           PERFORM 2000-CALL.
           IF WS-STATUS = 0
               GOBACK
           END-IF.
       2000-CALL.
           CALL 'EXT-ROUTINE'.
           IF WS-STATUS NOT = 0
               PERFORM 9999-ERROR-EXIT
           END-IF.
       9999-ERROR-EXIT.
           STOP RUN.
"""


class TestSokolRadarAndObserver(unittest.TestCase):
    """Test suite for Sokół Step 5 architectural components."""

    def setUp(self):
        self.comparator = ProgramComparator()
        self.analysis_base = self.comparator.analyze_single(SAMPLE_COBOL_BASELINE)
        self.analysis_cand = self.comparator.analyze_single(SAMPLE_COBOL_CANDIDATE)

    def test_01_radar_compatibility_check(self):
        """Verifies like-for-like compatibility validation."""
        radar = SokolRadar()

        # Both analyzed with same parser -> COMPATIBLE
        compat = radar.check_compatibility(self.analysis_base, self.analysis_cand)
        self.assertTrue(compat["compatible"])
        self.assertEqual(compat["status"], "COMPATIBLE")

        # Artificial engine mismatch
        mismatched = dict(self.analysis_cand)
        mismatched["provenance"] = {
            "parser_options": {"selected_engine": "different_synthetic_engine"}
        }
        incompat = radar.check_compatibility(self.analysis_base, mismatched)
        self.assertFalse(incompat["compatible"])
        self.assertEqual(incompat["status"], "INCOMPATIBLE_ANALYSIS_SNAPSHOTS")
        self.assertTrue(any("Mismatched parser engines" in r for r in incompat["reasons"]))

    def test_02_radar_metric_deltas_and_review_candidates(self):
        """Verifies metric deltas and review candidate nomination without failure diagnoses."""
        radar = SokolRadar(fiedler_threshold=0.01)
        report = radar.evaluate(self.analysis_base, self.analysis_cand)

        self.assertEqual(report["schema_version"], "sokol.radar.v1")
        self.assertIn("metric_deltas", report)
        self.assertIn("review_candidates", report)

        deltas = report["metric_deltas"]
        self.assertIn("netlsd_distance", deltas)
        self.assertIn("fiedler_delta", deltas)
        self.assertIn("stochastic_noise_floor", deltas)

        # Candidates should be present and strictly advisory
        for cand in report["review_candidates"]:
            # Golden rule: Never diagnose as business-logic failure
            cleaned_basis = cand["rational_basis"].lower().replace("not a business-logic failure", "")
            self.assertNotIn("business-logic failure", cleaned_basis)
            self.assertNotIn("logic is broken", cleaned_basis)
            self.assertIn("review_guidance", cand)
            self.assertIn("rational_basis", cand)

        md = radar_report_to_markdown(report)
        self.assertIn("# Sokół Spectral Change Radar Report", md)
        self.assertIn("Radar Verdict:", md)

    def test_03_idiom_miner_strict_inferred_status(self):
        """Verifies that mined idioms are strictly labeled INFERRED and convertible to facts."""
        parsed = CobolParser().parse(SAMPLE_COBOL_DEFENSIVE)
        valid_src_hash = "a" * 64
        valid_grp_hash = "b" * 64

        miner = IdiomMiner(min_pattern_instances=1)
        idioms = miner.mine_idioms(parsed, source_snapshot=valid_src_hash, graph_snapshot=valid_grp_hash)

        self.assertGreater(len(idioms), 0)
        for idiom in idioms:
            # Epistemic invariant: Mined patterns must be INFERRED
            self.assertEqual(idiom["status"], "INFERRED")
            self.assertIn("pattern_name", idiom)
            self.assertIn("supporting_anchors", idiom)
            self.assertGreater(len(idiom["supporting_anchors"]), 0)

            # Convert to ProjectMemory fact
            fact = mined_idiom_to_fact(idiom, source_snapshot=valid_src_hash, graph_snapshot=valid_grp_hash)
            self.assertEqual(fact["status"], "INFERRED")
            self.assertEqual(fact["schema_version"], "sokol.fact.v1")
            self.assertIn("evidence_ids", fact)

            # Store in ProjectMemory
            memory = ProjectMemory()
            fact_id = memory.register_fact(fact)
            self.assertTrue(fact_id.startswith("fact:sha256:"))

    def test_04_data_transfer_policy_rejection_rules(self):
        """Verifies DataTransferPolicy privacy boundaries."""
        policy = DataTransferPolicy(
            local_only=True,
            require_truncation_disclosure=True,
            allow_variable_values=False,
        )

        # 1. Reject undeclared truncation
        with self.assertRaises(PolicyViolationError):
            policy.validate_packet({
                "truncation_disclosed": False,
            })

        # 2. Reject raw variable values
        with self.assertRaises(PolicyViolationError):
            policy.validate_packet({
                "truncation_disclosed": True,
                "variable_values": {"WS-FLAG": "Y", "WS-COUNT": 42},
            })

        # 3. Reject unauthorized remote transfer
        remote_policy = DataTransferPolicy(local_only=False, allow_remote_transfer=False)
        with self.assertRaises(PolicyViolationError):
            remote_policy.validate_packet({
                "truncation_disclosed": True,
            })

    def test_05_observer_context_packet_and_untrusted_data_shielding(self):
        """Verifies packet structure and prompt shielding of untrusted code."""
        slice_data = {
            "seed_statement": "MOVE 'Y' TO WS-FLAG",
            "direction": "forward",
            "source_text": "0000-MAIN. MOVE 'Y' TO WS-FLAG. PERFORM 1000-PROCESS.",
            "omitted_nodes": 4,
        }
        packet = ObserverContextPacket(
            source_snapshot_id="sha256:source-1234",
            analysis_snapshot_id="sha256:analysis-5678",
            context_slice=slice_data,
            truncation_disclosed=True,
        )

        self.assertTrue(packet.packet_id.startswith("packet:sha256:"))
        prompt = packet.format_prompt_text()

        # Prompt must clearly demarcate untrusted data
        self.assertIn("UNTRUSTED DATA BOUNDARY", prompt)
        self.assertIn("READ-ONLY COBOL OBSERVER", prompt)
        self.assertIn("PACKET ID:", prompt)

    def test_06_sokol_observer_deterministic_offline_mode(self):
        """Verifies 100% offline deterministic synthesis mode."""
        slice_data = {
            "seed_statement": "MOVE 'Y' TO WS-FLAG",
            "direction": "forward",
            "source_text": "0000-MAIN. MOVE 'Y' TO WS-FLAG.",
        }
        packet = ObserverContextPacket(
            source_snapshot_id="sha256:source-1234",
            analysis_snapshot_id="sha256:analysis-5678",
            context_slice=slice_data,
            truncation_disclosed=True,
        )

        observer = SokolObserver()
        res = observer.observe(packet)

        self.assertEqual(res["schema_version"], "sokol.observer.v1")
        self.assertEqual(res["observer_mode"], "DETERMINISTIC_OFFLINE")
        self.assertEqual(res["status"], "COMPLETED")
        self.assertGreater(len(res["hypotheses"]), 0)

        # Every hypothesis must be INFERRED
        for hyp in res["hypotheses"]:
            self.assertEqual(hyp["status"], "INFERRED")

        self.assertGreater(len(res["review_questions"]), 0)

    def test_07_sokol_observer_model_epistemic_gate(self):
        """Verifies that model claims of VERIFIED are downgraded and invalid citations are stripped."""
        slice_data = {"seed_statement": "ADD 1 TO WS-COUNT", "direction": "forward"}
        packet = ObserverContextPacket(
            source_snapshot_id="sha256:src-abc",
            analysis_snapshot_id="sha256:ana-xyz",
            context_slice=slice_data,
            truncation_disclosed=True,
        )

        # Mock model adapter returning unverified claim with hallucinated citation
        def mock_llm_adapter(prompt: str):
            return {
                "hypotheses": [
                    {
                        "hypothesis_id": "hyp:test-1",
                        "status": "VERIFIED",  # Model claims VERIFIED without authority
                        "claim": "WS-COUNT is definitely incremented in every loop cycle",
                        "cited_evidence_ids": [
                            f"snapshot:{packet.source_snapshot_id}",
                            "event:hallucinated-id-9999",  # Hallucinated evidence ID
                        ],
                    }
                ],
                "review_questions": ["Is WS-COUNT checked for overflow?"],
            }

        observer = SokolObserver(observer_fn=mock_llm_adapter)
        res = observer.observe(packet)

        self.assertEqual(res["observer_mode"], "EXTERNAL_MODEL_ADAPTER")
        self.assertEqual(len(res["hypotheses"]), 1)
        hyp = res["hypotheses"][0]

        # Epistemic gate: Model-claimed VERIFIED MUST be downgraded to INFERRED
        self.assertEqual(hyp["status"], "INFERRED")
        self.assertIn("downgraded to INFERRED", hyp["epistemic_note"])

        # Hallucinated evidence ID must be stripped
        self.assertIn(f"snapshot:{packet.source_snapshot_id}", hyp["cited_evidence_ids"])
        self.assertNotIn("event:hallucinated-id-9999", hyp["cited_evidence_ids"])

    def test_08_backward_compatibility_exports(self):
        """Verifies that mathy exports resolve to the exact same rezonator classes."""
        self.assertIs(mathy.SokolRadar, SokolRadar)
        self.assertIs(mathy.build_radar_report, build_radar_report)
        self.assertIs(mathy.IdiomMiner, IdiomMiner)
        self.assertIs(mathy.SokolObserver, SokolObserver)
        self.assertIs(mathy.DataTransferPolicy, DataTransferPolicy)
        self.assertIs(mathy.ObserverContextPacket, ObserverContextPacket)


if __name__ == "__main__":
    unittest.main()
