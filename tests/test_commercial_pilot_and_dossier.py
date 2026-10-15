"""
Unit and Integration Tests for Commercial Pilot & Architecture Review Board (ARB) Dossier:
1. PdsDirectoryScanner: Automated mainframe filesystem / PDS discovery and copybook auto-indexing.
2. DatabaseTransactionFrictionMatrix: Pairwise DB2/DSN/JCL distributed transaction friction & hard barriers.
3. ArbDossierGenerator: Bank-grade monolith decomposition scorecard, Strangler Fig migration waves, and ARB sign-off.
4. Real-world validation on repository examples/corpus estate.
"""

import os
import tempfile
import pytest

from rezonator.pds_scanner import PdsDirectoryScanner, ScanResult
from rezonator.friction_matrix import DatabaseTransactionFrictionMatrix
from rezonator.arb_dossier import ArbDossierGenerator, MigrationWave
from rezonator.portfolio_graph import PortfolioGraphBuilder
from rezonator.portfolio_manifest import (
    DatasetEntry,
    Db2TableEntry,
    JclEntry,
    PortfolioManifest,
    ProgramEntry,
)


@pytest.fixture
def mock_pds_estate(tmp_path):
    """Creates a realistic enterprise PDS filesystem structure."""
    cbl_dir = tmp_path / "cbl"
    cpy_dir = tmp_path / "cpy"
    jcl_dir = tmp_path / "jcl"

    cbl_dir.mkdir()
    cpy_dir.mkdir()
    jcl_dir.mkdir()

    # 1. Copybook
    custrec_cpy = (
        "      * CUSTOMER RECORD COPYBOOK\n"
        "       01 CUST-REC.\n"
        "          05 CUST-ID        PIC 9(8).\n"
        "          05 CUST-BALANCE   PIC S9(9)V99 COMP-3.\n"
    )
    (cpy_dir / "CUSTREC.cpy").write_text(custrec_cpy, encoding="utf-8")

    # 2. Program A (Banking Ledger)
    prog_a = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. BANKPGMA.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "           COPY CUSTREC.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC SQL\n"
        "               UPDATE ACCOUNTS SET BALANCE = 100 WHERE CUST_ID = 1\n"
        "           END-EXEC.\n"
        "           CALL 'BANKPGMB'.\n"
        "           STOP RUN.\n"
    )
    (cbl_dir / "BANKPGMA.cbl").write_text(prog_a, encoding="utf-8")

    # 3. Program B (Audit Logging)
    prog_b = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. BANKPGMB.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC SQL\n"
        "               INSERT INTO AUDIT_LOG VALUES (1, 'UPDATE')\n"
        "           END-EXEC.\n"
        "           STOP RUN.\n"
    )
    (cbl_dir / "BANKPGMB.cbl").write_text(prog_b, encoding="utf-8")

    # 4. Program C (Settlement Engine, conflicts on ACCOUNTS)
    prog_c = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. SETTLE01.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC SQL\n"
        "               UPDATE ACCOUNTS SET BALANCE = 0 WHERE CUST_ID = 9\n"
        "           END-EXEC.\n"
        "           STOP RUN.\n"
    )
    (cbl_dir / "SETTLE01.cbl").write_text(prog_c, encoding="utf-8")

    # 5. JCL Batch Job
    job_text = (
        "//NIGHT01  JOB (ACCT),'DAILY SETTLEMENT',CLASS=A\n"
        "//STEP01   EXEC PGM=BANKPGMA\n"
        "//INFILE   DD DSN=BANK.MASTER.DATA,DISP=SHR\n"
        "//STEP02   EXEC PGM=SETTLE01\n"
        "//OUTFILE  DD DSN=BANK.SETTLE.REPORT,DISP=(NEW,CATLG)\n"
    )
    (jcl_dir / "NIGHT01.jcl").write_text(job_text, encoding="utf-8")

    return tmp_path


