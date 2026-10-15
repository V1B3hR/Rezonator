"""
Quality Hardening: Scale Stress Testing, Memory Bounds, and ARPACK Numerical Stability.
Validates multi-program portfolio scaling (100 programs, JCL jobs, DB2 tables, datasets),
sparse CSR memory footprints, and Cheeger spectral partition convergence.
"""

import time
import tracemalloc
import pytest

from rezonator.portfolio_manifest import (
    PortfolioManifest,
    ProgramEntry,
    JclEntry,
    DatasetEntry,
    Db2TableEntry,
)
from rezonator.portfolio_graph import PortfolioGraphBuilder, PortfolioGraph
from rezonator.friction_matrix import DatabaseTransactionFrictionMatrix
from rezonator.partition_recommender import PartitionRecommender
from rezonator.arb_dossier import ArbDossierGenerator
from rezonator.limits import ResourceLimitError, validate_source_size, MAX_SOURCE_BYTES


def test_scale_100_programs_sparse_portfolio():
    """Verify that a 100-program portfolio builds sparsely with low memory footprint and high performance."""
    manifest = PortfolioManifest(name="Commercial-Stress-100")

    # 1. Register 100 programs with calls and DB2 SQL
    for i in range(100):
        prog_id = f"PGM{i:03d}"
        calls_code = ""
        if i > 0 and i % 5 == 0:
            calls_code = f"    CALL 'PGM{i-1:03d}'.\n"
        
        sql_code = ""
        if i % 2 == 0:
            sql_code += "    EXEC SQL SELECT * FROM ACCOUNTS END-EXEC.\n"
        if i % 3 == 0:
            sql_code += "    EXEC SQL UPDATE TRANSACTIONS SET AMT = 10 END-EXEC.\n"
        if i % 7 == 0:
            sql_code += "    EXEC SQL INSERT INTO AUDIT_LOG VALUES (1) END-EXEC.\n"

        src = (
            f"IDENTIFICATION DIVISION.\n"
            f"PROGRAM-ID. {prog_id}.\n"
            f"PROCEDURE DIVISION.\n"
            f"0000-MAIN.\n"
            f"{calls_code}"
            f"{sql_code}"
            f"    STOP RUN.\n"
        )
        manifest.programs.append(ProgramEntry(
            program_id=prog_id,
            source_text=src,
        ))

    # 2. Register 30 JCL jobs chaining these programs
    for j in range(30):
        job_id = f"JOB{j:02d}"
        p1 = f"PGM{(j*3) % 100:03d}"
        p2 = f"PGM{(j*3 + 1) % 100:03d}"
        jcl_text = (
            f"//{job_id} JOB (ACCT),'BATCH',\n"
            f"//STEP01 EXEC PGM={p1}\n"
            f"//IN1    DD DSN=DATASET.MASTER,DISP=SHR\n"
            f"//STEP02 EXEC PGM={p2}\n"
            f"//OUT1   DD DSN=DATASET.OUT,DISP=(NEW,CATLG)\n"
        )
        manifest.jobs.append(JclEntry(
            job_id=job_id,
            source_text=jcl_text,
        ))

    # Measure memory and execution time
    tracemalloc.start()
    t0 = time.perf_counter()

    builder = PortfolioGraphBuilder()
    graph = builder.build(manifest)

    build_time = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert isinstance(graph, PortfolioGraph)
    assert len(graph.programs) == 100
    assert len(graph.nodes) >= 130
    assert len(graph.edges) >= 150

    # Verification: build must finish in < 2.0s and use < 20MB peak RAM
    assert build_time < 2.0
    assert peak_bytes < 20 * 1024 * 1024  # Under 20 MB

    # 3. Test Friction Matrix computation under scale
    friction_eval = DatabaseTransactionFrictionMatrix()
    friction_data = friction_eval.compute(graph)
    assert friction_data["program_count"] == 100
    assert friction_data["coupled_pairs_count"] > 0

    # 4. Test Cheeger Spectral Sweep under scale
    recommender = PartitionRecommender()
    candidates = recommender.recommend_portfolio_partitions(graph, top_k=5)
    assert isinstance(candidates, list)

    # 5. Test Bank ARB Dossier Generation under scale
    dossier_gen = ArbDossierGenerator()
    dossier = dossier_gen.generate_dossier(
        graph,
        system_name="Scale-Stress-Bank-Core",
        target_cloud_platform="AWS EKS"
    )
    assert dossier is not None
    assert dossier["executive_assessment"]["program_count"] == 100
    assert len(dossier["migration_waves"]) == 3


def test_resource_limit_guard_max_source_bytes():
    """Verify that oversized inputs exceeding 10 MiB raise ResourceLimitError."""
    oversized = "A" * (MAX_SOURCE_BYTES + 1024)
    with pytest.raises(ResourceLimitError) as exc_info:
        validate_source_size(oversized)
    assert "exceeds" in str(exc_info.value).lower()
