"""
Verification Suite for Filar F5: Multi-Program Application Portfolio Graph.
Tests Portfolio Manifest, JCL Parser, Call Resolver, Shared Resource Coupling,
Sparse Reachability, Multi-Program Blast Radius, and Markdown Reporting.
"""

import os
import unittest

from rezonator.call_resolver import CallResolver, ProgramCall
from rezonator.jcl_parser import JclCondition, JclParser
from rezonator.portfolio_graph import PortfolioGraph, PortfolioGraphBuilder
from rezonator.portfolio_manifest import (
    DatasetEntry,
    Db2TableEntry,
    JclEntry,
    PortfolioManifest,
    ProgramEntry,
)


class TestF5PortfolioManifest(unittest.TestCase):
    def test_01_manifest_dataclasses_and_serialization(self):
        p1 = ProgramEntry(program_id="cbl001", source_path="cbl001.cbl", copybooks={"CUSTREC": "abc"})
        self.assertEqual(p1.program_id, "CBL001")
        self.assertEqual(p1.copybooks["CUSTREC"], "abc")

        j1 = JclEntry(job_id="dailyjob", source_text="//DAILYJOB JOB ...")
        self.assertEqual(j1.job_id, "DAILYJOB")

        d1 = DatasetEntry(dsn="cust.master.file", is_vsam=True, catalog_status="CATALOGED")
        self.assertEqual(d1.dsn, "CUST.MASTER.FILE")
        self.assertTrue(d1.is_vsam)

        t1 = Db2TableEntry(table_name="accounts", schema="prod", catalog_status="CATALOGED")
        self.assertEqual(t1.table_name, "ACCOUNTS")
        self.assertEqual(t1.schema, "PROD")

        manifest = PortfolioManifest(
            name="Core-Banking",
            programs=[p1],
            jobs=[j1],
            known_datasets=[d1],
            known_tables=[t1],
            description="Pilot manifest",
        )

        d = manifest.to_dict()
        self.assertEqual(d["schema_version"], "sokol.portfolio.manifest.v1")
        self.assertEqual(len(d["programs"]), 1)
        self.assertEqual(len(d["jobs"]), 1)
        self.assertEqual(len(d["known_datasets"]), 1)
        self.assertEqual(len(d["known_tables"]), 1)

        # Check round-trip from_dict
        restored = PortfolioManifest.from_dict(d)
        self.assertEqual(restored.name, "Core-Banking")
        self.assertEqual(restored.get_program("CBL001").program_id, "CBL001")
        self.assertEqual(restored.get_job("DAILYJOB").job_id, "DAILYJOB")
        self.assertEqual(restored.get_dataset("CUST.MASTER.FILE").dsn, "CUST.MASTER.FILE")
        self.assertEqual(restored.get_table("ACCOUNTS").table_name, "ACCOUNTS")

        # Deterministic checksum
        cs1 = manifest.compute_checksum()
        cs2 = restored.compute_checksum()
        self.assertEqual(cs1, cs2)
        self.assertEqual(len(cs1), 64)

    def test_02_manifest_unknown_catalog_status(self):
        d_unknown = DatasetEntry(dsn="TEMP.FILE", catalog_status="NONEXISTENT")
        self.assertEqual(d_unknown.catalog_status, "UNKNOWN")

        t_unknown = Db2TableEntry(table_name="SECRET_TABLE", catalog_status="INVALID")
        self.assertEqual(t_unknown.catalog_status, "UNKNOWN")


