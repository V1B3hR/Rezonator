"""
Graph Field: Tensorization, Adjacency, and Laplacian Operators.
Converts symbolic Program Graphs (CFG + DFG) into continuous mathematical operators.
Includes both statement basic blocks and shared WORKING-STORAGE memory hubs.
"""

from typing import Dict, List, Any, Tuple
import numpy as np


class GraphField:
    """
    Mathematical manifold representation of the program graph.
    Computes Adjacency, Degree, and Graph Laplacian matrices.
    Optionally embeds shared WORKING-STORAGE variables as memory hub nodes.
    """

    def __init__(self, parsed_data: Dict[str, Any], symmetrize: bool = True, include_variables: bool = True):
        self.program_id = parsed_data.get("program_id", "ANONYMOUS")
        raw_nodes = list(parsed_data.get("nodes", []))
        raw_edges = list(parsed_data.get("edges", []))
        self.variables = list(parsed_data.get("variables", []))
        self.symmetrize = symmetrize
        self.include_variables = include_variables

        self.nodes = raw_nodes
        self.edges = raw_edges

        # Embed WORKING-STORAGE variable hubs
        if self.include_variables:
            for var in self.variables:
                var_node_id = f"var_{var['name']}"
                self.nodes.append({
                    "id": var_node_id,
                    "label": f"[{var['name']}]",
                    "node_type": "var",
                    "paragraph": "WORKING-STORAGE",
                    "code": f"01 {var['name']} PIC {var.get('pic', '')}",
                    "reads": [],
                    "writes": []
                })

            # Create edges between statements and variable hubs
            for node in raw_nodes:
                nid = node["id"]
                for r_var in node.get("reads", []):
                    self.edges.append({
                        "source": f"var_{r_var}",
                        "target": nid,
                        "edge_type": "dfg_read",
                        "weight": 1.2,
                        "label": f"read({r_var})"
                    })
                for w_var in node.get("writes", []):
                    self.edges.append({
                        "source": nid,
                        "target": f"var_{w_var}",
                        "edge_type": "dfg_write",
                        "weight": 1.5,
                        "label": f"write({w_var})"
                    })

        self.num_nodes = len(self.nodes)
        self.node_id_to_idx: Dict[str, int] = {n["id"]: idx for idx, n in enumerate(self.nodes)}
        self.idx_to_node_id: Dict[int, str] = {idx: n["id"] for idx, n in enumerate(self.nodes)}

        # Build matrices
        self.A_dir: np.ndarray = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float64)
        self.A: np.ndarray = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float64)
        self.D: np.ndarray = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float64)
        self.L: np.ndarray = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float64)
        self.L_norm: np.ndarray = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float64)
        self.num_components: int = 1
        self.component_labels: List[int] = []
        self.isolated_nodes: List[str] = []

        if self.num_nodes > 0:
            self._compute_matrices()

    def _compute_matrices(self):
        from scipy.sparse.csgraph import connected_components

        # 1. Fill Directed Adjacency Matrix A_dir
        for edge in self.edges:
            src = edge["source"]
            dst = edge["target"]
            if src in self.node_id_to_idx and dst in self.node_id_to_idx:
                u = self.node_id_to_idx[src]
                v = self.node_id_to_idx[dst]
                weight = float(edge.get("weight", 1.0))
                self.A_dir[u, v] += weight

        # 2. Symmetric Adjacency Matrix A (for spectral decomposition)
        if self.symmetrize:
            self.A = 0.5 * (self.A_dir + self.A_dir.T)
        else:
            self.A = self.A_dir.copy()

        # 3. Detect Connected Components explicitly
        k, labels = connected_components(self.A > 0, directed=False)
        self.num_components = int(k)
        self.component_labels = labels.tolist()

        # 4. Degree Matrix D (unweighted degree count & weighted row sum)
        degrees = np.sum(self.A, axis=1)
        self.D = np.diag(degrees)

        # Identify isolated nodes
        iso_indices = np.where(degrees == 0)[0]
        self.isolated_nodes = [self.idx_to_node_id[i] for i in iso_indices]

        # 5. Unnormalized Laplacian: L = D - A
        self.L = self.D - self.A
        self.L = 0.5 * (self.L + self.L.T)

        # 6. Symmetric Normalized Laplacian (Fan Chung formulation):
        # L_norm = I - D^(-1/2) * A * D^(-1/2) with L_norm[i, i] = 0 if degree[i] == 0
        inv_sqrt_deg = np.zeros_like(degrees)
        pos_mask = degrees > 0
        inv_sqrt_deg[pos_mask] = 1.0 / np.sqrt(degrees[pos_mask])
        D_inv_sqrt = np.diag(inv_sqrt_deg)

        self.L_norm = np.eye(self.num_nodes) - D_inv_sqrt @ self.A @ D_inv_sqrt
        # Zero out entries corresponding to isolated nodes
        self.L_norm[~pos_mask, :] = 0.0
        self.L_norm[:, ~pos_mask] = 0.0
        self.L_norm = 0.5 * (self.L_norm + self.L_norm.T)

    def get_node_by_index(self, idx: int) -> Dict[str, Any]:
        return self.nodes[idx]

    def get_summary_stats(self) -> Dict[str, Any]:
        degrees = np.diag(self.D)
        return {
            "num_nodes": self.num_nodes,
            "num_edges": len(self.edges),
            "num_variables": len(self.variables),
            "num_components": self.num_components,
            "num_isolated_nodes": len(self.isolated_nodes),
            "isolated_nodes": self.isolated_nodes,
            "density": float(np.count_nonzero(self.A) / max(1, self.num_nodes * (self.num_nodes - 1))),
            "avg_degree": float(np.mean(degrees)) if self.num_nodes > 0 else 0.0,
            "max_degree": float(np.max(degrees)) if self.num_nodes > 0 else 0.0,
            "min_degree": float(np.min(degrees)) if self.num_nodes > 0 else 0.0,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "stats": self.get_summary_stats(),
            "nodes": self.nodes,
            "edges": self.edges,
            "adjacency_matrix": self.A.tolist(),
            "adjacency_matrix_directed": self.A_dir.tolist(),
            "laplacian_matrix": self.L.tolist(),
            "laplacian_normalized": self.L_norm.tolist()
        }
