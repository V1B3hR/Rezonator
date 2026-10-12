"""Sparse tensorization of symbolic program graphs.

Adjacency and Laplacian operators are kept in SciPy CSR form throughout the
normal analysis path. Dense conversion is an explicit, size-limited export
option only.
"""

from typing import Any, Dict, List

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from rezonator.limits import (
    MAX_DENSE_MATRIX_NODES,
    MAX_GRAPH_EDGES,
    GraphLimitError,
    validate_graph_payload,
)
from rezonator.analysis_config import VARIABLE_READ_EDGE_WEIGHT, VARIABLE_WRITE_EDGE_WEIGHT


class GraphField:
    """Sparse mathematical representation of a program dependence graph."""

    def __init__(
        self,
        parsed_data: Dict[str, Any],
        symmetrize: bool = True,
        include_variables: bool = True,
    ):
        self.program_id = parsed_data.get("program_id", "ANONYMOUS")
        raw_nodes = list(parsed_data.get("nodes", []))
        raw_edges = list(parsed_data.get("edges", []))
        self.variables = list(parsed_data.get("variables", []))
        self.symmetrize = symmetrize
        self.include_variables = include_variables

        validate_graph_payload(parsed_data, include_variables=include_variables)
        self.nodes = raw_nodes
        self.edges = raw_edges

        if include_variables:
            for var in self.variables:
                self.nodes.append({
                    "id": f"var_{var['name']}",
                    "label": f"[{var['name']}]",
                    "node_type": "var",
                    "paragraph": "WORKING-STORAGE",
                    "code": f"01 {var['name']} PIC {var.get('pic', '')}",
                    "reads": [],
                    "writes": [],
                })

            for node in raw_nodes:
                nid = node["id"]
                for r_var in node.get("reads", []):
                    if len(self.edges) >= MAX_GRAPH_EDGES:
                        raise GraphLimitError(
                            f"Expanded graph edge limit exceeded: more than {MAX_GRAPH_EDGES}"
                        )
                    self.edges.append({
                        "source": f"var_{r_var}",
                        "target": nid,
                        "edge_type": "dfg_read",
                        "weight": VARIABLE_READ_EDGE_WEIGHT,
                        "label": f"read({r_var})",
                    })
                for w_var in node.get("writes", []):
                    if len(self.edges) >= MAX_GRAPH_EDGES:
                        raise GraphLimitError(
                            f"Expanded graph edge limit exceeded: more than {MAX_GRAPH_EDGES}"
                        )
                    self.edges.append({
                        "source": nid,
                        "target": f"var_{w_var}",
                        "edge_type": "dfg_write",
                        "weight": VARIABLE_WRITE_EDGE_WEIGHT,
                        "label": f"write({w_var})",
                    })

        if len(self.edges) > MAX_GRAPH_EDGES:
            raise GraphLimitError(
                f"Expanded graph edge limit exceeded: {len(self.edges)} > {MAX_GRAPH_EDGES}"
            )

        self.num_nodes = len(self.nodes)
        if len({node["id"] for node in self.nodes}) != self.num_nodes:
            raise ValueError("Graph node identifiers must be unique")
        self.node_id_to_idx = {node["id"]: idx for idx, node in enumerate(self.nodes)}
        self.idx_to_node_id = {idx: node["id"] for idx, node in enumerate(self.nodes)}
        self.num_components = 0
        self.component_labels: List[int] = []
        self.isolated_nodes: List[str] = []

        if self.num_nodes:
            self._compute_matrices()
        else:
            empty = sp.csr_matrix((0, 0), dtype=np.float64)
            self.A_dir = empty.copy()
            self.A = empty.copy()
            self.D = empty.copy()
            self.L = empty.copy()
            self.L_norm = empty.copy()

    def _compute_matrices(self) -> None:
        rows: List[int] = []
        cols: List[int] = []
        weights: List[float] = []

        for edge in self.edges:
            src = edge["source"]
            dst = edge["target"]
            if src not in self.node_id_to_idx or dst not in self.node_id_to_idx:
                continue
            weight = float(edge.get("weight", 1.0))
            if not np.isfinite(weight) or weight < 0.0:
                raise ValueError("Graph edge weights must be finite and non-negative")
            rows.append(self.node_id_to_idx[src])
            cols.append(self.node_id_to_idx[dst])
            weights.append(weight)

        self.A_dir = sp.coo_matrix(
            (np.asarray(weights, dtype=np.float64), (rows, cols)),
            shape=(self.num_nodes, self.num_nodes),
            dtype=np.float64,
        ).tocsr()
        self.A_dir.sum_duplicates()
        self.A_dir.eliminate_zeros()
        self.A_dir.sort_indices()

        if self.symmetrize:
            self.A = (0.5 * (self.A_dir + self.A_dir.transpose())).tocsr()
        else:
            self.A = self.A_dir.copy()
        self.A.sum_duplicates()
        self.A.eliminate_zeros()
        self.A.sort_indices()

        count, labels = connected_components(self.A, directed=False)
        self.num_components = int(count)
        self.component_labels = labels.astype(int).tolist()

        degrees = np.asarray(self.A.sum(axis=1)).ravel()
        self.D = sp.diags(degrees, offsets=0, shape=(self.num_nodes, self.num_nodes), format="csr")
        isolated = np.flatnonzero(degrees == 0.0)
        self.isolated_nodes = [self.idx_to_node_id[int(i)] for i in isolated]

        self.L = (self.D - self.A).tocsr()
        # Preserve the previous symmetric-Laplacian contract when callers ask
        # for a directed adjacency (symmetrize=False).
        self.L = (0.5 * (self.L + self.L.transpose())).tocsr()
        self.L.eliminate_zeros()
        self.L.sort_indices()

        inv_sqrt_degree = np.zeros_like(degrees)
        positive = degrees > 0.0
        inv_sqrt_degree[positive] = 1.0 / np.sqrt(degrees[positive])
        D_inv_sqrt = sp.diags(inv_sqrt_degree, format="csr")
        self.L_norm = (
            sp.eye(self.num_nodes, format="csr", dtype=np.float64)
            - D_inv_sqrt @ self.A @ D_inv_sqrt
        ).tocsr()
        # Isolated vertices are represented by a zero row/column, not an
        # artificial unit eigenvalue.
        if np.any(~positive):
            keep = sp.diags(positive.astype(np.float64), format="csr")
            self.L_norm = (keep @ self.L_norm @ keep).tocsr()
        self.L_norm = (0.5 * (self.L_norm + self.L_norm.transpose())).tocsr()
        self.L_norm.eliminate_zeros()
        self.L_norm.sort_indices()

    def get_node_by_index(self, idx: int) -> Dict[str, Any]:
        return self.nodes[idx]

    def get_operator_storage_bytes(self) -> int:
        """Return exact NumPy-buffer bytes held by the five CSR operators."""
        operators = (self.A_dir, self.A, self.D, self.L, self.L_norm)
        return int(sum(matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes
                       for matrix in operators))

    def get_summary_stats(self) -> Dict[str, Any]:
        degrees = self.D.diagonal()
        return {
            "num_nodes": self.num_nodes,
            "num_edges": len(self.edges),
            "num_variables": len(self.variables),
            "num_components": self.num_components,
            "num_isolated_nodes": len(self.isolated_nodes),
            "isolated_nodes": self.isolated_nodes,
            "density": float(self.A.nnz / max(1, self.num_nodes * (self.num_nodes - 1))),
            "operator_storage_bytes": self.get_operator_storage_bytes(),
            "avg_degree": float(np.mean(degrees)) if self.num_nodes else 0.0,
            "max_degree": float(np.max(degrees)) if self.num_nodes else 0.0,
            "min_degree": float(np.min(degrees)) if self.num_nodes else 0.0,
        }

    @staticmethod
    def _csr_payload(matrix: sp.csr_matrix) -> Dict[str, Any]:
        return {
            "format": "csr",
            "shape": list(matrix.shape),
            "data": matrix.data.tolist(),
            "indices": matrix.indices.tolist(),
            "indptr": matrix.indptr.tolist(),
        }

    def to_dict(self, *, include_matrices: bool = False, matrix_format: str = "csr") -> Dict[str, Any]:
        """Serialize graph metadata; operator matrices are opt-in.

        CSR is the default encoding when matrices are requested. Dense export
        remains available for legacy consumers on small graphs only.
        """
        result = {
            "program_id": self.program_id,
            "stats": self.get_summary_stats(),
            "nodes": self.nodes,
            "edges": self.edges,
        }
        if not include_matrices:
            return result

        matrices = {
            "adjacency_matrix": self.A,
            "adjacency_matrix_directed": self.A_dir,
            "laplacian_matrix": self.L,
            "laplacian_normalized": self.L_norm,
        }
        if matrix_format == "csr":
            result["matrix_format"] = "csr"
            result.update({name: self._csr_payload(matrix) for name, matrix in matrices.items()})
            return result
        if matrix_format == "dense":
            if self.num_nodes > MAX_DENSE_MATRIX_NODES:
                raise GraphLimitError(
                    "Dense matrix export limit exceeded: "
                    f"{self.num_nodes} > {MAX_DENSE_MATRIX_NODES} nodes"
                )
            result["matrix_format"] = "dense"
            result.update({name: matrix.toarray().tolist() for name, matrix in matrices.items()})
            return result
        raise ValueError("matrix_format must be 'csr' or 'dense'")