class TestF5JclParser(unittest.TestCase):
    def setUp(self):
        self.parser = JclParser()

    def test_01_parse_standard_job_and_steps(self):
        jcl_text = """
//MYJOB01  JOB (ACCT123),'TEST BATCH',CLASS=A,MSGCLASS=X
//* Comment line to ignore
//STEP01   EXEC PGM=CBL001
//INFILE   DD DSN=PROD.IN.FILE,DISP=SHR
//OUTFILE  DD DSN=PROD.OUT.FILE,DISP=(NEW,CATLG,DELETE)
//STEP02   EXEC PGM=CBL002,COND=(4,LT)
//WORKDD   DD DSN=&&TEMPWORK,DISP=(NEW,DELETE)
//SYSOUT   DD SYSOUT=*
//DUMMYDD  DD DUMMY
        """.strip()

        jobs = self.parser.parse(jcl_text)
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.job_name, "MYJOB01")
        self.assertEqual(job.job_class, "A")
        self.assertEqual(job.msgclass, "X")
        self.assertEqual(len(job.steps), 2)

        # Step 01
        s1 = job.steps[0]
        self.assertEqual(s1.step_name, "STEP01")
        self.assertEqual(s1.program_name, "CBL001")
        self.assertEqual(s1.exec_type, "PGM")
        self.assertEqual(len(s1.dds), 2)
        dd_in = s1.get_dd("INFILE")
        self.assertIsNotNone(dd_in)
        self.assertEqual(dd_in.dsn, "PROD.IN.FILE")
        self.assertEqual(dd_in.access_intent, "READ")
        dd_out = s1.get_dd("OUTFILE")
        self.assertIsNotNone(dd_out)
        self.assertEqual(dd_out.access_intent, "WRITE")

        # Step 02
        s2 = job.steps[1]
        self.assertEqual(s2.step_name, "STEP02")
        self.assertEqual(s2.program_name, "CBL002")
        self.assertEqual(len(s2.conditions), 1)
        self.assertEqual(s2.conditions[0].code, 4)
        self.assertEqual(s2.conditions[0].operator, "LT")
        # In JCL, if 4 < step_rc (e.g. step_rc = 8), condition evaluates true -> step bypassed
        self.assertTrue(s2.conditions[0].evaluates_true(8))
        self.assertFalse(s2.conditions[0].evaluates_true(2))

        dd_temp = s2.get_dd("WORKDD")
        self.assertTrue(dd_temp.is_temporary)
        dd_dummy = s2.get_dd("DUMMYDD")
        self.assertTrue(dd_dummy.is_dummy)
        dd_sysout = s2.get_dd("SYSOUT")
        self.assertTrue(dd_sysout.is_sysout)

    def test_02_jcl_continuation_lines(self):
        jcl_text = """
//RUNJOB   JOB 100,CLASS=C,
//             MSGCLASS=Z
//STEP01   EXEC PGM=CBL003,
//            COND=(0,NE,STEP00)
//BIGDD    DD DSN=MY.VERY.LONG.DATASET.NAME,
//            DISP=(NEW,CATLG),
//            SPACE=(CYL,(50,10))
        """.strip()

        jobs = self.parser.parse(jcl_text)
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.job_name, "RUNJOB")
        self.assertEqual(job.job_class, "C")
        self.assertEqual(job.msgclass, "Z")

        step = job.steps[0]
        self.assertEqual(step.program_name, "CBL003")
        self.assertEqual(len(step.conditions), 1)
        self.assertEqual(step.conditions[0].reference_step, "STEP00")

        dd = step.get_dd("BIGDD")
        self.assertIsNotNone(dd)
        self.assertEqual(dd.dsn, "MY.VERY.LONG.DATASET.NAME")
        self.assertEqual(dd.access_intent, "WRITE")


