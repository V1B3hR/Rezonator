"""Sparse directed-diffusion and personalized-PageRank graph rankers."""

from typing import Any, Dict, List, Optional, Set

import numpy as np
import scipy.linalg
import scipy.sparse as sp
import scipy.sparse.linalg as spla


class DiffusionRanker:
    """Rank downstream statements using a CSR transition operator."""

    def __init__(self, graph_data: Dict[str, Any]):
        self.graph_data = graph_data
        self.nodes = graph_data.get("nodes", [])
        self.node_ids = [node["id"] for node in self.nodes]
        self.node_id_to_idx = {node_id: i for i, node_id in enumerate(self.node_ids)}
        self.N = len(self.node_ids)

        rows: List[int] = []
        cols: List[int] = []
        weights: List[float] = []
        for edge in graph_data.get("edges", []):
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

        adjacency = sp.coo_matrix(
            (np.asarray(weights, dtype=np.float64), (rows, cols)),
            shape=(self.N, self.N),
        ).tocsr()
        adjacency.sum_duplicates()
        adjacency.eliminate_zeros()
        row_sums = np.asarray(adjacency.sum(axis=1)).ravel()
        inverse = np.zeros_like(row_sums)
        non_sinks = row_sums > 1e-9
        inverse[non_sinks] = 1.0 / row_sums[non_sinks]
        transition = (sp.diags(inverse, format="csr") @ adjacency).tocsr()

        # Preserve the established absorbing-state semantics for sinks.
        sinks = np.flatnonzero(~non_sinks)
        if len(sinks):
            transition = transition + sp.csr_matrix(
                (np.ones(len(sinks)), (sinks, sinks)), shape=(self.N, self.N)
            )
        transition.sum_duplicates()
        transition.sort_indices()
        self.A_dir = adjacency
        self.P = transition
        self._cached_embedding_3d: Optional[np.ndarray] = None

    def _seed(self, seed_node_id: str):
        if seed_node_id not in self.node_id_to_idx:
            return None, None
        seed_idx = self.node_id_to_idx[seed_node_id]
        u0 = np.zeros(self.N, dtype=np.float64)
        u0[seed_idx] = 1.0
        return seed_idx, u0

    def _candidates(self, seed_node_id: str, slice_nodes: Optional[Set[str]]) -> List[str]:
        targets = slice_nodes if slice_nodes is not None else self.node_ids
        return [
            node_id for node_id in targets
            if node_id != seed_node_id and node_id in self.node_id_to_idx
        ]

    def rank_by_diffusion(
        self,
        seed_node_id: str,
        slice_nodes: Optional[Set[str]] = None,
        t: float = 1.5,
        degree_normalized: bool = False,
    ) -> List[str]:
        """
        Rank downstream statements by continuous Markov propagation ``exp((P.T-I)t) u0``.
        If degree_normalized=True, normalizes raw probability mass by node in-degree to reduce
        bias toward high in-degree structural hubs.
        """
        seed_idx, u0 = self._seed(seed_node_id)
        if seed_idx is None:
            return []
        generator = self.P.transpose().tocsr() - sp.eye(self.N, format="csr")
        scores = spla.expm_multiply(generator * t, u0)
        if degree_normalized:
            in_degrees = np.asarray(self.A_dir.sum(axis=0)).ravel()
            norm_factors = np.maximum(in_degrees, 1.0)
            adjusted_scores = scores / norm_factors
        else:
            adjusted_scores = scores
        candidates = self._candidates(seed_node_id, slice_nodes)
        candidates.sort(key=lambda node_id: (-adjusted_scores[self.node_id_to_idx[node_id]], node_id))
        return candidates

    def rank_by_ppr(
        self,
        seed_node_id: str,
        slice_nodes: Optional[Set[str]] = None,
        alpha: float = 0.85,
        *,
        tolerance: float = 1e-12,
        max_iterations: int = 10_000,
    ) -> List[str]:
        """Rank by personalized PageRank using a sparse fixed-point iteration."""
        if not 0.0 <= alpha < 1.0:
            raise ValueError("alpha must be in [0, 1)")
        seed_idx, u0 = self._seed(seed_node_id)
        if seed_idx is None:
            return []

        if self.N < 100:
            matrix = np.eye(self.N, dtype=np.float64) - alpha * self.P.transpose().toarray()
            scores = (1.0 - alpha) * scipy.linalg.solve(matrix, u0)
        else:
            scores = u0.copy()
            converged = False
            for _ in range(max_iterations):
                next_scores = (1.0 - alpha) * u0 + alpha * (self.P.transpose() @ scores)
                if np.linalg.norm(next_scores - scores, ord=1) <= tolerance:
                    scores = next_scores
                    converged = True
                    break
                scores = next_scores
            if not converged:
                raise RuntimeError("Sparse personalized PageRank did not converge within its iteration budget")

        candidates = self._candidates(seed_node_id, slice_nodes)
        candidates.sort(key=lambda node_id: (-scores[self.node_id_to_idx[node_id]], node_id))
        return candidates

    def compute_3d_spectral_embedding(self) -> np.ndarray:
        """
        Computes or retrieves cached 3D topological spectral embedding X in R^{N x 3}
        from the Fan Chung normalized Laplacian of the graph.
        Reduces downstream topological ranking to O(N) distance calculations.
        """
        if self._cached_embedding_3d is not None:
            return self._cached_embedding_3d

        if self.N == 0:
            self._cached_embedding_3d = np.zeros((0, 3), dtype=np.float64)
            return self._cached_embedding_3d
        if self.N == 1:
            self._cached_embedding_3d = np.zeros((1, 3), dtype=np.float64)
            return self._cached_embedding_3d

        # Symmetrized adjacency: A_sym = 0.5 * (A_dir + A_dir.T)
        A_sym = (0.5 * (self.A_dir + self.A_dir.transpose())).tocsr()
        A_sym.sum_duplicates()
        A_sym.eliminate_zeros()

        degrees = np.asarray(A_sym.sum(axis=1)).ravel()
        inv_sqrt = np.zeros_like(degrees)
        pos = degrees > 1e-9
        inv_sqrt[pos] = 1.0 / np.sqrt(degrees[pos])
        D_inv_sqrt = sp.diags(inv_sqrt, format="csr")

        L_norm = (sp.eye(self.N, format="csr", dtype=np.float64) - D_inv_sqrt @ A_sym @ D_inv_sqrt).tocsr()
        if np.any(~pos):
            keep = sp.diags(pos.astype(np.float64), format="csr")
            L_norm = (keep @ L_norm @ keep).tocsr()
        L_norm = (0.5 * (L_norm + L_norm.transpose())).tocsr()
        L_norm.eliminate_zeros()

        from rezonator.diamond_yant import DiamondYantSpectralEngine
        engine = DiamondYantSpectralEngine()
        emb_res = engine.compute_3d_spectral_embedding(L_norm)
        self._cached_embedding_3d = emb_res["embedding"]
        return self._cached_embedding_3d

    def rank_by_spectral_distance(
        self,
        seed_node_id: str,
        slice_nodes: Optional[Set[str]] = None,
        embedding_3d: Optional[np.ndarray] = None,
    ) -> List[str]:
        """
        Rank candidate statements by topological proximity in 3D spectral space:
            d(seed, j) = ||X_{seed, :} - X_{j, :}||_2
        Complexity: O(N) distance checks and O(k log k) sort,
        replacing iterative matrix exponential steps while preserving diffusion coupling.
        Closest nodes in spectral space are ranked highest (first).
        """
        if seed_node_id not in self.node_id_to_idx:
            return []
        seed_idx = self.node_id_to_idx[seed_node_id]
        X = embedding_3d if embedding_3d is not None else self.compute_3d_spectral_embedding()
        if len(X) == 0:
            return []
        if len(X) != self.N:
            raise ValueError(f"embedding_3d row count {len(X)} does not match ranker node count {self.N}")

        seed_coord = X[seed_idx]
        distances = np.linalg.norm(X - seed_coord, axis=1)

        candidates = self._candidates(seed_node_id, slice_nodes)
        candidates.sort(key=lambda node_id: (distances[self.node_id_to_idx[node_id]], node_id))
        return candidates
