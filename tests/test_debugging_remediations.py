"""
Unit and integration tests for Debugging Remediations.
Verifies mathematical precision, algorithmic complexity invariants, and parser fidelity:
1. N=1 graph spectral trace consistency (NetLSD full == reduced == 1.0).
2. COBOL English relational phrase parsing and hermetic runtime evaluation.
3. Sparse eigensolver shift stability (sigma < 0 for positive semi-definite Laplacians).
4. O(V+E) reverse reachability for trapped SCC detection in cycle_detector.
5. Deque BFS in pinn_diffusion directed impact reachability.
6. Defensive dimension guard in diffusion_ranker rank_by_spectral_distance.
"""

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


def test_n1_graph_spectral_reduction_invariants():
    """Verify N=1 graph reduced NetLSD trace is identically 1.0, matching full trace."""
    engine = DiamondYantSpectralEngine()
    L_1 = np.zeros((1, 1), dtype=np.float64)

    spec = engine.compute_spectrum(L_1, L_norm=L_1)
    assert len(spec["netlsd_signature"]) > 0
    assert len(spec["netlsd_reduced_3d"]) > 0

    # At all time scales, e^(-t*0) / 1 == 1.0
    for full_val, red_val in zip(spec["netlsd_signature"], spec["netlsd_reduced_3d"]):
        assert pytest.approx(full_val, rel=1e-9) == 1.0
        assert pytest.approx(red_val, rel=1e-9) == 1.0

    emb = engine.compute_3d_spectral_embedding(L_1)
    assert emb["eigenvalues"] == []
    assert emb["lambda_0"] == 0.0


def test_cobol_english_relational_phrases_ast():
    """Verify COBOL English relational operators are normalized to standard symbols."""
    # GREATER THAN
    c1 = parse_condition_expr("A GREATER THAN B")
    assert c1.left_operand == "A"
    assert c1.operator == ">"
    assert c1.right_operand == "B"

    # LESS THAN OR EQUAL TO
    c2 = parse_condition_expr("TOTAL-X LESS THAN OR EQUAL TO LIMIT-Y")
    assert c2.left_operand == "TOTAL-X"
    assert c2.operator == "<="
    assert c2.right_operand == "LIMIT-Y"

    # IS NOT EQUAL TO
    c3 = parse_condition_expr("STATUS-CODE IS NOT EQUAL TO 200")
    assert c3.left_operand == "STATUS-CODE"
    assert c3.operator == "!="
    assert c3.right_operand == "200"

    # IS EQUAL TO
    c4 = parse_condition_expr("FLAG IS EQUAL TO 'Y'")
    assert c4.left_operand == "FLAG"
    assert c4.operator == "="
    assert c4.right_operand == "'Y'"

    # Compound condition with AND
    c5 = parse_condition_expr("A GREATER THAN 10 AND B LESS OR EQUAL TO 20")
    assert hasattr(c5, "left_condition")
    assert c5.left_condition.operator == ">"
    assert c5.right_condition.operator == "<="