class TestF5CallResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = CallResolver()

    def test_01_extract_static_and_dynamic_calls(self):
        code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. MAINPGM.
        PROCEDURE DIVISION.
        0000-MAIN.
            CALL 'SUBPGM1' USING WS-PARAM1, WS-PARAM2.
            CALL "SUBPGM2" USING BY REFERENCE WS-PARAM3, BY CONTENT "LITERAL".
            CALL WS-DYNAMIC-TARGET USING WS-PARM.
            STOP RUN.
        """.strip()

        calls = self.resolver.extract_calls_from_source(code, "MAINPGM")
        self.assertEqual(len(calls), 3)

        # Call 1: Static
        c1 = calls[0]
        self.assertEqual(c1.target_name, "SUBPGM1")
        self.assertEqual(c1.call_type, "COBOL_STATIC")
        self.assertFalse(c1.is_dynamic)
        self.assertEqual(c1.parameters, ["WS-PARAM1", "WS-PARAM2"])

        # Call 2: Static with quotes & BY REFERENCE
        c2 = calls[1]
        self.assertEqual(c2.target_name, "SUBPGM2")
        self.assertFalse(c2.is_dynamic)
        self.assertEqual(c2.parameters, ["WS-PARAM3", '"LITERAL"'])

        # Call 3: Dynamic identifier
        c3 = calls[2]
        self.assertEqual(c3.target_name, "WS-DYNAMIC-TARGET")
        self.assertEqual(c3.call_type, "COBOL_DYNAMIC")
        self.assertTrue(c3.is_dynamic)
        self.assertEqual(c3.parameters, ["WS-PARM"])

    def test_02_extract_cics_link_and_xctl(self):
        code = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. CICSPGM.
        PROCEDURE DIVISION.
        0000-MAIN.
            EXEC CICS LINK PROGRAM('AUTH01')
                COMMAREA(WS-COMM)
            END-EXEC.
            EXEC CICS XCTL PROGRAM('MENU01')
            END-EXEC.
            GOBACK.
        """.strip()

        calls = self.resolver.extract_calls_from_source(code, "CICSPGM")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].target_name, "AUTH01")
        self.assertEqual(calls[0].call_type, "CICS_LINK")
        self.assertEqual(calls[0].parameters, ["WS-COMM"])

        self.assertEqual(calls[1].target_name, "MENU01")
        self.assertEqual(calls[1].call_type, "CICS_XCTL")

    def test_03_resolve_portfolio_epistemic_discipline(self):
        # Manifest defines PGM_A and PGM_B, but NOT PGM_C
        code_a = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PGM-A.
        PROCEDURE DIVISION.
            CALL 'PGM-B' USING WS-X.
            CALL 'PGM-C' USING WS-Y.
            CALL WS-VAR USING WS-Z.
            STOP RUN.
        """.strip()

        manifest = PortfolioManifest(
            name="TestPortfolio",
            programs=[
                ProgramEntry(program_id="PGM-A", source_text=code_a),
                ProgramEntry(program_id="PGM-B", source_text="PROGRAM-ID. PGM-B. STOP RUN."),
            ],
        )

        calls_by_prog, _ = self.resolver.resolve_portfolio(manifest)
        calls = calls_by_prog["PGM-A"]
        self.assertEqual(len(calls), 3)

        # Call to PGM-B should be RESOLVED
        c_b = [c for c in calls if c.target_name == "PGM-B"][0]
        self.assertEqual(c_b.resolution_status, "RESOLVED")
        self.assertEqual(c_b.resolved_target, "PGM-B")

        # Call to PGM-C should be UNRESOLVED_EXTERNAL
        c_c = [c for c in calls if c.target_name == "PGM-C"][0]
        self.assertEqual(c_c.resolution_status, "UNRESOLVED_EXTERNAL")
        self.assertIsNone(c_c.resolved_target)

        # Dynamic call to WS-VAR should be DYNAMIC_UNRESOLVED
        c_dyn = [c for c in calls if c.target_name == "WS-VAR"][0]
        self.assertEqual(c_dyn.resolution_status, "DYNAMIC_UNRESOLVED")
        self.assertIsNone(c_dyn.resolved_target)


class TestF5PortfolioGraphAndBlastRadius(unittest.TestCase):
    def setUp(self):
        # Build multi-program scenario:
        # PGM-A -> calls PGM-B (resolved) and writes TABLE:ACCOUNTS
        # PGM-B -> reads TABLE:ACCOUNTS, calls PGM-C (unresolved external)
        # JCL-JOB:
        #   STEP01 -> runs PGM-A, writes DSN:TRANS.DATA
        #   STEP02 -> runs PGM-B, reads DSN:TRANS.DATA
        prog_a_src = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PGM-A.
        PROCEDURE DIVISION.
            CALL 'PGM-B' USING WS-X.
            EXEC SQL
                UPDATE ACCOUNTS SET BAL = 100 WHERE ID = 1
            END-EXEC.
            STOP RUN.
        """.strip()

        prog_b_src = """
        IDENTIFICATION DIVISION.
        PROGRAM-ID. PGM-B.
        PROCEDURE DIVISION.
            EXEC SQL
                SELECT BAL FROM ACCOUNTS WHERE ID = 1
            END-EXEC.
            CALL 'EXT-SEC' USING WS-TOKEN.
            STOP RUN.
        """.strip()

        jcl_src = """
//FLOW01  JOB (ACCT),'DAILY FLOW',CLASS=A
//STEP01  EXEC PGM=PGM-A
//TRANOUT DD DSN=TRANS.DATA,DISP=(NEW,CATLG)
//STEP02  EXEC PGM=PGM-B
//TRANIN  DD DSN=TRANS.DATA,DISP=SHR
        """.strip()

        self.manifest = PortfolioManifest(
            name="FlowPortfolio",
            programs=[
                ProgramEntry(program_id="PGM-A", source_text=prog_a_src),
                ProgramEntry(program_id="PGM-B", source_text=prog_b_src),
            ],
            jobs=[
                JclEntry(job_id="FLOW01", source_text=jcl_src),
            ],
            known_tables=[
                Db2TableEntry(table_name="ACCOUNTS", catalog_status="CATALOGED"),
            ],
        )

        builder = PortfolioGraphBuilder()
        self.graph = builder.build(self.manifest)

    def test_01_graph_nodes_and_edges_inventory(self):
        nodes = self.graph.nodes
        self.assertIn("PGM:PGM-A", nodes)
        self.assertIn("PGM:PGM-B", nodes)
        self.assertIn("JOB:FLOW01", nodes)
        self.assertIn("STEP:FLOW01.STEP01", nodes)
        self.assertIn("STEP:FLOW01.STEP02", nodes)
        self.assertIn("DSN:TRANS.DATA", nodes)
        self.assertIn("TABLE:ACCOUNTS", nodes)
        self.assertIn("EXT_PGM:EXT-SEC", nodes)

        edges = self.graph.edges
        edge_types = {e.edge_type for e in edges}
        self.assertIn("JOB_STEP", edge_types)
        self.assertIn("STEP_SEQUENCE", edge_types)
        self.assertIn("STEP_EXEC", edge_types)
        self.assertIn("CALL_RESOLVED", edge_types)
        self.assertIn("CALL_UNRESOLVED", edge_types)
        self.assertIn("PGM_SQL_WRITE", edge_types)
        self.assertIn("PGM_SQL_READ", edge_types)
        self.assertIn("STEP_WRITE_DSN", edge_types)
        self.assertIn("STEP_READ_DSN", edge_types)

    def test_02_sparse_adjacency_matrix(self):
        adj, node_to_idx, idx_to_node = self.graph.compute_adjacency_matrix()
        self.assertEqual(adj.shape[0], len(self.graph.nodes))
        self.assertEqual(adj.shape[1], len(self.graph.nodes))
        self.assertGreater(adj.nnz, 0)
        # Verify edge PGM-A -> PGM-B exists in adjacency
        idx_a = node_to_idx["PGM:PGM-A"]
        idx_b = node_to_idx["PGM:PGM-B"]
        self.assertEqual(adj[idx_a, idx_b], 1.0)

    def test_03_blast_radius_computation(self):
        radius_a = self.graph.compute_blast_radius("PGM:PGM-A")
        self.assertEqual(radius_a.target_node, "PGM:PGM-A")
        self.assertEqual(radius_a.node_type, "program")

        # Direct outgoing: PGM-B and TABLE:ACCOUNTS
        self.assertIn("PGM:PGM-B", radius_a.direct_outgoing)
        self.assertIn("TABLE:ACCOUNTS", radius_a.direct_outgoing)

        # Transitive downstream reachable from PGM-A:
        # PGM-B, TABLE:ACCOUNTS, and through PGM-B -> EXT_PGM:EXT-SEC
        self.assertIn("PGM:PGM-B", radius_a.transitive_downstream)
        self.assertIn("TABLE:ACCOUNTS", radius_a.transitive_downstream)
        self.assertIn("EXT_PGM:EXT-SEC", radius_a.transitive_downstream)

        # Upstream callers/triggers for PGM-A: STEP:FLOW01.STEP01 and JOB:FLOW01
        self.assertIn("STEP:FLOW01.STEP01", radius_a.transitive_upstream)
        self.assertIn("JOB:FLOW01", radius_a.transitive_upstream)

    def test_04_shared_resources_and_coupling_metrics(self):
        metrics = self.graph.compute_metrics()

        # Shared DB2 Table: ACCOUNTS accessed by both PGM-A and PGM-B
        self.assertEqual(metrics["shared_tables_count"], 1)
        shared_t = metrics["shared_tables"][0]
        self.assertEqual(shared_t["table_name"], "ACCOUNTS")
        self.assertEqual(shared_t["program_count"], 2)

        # Shared Dataset: TRANS.DATA accessed by STEP01 and STEP02
        self.assertEqual(metrics["shared_datasets_count"], 1)
        shared_d = metrics["shared_datasets"][0]
        self.assertEqual(shared_d["dsn"], "TRANS.DATA")
        self.assertEqual(shared_d["accessor_count"], 2)

        # Call resolution coverage
        call_m = metrics["call_metrics"]
        self.assertEqual(call_m["total_calls"], 2)
        self.assertEqual(call_m["resolved_calls"], 1)  # PGM-B
        self.assertEqual(call_m["unresolved_static_calls"], 1)  # EXT-SEC
        self.assertAlmostEqual(call_m["call_resolution_ratio"], 0.50, places=2)

        # Pairwise coupling
        pairs = metrics["pairwise_coupling"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["program_a"], "PGM:PGM-A")
        self.assertEqual(pairs[0]["program_b"], "PGM:PGM-B")
        self.assertGreater(pairs[0]["coupling_score"], 0)

    def test_05_markdown_report_generation(self):
        md = self.graph.to_markdown_report()
        self.assertIn("# Application Portfolio Graph Report (Filar F5)", md)
        self.assertIn("COBOL Programs", md)
        self.assertIn("JCL Batch Jobs", md)
        self.assertIn("ACCOUNTS", md)
        self.assertIn("TRANS.DATA", md)
        self.assertIn("Blast Radius Analysis", md)


