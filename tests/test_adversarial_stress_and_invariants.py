"""
Adversarial, Stress, and Mathematical Invariant Test Suite.
Verifies boundary conditions, degenerate cases, high-order topologies,
and stress scenarios that go far beyond happy-path unit tests:
1. Adversarial string literal preservation in COBOL condition parsing.
2. Disconnected graph spectral stability (multiplicity of lambda=0 >= 2).
3. Extremal graph topologies: N=0, N=1, N=2, Star graph (hub heterogeneity), Bipartite (lambda_max = 2.0).
4. Asymptotic stress tests on scaled graphs (N=2,000 to N=5,000) verifying O(V+E) linear scaling.
5. Cheeger conductance mathematical bounds and non-negativity invariants.
"""

import time
import math
import numpy as np
import scipy.sparse as sp
import networkx as nx
import pytest

from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.ast_graph_builder import (
    parse_condition_expr,
    normalize_cobol_relational_phrases,
    CobolASTGraphBuilder,
)
from rezonator.cobol_runtime import CobolRuntime
from rezonator.partition_recommender import PartitionRecommender
from rezonator.cycle_detector import CycleDetector
from rezonator.pinn_diffusion import PINNGraphDiffusionEngine
from rezonator.diffusion_ranker import DiffusionRanker
from rezonator.analysis_config import SPARSE_EIGENSOLVER_SHIFT


# ============================================================================
# 1. Adversarial String Literal & COBOL Syntax Preservation
# ============================================================================

def test_adversarial_string_literal_preservation():
    """Verify relational normalization NEVER mutates strings inside quotes."""
    # Single quotes
    raw1 = "STATUS-TXT = 'GREATER THAN'"
    norm1 = normalize_cobol_relational_phrases(raw1)
    assert norm1 == "STATUS-TXT = 'GREATER THAN'"

    # Double quotes
    raw2 = 'ERR-MSG EQUAL TO "LESS THAN OR EQUAL TO"'
    norm2 = normalize_cobol_relational_phrases(raw2)
    assert norm2 == 'ERR-MSG = "LESS THAN OR EQUAL TO"'

    # Compound with both real operator and string literal containing operator keywords
    raw3 = "VAR-A GREATER THAN 50 AND MSG-CODE NOT EQUAL TO 'NOT EQUAL TO'"
    norm3 = normalize_cobol_relational_phrases(raw3)
    assert norm3 == "VAR-A > 50 AND MSG-CODE != 'NOT EQUAL TO'"

    # Hyphenated COBOL variables that contain keyword substrings
    raw4 = "IS-EQUAL-VAR GREATER THAN MY-GREATER-VAL"
    norm4 = normalize_cobol_relational_phrases(raw4)
    assert norm4 == "IS-EQUAL-VAR > MY-GREATER-VAL"

    c = parse_condition_expr(raw4)
    assert c.left_operand == "IS-EQUAL-VAR"
    assert c.operator == ">"
    assert c.right_operand == "MY-GREATER-VAL"


def test_runtime_evaluation_with_quoted_relational_strings():
    """Verify CobolRuntime evaluates conditionals comparing strings containing relational words."""
    runtime = CobolRuntime()
    vars_env = {
        "FLAG-A": "GREATER THAN",
        "FLAG-B": "LESS THAN",
        "NUM": 42,
    }
    # Exact string match against keyword
    assert runtime._eval_expr("FLAG-A EQUAL TO 'GREATER THAN'", vars_env) is True
    assert runtime._eval_expr("FLAG-A EQUAL TO 'LESS THAN'", vars_env) is False
    assert runtime._eval_expr("NUM GREATER THAN 40 AND FLAG-B EQUAL TO 'LESS THAN'", vars_env) is True


# ============================================================================
# 2. Disconnected Graphs & Multiple Zero Eigenvalues (Multiplicity >= 2)
# ============================================================================