def test_pds_directory_scanner_discovery(mock_pds_estate):
    """Verify automated discovery, classification, and copybook attachment."""
    scanner = PdsDirectoryScanner()
    result = scanner.scan_directory(str(mock_pds_estate), manifest_name="Bank-PDS-Pilot")

    assert isinstance(result, ScanResult)
    stats = result.scan_stats
    assert stats["cobol_programs"] == 3
    assert stats["copybooks"] == 1
    assert stats["jcl_jobs"] == 1
    assert "ACCOUNTS" in stats or stats["db2_tables"] >= 2
    assert stats["datasets"] >= 2

    # Verify Program A got its copybook automatically attached
    prog_a = result.manifest.get_program("BANKPGMA")
    assert prog_a is not None
    assert "CUSTREC" in prog_a.copybooks
    assert "CUST-BALANCE" in prog_a.copybooks["CUSTREC"]

    # Verify Markdown report generation
    md_report = result.to_markdown()
    assert "Enterprise Portfolio Discovery Dossier" in md_report
    assert "BANKPGMA" in md_report
    assert "NIGHT01" in md_report


def test_database_transaction_friction_matrix(mock_pds_estate):
    """Verify pairwise friction calculation and hard migration barrier detection."""
    scanner = PdsDirectoryScanner()
    scan_res = scanner.scan_directory(str(mock_pds_estate))

    builder = PortfolioGraphBuilder()
    graph = builder.build(scan_res.manifest)

    friction_eval = DatabaseTransactionFrictionMatrix()
    friction_data = friction_eval.compute(graph)

    assert friction_data["program_count"] == 3
    assert friction_data["coupled_pairs_count"] >= 1

    # BANKPGMA and SETTLE01 both update ACCOUNTS and run in job NIGHT01
    pairwise = friction_data["pairwise_friction"]
    barrier_pair = next(
        (p for p in pairwise if ("BANKPGMA" in (p["program_a"], p["program_b"]) and "SETTLE01" in (p["program_a"], p["program_b"]))),
        None
    )
    assert barrier_pair is not None
    assert barrier_pair["is_hard_barrier"] is True
    assert barrier_pair["friction_level"] == "CRITICAL"
    assert "ACCOUNTS" in barrier_pair["shared_tables"]
    assert "NIGHT01" in barrier_pair["shared_jcl_jobs"]

    md = friction_eval.to_markdown(friction_data)
    assert "Database & Transactional Friction Matrix" in md
    assert "Hard Migration Barriers" in md
    assert "BANKPGMA" in md


def test_arb_dossier_generator_bank_grade(mock_pds_estate):
    """Verify ARB dossier executive scorecard, migration waves, and sign-off block."""
    scanner = PdsDirectoryScanner()
    scan_res = scanner.scan_directory(str(mock_pds_estate))

    builder = PortfolioGraphBuilder()
    graph = builder.build(scan_res.manifest)

    dossier_gen = ArbDossierGenerator()
    dossier = dossier_gen.generate_dossier(
        graph,
        system_name="Core Banking Retail Estate",
        target_cloud_platform="AWS EKS Microservices",
    )

    ea = dossier["executive_assessment"]
    assert 0.0 <= ea["separability_index"] <= 100.0
    assert ea["program_count"] == 3
    assert "risk_grade" in ea

    waves = dossier["migration_waves"]
    assert len(waves) == 3
    assert waves[0]["wave_number"] == 1
    assert waves[0]["risk_level"] == "LOW"

    # BANKPGMB should be early wave since it only writes to AUDIT_LOG without hard conflicts
    assert "BANKPGMB" in waves[0]["target_programs"] or "BANKPGMB" in waves[1]["target_programs"]

    md_dossier = dossier_gen.to_markdown(dossier)
    assert "Monolith Decomposition Dossier" in md_dossier
    assert "BANK ARCHITECTURE REVIEW BOARD (ARB)" in md_dossier
    assert "Separability Scorecard" in md_dossier
    assert "Strangler Fig Phased Migration Roadmap" in md_dossier


def test_scanner_on_existing_corpus():
    """Verify PdsDirectoryScanner successfully scans the real enterprise corpus in examples/corpus."""
    corpus_dir = os.path.join(os.path.dirname(__file__), "..", "examples", "corpus")
    if not os.path.exists(corpus_dir):
        pytest.skip("examples/corpus not found")

    scanner = PdsDirectoryScanner()
    res = scanner.scan_directory(corpus_dir, manifest_name="Real-Enterprise-Corpus")

    assert res.scan_stats["cobol_programs"] >= 6
    assert res.scan_stats["copybooks"] >= 4
    assert res.scan_stats["total_loc"] > 300
    assert res.scan_duration_ms < 100.0  # Must be fast under 100ms
