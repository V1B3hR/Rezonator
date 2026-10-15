"""
PINN Graph Diffusion Engine: Information & Taint Flow Solver.
Solves the parabolic heat diffusion PDE on the program graph:
    du/dt = -alpha * L * u  ==>  u(t) = exp(-alpha * L * t) * u_0
Models transactional propagation, variable taint, deadlock bottlenecks, and asymptotic stability.
"""

from collections import deque
from typing import Dict, List, Any, Optional
import numpy as np
import scipy.linalg as la
import torch
import torch.nn as nn
from rezonator.analysis_config import (
    DIFFUSION_COLD_NODE_THRESHOLD,
    DIFFUSION_HALF_LIFE_EIGENVALUE_THRESHOLD,
    SPARSE_CUTOFF,
)


def _to_dense(matrix: Any) -> np.ndarray:
    arr: np.ndarray = np.asarray(matrix.toarray() if hasattr(matrix, "toarray") else matrix)
    return arr


class PINNGraphDiffusionEngine:
    """
    Simulates temporal diffusion of data flow and transactional impulses
    across the program graph using both analytical matrix exponentials and PyTorch PINN.
    """

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha

    def solve_analytical(
        self,
        L: np.ndarray,
        initial_impulse: np.ndarray,
        time_steps: int = 20,
        t_max: float = 2.0,
        *,
        fiedler_value: Optional[float] = None,
        estimate_spectral_radius: bool = False,
    ) -> Dict[str, Any]:
        """
        Computes analytical diffusion trajectory using matrix exponential:
        u(t) = exp(-alpha * L * t) * u_0
        on the symmetrized Laplacian L (undirected structural dispersion).

        Note: Continuous graph heat diffusion on symmetric L is undirected: heat spreads
        symmetrically across edges regardless of CFG arrow directions. For directed forward
        reachability along control/data flow dependencies, see `solve_directed_impact`.

        Relaxation half-life tau_1/2 = ln(2) / (alpha * lambda_min_positive) measures the decay
        rate of the slowest decaying non-trivial Laplacian eigenmode toward component-wise
        harmonic steady state (total mass sum(u) is conserved).
        """
        n = L.shape[0]
        if n == 0:
            return {"timeline": [], "trajectory": [], "bottlenecks": [], "diffusion_half_life": float("inf")}

        # Normalize initial impulse
        u0 = initial_impulse.astype(np.float64)
        if np.sum(u0) > 0:
            u0 = u0 / np.sum(u0)

        import scipy.sparse as sp
        import scipy.sparse.linalg as spla

        times = np.linspace(0.0, t_max, time_steps)
        if n >= SPARSE_CUTOFF:
            L_sp = sp.csr_matrix(L, dtype=np.float64)
            # Efficient Krylov subspace matrix exponential trajectory
            traj_arr = spla.expm_multiply(-self.alpha * L_sp, u0, start=0.0, stop=t_max, num=time_steps)
            trajectory = [np.clip(traj_arr[s], a_min=0.0, a_max=None).tolist() for s in range(time_steps)]
            final_distribution = np.array(trajectory[-1])
            cold_nodes = [
                int(i) for i in np.where(
                    final_distribution < DIFFUSION_COLD_NODE_THRESHOLD * np.max(final_distribution)
                )[0]
            ]
            if fiedler_value is not None and fiedler_value > DIFFUSION_HALF_LIFE_EIGENVALUE_THRESHOLD:
                slowest_mode_lambda = float(fiedler_value)
                half_life = float(np.log(2.0) / (self.alpha * slowest_mode_lambda))
            elif n > 1:
                # Solve for smallest eigenvalues with shift-invert to find the smallest non-zero eigenvalue
                k_evals = min(max(6, 2), n - 1)
                try:
                    evals_sm, _ = spla.eigsh(L_sp, k=k_evals, sigma=-1e-4, which='LM')
                    evals_sm = np.sort(np.clip(evals_sm, 0.0, None))
                    pos_evals = evals_sm[evals_sm > DIFFUSION_HALF_LIFE_EIGENVALUE_THRESHOLD]
                    if len(pos_evals) > 0:
                        slowest_mode_lambda = float(pos_evals[0])
                        half_life = float(np.log(2.0) / (self.alpha * slowest_mode_lambda))
                    else:
                        slowest_mode_lambda = 0.0
                        half_life = float("inf")
                except Exception:
                    slowest_mode_lambda = 0.0
                    half_life = float("inf")
            else:
                slowest_mode_lambda = 0.0
                half_life = float("inf")

            if estimate_spectral_radius and n > 1:
                try:
                    spectral_rad = float(abs(spla.eigsh(L_sp, k=1, which="LM", return_eigenvectors=False)[0]))
                except Exception:
                    # This auxiliary metric is not needed for the trajectory; do
                    # not substitute a misleading zero if ARPACK cannot estimate it.
                    spectral_rad = None
            else:
                # A largest-eigenvalue solve can dominate sparse end-to-end
                # latency; expose the omission instead of silently guessing.
                spectral_rad = None
            spectral_radius_status = "computed" if spectral_rad is not None else "not_computed_sparse"
        else:
            # Eigen-decomposition for fast, exact matrix exponential:
            evals, evecs = la.eigh(_to_dense(L))
            evals = np.clip(evals, a_min=0.0, a_max=None)

            trajectory = []
            # Project u0 onto eigenvector basis: c = V^T * u0
            c = evecs.T @ u0

            for t in times:
                decay = np.exp(-self.alpha * evals * t)
                u_t = evecs @ (decay * c)
                u_t = np.clip(u_t, a_min=0.0, a_max=None)
                trajectory.append(u_t.tolist())

            final_distribution = np.array(trajectory[-1])
            cold_nodes = [
                int(i) for i in np.where(
                    final_distribution < DIFFUSION_COLD_NODE_THRESHOLD * np.max(final_distribution)
                )[0]
            ]

            # Relaxation half-life of the slowest decaying non-trivial mode:
            # tau = ln(2) / (alpha * lambda_min_positive).
            # For a connected graph, lambda_min_positive = lambda_1 (the Fiedler value).
            # For a graph with k components, lambda_0 = ... = lambda_{k-1} = 0, so we select
            # the smallest strictly positive eigenvalue above numerical zero tolerance.
            pos_evals = evals[evals > DIFFUSION_HALF_LIFE_EIGENVALUE_THRESHOLD]
            if len(pos_evals) > 0:
                slowest_mode_lambda = float(pos_evals[0])
                half_life = float(np.log(2.0) / (self.alpha * slowest_mode_lambda))
            else:
                slowest_mode_lambda = 0.0
                half_life = float("inf")
            spectral_rad = float(np.max(evals)) if n > 0 else 0.0
            spectral_radius_status = "computed"

        return {
            "alpha": self.alpha,
            "times": times.tolist(),
            "trajectory": trajectory,
            "final_state": final_distribution.tolist(),
            "cold_nodes_unreached": cold_nodes,
            "diffusion_half_life": half_life,
            "spectral_radius": spectral_rad,
            "spectral_radius_status": spectral_radius_status,
        }

    def solve_directed_impact(
        self,
        A_dir: np.ndarray,
        source_idx: int,
        t: float = 1.5,
        threshold: float = 1e-4
    ) -> Dict[str, Any]:
        """
        Computes forward directed impact propagation (blast radius) along CFG and DFG edges.
        Influences propagate strictly forward along dependencies: u(t) = exp((P^T - I) * t) * u0.

        Note on reachability: For any t > 0, every topologically reachable node in the continuous
        Markov chain has strictly positive probability mass. Ranking is thresholded by `threshold`
        to filter out negligible numerical tail concentrations; exact topological reachability is
        also reported separately via `exact_reachable_count`.
        """
        n = A_dir.shape[0]
        if n == 0 or source_idx < 0 or source_idx >= n:
            return {
                "source_idx": source_idx,
                "propagation_time": t,
                "threshold": threshold,
                "impact_ranking": [],
                "reachable_count": 0,
                "threshold_filtered_count": 0,
                "exact_reachable_count": 0,
                "max_impact": 0.0,
            }

        import scipy.sparse as sp
        import scipy.sparse.linalg as spla

        u0 = np.zeros(n, dtype=np.float64)
        u0[source_idx] = 1.0

        if n >= SPARSE_CUTOFF or sp.issparse(A_dir):
            A_sp = sp.csr_matrix(A_dir, dtype=np.float64)
            out_degrees = np.array(A_sp.sum(axis=1)).flatten()
            pos_mask = out_degrees > 0
            inv_deg = np.zeros_like(out_degrees)
            inv_deg[pos_mask] = 1.0 / out_degrees[pos_mask]
            D_inv = sp.diags(inv_deg, format='csr')
            P_sp = D_inv @ A_sp
            # Absorbing state semantics: sink nodes retain mass via self-loops
            sinks = np.flatnonzero(~pos_mask)
            if len(sinks):
                P_sp = P_sp + sp.csr_matrix(
                    (np.ones(len(sinks), dtype=np.float64), (sinks, sinks)), shape=(n, n)
                )
            Q_sp = P_sp.T - sp.eye(n, format='csr')
            u_t = spla.expm_multiply(Q_sp * t, u0)
        else:
            A_dense = _to_dense(A_dir)
            out_degrees = np.sum(A_dense, axis=1)
            P = np.zeros_like(A_dense)
            pos_mask = out_degrees > 0
            P[pos_mask, :] = A_dense[pos_mask, :] / out_degrees[pos_mask, np.newaxis]
            # Absorbing state semantics: sink nodes retain mass via self-loops
            sinks = np.flatnonzero(~pos_mask)
            if len(sinks):
                P[sinks, sinks] = 1.0

            generator = P.T - np.eye(n)
            u_t = la.expm(generator * t) @ u0

        u_t = np.clip(u_t, a_min=0.0, a_max=None)

        ranking_indices = np.argsort(-u_t)
        ranking = [
            {"node_idx": int(i), "impact_score": float(u_t[i])}
            for i in ranking_indices
            if u_t[i] >= threshold
        ]

        # Exact topological reachability via graph traversal (independent of threshold & time t)
        visited = set()
        queue = deque([source_idx])
        visited.add(source_idx)
        if sp.issparse(A_dir):
            A_csr = sp.csr_matrix(A_dir)
            while queue:
                curr = queue.popleft()
                neighbors = A_csr.indices[A_csr.indptr[curr]:A_csr.indptr[curr+1]]
                for nbr in neighbors:
                    nbr_int = int(nbr)
                    if nbr_int not in visited:
                        visited.add(nbr_int)
                        queue.append(nbr_int)
        else:
            A_dense_adj = _to_dense(A_dir)
            while queue:
                curr = queue.popleft()
                neighbors = np.where(A_dense_adj[curr] > 0)[0]
                for nbr in neighbors:
                    nbr_int = int(nbr)
                    if nbr_int not in visited:
                        visited.add(nbr_int)
                        queue.append(nbr_int)

        return {
            "source_idx": source_idx,
            "propagation_time": t,
            "threshold": threshold,
            "impact_ranking": ranking,
            "reachable_count": len(ranking),
            "threshold_filtered_count": len(ranking),
            "exact_reachable_count": len(visited),
            "max_impact": float(np.max(u_t)) if n > 0 else 0.0,
        }

    def train_pinn_residual(
        self,
        L: np.ndarray,
        u0: np.ndarray,
        epochs: int = 150,
        lr: float = 0.01
    ) -> Dict[str, Any]:
        """
        Physics-Informed Neural Network (PINN) training loop.
        Learns continuous temporal trajectory u_theta(t) minimizing:
        Loss = Loss_initial + Loss_physics(du/dt + alpha * L * u)
        """
        n = L.shape[0]
        if n == 0:
            return {"final_loss": 0.0, "status": "empty"}
        from rezonator.limits import MAX_PINN_NODES, GraphLimitError
        if n > MAX_PINN_NODES:
            raise GraphLimitError(
                f"PINN training node limit exceeded: {n} > {MAX_PINN_NODES}; "
                "use the sparse analytical solver for larger graphs"
            )

        import scipy.sparse as sp
        if sp.issparse(L):
            coo = sp.coo_matrix(L)
            indices = torch.as_tensor(
                np.vstack((coo.row, coo.col)), dtype=torch.int64
            )
            values = torch.as_tensor(coo.data, dtype=torch.float32)
            L_tensor = torch.sparse_coo_tensor(indices, values, size=coo.shape).coalesce()
        else:
            L_tensor = torch.as_tensor(L, dtype=torch.float32)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        L_tensor = L_tensor.to(device)
        u0_tensor = torch.tensor(u0, dtype=torch.float32, device=device).unsqueeze(0)

        # Small MLP: t (1D) -> u(t) (n-D)
        model = nn.Sequential(
            nn.Linear(1, 32),
            nn.Tanh(),
            nn.Linear(32, 32),
            nn.Tanh(),
            nn.Linear(32, n)
        ).to(device)

        optimizer = torch.optim.Adam(model.parameters(), lr=lr)

        losses = []
        for epoch in range(epochs):
            optimizer.zero_grad()

            # 1. Initial condition loss at t=0
            t_zero = torch.zeros(1, 1, device=device)
            u_pred_0 = model(t_zero)
            loss_init = torch.mean((u_pred_0 - u0_tensor) ** 2)

            # 2. Collocation points in time t in [0, 2]
            t_colloc = torch.rand(20, 1, device=device, requires_grad=True) * 2.0
            u_colloc = model(t_colloc)

            # Compute time derivative du/dt using autograd
            du_dt_list = []
            for dim in range(n):
                u_dim = u_colloc[:, dim:dim+1]
                grad_u = torch.autograd.grad(
                    u_dim, t_colloc,
                    grad_outputs=torch.ones_like(u_dim),
                    create_graph=True,
                    retain_graph=True
                )[0]
                du_dt_list.append(grad_u)

            du_dt = torch.cat(du_dt_list, dim=1)

            # Physical residual: f = du/dt + alpha * L * u
            if L_tensor.layout == torch.sparse_coo:
                Lu = torch.sparse.mm(L_tensor, u_colloc.T).T
            else:
                Lu = (L_tensor @ u_colloc.T).T
            f_res = du_dt + self.alpha * Lu
            loss_phys = torch.mean(f_res ** 2)

            total_loss = loss_init + 0.5 * loss_phys
            total_loss.backward()
            optimizer.step()
            losses.append(float(total_loss.item()))

        return {
            "initial_loss": losses[0] if losses else 0.0,
            "final_loss": losses[-1] if losses else 0.0,
            "loss_reduction_pct": float((1.0 - losses[-1] / max(1e-8, losses[0])) * 100.0) if losses else 0.0,
            "device": str(device)
        }