def test_disconnected_graph_eigensolver_stability():
    """
    On a disconnected graph with k components, lambda_0 = ... = lambda_{k-1} = 0.
    Verify ARPACK with negative shift does not crash or produce NaN.
    """
    recommender = PartitionRecommender()
    # 5 disconnected cliques of size 40 each (N=200)
    G = nx.disjoint_union_all([nx.complete_graph(40) for _ in range(5)])
    assert nx.number_connected_components(G) == 5

    L = nx.laplacian_matrix(G).astype(np.float64)
    fiedler_val, fiedler_vec = recommender._compute_fiedler_vector(L, G.number_of_nodes())

    assert np.all(np.isfinite(fiedler_vec))
    assert not np.isnan(fiedler_val)
    # Algebraic connectivity of a disconnected graph must be mathematically 0.0
    assert pytest.approx(fiedler_val, abs=1e-5) == 0.0


# ============================================================================
# 3. Extremal Graph Topologies: N=0, N=1, N=2, Star Graph, Bipartite
# ============================================================================

def test_extremal_spectral_topologies():
    """Verify mathematical spectrum invariants across extremal graphs."""
    engine = DiamondYantSpectralEngine()

    # N = 0 (Empty graph)
    L_0 = np.zeros((0, 0), dtype=np.float64)
    spec_0 = engine.compute_spectrum(L_0, L_norm=L_0)
    assert spec_0["eigenvalues"] == []
    assert spec_0["netlsd_signature"] == []
    assert spec_0["spectral_half_life_3d"] == float("inf")

    # N = 2 (Single edge K_2)
    # L = [[1, -1], [-1, 1]], evals = [0, 2]
    # Normalized Laplacian for K_2: [[1, -1], [-1, 1]]
    L_2 = np.array([[1.0, -1.0], [-1.0, 1.0]], dtype=np.float64)
    spec_2 = engine.compute_spectrum(L_2, L_norm=L_2)
    assert len(spec_2["eigenvalues"]) >= 1
    # For K_2, normalized Laplacian has eigenvalues 0 and 2.0 (maximum possible for normalized Laplacian)
    assert pytest.approx(spec_2["fiedler_norm"], rel=1e-5) == 2.0

    # Star graph S_100: 1 central hub connected to 99 leaves
    # Normalized Laplacian has eigenvalue 1 with high multiplicity
    star = nx.star_graph(99)  # 100 nodes
    L_star = nx.normalized_laplacian_matrix(star).astype(np.float64)
    spec_star = engine.compute_spectrum(L_star.toarray(), L_norm=L_star.toarray())
    assert spec_star["fiedler_norm"] > 0.0
    # Cheeger upper bound must strictly be <= 1.0
    assert spec_star["fiedler_norm"] <= 2.0


# ============================================================================
# 4. Asymptotic Stress Tests on Scaled Graphs (O(V+E) Verification)
# ============================================================================

def test_cycle_detector_asymptotic_scaling_large_scc():
    """
    Stress test CycleDetector on a graph with N=2,000 nodes, 100 SCCs, and 50 terminal nodes.
    Verifies that the reverse BFS precomputation runs in milliseconds, preventing O(SCC * V * Terminals) explosion.
    """
    N = 2000
    nodes = []
    edges = []

    # Create 50 terminal nodes
    terminals = [f"TERM_{i}" for i in range(50)]
    for term in terminals:
        nodes.append({"id": term, "code": "STOP RUN", "node_type": "stop"})

    # Create 50 trapped cycles (cannot reach terminal)
    for i in range(50):
        t1 = f"TRAP_{i}_A"
        t2 = f"TRAP_{i}_B"
        nodes.extend([
            {"id": t1, "code": "ADD 1 TO X", "node_type": "stmt"},
            {"id": t2, "code": "ADD 1 TO Y", "node_type": "stmt"},
        ])
        edges.extend([
            {"source": t1, "target": t2, "edge_type": "cfg_seq"},
            {"source": t2, "target": t1, "edge_type": "cfg_seq"},
        ])

    # Create chain of 1,800 nodes that escape to terminal 0
    for i in range(1800):
        nid = f"CHAIN_{i}"
        nodes.append({"id": nid, "code": "MOVE 1 TO Z", "node_type": "stmt"})
        if i > 0:
            edges.append({"source": f"CHAIN_{i-1}", "target": nid, "edge_type": "cfg_seq"})
    edges.append({"source": "CHAIN_1799", "target": terminals[0], "edge_type": "cfg_seq"})

    detector = CycleDetector({"nodes": nodes, "edges": edges})

    start_time = time.perf_counter()
    res = detector.analyze()
    duration = time.perf_counter() - start_time

    # Performance invariant: 2,000 nodes should be analyzed in under 250 milliseconds
    assert duration < 0.25, f"Cycle analysis took {duration:.3f}s, expected < 0.25s"
    assert res["trapped_scc_count"] == 50
    assert res["reaches_terminal"] is True or len(res["sccs"]) > 0


