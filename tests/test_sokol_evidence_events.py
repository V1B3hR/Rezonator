"""Regression checks for bounded, opt-in Sokół evidence-event envelopes."""

import json
from types import SimpleNamespace
import unittest

from rezonator.audit_report import build_audit_report
from rezonator.evidence_events import (
    build_analysis_events,
    build_interpreter_run_event,
    parse_jsonl_events,
    serialize_jsonl_events,
)
from rezonator.program_comparator import ProgramComparator


SOURCE = '''       IDENTIFICATION DIVISION.
       PROGRAM-ID. EVENT-FIXTURE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNT PIC 9 VALUE 1.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "PRIVATE-SENTINEL" WS-COUNT.
           STOP RUN.
'''


class TestSokolEvidenceEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        analysis = ProgramComparator().analyze_single(SOURCE)
        cls.report = build_audit_report(analysis)
        cls.graph = analysis["parsed"]

    def test_analysis_events_are_snapshot_scoped_and_repeatable(self):
        timestamp = "2026-10-12T12:00:00Z"
        first = build_analysis_events(
            self.report, "test-project", git_commit="b365741", observed_at_utc=timestamp,
        )
        repeat = build_analysis_events(
            self.report, "test-project", git_commit="b365741", observed_at_utc=timestamp,
        )
        self.assertEqual(first, repeat)
        self.assertEqual([event["event_type"] for event in first], ["source.snapshot", "analysis.completed"])
        self.assertEqual(first[0]["payload"]["source_snapshot_id"], first[1]["payload"]["source_snapshot_id"])
        self.assertEqual(
            first[1]["payload"]["analysis_snapshot_id"],
            self.report["provenance"]["analysis_fingerprint"],
        )
        self.assertIn("graph_digest", first[1]["payload"]["graph_digests"])
        self.assertIn("coverage_ratio", first[1]["payload"]["parser"]["coverage"])
        self.assertEqual(first[1]["epistemic_status"], "OBSERVED")

    def test_jsonl_round_trip_and_checksum_rejects_edits(self):
        events = build_analysis_events(
            self.report, "test-project", observed_at_utc="2026-10-12T12:00:00Z",
        )
        stream = serialize_jsonl_events(events)
        self.assertTrue(stream.endswith("\n"))
        self.assertEqual(parse_jsonl_events(stream), events)

        edited = json.loads(stream.splitlines()[1])
        edited["payload"]["parser"]["engine"] = "forged"
        with self.assertRaisesRegex(ValueError, "checksum"):
            parse_jsonl_events(json.dumps(edited))

    def test_events_exclude_source_and_statement_text(self):
        events = build_analysis_events(
            self.report, "test-project", observed_at_utc="2026-10-12T12:00:00Z",
        )
        stream = serialize_jsonl_events(events)
        self.assertNotIn("PRIVATE-SENTINEL", stream)
        self.assertNotIn('"code":', stream)
        self.assertIn("source_anchors", events[1]["payload"])

    def test_interpreter_event_omits_values_and_bounds_trace(self):
        state = SimpleNamespace(
            variables={"WS-SECRET": "DO-NOT-EXPORT"},
            trace=["NODE-1", "NODE-2", "NODE-1"],
            steps=3,
            terminated=True,
            timed_out=False,
        )
        graph = {"nodes": [
            {"id": "NODE-1", "paragraph": "MAIN-PARA", "location": {"line": 8}},
            {"id": "NODE-2", "paragraph": "MAIN-PARA", "source_origin": {
                "source": "LOGIC.CPY", "line": 3, "copybook_stack": ["ROOT.CPY", "LOGIC.CPY"],
            }},
        ]}
        event = build_interpreter_run_event(
            state,
            "test-project",
            run_id="fixture-run-1",
            source_snapshot_id="a" * 64,
            analysis_snapshot_id="b" * 64,
            graph_data=graph,
            observed_at_utc="2026-10-12T12:00:00Z",
            max_trace_nodes=2,
        )
        payload = event["payload"]
        self.assertEqual(event["epistemic_status"], "OBSERVED")
        self.assertEqual(payload["observation_scope"], "bounded_interpreter_only")
        self.assertEqual(payload["visited_nodes_omitted"], 1)
        self.assertEqual(payload["visited_nodes"][1]["source_origin"]["source"], "LOGIC.CPY")
        serialized = serialize_jsonl_events([event])
        self.assertNotIn("DO-NOT-EXPORT", serialized)
        self.assertNotIn("WS-SECRET", serialized)
        self.assertFalse(payload["raw_variable_values_included"])

    def test_invalid_timestamps_and_blank_jsonl_records_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            build_analysis_events(self.report, "test-project", observed_at_utc="2026-10-12T12:00:00")
        with self.assertRaisesRegex(ValueError, "filesystem path"):
            build_analysis_events(self.report, r"C:\customer\project")
        with self.assertRaisesRegex(ValueError, "blank JSONL"):
            parse_jsonl_events("\n")


if __name__ == "__main__":
    unittest.main()
