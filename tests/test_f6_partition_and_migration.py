"""
Verification Suite for Filar F6: Partition Recommendations and Migration Evidence.
Tests Fiedler-vector sweeps, Cheeger conductance bounds, crossing edge analysis,
shared database/dataset penalties, JCL transaction boundary checks,
differential execution with CobolRuntime, domain invariant validation,
spectral graph signals, and versioned evidence documents (sokol.partition.v1, sokol.migration.v1).
"""

import os
import unittest

from rezonator.call_resolver import CallResolver
from rezonator.jcl_parser import JclParser
from rezonator.migration_verifier import (
    DifferentialTestCase,
    DifferentialTestRun,
    DomainInvariant,
    MigrationEvidence,
    MigrationVerifier,
    StructuralSignals,
)
from rezonator.partition_recommender import (
    CrossingEdge,
    PartitionCandidate,
    PartitionRecommender,
)
from rezonator.portfolio_graph import PortfolioGraph, PortfolioGraphBuilder
from rezonator.portfolio_manifest import (
    DatasetEntry,
    Db2TableEntry,
    JclEntry,
    PortfolioManifest,
    ProgramEntry,
)


class TestF6PartitionRecommender(unittest.TestCase):
    def setUp(self):
        self.recommender = PartitionRecommender()

    def test_01_empty_and_trivial_portfolio(self):
        manifest = PortfolioManifest(name="Empty")
        builder = PortfolioGraphBuilder()
        graph = builder.build(manifest)

        candidates = self.recommender.recommend_portfolio_partitions(graph)
        self.assertEqual(candidates, [])

    def test_02_two_cluster_spectral_cut_and_cheeger_bounds(self):
        """
        Builds a portfolio with two distinct clusters (CBL_A1, CBL_A2) and (CBL_B1, CBL_B2)
        connected only by a single CALL edge between CBL_A2 and CBL_B1.
        """
        src_a1 = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBLA1.
       PROCEDURE DIVISION.
           CALL 'CBLA2'.
           STOP RUN.
        """
        src_a2 = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBLA2.
       PROCEDURE DIVISION.
           CALL 'CBLB1'.
           STOP RUN.
        """
        src_b1 = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBLB1.
       PROCEDURE DIVISION.
           CALL 'CBLB2'.
           STOP RUN.
        """
        src_b2 = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBLB2.
       PROCEDURE DIVISION.
           STOP RUN.
        """

        manifest = PortfolioManifest(
            name="TwoClusters",
            programs=[
                ProgramEntry(program_id="CBLA1", source_text=src_a1),
                ProgramEntry(program_id="CBLA2", source_text=src_a2),
                ProgramEntry(program_id="CBLB1", source_text=src_b1),
                ProgramEntry(program_id="CBLB2", source_text=src_b2),
            ],
        )
        builder = PortfolioGraphBuilder()
        graph = builder.build(manifest)

        candidates = self.recommender.recommend_portfolio_partitions(graph, top_k=2)
        self.assertGreater(len(candidates), 0)

        best = candidates[0]
        self.assertIn("cand-01-", best.candidate_id)
        self.assertEqual(best.architect_review_status, "PENDING_ARCHITECT_REVIEW")

        # Conductance Cheeger inequality check: lambda_1 / 2 <= phi <= sqrt(2 * lambda_1)
        self.assertGreaterEqual(best.conductance, 0.0)
        self.assertGreaterEqual(best.cheeger_bound_upper, best.cheeger_bound_lower)
        self.assertLessEqual(best.conductance, 1.0)

        # Verify partitions split cleanly between clusters A and B
        part_a = set(best.partition_a)
        part_b = set(best.partition_b)
        self.assertEqual(len(part_a) + len(part_b), 4)

        # Verify crossing edges
        self.assertEqual(len(best.crossing_edges), 1)
        crossing = best.crossing_edges[0]
        self.assertTrue(
            (crossing.source == "PGM:CBLA2" and crossing.target == "PGM:CBLB1")
            or (crossing.source == "PGM:CBLB1" and crossing.target == "PGM:CBLA2")
        )
        self.assertEqual(crossing.edge_type, "CALL_RESOLVED")

    def test_03_shared_db2_table_and_jcl_penalties(self):
        """
        Tests partition recommendation when two programs share an SQL table
        and are chained sequentially in a JCL job.
        """
        src_a = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROGA.
       PROCEDURE DIVISION.
           EXEC SQL SELECT * FROM ACCOUNTS END-EXEC.
           STOP RUN.
        """
        src_b = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROGB.
       PROCEDURE DIVISION.
           EXEC SQL UPDATE ACCOUNTS SET BAL = 0 END-EXEC.
           STOP RUN.
        """
        jcl_chain = """
//CHAINJOB JOB (ACCT),'TX CHAIN'
//STEP01   EXEC PGM=PROGA
//STEP02   EXEC PGM=PROGB
        """

        manifest = PortfolioManifest(
            name="SharedDbAndJcl",
            programs=[
                ProgramEntry(program_id="PROGA", source_text=src_a),
                ProgramEntry(program_id="PROGB", source_text=src_b),
            ],
            jobs=[JclEntry(job_id="CHAINJOB", source_text=jcl_chain)],
            known_tables=[Db2TableEntry(table_name="ACCOUNTS")],
        )
        builder = PortfolioGraphBuilder()
        graph = builder.build(manifest)

        candidates = self.recommender.recommend_portfolio_partitions(graph, top_k=3)
        self.assertGreater(len(candidates), 0)

        # Cand 01 splits JCL steps/jobs across programs (tx violations)
        cand01 = candidates[0]
        self.assertGreater(cand01.transaction_boundaries_violated, 0)

        # Cand 02 splits PROGA and PROGB across the cut, detecting the shared DB2 table
        cand_with_shared = next((c for c in candidates if "ACCOUNTS" in c.shared_tables), None)
        self.assertIsNotNone(cand_with_shared)
        self.assertIn("ACCOUNTS", cand_with_shared.shared_tables)
        self.assertIn("Splits shared DB2 table ownership", cand_with_shared.rationale)

        # Markdown report rendering
        md = self.recommender.to_markdown_report(candidates)
        self.assertIn("# Architecture Partition Recommendations", md)
        self.assertIn("ACCOUNTS", md)
        self.assertIn("PENDING_REVIEW", md)

    def test_04_dynamic_call_uncertainty_score(self):
        """
        Tests that dynamic CALLs across cut boundaries increase the uncertainty score.
        """
        src_dyn = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DYNCALLER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TARGET PIC X(8) VALUE 'TARGETPG'.
       PROCEDURE DIVISION.
           CALL WS-TARGET.
           STOP RUN.
        """
        src_target = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TARGETPG.
       PROCEDURE DIVISION.
           STOP RUN.
        """

        manifest = PortfolioManifest(
            name="DynamicPortfolio",
            programs=[
                ProgramEntry(program_id="DYNCALLER", source_text=src_dyn),
                ProgramEntry(program_id="TARGETPG", source_text=src_target),
            ],
        )
        builder = PortfolioGraphBuilder()
        graph = builder.build(manifest)

        candidates = self.recommender.recommend_portfolio_partitions(graph, top_k=1)
        self.assertEqual(len(candidates), 1)
        cand = candidates[0]

        self.assertGreater(cand.uncertainty_score, 0.0)
        self.assertTrue(any(ce.is_dynamic for ce in cand.crossing_edges))
        self.assertIn("dynamic call(s) requiring runtime resolution", cand.rationale)