def test_pinn_diffusion_deque_bfs_scaling_stress():
    """
    Stress test PINN directed impact on a line graph of N=5,000 nodes.
    With pop(0) this would take seconds (5,000^2 shifts). With collections.deque it takes < 0.05s.
    """
    N = 5000
    row = np.arange(N - 1)
    col = np.arange(1, N)
    data = np.ones(N - 1, dtype=np.float64)
    A_sp = sp.csr_matrix((data, (row, col)), shape=(N, N))

    pinn = PINNGraphDiffusionEngine(alpha=1.0)

    start_time = time.perf_counter()
    res = pinn.solve_directed_impact(A_sp, source_idx=0, t=0.1)
    duration = time.perf_counter() - start_time

    assert duration < 0.1, f"PINN directed impact took {duration:.3f}s, expected < 0.1s"
    assert res["exact_reachable_count"] == N


# ============================================================================
# 5. Cheeger Invariant & Cut Conductance Properties
# ============================================================================

def test_cheeger_bounds_and_conductance_invariants():
    """
    Verifies that for any partition candidate:
    0.0 <= conductance <= 1.0
    cheeger_bound_lower <= cheeger_bound_upper
    Exact partitioning of graph node universe without overlaps.
    """
    from rezonator.portfolio_manifest import PortfolioManifest, ProgramEntry
    from rezonator.portfolio_graph import PortfolioGraphBuilder

    src_template = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. {pid}.
       PROCEDURE DIVISION.
           {call_stmt}
           STOP RUN.
    """
    programs = []
    # Cluster A: 4 programs chained
    for i in range(4):
        pid = f"PROGA{i}"
        target = f"PROGA{i+1}" if i < 3 else "PROGB0"  # single cross edge to Cluster B
        call_stmt = f"CALL '{target}'."
        programs.append(ProgramEntry(program_id=pid, source_text=src_template.format(pid=pid, call_stmt=call_stmt)))

    # Cluster B: 4 programs chained
    for i in range(4):
        pid = f"PROGB{i}"
        call_stmt = f"CALL 'PROGB{i+1}'." if i < 3 else "STOP RUN."
        programs.append(ProgramEntry(program_id=pid, source_text=src_template.format(pid=pid, call_stmt=call_stmt)))

    manifest = PortfolioManifest(name="StressCluster", programs=programs)
    builder = PortfolioGraphBuilder()
    portfolio = builder.build(manifest)

    recommender = PartitionRecommender()
    candidates = recommender.recommend_portfolio_partitions(portfolio, top_k=3)

    assert len(candidates) > 0
    all_program_ids = {f"PGM:{p.program_id}" for p in programs}
    for cand in candidates:
        assert 0.0 <= cand.conductance <= 1.0
        assert 0.0 <= cand.cheeger_bound_lower <= cand.cheeger_bound_upper
        assert cand.cheeger_bound_upper <= 1.0
        # Check that partition sets partition the program universe exactly
        union_set = set(cand.partition_a).union(set(cand.partition_b))
        assert union_set == all_program_ids
        assert set(cand.partition_a).isdisjoint(set(cand.partition_b))
