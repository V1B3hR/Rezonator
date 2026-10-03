"""
Relativistic State-Space Geodesic Solver for Code Execution Paths.
Adapts Błyskawica's General Relativity Boyer-Lindquist Geodesic Integrator (Kerr/Schwarzschild)
to model program state-space trajectories, terminal event horizons (deadlocks/infinite loops),
and frame-dragging effects caused by global WORKING-STORAGE variable coupling.
"""

import math
from typing import Dict, List, Any, Tuple
import numpy as np


class RelativisticStateSpaceGeodesicSolver:
    """
    Solves state-space trajectories as geodesics in curved program manifolds.
    Incorporates branch curvature (mass M), variable coupling frame-dragging (spin a),
    and event horizon trap boundaries.
    """

    def __init__(self, M: float = 10.0, a: float = 2.0, c: float = 1.0, G: float = 1.0):
        self.M = M      # Program complexity mass (nodes/branch count)
        self.a = a      # Global variable coupling parameter (frame-dragging)
        self.c = c
        self.G = G

    @classmethod
    def from_program_graph(cls, num_nodes: int, num_edges: int, num_vars: int):
        """Constructs physical parameters directly from program graph topology."""
        M = max(2.0, float(num_nodes) * 0.75 + float(num_edges) * 0.25)
        # Spin/frame-dragging is proportional to shared variable coupling density
        max_spin = M * 0.95  # Avoid naked singularity
        a = min(max_spin, float(num_vars) * 0.45)
        return cls(M=M, a=a)

    def schwarzschild_radius(self) -> float:
        """Radius of the event horizon in non-rotating frame: r_s = 2 * G * M / c^2"""
        return 2.0 * self.G * self.M / (self.c ** 2)

    def kerr_horizons(self) -> Tuple[float, float]:
        """
        Outer (r_plus) and inner (r_minus) event horizons:
        r_pm = GM/c^2 +/- sqrt((GM/c^2)^2 - a^2)
        """
        rg = self.G * self.M / (self.c ** 2)
        disc = (rg ** 2) - (self.a ** 2)
        if disc < 0:
            return rg, rg  # Extremal limit
        r_plus = rg + math.sqrt(disc)
        r_minus = rg - math.sqrt(disc)
        return r_plus, r_minus

    def compute_energy_constant(self, r0: float, pr0: float, L_ang: float) -> float:
        """Solves quadratic relation for effective particle/trajectory energy E."""
        G, M, c, a = self.G, self.M, self.c, self.a
        r = max(1e-3, r0)

        A = 1.0 + (a ** 2) / (r ** 2) + (2.0 * G * M * (a ** 2)) / ((c ** 2) * (r ** 3))
        B = (4.0 * G * M * a * L_ang) / ((c ** 2) * (r ** 3))
        C_val = (
            (2.0 * G * M * (L_ang ** 2)) / ((c ** 2) * (r ** 3)) -
            (L_ang ** 2) / (r ** 2) -
            (c ** 2) +
            (2.0 * G * M) / r -
            ((a * c) ** 2) / (r ** 2) -
            (pr0 ** 2)
        )

        disc = B ** 2 - 4.0 * A * C_val
        disc = max(0.0, disc)
        E = (B + math.sqrt(disc)) / (2.0 * A)
        return float(E)

    def _derivatives(self, state: np.ndarray, E: float, L_ang: float) -> np.ndarray:
        """Calculates state derivatives w.r.t proper execution time tau."""
        r, phi, pr, t = state
        G, M, c, a = self.G, self.M, self.c, self.a

        r_s = 2.0 * G * M / (c ** 2)
        delta = r ** 2 - r_s * r + a ** 2

        r_plus, _ = self.kerr_horizons()
        if r <= r_plus + 1e-2:
            return np.zeros(4)

        dr_dtau = pr
        dphi_dtau = (1.0 / delta) * ((r_s * a / r) * E + (1.0 - r_s / r) * L_ang)

        # Radial force with GR relativistic and frame-dragging corrections
        term1 = - G * M / (r ** 2)
        term2 = - (a ** 2 * E ** 2 - L_ang ** 2 - a ** 2 * c ** 2) / (r ** 3)
        term3 = - (3.0 * G * M / (c ** 2 * r ** 4)) * ((L_ang - a * E) ** 2)
        dpr_dtau = term1 + term2 + term3

        dt_dtau = (1.0 / delta) * ((r ** 2 + a ** 2 + r_s * a ** 2 / r) * E - (r_s * a / r) * L_ang)

        return np.array([dr_dtau, dphi_dtau, dpr_dtau, dt_dtau])

    def integrate_trajectory(
        self,
        r0: float = 35.0,
        phi0: float = 0.0,
        pr0: float = -0.05,
        L_ang: float = 3.5,
        steps: int = 120,
        dtau: float = 0.1
    ) -> Dict[str, Any]:
        """
        Integrates equatorial state-space geodesic trajectory using Runge-Kutta 4th order (RK4).
        Simulates how an execution flow travels from entry (r0) through branch space (phi) toward sink.
        """
        E = self.compute_energy_constant(r0, pr0, L_ang)
        state = np.array([r0, phi0, pr0, 0.0])  # [r, phi, pr, t]

        r_plus, r_minus = self.kerr_horizons()

        r_history = []
        phi_history = []
        x_history = []
        y_history = []
        t_history = []

        fell_into_horizon = False

        for step in range(steps):
            r, phi, pr, t = state
            r_history.append(float(r))
            phi_history.append(float(phi))
            # Coordinate conversion to 2D phase-space cartesian
            x_history.append(float(r * math.cos(phi)))
            y_history.append(float(r * math.sin(phi)))
            t_history.append(float(t))

            # Horizon crossing check (terminal sink / deadlock trap)
            if r <= r_plus + 1e-2:
                fell_into_horizon = True
                break

            # RK4 numerical integration
            k1 = self._derivatives(state, E, L_ang)
            k2 = self._derivatives(state + 0.5 * dtau * k1, E, L_ang)
            k3 = self._derivatives(state + 0.5 * dtau * k2, E, L_ang)
            k4 = self._derivatives(state + dtau * k3, E, L_ang)

            state = state + (dtau / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        return {
            "mass_M": self.M,
            "spin_a": self.a,
            "event_horizon_r_plus": float(r_plus),
            "cauchy_horizon_r_minus": float(r_minus),
            "energy_constant": float(E),
            "angular_momentum": float(L_ang),
            "fell_into_horizon_trap": fell_into_horizon,
            "trajectory_steps": len(r_history),
            "r_points": r_history,
            "phi_points": phi_history,
            "x_phase": x_history,
            "y_phase": y_history,
            "time_coordinate": t_history,
            "frame_dragging_coupling_factor": float(self.a / self.M) if self.M > 0 else 0.0
        }
