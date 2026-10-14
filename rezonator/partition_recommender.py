"""
Spectral Partition Recommender (Filar F6).
Computes Fiedler-vector sweeps, Cheeger conductance bounds, and domain-aware
decomposition candidates across program dependence and application portfolio graphs.
Explains crossing edges, shared database state, call traffic, and uncertainty.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from rezonator.portfolio_graph import PortfolioGraph
from rezonator.analysis_config import SPARSE_EIGENSOLVER_SHIFT


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass
class CrossingEdge:
    source: str
    target: str
    edge_type: str
    weight: float = 1.0
    label: str = ""
    is_dynamic: bool = False
    source_location: Optional[int] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "label": self.label,
            "is_dynamic": self.is_dynamic,
            "source_location": self.source_location,
            "description": self.description,
        }


@dataclass
class PartitionCandidate:
    candidate_id: str
    name: str
    partition_a: List[str]
    partition_b: List[str]
    conductance: float
    cheeger_bound_lower: float
    cheeger_bound_upper: float
    fiedler_threshold: float
    crossing_edges: List[CrossingEdge]
    shared_tables: List[str] = field(default_factory=list)
    shared_datasets: List[str] = field(default_factory=list)
    transaction_boundaries_violated: int = 0
    uncertainty_score: float = 0.0  # 0.0 to 1.0
    architect_review_status: str = "PENDING_ARCHITECT_REVIEW"
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "partition_a_size": len(self.partition_a),
            "partition_b_size": len(self.partition_b),
            "partition_a": list(self.partition_a),
            "partition_b": list(self.partition_b),
            "conductance": round(self.conductance, 4),
            "cheeger_bound_lower": round(self.cheeger_bound_lower, 4),
            "cheeger_bound_upper": round(self.cheeger_bound_upper, 4),
            "fiedler_threshold": round(self.fiedler_threshold, 4),
            "crossing_edges_count": len(self.crossing_edges),
            "crossing_edges": [e.to_dict() for e in self.crossing_edges],
            "shared_tables": list(self.shared_tables),
            "shared_datasets": list(self.shared_datasets),
            "transaction_boundaries_violated": self.transaction_boundaries_violated,
            "uncertainty_score": round(self.uncertainty_score, 4),
            "architect_review_status": self.architect_review_status,
            "rationale": self.rationale,
        }


class PartitionRecommender:
    """
    Spectral & Domain-Aware Graph Partitioner (sokol.partition.v1).
    Generates explainable architectural partition candidates using Fiedler vector sweeps,
    Cheeger conductance evaluation, and mainframe transaction/data ownership constraints.
    """

    SCHEMA_VERSION = "sokol.partition.v1"

    def __init__(
        self,
        conductance_weight: float = 1.0,
        shared_table_weight: float = 2.5,
        shared_dataset_weight: float = 1.5,
        transaction_weight: float = 3.0,
    ):
        self.conductance_weight = conductance_weight
        self.shared_table_weight = shared_table_weight
        self.shared_dataset_weight = shared_dataset_weight
        self.transaction_weight = transaction_weight

    def recommend_portfolio_partitions(
        self, portfolio: PortfolioGraph, top_k: int = 3
    ) -> List[PartitionCandidate]:
        """
        Recommends decomposition boundaries for a multi-program portfolio graph.
        """
        nodes_dict = portfolio.nodes
        edges_list = portfolio.edges
        node_ids = sorted(list(nodes_dict.keys()))
        n = len(node_ids)

        if n < 2:
            return []

        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}

        # Build symmetrized adjacency matrix for spectral analysis
        rows = []
        cols = []
        data = []
        edge_lookup: Dict[Tuple[str, str], List[Any]] = collections.defaultdict(list)

        for e in edges_list:
            src = e.source
            dst = e.target
            if src in node_to_idx and dst in node_to_idx:
                u = node_to_idx[src]
                v = node_to_idx[dst]
                w = float(getattr(e, "weight", 1.0) or 1.0)
                rows.extend([u, v])
                cols.extend([v, u])
                data.extend([w, w])
                edge_lookup[(src, dst)].append(e)

        A_sp = sp.csr_matrix((data, (rows, cols)), shape=(n, n), dtype=np.float64)
        degrees = np.asarray(A_sp.sum(axis=1)).ravel()

        # Compute graph Laplacian L = D - A
        D_sp = sp.diags(degrees, format="csr")
        L_sp = D_sp - A_sp

        # Solve for Fiedler vector v_2
        fiedler_val, fiedler_vec = self._compute_fiedler_vector(L_sp, n)

        # Cheeger bounds: lambda_1 / 2 <= phi <= sqrt(2 * lambda_1)
        cheeger_lower = max(0.0, fiedler_val / 2.0)
        cheeger_upper = min(1.0, math.sqrt(max(0.0, 2.0 * fiedler_val)))

        # Sweep along Fiedler vector
        sorted_indices = np.argsort(fiedler_vec)
        vol_total = float(np.sum(degrees))

        candidates: List[PartitionCandidate] = []
        best_cuts: List[Tuple[float, int, Set[str], Set[str]]] = []

        for split_pos in range(1, n):
            set_a_idx = set(sorted_indices[:split_pos])
            set_b_idx = set(sorted_indices[split_pos:])

            set_a_nodes = {node_ids[i] for i in set_a_idx}
            set_b_nodes = {node_ids[i] for i in set_b_idx}

            # Conductance phi(S) = cut(S, S_bar) / min(vol(S), vol(S_bar))
            vol_a = float(np.sum(degrees[list(set_a_idx)]))
            vol_b = float(np.sum(degrees[list(set_b_idx)]))
            min_vol = min(vol_a, vol_b)

            if min_vol <= 1e-9:
                continue

            # Calculate cut weight
            cut_weight = 0.0
            for u in set_a_idx:
                row_start = A_sp.indptr[u]
                row_end = A_sp.indptr[u + 1]
                for p in range(row_start, row_end):
                    v = A_sp.indices[p]
                    if v in set_b_idx:
                        cut_weight += A_sp.data[p]

            conductance = cut_weight / min_vol
            threshold = float(fiedler_vec[sorted_indices[split_pos - 1]])
            best_cuts.append((conductance, split_pos, set_a_nodes, set_b_nodes, threshold))

        # Sort cuts by conductance
        best_cuts.sort(key=lambda x: x[0])

        candidate_counter = 1
        seen_partitions = set()

        for cond, split_pos, part_a, part_b, thresh in best_cuts:
            part_key = (frozenset(part_a), frozenset(part_b))
            if part_key in seen_partitions or (frozenset(part_b), frozenset(part_a)) in seen_partitions:
                continue
            seen_partitions.add(part_key)

            # Analyze crossing edges and domain frictions
            crossing_edges: List[CrossingEdge] = []
            shared_tables: Set[str] = set()
            shared_datasets: Set[str] = set()
            tx_violations = 0
            dynamic_crossings = 0

            for e in edges_list:
                src_in_a = e.source in part_a
                dst_in_a = e.target in part_a
                src_in_b = e.source in part_b
                dst_in_b = e.target in part_b

                # Edge crosses if endpoints are in different partitions
                if (src_in_a and dst_in_b) or (src_in_b and dst_in_a):
                    is_dyn = bool(getattr(e, "metadata", {}).get("is_dynamic", False)) or e.edge_type == "CALL_DYNAMIC"
                    if is_dyn:
                        dynamic_crossings += 1

                    line_loc = getattr(e, "metadata", {}).get("line")

                    desc = f"Crossing interaction: {e.source} -> {e.target} ({e.edge_type})"
                    if "SQL" in e.edge_type:
                        desc += " [Relational Database coupling]"
                    elif "DSN" in e.edge_type:
                        desc += " [Dataset File coupling]"
                    elif "STEP" in e.edge_type:
                        desc += " [Batch Workflow execution chain]"
                        tx_violations += 1

                    crossing_edges.append(CrossingEdge(
                        source=e.source,
                        target=e.target,
                        edge_type=e.edge_type,
                        weight=getattr(e, "weight", 1.0),
                        label=getattr(e, "label", ""),
                        is_dynamic=is_dyn,
                        source_location=line_loc,
                        description=desc,
                    ))

            # Detect shared DB2 tables across partitions
            for nid, node in nodes_dict.items():
                if node.node_type == "db2_table":
                    progs_a = [e.source for e in edges_list if e.target == nid and e.source in part_a]
                    progs_b = [e.source for e in edges_list if e.target == nid and e.source in part_b]
                    if progs_a and progs_b:
                        shared_tables.add(node.label)

                elif node.node_type == "dataset":
                    accs_a = [e.source for e in edges_list if e.target == nid and e.source in part_a]
                    accs_b = [e.source for e in edges_list if e.target == nid and e.source in part_b]
                    if accs_a and accs_b:
                        shared_datasets.add(node.label)

            # Uncertainty score based on dynamic calls and unresolved targets
            total_crossings = len(crossing_edges)
            uncertainty = (dynamic_crossings / max(1, total_crossings)) if total_crossings > 0 else 0.0

            # Composite cost score
            composite_score = (
                self.conductance_weight * cond
                + self.shared_table_weight * len(shared_tables)
                + self.shared_dataset_weight * len(shared_datasets)
                + self.transaction_weight * tx_violations
            )

            # Rationale explanation
            rationale_parts = [
                f"Spectral Cheeger partition with conductance phi = {cond:.4f} (Cheeger bound: [{cheeger_lower:.4f}, {cheeger_upper:.4f}])."
            ]
            if shared_tables:
                rationale_parts.append(f"Splits shared DB2 table ownership across {len(shared_tables)} tables ({', '.join(sorted(shared_tables))}).")
            if shared_datasets:
                rationale_parts.append(f"Requires distributed data-exchange for {len(shared_datasets)} datasets.")
            if tx_violations > 0:
                rationale_parts.append(f"Crosses {tx_violations} sequential JCL workflow execution step(s).")
            if dynamic_crossings > 0:
                rationale_parts.append(f"Includes {dynamic_crossings} dynamic call(s) requiring runtime resolution.")

            rationale = " ".join(rationale_parts)

            cid = f"cand-{candidate_counter:02d}-{hashlib.sha256(_canonical_json(sorted(list(part_a)))).hexdigest()[:8]}"
            name = f"Candidate Boundary {candidate_counter} (phi={cond:.3f})"

            candidates.append(PartitionCandidate(
                candidate_id=cid,
                name=name,
                partition_a=sorted(list(part_a)),
                partition_b=sorted(list(part_b)),
                conductance=conductance,
                cheeger_bound_lower=cheeger_lower,
                cheeger_bound_upper=cheeger_upper,
                fiedler_threshold=thresh,
                crossing_edges=crossing_edges,
                shared_tables=sorted(list(shared_tables)),
                shared_datasets=sorted(list(shared_datasets)),
                transaction_boundaries_violated=tx_violations,
                uncertainty_score=uncertainty,
                architect_review_status="PENDING_ARCHITECT_REVIEW",
                rationale=rationale,
            ))

            candidate_counter += 1
            if len(candidates) >= top_k:
                break

        return candidates

    def _compute_fiedler_vector(self, L_sp: sp.csr_matrix, n: int) -> Tuple[float, np.ndarray]:
        if n <= 128:
            L_dense = L_sp.toarray()
            evals, evecs = la.eigh(L_dense)
            idx = np.argsort(evals)
            evals = np.clip(evals[idx], 0.0, None)
            evecs = evecs[:, idx]
            fiedler_val = float(evals[1]) if len(evals) > 1 else float(evals[0])
            fiedler_vec = evecs[:, 1] if evecs.shape[1] > 1 else evecs[:, 0]
            return fiedler_val, fiedler_vec

        try:
            evals, evecs = spla.eigsh(L_sp, k=2, sigma=SPARSE_EIGENSOLVER_SHIFT, which="LM")
            idx = np.argsort(evals)
            evals = np.clip(evals[idx], 0.0, None)
            evecs = evecs[:, idx]
            return float(evals[1]), evecs[:, 1]
        except Exception:
            evals, evecs = spla.eigsh(L_sp, k=2, which="SM")
            idx = np.argsort(evals)
            return float(evals[1]), evecs[:, 1]

    def to_markdown_report(self, candidates: List[PartitionCandidate]) -> str:
        """Renders explainable architectural partition candidates in Markdown."""
        lines = [
            "# Architecture Partition Recommendations (Filar F6)",
            "",
            "> **Epistemic Invariant:** A spectral cut is a topological heuristic; it does not by itself prove a valid microservice boundary or minimize real distributed transaction costs.",
            "> **Governance Rule:** All candidate partitions remain `PENDING_ARCHITECT_REVIEW`. Rezonator gathers evidence; it does not autonomously rewrite boundaries.",
            "",
            "## 1. Candidate Decomposition Summary",
            "",
            "| ID | Name | Partition Sizes (A / B) | Conductance (phi) | Cheeger Bounds | Shared Tables | Crossing Edges | Status |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |",
        ]

        for c in candidates:
            lines.append(
                f"| `{c.candidate_id}` | **{c.name}** | {len(c.partition_a)} / {len(c.partition_b)} | "
                f"`{c.conductance:.4f}` | `[{c.cheeger_bound_lower:.3f}, {c.cheeger_bound_upper:.3f}]` | "
                f"`{len(c.shared_tables)}` | `{len(c.crossing_edges)}` | `PENDING_REVIEW` |"
            )

        lines.extend(["", "---", "", "## 2. In-Depth Boundary Breakdown"])

        for idx, c in enumerate(candidates, 1):
            lines.extend([
                "",
                f"### 2.{idx} {c.name} (`{c.candidate_id}`)",
                "",
                f"- **Rationale:** {c.rationale}",
                f"- **Conductance:** `{c.conductance:.4f}` (lower indicates cleaner graph cut)",
                f"- **Uncertainty Score:** `{c.uncertainty_score * 100:.1f}%` (derived from dynamic call edges)",
                f"- **Transaction Violations:** `{c.transaction_boundaries_violated}` step/transaction boundary crossings",
                "",
                "#### Partition A Components:",
                f"- `{', '.join(c.partition_a[:8])}{' ...' if len(c.partition_a) > 8 else ''}`",
                "",
                "#### Partition B Components:",
                f"- `{', '.join(c.partition_b[:8])}{' ...' if len(c.partition_b) > 8 else ''}`",
                "",
            ])

            if c.shared_tables:
                lines.append(f"#### ⚠️ Shared Relational Tables Crossing Boundary: `{', '.join(c.shared_tables)}`")
            if c.shared_datasets:
                lines.append(f"#### ⚠️ Shared Datasets Crossing Boundary: `{', '.join(c.shared_datasets)}`")

            if c.crossing_edges:
                lines.extend([
                    "",
                    "#### Crossing Interaction Edges:",
                    "| Source | Target | Edge Type | Description | Location |",
                    "| :--- | :--- | :--- | :--- | :--- |",
                ])
                for ce in c.crossing_edges[:10]:
                    loc_str = f"L{ce.source_location}" if ce.source_location else "N/A"
                    lines.append(f"| `{ce.source}` | `{ce.target}` | `{ce.edge_type}` | {ce.description} | `{loc_str}` |")
                if len(c.crossing_edges) > 10:
                    lines.append(f"| *...* | *...* | *...* | *(+{len(c.crossing_edges) - 10} additional edges omitted)* | |")

        return "\n".join(lines)
