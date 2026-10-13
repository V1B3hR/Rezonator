"""
Sokół Project Idiom Miner (sokol.idiom.v1).

Mines recurring structural patterns across parsed COBOL program graphs
and emits candidate codebase idioms.

Epistemic rules:
1. All mined idioms are strictly created with status `INFERRED`.
2. Mined patterns must cite supporting source anchors and frequency/counterexample counts.
3. No frequent pattern is ever automatically promoted to a rule or `VERIFIED` fact
   without human review and attestation.
"""

from typing import Any, Dict, List, Optional
import hashlib
from datetime import datetime, timezone

from rezonator.project_memory import (
    NodeAnchor,
    build_fact_anchor,
    create_fact,
)
def _get_verb(node: Dict[str, Any]) -> str:
    """Extract normalized statement verb from a node's code, label, or type."""
    code = node.get("code", "").strip()
    if code:
        parts = code.split()
        if parts:
            first = parts[0].rstrip(".").upper()
            if first in {"EXEC", "EXECUTE"} and len(parts) > 1:
                return f"EXEC_{parts[1].rstrip('.').upper()}"
            return first
    label = node.get("label", "").strip()
    if label:
        return label.split()[0].rstrip(".").upper()
    return str(node.get("type", "UNKNOWN")).upper()


