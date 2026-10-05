"""
Program Comparator: Mathematical Divergence & Anomaly Radar.
Computes NetLSD spectral distance, algebraic connectivity shifts,
directed impact diffusion, and formal cycle/deadlock verification.
"""

from typing import Dict, List, Any
import numpy as np

from rezonator.cobol_parser import CobolParser
from rezonator.graph_field import GraphField
from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.pinn_diffusion import PINNGraphDiffusionEngine
from rezonator.cycle_detector import CycleDetector


class ProgramComparator:
    """
    Rigorously compares two COBOL programs via NetLSD spectral topology,
    directed impact propagation, and formal cycle/deadlock detection.
    """

    def __init__(self, lattice_size: int = 32):
        self.parser = CobolParser()
        self.yant_engine = DiamondYantSpectralEngine(lattice_size=lattice_size)
        self.diffusion_engine = PINNGraphDiffusionEngine(alpha=0.5)

    def analyze_single(self, source_code: str) -> Dict[str, Any]:
        """Runs the complete multi-modal mathematical pipeline on a COBOL program."""
        # 1. Parse into graph
        parsed = self.parser.parse(source_code)

        # 2. Graph Field (both directed A_dir and symmetric Laplacian L & L_norm)
        field = GraphField(parsed, symmetrize=True, include_variables=True)

        # 3. Modal spectrum & NetLSD signature & Chladni surface
        spectrum = self.yant_engine.compute_spectrum(field.L, L_norm=field.L_norm, num_modes=12)
        chladni = self.yant_engine.generate_chladni_surface(spectrum)

        # 4. Diffusion (symmetric equilibration + directed forward impact)
        u0 = np.zeros(field.num_nodes)
        if field.num_nodes > 0:
            u0[0] = 1.0
        diffusion = self.diffusion_engine.solve_analytical(field.L, u0, time_steps=20, t_max=2.0)
        directed_impact = self.diffusion_engine.solve_directed_impact(field.A_dir, source_idx=0, t=1.5)

        # 5. Formal Cycle, Recursion & Deadlock Verification
        cycle_analysis = CycleDetector(parsed).analyze()

        return {
            "program_id": field.program_id,
            "parsed": parsed,
            "stats": field.get_summary_stats(),
            "spectrum": spectrum,
            "chladni": chladni,
            "diffusion": diffusion,
            "directed_impact": directed_impact,
            "cycles": cycle_analysis,
            # Backwards compatibility stub for legacy clients
            "geodesic": {
                "mass_M": float(field.num_nodes * 0.75 + len(field.edges) * 0.25),
                "spin_a": float(len(field.variables) * 0.45),
                "event_horizon_r_plus": 2.0 * float(field.num_nodes * 0.75 + len(field.edges) * 0.25),
                "fell_into_horizon_trap": cycle_analysis["has_deadlock"],
                "frame_dragging_coupling_factor": float(len(field.variables) * 0.45)
            }
        }

    def compare(self, source_a: str, source_b: str) -> Dict[str, Any]:
        """Performs rigorous comparative analysis between Program A and Program B."""
        res_a = self.analyze_single(source_a)
        res_b = self.analyze_single(source_b)

        # 1. NetLSD Topological Distance (Size-invariant heat trace L2 distance)
        netlsd_dist = self.yant_engine.compute_spectral_distance(res_a["spectrum"], res_b["spectrum"])

        # 2. Algebraic Connectivity Shift (Fiedler value delta)
        fiedler_a = res_a["spectrum"]["fiedler_value"]
        fiedler_b = res_b["spectrum"]["fiedler_value"]
        fiedler_delta = float(fiedler_b - fiedler_a)

        fiedler_norm_a = res_a["spectrum"].get("fiedler_norm", 0.0)
        fiedler_norm_b = res_b["spectrum"].get("fiedler_norm", 0.0)
        fiedler_norm_delta = float(fiedler_norm_b - fiedler_norm_a)

        # 3. Chladni Surface Cosine Similarity (Modal cymatic overlap)
        w_a = np.array(res_a["chladni"]["chladni_matrix"]).flatten()
        w_b = np.array(res_b["chladni"]["chladni_matrix"]).flatten()
        norm_a = np.linalg.norm(w_a)
        norm_b = np.linalg.norm(w_b)
        cymatic_similarity = float(np.dot(w_a, w_b) / (norm_a * norm_b)) if (norm_a > 1e-8 and norm_b > 1e-8) else 0.0

        # 4. Diffusion Half-Life Shift
        hl_a = res_a["diffusion"]["diffusion_half_life"]
        hl_b = res_b["diffusion"]["diffusion_half_life"]
        hl_delta = float(hl_b - hl_a) if (not np.isinf(hl_a) and not np.isinf(hl_b)) else 0.0

        # 5. Cycle & Deadlock Regression Check
        deadlock_a = res_a["cycles"]["has_deadlock"]
        deadlock_b = res_b["cycles"]["has_deadlock"]

        # 6. Refactoring Fidelity Score (0 - 100)
        # Based on NetLSD distance and penalty for introducing deadlocks
        base_fidelity = max(0.0, min(100.0, 100.0 * (1.0 - netlsd_dist * 2.5)))
        if deadlock_b and not deadlock_a:
            refactoring_score = 0.0  # Critical defect introduced
        elif deadlock_b:
            refactoring_score = min(20.0, base_fidelity * 0.2)
        else:
            refactoring_score = base_fidelity

        complexity_ratio = res_b["stats"]["num_nodes"] / max(1, res_a["stats"]["num_nodes"])

        # Qualitative scientific verdict
        if netlsd_dist < 0.001:
            verdict = "IDENTICAL_TOPOLOGY: Structural isomorphism preserved under renaming."
        elif deadlock_b and not deadlock_a:
            verdict = "CRITICAL_REGRESSION: Program B introduces an infinite loop or recursive deadlock cycle!"
        elif not deadlock_b and deadlock_a:
            verdict = "DEFECT_RESOLVED: Program B successfully eliminates recursion deadlock present in Program A."
        elif netlsd_dist < 0.08:
            verdict = "SAFE_MODULAR_EXTENSION: High topological fidelity maintained with conservative logic extension."
        elif fiedler_delta < -0.04:
            verdict = "MODULAR_DECOUPLING: Program branched into more cleanly partitioned subroutines."
        else:
            verdict = "STRUCTURAL_REORGANIZATION: Substantial topological shift in control and data dependencies."

        return {
            "program_a": res_a["program_id"],
            "program_b": res_b["program_id"],
            "metrics": {
                "spectral_distance_L2": netlsd_dist,
                "spectral_distance_netlsd": netlsd_dist,
                "fiedler_delta": fiedler_delta,
                "fiedler_norm_delta": fiedler_norm_delta,
                "cymatic_cross_similarity": cymatic_similarity,
                "diffusion_half_life_delta": hl_delta,
                "frame_dragging_shift": 0.0,
                "node_growth_ratio": float(complexity_ratio),
                "refactoring_health_score": float(refactoring_score),
                "deadlock_introduced": bool(deadlock_b and not deadlock_a),
                "deadlock_fixed": bool(not deadlock_b and deadlock_a)
            },
            "verdict": verdict,
            "program_a_details": res_a,
            "program_b_details": res_b
        }
