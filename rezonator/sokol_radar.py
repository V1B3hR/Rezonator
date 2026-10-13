"""
Sokół Spectral Change Radar (sokol.radar.v1).

Compares like-for-like analysis snapshots, enforces parser/configuration
compatibility, computes spectral and topological metric deltas, and nominates
structured review candidates for human engineering inspection.

Epistemic rule:
The spectral radar reports METRIC DELTAS, never semantic diagnoses.
A Fiedler-value drop or NetLSD shift is a structural metric change in a specific
parsed graph model; it must NEVER be labeled as a business-logic failure.
"""

from typing import Any, Dict, List, Optional
import hashlib
import json
import numpy as np

from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.project_memory import NodeAnchor, build_fact_anchor


# Sensitivity thresholds for nominating review candidates
RADAR_FIEDLER_DELTA_THRESHOLD = 0.04
RADAR_NETLSD_DISTANCE_THRESHOLD = 0.05
RADAR_COVERAGE_DRIFT_THRESHOLD = 0.05


class SokolRadar:
    """
    Spectral change radar for comparing versioned Rezonator analysis snapshots.
    Produces metric deltas and review candidates without subjective verdicts.
    """

    def __init__(
        self,
        fiedler_threshold: float = RADAR_FIEDLER_DELTA_THRESHOLD,
        netlsd_threshold: float = RADAR_NETLSD_DISTANCE_THRESHOLD,
        coverage_drift_threshold: float = RADAR_COVERAGE_DRIFT_THRESHOLD,
    ):
        self.fiedler_threshold = float(fiedler_threshold)
        self.netlsd_threshold = float(netlsd_threshold)
        self.coverage_drift_threshold = float(coverage_drift_threshold)
        self.yant_engine = DiamondYantSpectralEngine()

    def check_compatibility(
        self,
        analysis_a: Dict[str, Any],
        analysis_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validates whether two analysis snapshots are compatible for comparison.
        Prevents misleading alerts caused by differing parser engines, options,
        or major coverage drop-offs.
        """
        reasons: List[str] = []
        is_compatible = True

        # 1. Compare parser engines
        prov_a = analysis_a.get("provenance", {})
        prov_b = analysis_b.get("provenance", {})
        engine_a = prov_a.get("parser_options", {}).get("selected_engine") or prov_a.get("analysis_options", {}).get("parser", {}).get("selected_engine")
        engine_b = prov_b.get("parser_options", {}).get("selected_engine") or prov_b.get("analysis_options", {}).get("parser", {}).get("selected_engine")
        if engine_a and engine_b and engine_a != engine_b:
            is_compatible = False
            reasons.append(f"Mismatched parser engines: '{engine_a}' vs '{engine_b}'")

        # 2. Compare coverage ratios
        cov_a = analysis_a.get("stats", {}).get("parser_coverage_ratio", 1.0)
        cov_b = analysis_b.get("stats", {}).get("parser_coverage_ratio", 1.0)
        cov_delta = abs(float(cov_b) - float(cov_a))
        if cov_delta > self.coverage_drift_threshold:
            reasons.append(
                f"Significant parser coverage disparity (|{cov_b:.2f} - {cov_a:.2f}| = {cov_delta:.2f} > {self.coverage_drift_threshold})"
            )

        # 3. Check lattice size / modal configurations
        modes_a = analysis_a.get("spectrum", {}).get("total_modes")
        modes_b = analysis_b.get("spectrum", {}).get("total_modes")

        status = "COMPATIBLE"
        if not is_compatible:
            status = "INCOMPATIBLE_ANALYSIS_SNAPSHOTS"
        elif reasons:
            status = "COMPATIBILITY_WARNING"

        return {
            "compatible": is_compatible,
            "status": status,
            "reasons": reasons,
            "coverage_baseline": float(cov_a),
            "coverage_candidate": float(cov_b),
        }

    def compute_metric_deltas(
        self,
        analysis_a: Dict[str, Any],
        analysis_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculates exact scalar and spectral deltas between two analysis snapshots."""
        spec_a = analysis_a.get("spectrum", {})
        spec_b = analysis_b.get("spectrum", {})

        # NetLSD Topological Distance
        netlsd_dist = self.yant_engine.compute_spectral_distance(spec_a, spec_b)

        # Hutchinson stochastic noise floor (max standard error across probes)
        stderr_a = max(spec_a.get("netlsd_stderr", [0.0]) or [0.0])
        stderr_b = max(spec_b.get("netlsd_stderr", [0.0]) or [0.0])
        stochastic_noise_floor = max(float(stderr_a), float(stderr_b))

        # Fiedler algebraic connectivity shift
        fiedler_a = float(spec_a.get("fiedler_value", 0.0))
        fiedler_b = float(spec_b.get("fiedler_value", 0.0))
        fiedler_delta = fiedler_b - fiedler_a

        # Normalized Fiedler shift
        fiedler_norm_a = float(spec_a.get("fiedler_norm", 0.0))
        fiedler_norm_b = float(spec_b.get("fiedler_norm", 0.0))
        fiedler_norm_delta = fiedler_norm_b - fiedler_norm_a

        # Cycle and deadlock heuristics
        cycles_a = analysis_a.get("cycles", {})
        cycles_b = analysis_b.get("cycles", {})
        cycle_count_a = int(cycles_a.get("cycle_count", 0))
        cycle_count_b = int(cycles_b.get("cycle_count", 0))
        cycle_delta = cycle_count_b - cycle_count_a
        deadlock_a = bool(cycles_a.get("has_deadlock", False))
        deadlock_b = bool(cycles_b.get("has_deadlock", False))
        reaches_term_a = bool(cycles_a.get("reaches_terminal", True))
        reaches_term_b = bool(cycles_b.get("reaches_terminal", True))

        # Node and graph statistics
        stats_a = analysis_a.get("stats", {})
        stats_b = analysis_b.get("stats", {})
        node_delta = int(stats_b.get("num_nodes", 0)) - int(stats_a.get("num_nodes", 0))
        edge_delta = int(stats_b.get("num_edges", 0)) - int(stats_a.get("num_edges", 0))

        # Diffusion half-life delta
        diff_a = analysis_a.get("diffusion", {})
        diff_b = analysis_b.get("diffusion", {})
        hl_a = diff_a.get("diffusion_half_life")
        hl_b = diff_b.get("diffusion_half_life")
        if hl_a is not None and hl_b is not None and np.isfinite(hl_a) and np.isfinite(hl_b):
            half_life_delta = float(hl_b - hl_a)
        else:
            half_life_delta = None

        return {
            "netlsd_distance": float(netlsd_dist),
            "stochastic_noise_floor": float(stochastic_noise_floor),
            "is_above_noise_floor": bool(netlsd_dist > (2.0 * stochastic_noise_floor)),
            "fiedler_baseline": fiedler_a,
            "fiedler_candidate": fiedler_b,
            "fiedler_delta": float(fiedler_delta),
            "fiedler_norm_delta": float(fiedler_norm_delta),
            "cycle_count_delta": cycle_delta,
            "deadlock_flag_baseline": deadlock_a,
            "deadlock_flag_candidate": deadlock_b,
            "reaches_terminal_baseline": reaches_term_a,
            "reaches_terminal_candidate": reaches_term_b,
            "node_count_delta": node_delta,
            "edge_count_delta": edge_delta,
            "diffusion_half_life_delta": half_life_delta,
        }

    def generate_review_candidates(
        self,
        analysis_a: Dict[str, Any],
        analysis_b: Dict[str, Any],
        deltas: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Nominates structured review candidates based on metric shifts.
        Strictly frames observations as targets for human code review.
        """
        candidates: List[Dict[str, Any]] = []

        # 1. Algebraic Connectivity (Fiedler value) shift
        f_delta = deltas["fiedler_delta"]
        if abs(f_delta) >= self.fiedler_threshold:
            direction = "drop" if f_delta < 0 else "increase"
            priority = "HIGH" if abs(f_delta) >= 0.10 else "MEDIUM"
            candidates.append({
                "candidate_id": f"radar:fiedler:{abs(f_delta):.4f}",
                "category": "SPECTRAL_CONNECTIVITY_SHIFT",
                "metric_name": "fiedler_value",
                "baseline_value": deltas["fiedler_baseline"],
                "candidate_value": deltas["fiedler_candidate"],
                "delta": f_delta,
                "review_priority": priority,
                "rational_basis": (
                    f"A structural {direction} of {abs(f_delta):.4f} in algebraic connectivity "
                    f"(lambda_1) was observed. In graph spectral theory, this indicates "
                    f"{'weakened coupling / modular separation' if f_delta < 0 else 'denser inter-block coupling'}. "
                    "This is an objective metric change in the modeled graph, NOT a business-logic failure."
                ),
                "review_guidance": (
                    "Inspect whether paragraph modularization or unreferenced variable declarations "
                    "altered graph connectivity between subroutines."
                ),
            })

        # 2. NetLSD Topological Distance shift
        netlsd_dist = deltas["netlsd_distance"]
        if netlsd_dist >= self.netlsd_threshold and deltas["is_above_noise_floor"]:
            candidates.append({
                "candidate_id": f"radar:netlsd:{netlsd_dist:.4f}",
                "category": "TOPOLOGY_DISTANCE_ALERT",
                "metric_name": "netlsd_distance",
                "baseline_value": 0.0,
                "candidate_value": netlsd_dist,
                "delta": netlsd_dist,
                "review_priority": "MEDIUM" if netlsd_dist < 0.15 else "HIGH",
                "rational_basis": (
                    f"Multi-scale heat trace topological distance is {netlsd_dist:.4f}, "
                    f"exceeding the estimator noise floor ({deltas['stochastic_noise_floor']:.6f}). "
                    "Indicates non-trivial topological restructuring across control or data paths."
                ),
                "review_guidance": "Review statement additions/deletions and cross-procedural flow changes.",
            })

        # 3. Control-flow cycle or deadlock flag changes
        if deltas["deadlock_flag_candidate"] != deltas["deadlock_flag_baseline"]:
            introduced = deltas["deadlock_flag_candidate"]
            candidates.append({
                "candidate_id": "radar:deadlock:state_change",
                "category": "CYCLE_TOPOLOGY_CHANGE",
                "metric_name": "has_deadlock",
                "baseline_value": deltas["deadlock_flag_baseline"],
                "candidate_value": deltas["deadlock_flag_candidate"],
                "delta": None,
                "review_priority": "CRITICAL" if introduced else "MEDIUM",
                "rational_basis": (
                    "Heuristic deadlock/trapped-cycle flag changed state: "
                    f"{'introduced in candidate' if introduced else 'resolved in candidate'}. "
                    "Note: static cycle detection does not prove runtime nontermination or termination."
                ),
                "review_guidance": (
                    "Inspect the enumerated cycles in CycleDetector output to verify whether "
                    "loop guards are modified during execution."
                ),
            })
        elif deltas["cycle_count_delta"] != 0:
            candidates.append({
                "candidate_id": f"radar:cycles:{deltas['cycle_count_delta']:+d}",
                "category": "CYCLE_TOPOLOGY_CHANGE",
                "metric_name": "cycle_count",
                "baseline_value": deltas["cycle_count_delta"],
                "candidate_value": None,
                "delta": deltas["cycle_count_delta"],
                "review_priority": "MEDIUM",
                "rational_basis": f"Cycle count shifted by {deltas['cycle_count_delta']:+d} in parsed control flow graph.",
                "review_guidance": "Inspect whether new iterative PERFORM constructs or branch loops were added.",
            })

        return candidates

    def evaluate(
        self,
        analysis_a: Dict[str, Any],
        analysis_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Runs full radar evaluation between baseline (A) and candidate (B) snapshots.
        Returns a complete `sokol.radar.v1` structured report.
        """
        compatibility = self.check_compatibility(analysis_a, analysis_b)
        deltas = self.compute_metric_deltas(analysis_a, analysis_b)
        candidates = self.generate_review_candidates(analysis_a, analysis_b, deltas)

        # Baseline & candidate IDs
        id_a = analysis_a.get("provenance", {}).get("source_snapshot_id") or analysis_a.get("program_id", "baseline")
        id_b = analysis_b.get("provenance", {}).get("source_snapshot_id") or analysis_b.get("program_id", "candidate")

        if not compatibility["compatible"]:
            verdict = "INCOMPATIBLE_ANALYSIS_SNAPSHOTS"
        elif len(candidates) == 0:
            verdict = "METRIC_STABLE: No structural review candidates identified"
        elif any(c["review_priority"] == "CRITICAL" for c in candidates):
            verdict = "CRITICAL_REVIEW_RECOMMENDED: Control-flow cycle or hazard change observed"
        else:
            verdict = "REVIEW_RECOMMENDED: Structural metric deltas exceed sensitivity threshold"

        return {
            "schema_version": "sokol.radar.v1",
            "baseline_snapshot": id_a,
            "candidate_snapshot": id_b,
            "radar_verdict": verdict,
            "compatibility": compatibility,
            "metric_deltas": deltas,
            "review_candidates": candidates,
            "candidate_count": len(candidates),
        }


def build_radar_report(
    analysis_a: Dict[str, Any],
    analysis_b: Dict[str, Any],
    fiedler_threshold: float = RADAR_FIEDLER_DELTA_THRESHOLD,
    netlsd_threshold: float = RADAR_NETLSD_DISTANCE_THRESHOLD,
) -> Dict[str, Any]:
    """Helper function to build a Sokół radar report from two analysis results."""
    radar = SokolRadar(fiedler_threshold=fiedler_threshold, netlsd_threshold=netlsd_threshold)
    return radar.evaluate(analysis_a, analysis_b)


def radar_report_to_markdown(report: Dict[str, Any]) -> str:
    """Formats a Sokół radar report as readable Markdown for engineering reviews."""
    lines: List[str] = [
        "# Sokół Spectral Change Radar Report",
        f"**Schema Version:** `{report.get('schema_version', 'sokol.radar.v1')}`",
        f"**Radar Verdict:** `{report.get('radar_verdict', 'UNKNOWN')}`",
        f"- **Baseline Snapshot:** `{report.get('baseline_snapshot', 'unknown')}`",
        f"- **Candidate Snapshot:** `{report.get('candidate_snapshot', 'unknown')}`",
        "",
        "## Compatibility",
        f"- **Status:** `{report['compatibility']['status']}`",
    ]
    if report["compatibility"]["reasons"]:
        lines.append("- **Caveats:**")
        for r in report["compatibility"]["reasons"]:
            lines.append(f"  - {r}")
    lines.append("")

    lines.extend([
        "## Metric Deltas",
        "| Metric | Baseline | Candidate | Delta | Noise Floor |",
        "|---|---|---|---|---|",
    ])
    d = report["metric_deltas"]
    lines.append(f"| NetLSD Distance | 0.0000 | {d['netlsd_distance']:.4f} | {d['netlsd_distance']:.4f} | {d['stochastic_noise_floor']:.6f} |")
    lines.append(rf"| Fiedler Value ($\lambda_1$) | {d['fiedler_baseline']:.4f} | {d['fiedler_candidate']:.4f} | {d['fiedler_delta']:+.4f} | N/A |")
    lines.append(f"| Node Count | - | - | {d['node_count_delta']:+d} | Exact |")
    lines.append(f"| Cycle Count | - | - | {d['cycle_count_delta']:+d} | Exact |")
    lines.append("")

    lines.append(f"## Review Candidates ({report['candidate_count']})")
    if not report["review_candidates"]:
        lines.append("No metric deltas exceeded the candidate nomination threshold.")
    else:
        for c in report["review_candidates"]:
            lines.extend([
                f"### [{c['review_priority']}] {c['category']} (`{c['metric_name']}`)",
                f"- **Basis:** {c['rational_basis']}",
                f"- **Guidance:** {c['review_guidance']}",
                "",
            ])

    lines.extend([
        "---",
        "> [!NOTE]",
        "> Radar signals reflect mathematical metric differences in the parsed graph models.",
        "> A metric delta is not a proof of functional defect or business-logic failure.",
    ])
    return "\n".join(lines)
