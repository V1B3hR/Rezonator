"""
Directed Diffusion & Personalized PageRank Rankers for COBOL Program Graphs.
Ranks downstream statements by continuous physical impact and blast radius.
"""

from typing import Dict, List, Set, Any, Tuple, Optional
import numpy as np
import scipy.linalg


class DiffusionRanker:
    """
    Ranks statements according to continuous directed impact diffusion u(t) = exp((P^T - I)t) u_0.
    """

    def __init__(self, graph_data: Dict[str, Any]):
        self.graph_data = graph_data
        self.nodes = graph_data.get("nodes", [])
        self.node_ids = [n["id"] for n in self.nodes]
        self.node_id_to_idx = {nid: i for i, nid in enumerate(self.node_ids)}
        self.N = len(self.node_ids)

        # Build directed adjacency matrix A_dir
        self.A_dir = np.zeros((self.N, self.N), dtype=np.float64)
        for edge in graph_data.get("edges", []):
            src = edge["source"]
            dst = edge["target"]
            if src in self.node_id_to_idx and dst in self.node_id_to_idx:
                u = self.node_id_to_idx[src]
                v = self.node_id_to_idx[dst]
                w = float(edge.get("weight", 1.0))
                self.A_dir[u, v] += w

        # Row-stochastic transition probability matrix P
        self.P = np.zeros((self.N, self.N), dtype=np.float64)
        row_sums = np.sum(self.A_dir, axis=1)
        for i in range(self.N):
            if row_sums[i] > 1e-9:
                self.P[i, :] = self.A_dir[i, :] / row_sums[i]
            else:
                self.P[i, i] = 1.0  # absorbing state for terminal sinks

    def rank_by_diffusion(self, seed_node_id: str, slice_nodes: Optional[Set[str]] = None, t: float = 1.5) -> List[str]:
        """
        Ranks downstream nodes by continuous forward diffusion impact u(t) = exp((P^T - I)t) u_0.
        """
        if seed_node_id not in self.node_id_to_idx:
            return []

        seed_idx = self.node_id_to_idx[seed_node_id]
        u0 = np.zeros(self.N, dtype=np.float64)
        u0[seed_idx] = 1.0

        # Continuous-time Markov generator: Q = P^T - I
        if self.N >= 100:
            import scipy.sparse as sp
            import scipy.sparse.linalg as spla
            P_sp = sp.csr_matrix(self.P)
            Q_sp = P_sp.T - sp.eye(self.N, format='csr')
            u_t = spla.expm_multiply(Q_sp * t, u0)
        else:
            Q = self.P.T - np.eye(self.N, dtype=np.float64)
            u_t = scipy.linalg.expm(Q * t) @ u0

        target_nodes = slice_nodes if slice_nodes is not None else set(self.node_ids)
        candidates = [nid for nid in target_nodes if nid != seed_node_id and nid in self.node_id_to_idx]

        # Sort descending by impact score u_t[idx], then by id for determinism
        candidates.sort(key=lambda nid: (-u_t[self.node_id_to_idx[nid]], nid))
        return candidates

    def rank_by_ppr(self, seed_node_id: str, slice_nodes: Optional[Set[str]] = None, alpha: float = 0.85) -> List[str]:
        """
        Alternative continuous random walk: Personalized PageRank with restart probability (1 - alpha).
        pi = (1 - alpha) * (I - alpha * P^T)^(-1) * u0
        """
        if seed_node_id not in self.node_id_to_idx:
            return []

        seed_idx = self.node_id_to_idx[seed_node_id]
        u0 = np.zeros(self.N, dtype=np.float64)
        u0[seed_idx] = 1.0

        if self.N >= 100:
            import scipy.sparse as sp
            import scipy.sparse.linalg as spla
            P_sp = sp.csr_matrix(self.P)
            M_sp = sp.eye(self.N, format='csr') - alpha * P_sp.T
            try:
                pi = (1.0 - alpha) * spla.spsolve(M_sp, u0)
            except Exception:
                pi = u0
        else:
            M = np.eye(self.N, dtype=np.float64) - alpha * self.P.T
            try:
                pi = (1.0 - alpha) * scipy.linalg.solve(M, u0)
            except Exception:
                pi = u0

        target_nodes = slice_nodes if slice_nodes is not None else set(self.node_ids)
        candidates = [nid for nid in target_nodes if nid != seed_node_id and nid in self.node_id_to_idx]

        candidates.sort(key=lambda nid: (-pi[self.node_id_to_idx[nid]], nid))
        return candidates