def test_cobol_english_relational_runtime_evaluation():
    """Verify CobolRuntime evaluates English relational phrases accurately in execution."""
    runtime = CobolRuntime()
    vars_env = {"ALPHA": 100, "BETA": 50, "GAMMA": 50}

    assert runtime._eval_expr("ALPHA GREATER THAN BETA", vars_env) is True
    assert runtime._eval_expr("ALPHA LESS THAN BETA", vars_env) is False
    assert runtime._eval_expr("BETA IS EQUAL TO GAMMA", vars_env) is True
    assert runtime._eval_expr("ALPHA IS NOT EQUAL TO BETA", vars_env) is True
    assert runtime._eval_expr("BETA GREATER THAN OR EQUAL TO GAMMA", vars_env) is True

    # Test complete execution of COBOL program with IF GREATER THAN
    src = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RELTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 NUM-A PIC 9(4) VALUE 25.
       01 NUM-B PIC 9(4) VALUE 10.
       01 RESULT-FLAG PIC X VALUE 'N'.
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF NUM-A GREATER THAN NUM-B
               MOVE 'Y' TO RESULT-FLAG
           ELSE
               MOVE 'N' TO RESULT-FLAG
           END-IF.
           STOP RUN.
    """
    builder = CobolASTGraphBuilder()
    graph = builder.build_from_source(src)
    state = runtime.run_graph(graph, initial_overrides={"NUM-A": 25, "NUM-B": 10, "RESULT-FLAG": "N"})
    assert state.terminated is True
    assert state.variables["RESULT-FLAG"] == "Y"


def test_partition_recommender_negative_shift_stability():
    """Verify eigensolver uses negative shift (SPARSE_EIGENSOLVER_SHIFT < 0) for positive semi-definite stability."""
    assert SPARSE_EIGENSOLVER_SHIFT < 0

    recommender = PartitionRecommender()
    # Construct a sparse Laplacian for a 200-node barbell-like graph
    n1, n2 = 100, 100
    G = nx.disjoint_union(nx.complete_graph(n1), nx.complete_graph(n2))
    G.add_edge(n1 - 1, n1)  # single bridge edge
    L = nx.laplacian_matrix(G).astype(np.float64)

    fiedler_val, fiedler_vec = recommender._compute_fiedler_vector(L, G.number_of_nodes())
    assert fiedler_val > 0.0
    assert len(fiedler_vec) == 200
    # Signs of Fiedler vector should clearly separate the two clusters
    signs = np.sign(fiedler_vec)
    assert np.all(signs[:n1] == signs[0])
    assert np.all(signs[n1:] == -signs[0])


def test_cycle_detector_reverse_reachability():
    """Verify O(V+E) reverse reachability correctly isolates trapped SCCs without quadratic traversals."""
    nodes = [
        {"id": "ENTRY", "code": "PERFORM PARA-A", "node_type": "perform"},
        {"id": "L1", "code": "ADD 1 TO X", "node_type": "stmt"},
        {"id": "L2", "code": "ADD 1 TO Y", "node_type": "stmt"},
        {"id": "TERM", "code": "STOP RUN", "node_type": "stop"},
        {"id": "TRAP1", "code": "ADD 1 TO Z", "node_type": "stmt"},
        {"id": "TRAP2", "code": "ADD 1 TO W", "node_type": "stmt"},
    ]
    edges = [
        {"source": "ENTRY", "target": "L1", "edge_type": "cfg_seq"},
        {"source": "L1", "target": "L2", "edge_type": "cfg_seq"},
        {"source": "L2", "target": "L1", "edge_type": "cfg_seq"},  # Loop 1
        {"source": "L2", "target": "TERM", "edge_type": "cfg_seq"},  # Escape to terminal
        {"source": "TRAP1", "target": "TRAP2", "edge_type": "cfg_seq"},  # Loop 2 (trapped)
        {"source": "TRAP2", "target": "TRAP1", "edge_type": "cfg_seq"},
    ]
    detector = CycleDetector({"nodes": nodes, "edges": edges})
    res = detector.analyze()

    assert res["scc_count"] >= 2
    # L1-L2 can reach TERM, so it is not trapped
    # TRAP1-TRAP2 cannot reach TERM, so it must be identified as trapped
    assert res["trapped_scc_count"] == 1
    trapped_summary = [s for s in res["sccs"] if s["is_trapped"]][0]
    assert "TRAP1" in trapped_summary["nodes"] and "TRAP2" in trapped_summary["nodes"]


def test_pinn_diffusion_directed_impact_reachability():
    """Verify PINN directed impact reachability with deque BFS produces exact topological reachability."""
    pinn = PINNGraphDiffusionEngine(alpha=1.0)
    # Directed line graph: 0 -> 1 -> 2 -> 3
    A = sp.csr_matrix(([1.0, 1.0, 1.0], ([0, 1, 2], [1, 2, 3])), shape=(4, 4))
    res = pinn.solve_directed_impact(A, source_idx=1, t=1.0)

    assert res["source_idx"] == 1
    assert res["exact_reachable_count"] == 3  # nodes 1, 2, 3


def test_diffusion_ranker_spectral_distance_dimension_guard():
    """Verify rank_by_spectral_distance raises ValueError on dimension mismatch."""
    ranker = DiffusionRanker({
        "nodes": [{"id": "A"}, {"id": "B"}],
        "edges": [{"source": "A", "target": "B", "weight": 1.0}],
    })

    # Pass 3D embedding with wrong length (e.g. 3 nodes instead of 2)
    wrong_emb = np.zeros((3, 3), dtype=np.float64)
    with pytest.raises(ValueError, match="embedding_3d row count 3 does not match ranker node count 2"):
        ranker.rank_by_spectral_distance("A", embedding_3d=wrong_emb)

    # Valid embedding passes
    valid_emb = np.zeros((2, 3), dtype=np.float64)
    ranking = ranker.rank_by_spectral_distance("A", embedding_3d=valid_emb)
    assert ranking == ["B"]