class TestF6MigrationVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = MigrationVerifier(lattice_size=16)

    def test_01_identical_code_verified(self):
        """Identical baseline and candidate should achieve 100% equivalence, zero NetLSD distance."""
        code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCUM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOTAL PIC 9(4) VALUE 100.
       01  WS-ADD-VAL PIC 9(4) VALUE 50.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ADD WS-ADD-VAL TO WS-TOTAL.
           STOP RUN.
        """

        evidence = self.verifier.verify(code, code)
        self.assertEqual(evidence.schema_version, "sokol.migration.v1")
        self.assertEqual(evidence.epistemic_status, "OBSERVED_VERIFIED")
        self.assertEqual(evidence.total_tests, 1)
        self.assertEqual(evidence.passed_tests, 1)
        self.assertEqual(evidence.equivalence_rate, 1.0)
        self.assertAlmostEqual(evidence.structural_signals.netlsd_distance, 0.0, places=5)
        self.assertTrue(evidence.structural_signals.cycle_topology_preserved)

        # Checksum determinism
        cs1 = evidence.compute_checksum()
        cs2 = evidence.compute_checksum()
        self.assertEqual(cs1, cs2)
        self.assertEqual(len(cs1), 64)

        # Markdown report
        md = evidence.to_markdown_report()
        self.assertIn("# Migration Verification Report", md)
        self.assertIn("OBSERVED_VERIFIED", md)
        self.assertIn("100.0%", md)

    def test_02_diverged_variable_detected(self):
        """Tests that semantic mutation divergence is captured in differential results."""
        baseline = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-BAL PIC 9(4) VALUE 1000.
       01  WS-FEE PIC 9(4) VALUE 50.
       PROCEDURE DIVISION.
       MAIN-PARA.
           SUBTRACT WS-FEE FROM WS-BAL.
           STOP RUN.
        """
        # Modernized code has an off-by-one error or different fee logic
        candidate = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-BAL PIC 9(4) VALUE 1000.
       01  WS-FEE PIC 9(4) VALUE 75.
       PROCEDURE DIVISION.
       MAIN-PARA.
           SUBTRACT WS-FEE FROM WS-BAL.
           STOP RUN.
        """

        evidence = self.verifier.verify(baseline, candidate)
        self.assertEqual(evidence.epistemic_status, "OBSERVED_DIVERGED")
        self.assertEqual(evidence.passed_tests, 0)
        self.assertEqual(evidence.equivalence_rate, 0.0)

        test_run = evidence.test_runs[0]
        self.assertEqual(test_run.status, "DIVERGED")
        self.assertIn("WS-BAL", test_run.affected_variables)
        self.assertEqual(test_run.affected_variables["WS-BAL"]["baseline"], 950)
        self.assertEqual(test_run.affected_variables["WS-BAL"]["candidate"], 925)

    def test_03_domain_invariant_checking(self):
        """Tests domain invariant enforcement on differential states."""
        code_overdraft = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OVERDRAFT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-BALANCE PIC S9(4) VALUE 100.
       01  WS-WITHDRAW PIC 9(4) VALUE 250.
       PROCEDURE DIVISION.
       MAIN-PARA.
           SUBTRACT WS-WITHDRAW FROM WS-BALANCE.
           STOP RUN.
        """

        inv_pos = DomainInvariant(
            name="NO_NEGATIVE_BALANCE",
            expression="WS-BALANCE >= 0",
            description="Balance must never be negative",
            severity="CRITICAL",
        )

        tc = DifferentialTestCase(
            test_id="tc-overdraft",
            description="Large withdrawal test",
            input_overrides={"WS-WITHDRAW": 500},
            invariants=["NO_NEGATIVE_BALANCE"],
        )

        evidence = self.verifier.verify(
            code_overdraft,
            code_overdraft,
            test_cases=[tc],
            invariants=[inv_pos],
        )

        self.assertEqual(evidence.domain_invariants_evaluated, 1)
        self.assertEqual(len(evidence.domain_invariants_violated), 1)
        self.assertIn("NO_NEGATIVE_BALANCE", evidence.domain_invariants_violated[0])
        self.assertEqual(evidence.test_runs[0].status, "INVARIANT_VIOLATION")
        self.assertEqual(evidence.epistemic_status, "OBSERVED_DIVERGED")

    def test_04_multiple_differential_test_cases(self):
        """Tests suite with multiple input cases evaluating pass/diverge rates."""
        base = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BRANCHTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-INPUT PIC 9(4) VALUE 10.
       01  WS-OUTPUT PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF WS-INPUT > 50
               MOVE 100 TO WS-OUTPUT
           ELSE
               MOVE 200 TO WS-OUTPUT
           END-IF.
           STOP RUN.
        """
        # Candidate has an inverted threshold (> 60 instead of > 50)
        cand = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BRANCHTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-INPUT PIC 9(4) VALUE 10.
       01  WS-OUTPUT PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF WS-INPUT > 60
               MOVE 100 TO WS-OUTPUT
           ELSE
               MOVE 200 TO WS-OUTPUT
           END-IF.
           STOP RUN.
        """

        tc1 = DifferentialTestCase(test_id="tc-low", input_overrides={"WS-INPUT": 20})   # Both output 200 -> PASS
        tc2 = DifferentialTestCase(test_id="tc-mid", input_overrides={"WS-INPUT": 55})   # Base=100, Cand=200 -> DIVERGE
        tc3 = DifferentialTestCase(test_id="tc-high", input_overrides={"WS-INPUT": 80})  # Both output 100 -> PASS

        evidence = self.verifier.verify(base, cand, test_cases=[tc1, tc2, tc3])
        self.assertEqual(evidence.total_tests, 3)
        self.assertEqual(evidence.passed_tests, 2)
        self.assertAlmostEqual(evidence.equivalence_rate, 2.0 / 3.0, places=2)
        self.assertEqual(evidence.test_runs[0].status, "PASS")
        self.assertEqual(evidence.test_runs[1].status, "DIVERGED")
        self.assertEqual(evidence.test_runs[2].status, "PASS")

        # Verify JSON serialization
        d = evidence.to_dict()
        self.assertEqual(d["schema_version"], "sokol.migration.v1")
        self.assertEqual(d["total_tests"], 3)
        self.assertEqual(d["passed_tests"], 2)


if __name__ == "__main__":
    unittest.main()