class TestF5CorpusPortfolioIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.corpus_dir = os.path.join(base_dir, "examples", "corpus")
        cls.jcl_dir = os.path.join(cls.corpus_dir, "jcl")

        program_files = [
            os.path.join(cls.corpus_dir, f)
            for f in sorted(os.listdir(cls.corpus_dir))
            if f.endswith(".cbl")
        ]
        jcl_files = [
            os.path.join(cls.jcl_dir, f)
            for f in sorted(os.listdir(cls.jcl_dir))
            if f.endswith(".jcl")
        ]

        cls.manifest = PortfolioManifest.from_files(
            program_paths=program_files,
            jcl_paths=jcl_files,
            name="CorpusEnterprisePortfolio",
            description="6-program enterprise portfolio with batch JCL workflows",
            known_tables=["ACCOUNTS", "AUDIT_LOG"],
            known_datasets=["CUST.MASTER.FILE", "CUST.OUTPUT.FILE"],
        )

        builder = PortfolioGraphBuilder()
        cls.graph = builder.build(cls.manifest)

    def test_01_corpus_portfolio_completeness(self):
        nodes = self.graph.nodes
        # Verify 6 programs registered
        programs = [n for n in nodes.values() if n.node_type == "program"]
        self.assertEqual(len(programs), 6)

        # Verify JCL jobs registered (SETTLE01, AUDIT99)
        jobs = [n for n in nodes.values() if n.node_type == "job"]
        self.assertEqual(len(jobs), 2)
        job_ids = {j.label for j in jobs}
        self.assertIn("SETTLE01", job_ids)
        self.assertIn("AUDIT99", job_ids)

        # Verify CICS LINK to SECCHECK in CBL003 is detected as external program
        self.assertIn("EXT_PGM:SECCHECK", nodes)

        # Verify DB2 tables
        self.assertIn("TABLE:ACCOUNTS", nodes)
        self.assertIn("TABLE:AUDIT_LOG", nodes)

    def test_02_corpus_shared_dataset_coupling(self):
        # CBL001 writes CUST.OUTPUT.FILE, CBL004 reads it in JCL
        metrics = self.graph.compute_metrics()
        shared_dsns = {sd["dsn"] for sd in metrics["shared_datasets"]}
        self.assertIn("CUST.OUTPUT.FILE", shared_dsns)

        # Blast radius of SETTLE01 covers multiple steps and programs
        radius_job = self.graph.compute_blast_radius("JOB:SETTLE01")
        self.assertGreater(radius_job.downstream_impact_count, 5)


if __name__ == "__main__":
    unittest.main()
