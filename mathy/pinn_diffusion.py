"""
PINN Graph Diffusion Engine: Information & Taint Flow Solver.
Solves the parabolic heat diffusion PDE on the program graph:
    du/dt = -alpha * L * u  ==>  u(t) = exp(-alpha * L * t) * u_0
Models transactional propagation, variable taint, deadlock bottlenecks, and asymptotic stability.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import scipy.linalg as la
import torch
import torch.nn as nn


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
        t_max: float = 2.0
    ) -> Dict[str, Any]:
        """
        Computes analytical diffusion trajectory using matrix exponential:
        u(t) = exp(-alpha * L * t) * u_0
        """
        n = L.shape[0]
        if n == 0:
            return {"timeline": [], "trajectory": [], "bottlenecks": []}

        # Normalize initial impulse
        u0 = initial_impulse.astype(np.float64)
        if np.sum(u0) > 0:
            u0 = u0 / np.sum(u0)

        # Eigen-decomposition for fast, exact matrix exponential:
        evals, evecs = la.eigh(L)
        evals = np.clip(evals, a_min=0.0, a_max=None)

        times = np.linspace(0.0, t_max, time_steps)
        trajectory = []

        # Project u0 onto eigenvector basis: c = V^T * u0
        c = evecs.T @ u0

        for t in times:
            decay = np.exp(-self.alpha * evals * t)
            u_t = evecs @ (decay * c)
            u_t = np.clip(u_t, a_min=0.0, a_max=None)
            trajectory.append(u_t.tolist())

        final_distribution = np.array(trajectory[-1])
        cold_nodes = [int(i) for i in np.where(final_distribution < 0.01 * np.max(final_distribution))[0]]

        # Clean half-life: tau = ln(2) / (alpha * lambda_1) if connected, else inf
        fiedler_val = evals[1] if n > 1 else evals[0]
        half_life = float(np.log(2.0) / (self.alpha * fiedler_val)) if fiedler_val > 1e-4 else float("inf")

        return {
            "alpha": self.alpha,
            "times": times.tolist(),
            "trajectory": trajectory,
            "final_state": final_distribution.tolist(),
            "cold_nodes_unreached": cold_nodes,
            "diffusion_half_life": half_life,
            "spectral_radius": float(np.max(evals)) if n > 0 else 0.0
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
        Influences propagate strictly forward along dependencies: u(t) = exp((P^T - I) * t) * u0
        """
        n = A_dir.shape[0]
        if n == 0 or source_idx < 0 or source_idx >= n:
            return {"source_idx": source_idx, "impact_ranking": [], "reachable_count": 0}

        out_degrees = np.sum(A_dir, axis=1)
        P = np.zeros_like(A_dir)
        pos_mask = out_degrees > 0
        P[pos_mask, :] = A_dir[pos_mask, :] / out_degrees[pos_mask, np.newaxis]

        generator = P.T - np.eye(n)
        u0 = np.zeros(n)
        u0[source_idx] = 1.0

        u_t = la.expm(generator * t) @ u0
        u_t = np.clip(u_t, a_min=0.0, a_max=None)

        ranking_indices = np.argsort(-u_t)
        ranking = [
            {"node_idx": int(i), "impact_score": float(u_t[i])}
            for i in ranking_indices
            if u_t[i] >= threshold
        ]

        return {
            "source_idx": source_idx,
            "propagation_time": t,
            "impact_ranking": ranking,
            "reachable_count": len(ranking),
            "max_impact": float(np.max(u_t)) if n > 0 else 0.0
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

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        L_tensor = torch.tensor(L, dtype=torch.float32, device=device)
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
