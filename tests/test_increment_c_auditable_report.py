"""Increment C regressions for deterministic provenance and audit reports."""

import copy
import hashlib
import json
import unittest

from rezonator.audit_report import audit_report_to_markdown, build_audit_report
from rezonator.copybooks import CopybookResolutionError
from rezonator.program_comparator import ProgramComparator
from rezonator.provenance import graph_digest, source_provenance


COPYBOOK_PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. AUDIT-COPYBOOK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ACCOUNT-FIELDS.
       PROCEDURE DIVISION.
       MAIN-PARA.
           COPY AUDIT-STATEMENT.
           STOP RUN.
"""


COPYBOOKS = {
    "ACCOUNT-FIELDS.CPY": "01 WS-ACCOUNT PIC 9(5).",
    "AUDIT-STATEMENT.CPY": 'DISPLAY "ACCOUNT " WS-ACCOUNT.',
}


class TestIncrementCAuditableReport(unittest.TestCase):
    def test_manifest_fingerprint_is_deterministic_and_sensitive_to_inputs(self):
        options = {"spectral": {"lattice_size": 32}, "graph": {"include_variables": True}}
        first = source_provenance(
            COPYBOOK_PROGRAM,
            analysis_options=options,
            copybooks=COPYBOOKS,
        )
        same = source_provenance(
            COPYBOOK_PROGRAM,
            analysis_options=options,
            copybooks=dict(reversed(list(COPYBOOKS.items()))),
        )
        changed_copybook = source_provenance(
            COPYBOOK_PROGRAM,
            analysis_options=options,
            copybooks={**COPYBOOKS, "AUDIT-STATEMENT.CPY": 'DISPLAY "CHANGED".'},
        )
        changed_options = source_provenance(
            COPYBOOK_PROGRAM,
            analysis_options={"spectral": {"lattice_size": 16}},
            copybooks=COPYBOOKS,
        )
        graph_a = {"nodes": [{"id": "A", "node_type": "stmt"}], "edges": []}
        graph_b = {"nodes": [{"id": "B", "node_type": "stmt"}], "edges": []}
        fingerprint_graph_a = source_provenance(
            COPYBOOK_PROGRAM, analysis_options=options, copybooks=COPYBOOKS, graph_data=graph_a,
        )
        fingerprint_graph_b = source_provenance(
            COPYBOOK_PROGRAM, analysis_options=options, copybooks=COPYBOOKS, graph_data=graph_b,
        )

        self.assertEqual(first["analysis_fingerprint"], same["analysis_fingerprint"])
        self.assertEqual(first["source_sha256"], same["source_sha256"])
        self.assertNotEqual(first["analysis_fingerprint"], changed_copybook["analysis_fingerprint"])
        self.assertNotEqual(first["analysis_fingerprint"], changed_options["analysis_fingerprint"])
        self.assertNotEqual(
            fingerprint_graph_a["analysis_fingerprint"],
            fingerprint_graph_b["analysis_fingerprint"],
        )
        self.assertIn("scipy", first["dependency_versions"])
        self.assertEqual(first["manifest_schema_version"], "1.0")

    def test_graph_digest_is_order_independent_and_topology_sensitive(self):
        parsed = {
            "nodes": [
                {"id": "A", "node_type": "stmt", "reads": ["X"], "writes": []},
                {"id": "B", "node_type": "stop", "reads": [], "writes": ["X"]},
            ],
            "variables": [{"name": "X"}],
            "edges": [{"source": "A", "target": "B", "edge_type": "cfg_seq", "weight": 1.0}],
        }
        reversed_payload = {
            **parsed,
            "nodes": list(reversed(parsed["nodes"])),
            "edges": list(reversed(parsed["edges"])),
        }
        changed_payload = copy.deepcopy(parsed)
        changed_payload["edges"][0]["target"] = "A"

        canonical_graph = {
            "edges": [
                {"edge_type": "cfg_seq", "source": "A", "target": "B", "weight": 1.0},
                {"edge_type": "dfg_read", "source": "var_X", "target": "A", "weight": 1.2},
                {"edge_type": "dfg_write", "source": "B", "target": "var_X", "weight": 1.5},
            ],
            "nodes": [
                {"id": "A", "node_type": "stmt"},
                {"id": "B", "node_type": "stop"},
                {"id": "var_X", "node_type": "var"},
            ],
        }
        expected_digest = hashlib.sha256(json.dumps(
            canonical_graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()

        self.assertEqual(graph_digest(parsed), graph_digest(reversed_payload))
        self.assertEqual(graph_digest(parsed), expected_digest)
        self.assertNotEqual(graph_digest(parsed), graph_digest(changed_payload))

    def test_copybook_analysis_provenance_and_report_trace_findings_to_origin(self):
        analysis = ProgramComparator(copybooks=COPYBOOKS).analyze_single(COPYBOOK_PROGRAM)
        report = build_audit_report(analysis)
        json.dumps(report, allow_nan=False)
        unsupported = next(
            finding for finding in report["findings"]
            if finding["kind"] == "unsupported_statement"
        )

        self.assertTrue(report["provenance"]["graph_digest"])
        self.assertTrue(report["provenance"]["analysis_fingerprint"])
        self.assertEqual(report["parser"]["engine"], "CobolASTGraphBuilder")
        self.assertEqual(
            report["provenance"]["analysis_options"]["parser"]["selected_engine"],
            "CobolASTGraphBuilder",
        )
        self.assertEqual(len(report["provenance"]["copybooks"]), 2)
        self.assertEqual(unsupported["source_origin"]["source"], "AUDIT-STATEMENT.CPY")
        self.assertEqual(unsupported["source_line"], 1)
        self.assertTrue(report["cycle_analysis"]["assumptions"])
        self.assertIn("parser_coverage_ratio", {metric["name"] for metric in report["metrics"]})

        markdown = audit_report_to_markdown(report)
        self.assertIn("## Parser coverage", markdown)
        self.assertIn("AUDIT-STATEMENT.CPY:1", markdown)
        self.assertIn("not a proof", markdown)

        comparison = ProgramComparator(copybooks=COPYBOOKS).compare(
            COPYBOOK_PROGRAM, COPYBOOK_PROGRAM,
        )
        comparison_provenance = comparison["provenance"]
        self.assertTrue(comparison_provenance["graph_digest_a"])
        self.assertTrue(comparison_provenance["graph_digest_b"])
        self.assertEqual(
            comparison_provenance["analysis_options"]["parser"]["selected_engines"],
            {"source_a": "CobolASTGraphBuilder", "source_b": "CobolASTGraphBuilder"},
        )

    def test_unresolved_copybook_is_not_silently_dropped_by_comparator(self):
        with self.assertRaises(CopybookResolutionError):
            ProgramComparator(copybooks={}).analyze_single(COPYBOOK_PROGRAM)


if __name__ == "__main__":
    unittest.main()