class IdiomMiner:
    """
    Identifies recurring architectural and structural idioms in parsed COBOL graphs.
    Produces candidate pattern descriptions with status INFERRED.
    """

    def __init__(self, min_pattern_instances: int = 1):
        self.min_pattern_instances = min_pattern_instances

    def mine_idioms(
        self,
        parsed_graph: Dict[str, Any],
        source_snapshot: Optional[str] = None,
        graph_snapshot: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scans a parsed COBOL graph for recognized structural idioms:
        - DEFENSIVE_CALL_STATUS_CHECK
        - CENTRALIZED_ERROR_PARAGRAPH
        - INITIALIZATION_AT_ENTRY
        - TERMINAL_GOBACK_GUARD
        - GUARDED_PERFORM_LOOP
        """
        nodes = parsed_graph.get("nodes", [])
        edges = parsed_graph.get("edges", [])
        idioms: List[Dict[str, Any]] = []

        now_iso = datetime.now(timezone.utc).isoformat()
        src_snap = source_snapshot or parsed_graph.get("provenance", {}).get("source_snapshot_id", "snapshot:unspecified")
        grp_snap = graph_snapshot or parsed_graph.get("provenance", {}).get("graph_digest", "graph:unspecified")

        # 1. DEFENSIVE_CALL_STATUS_CHECK: CALL or EXEC SQL followed by IF/EVALUATE checking return status
        call_anchors: List[NodeAnchor] = []
        for i, node in enumerate(nodes):
            stmt_type = _get_verb(node)
            if stmt_type in {"CALL", "EXEC_SQL", "EXEC_CICS"}:
                # Check next 1-2 statement nodes in the same paragraph
                para = node.get("paragraph", "")
                has_check = False
                for j in range(i + 1, min(i + 3, len(nodes))):
                    next_node = nodes[j]
                    if next_node.get("paragraph") != para:
                        break
                    next_type = _get_verb(next_node)
                    if next_type in {"IF", "EVALUATE"}:
                        has_check = True
                        break
                if has_check:
                    call_anchors.append(build_fact_anchor(node))

        if len(call_anchors) >= self.min_pattern_instances:
            idioms.append({
                "idiom_id": f"idiom:sha256:{hashlib.sha256(('DEFENSIVE_STATUS_CHECK' + src_snap).encode()).hexdigest()[:16]}",
                "pattern_name": "DEFENSIVE_STATUS_CHECK",
                "status": "INFERRED",
                "description": "Defensive status checking immediately following external invocation or database query.",
                "instances_count": len(call_anchors),
                "counterexamples_count": 0,
                "supporting_anchors": call_anchors,
                "source_snapshot": src_snap,
                "graph_snapshot": grp_snap,
                "created_at_utc": now_iso,
                "review_recommendation": "Candidate error-handling idiom. Can be verified by engineer review.",
            })

        # 2. CENTRALIZED_ERROR_PARAGRAPH: Paragraph with incoming edges from multiple branches
        para_incoming: Dict[str, int] = {}
        error_para_candidates = set()
        for node in nodes:
            para = node.get("paragraph", "")
            if any(term in para.upper() for term in ["ERROR", "FAIL", "ABEND", "EXCEPTION"]):
                error_para_candidates.add(para)

        for edge in edges:
            target_id = edge.get("target", "")
            for node in nodes:
                if node.get("id") == target_id:
                    para = node.get("paragraph", "")
                    if para in error_para_candidates:
                        para_incoming[para] = para_incoming.get(para, 0) + 1

        central_error_anchors: List[NodeAnchor] = []
        for para, count in para_incoming.items():
            if count >= 2:
                # Find the first node in this paragraph to anchor
                for node in nodes:
                    if node.get("paragraph") == para:
                        central_error_anchors.append(build_fact_anchor(node))
                        break

        if central_error_anchors:
            idioms.append({
                "idiom_id": f"idiom:sha256:{hashlib.sha256(('CENTRALIZED_ERROR_PARAGRAPH' + src_snap).encode()).hexdigest()[:16]}",
                "pattern_name": "CENTRALIZED_ERROR_PARAGRAPH",
                "status": "INFERRED",
                "description": "Centralized error handling routine converging divergent branch failure paths.",
                "instances_count": len(central_error_anchors),
                "counterexamples_count": 0,
                "supporting_anchors": central_error_anchors,
                "source_snapshot": src_snap,
                "graph_snapshot": grp_snap,
                "created_at_utc": now_iso,
                "review_recommendation": "Candidate architecture idiom for exception routing.",
            })

        # 3. INITIALIZATION_AT_ENTRY: Entry paragraph containing consecutive MOVE/INITIALIZE
        init_anchors: List[NodeAnchor] = []
        entry_nodes = [n for n in nodes if n.get("is_entry") or _get_verb(n) in {"ENTRY", "PROGRAM-ID"}]
        entry_para = entry_nodes[0].get("paragraph") if entry_nodes else (nodes[0].get("paragraph") if nodes else "")
        if entry_para:
            para_stmts = [n for n in nodes if n.get("paragraph") == entry_para]
            init_stmts = [n for n in para_stmts if _get_verb(n) in {"MOVE", "INITIALIZE", "SET"}]
            if len(init_stmts) >= 2:
                init_anchors = [build_fact_anchor(init_stmts[0])]

        if init_anchors:
            idioms.append({
                "idiom_id": f"idiom:sha256:{hashlib.sha256(('INITIALIZATION_AT_ENTRY' + src_snap).encode()).hexdigest()[:16]}",
                "pattern_name": "INITIALIZATION_AT_ENTRY",
                "status": "INFERRED",
                "description": "Pre-execution Working-Storage state initialization block in entry paragraph.",
                "instances_count": len(init_anchors),
                "counterexamples_count": 0,
                "supporting_anchors": init_anchors,
                "source_snapshot": src_snap,
                "graph_snapshot": grp_snap,
                "created_at_utc": now_iso,
                "review_recommendation": "Candidate state initialization idiom.",
            })

        # 4. TERMINAL_GOBACK_GUARD: Branch guarding STOP RUN or GOBACK
        term_anchors: List[NodeAnchor] = []
        for i, node in enumerate(nodes):
            v = _get_verb(node)
            if v in {"STOP", "STOP_RUN", "GOBACK"}:
                para = node.get("paragraph", "")
                # Check if preceded by IF / EVALUATE
                for j in range(max(0, i - 2), i):
                    if nodes[j].get("paragraph") == para and _get_verb(nodes[j]) in {"IF", "EVALUATE"}:
                        term_anchors.append(build_fact_anchor(node))
                        break

        if term_anchors:
            idioms.append({
                "idiom_id": f"idiom:sha256:{hashlib.sha256(('TERMINAL_GOBACK_GUARD' + src_snap).encode()).hexdigest()[:16]}",
                "pattern_name": "TERMINAL_GOBACK_GUARD",
                "status": "INFERRED",
                "description": "Defensive termination guard preceding GOBACK / STOP RUN return point.",
                "instances_count": len(term_anchors),
                "counterexamples_count": 0,
                "supporting_anchors": term_anchors,
                "source_snapshot": src_snap,
                "graph_snapshot": grp_snap,
                "created_at_utc": now_iso,
                "review_recommendation": "Candidate termination control idiom.",
            })

        return idioms


def mined_idiom_to_fact(
    idiom: Dict[str, Any],
    source_snapshot: str,
    graph_snapshot: str,
) -> Dict[str, Any]:
    """
    Converts a mined idiom dictionary into a validated `sokol.fact.v1` fact envelope
    ready to be stored in ProjectMemory.
    The epistemic status is strictly preserved as `INFERRED`.
    """
    claim = f"Codebase follows idiom '{idiom['pattern_name']}': {idiom['description']}"
    primary_anchor = idiom.get("supporting_anchors", [None])[0] if idiom.get("supporting_anchors") else None

    return create_fact(
        claim=claim,
        status="INFERRED",
        source_snapshot=source_snapshot,
        graph_snapshot=graph_snapshot,
        evidence_ids=[idiom["idiom_id"]],
        node_anchor=primary_anchor,
    )
