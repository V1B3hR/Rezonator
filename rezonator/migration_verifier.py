"""
Migration Verification & Differential Equivalence Engine (Filar F6).
Compares baseline and candidate/modernized implementations using:
1. Differential execution on bounded input states via CobolRuntime.
2. Variable mutation state diffs and trace divergence points.
3. Domain invariant validation (e.g. balance constraints, error flag consistency).
4. Structural topological signals (NetLSD spectral distance, Fiedler shift, cycle preservation).
5. Versioned evidence envelope: sokol.migration.v1.

Epistemic Invariant:
Structural signals (NetLSD distance, absence of detected cycles) are not formal
proofs of semantic equivalence. Functional equivalence requires comprehensive
differential testing across bounded workload domains.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from rezonator.cobol_runtime import CobolRuntime, ExecutionState
from rezonator.limits import validate_source_size
from rezonator.program_comparator import ProgramComparator


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


@dataclass
class DomainInvariant:
    """
    Domain assertion that must hold true after program execution.
    Example: 'WS-BALANCE >= 0', 'WS-ERROR-CODE == 0'
    """
    name: str
    expression: str
    description: str = ""
    severity: str = "CRITICAL"  # "CRITICAL", "WARNING"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "expression": self.expression,
            "description": self.description,
            "severity": self.severity,
        }


@dataclass
class DifferentialTestCase:
    """
    Input test vector for differential execution across baseline and candidate.
    """
    test_id: str
    description: str = ""
    input_overrides: Dict[str, Any] = field(default_factory=dict)
    expected_output_vars: Optional[Dict[str, Any]] = None
    invariants: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "description": self.description,
            "input_overrides": dict(self.input_overrides),
            "expected_output_vars": dict(self.expected_output_vars) if self.expected_output_vars else None,
            "invariants": list(self.invariants),
        }


@dataclass
class DifferentialTestRun:
    """
    Observed outcome of differential execution for a single test case.
    """
    test_id: str
    baseline_variables: Dict[str, Any]
    candidate_variables: Dict[str, Any]
    affected_variables: Dict[str, Dict[str, Any]]
    baseline_steps: int
    candidate_steps: int
    trace_diverged_at_step: Optional[int]
    passed_equivalence: bool
    invariant_violations: List[str]
    status: str  # "PASS", "DIVERGED", "INVARIANT_VIOLATION", "TIMEOUT", "ERROR"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "baseline_variables": self.baseline_variables,
            "candidate_variables": self.candidate_variables,
            "affected_variables": self.affected_variables,
            "baseline_steps": self.baseline_steps,
            "candidate_steps": self.candidate_steps,
            "trace_diverged_at_step": self.trace_diverged_at_step,
            "passed_equivalence": self.passed_equivalence,
            "invariant_violations": list(self.invariant_violations),
            "status": self.status,
        }


@dataclass
class StructuralSignals:
    """
    Topological and spectral comparison signals between baseline and candidate.
    """
    netlsd_distance: float
    fiedler_delta: float
    fiedler_norm_delta: float
    cymatic_similarity: float
    cycle_topology_preserved: bool
    baseline_has_deadlock: bool
    candidate_has_deadlock: bool
    baseline_node_count: int
    candidate_node_count: int
    baseline_edge_count: int
    candidate_edge_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "netlsd_distance": round(self.netlsd_distance, 6),
            "fiedler_delta": round(self.fiedler_delta, 6),
            "fiedler_norm_delta": round(self.fiedler_norm_delta, 6),
            "cymatic_similarity": round(self.cymatic_similarity, 4),
            "cycle_topology_preserved": self.cycle_topology_preserved,
            "baseline_has_deadlock": self.baseline_has_deadlock,
            "candidate_has_deadlock": self.candidate_has_deadlock,
            "baseline_node_count": self.baseline_node_count,
            "candidate_node_count": self.candidate_node_count,
            "baseline_edge_count": self.baseline_edge_count,
            "candidate_edge_count": self.candidate_edge_count,
        }


@dataclass
class MigrationEvidence:
    """
    Complete migration evidence document (sokol.migration.v1).
    Encapsulates differential test observations, domain invariants, and spectral signals.
    """
    evidence_id: str
    baseline_program_id: str
    candidate_program_id: str
    baseline_hash: str
    candidate_hash: str
    observed_at_utc: str
    epistemic_status: str  # "VERIFIED", "DIVERGED", "STRUCTURAL_ONLY"
    structural_signals: StructuralSignals
    test_runs: List[DifferentialTestRun]
    total_tests: int
    passed_tests: int
    equivalence_rate: float
    domain_invariants_evaluated: int
    domain_invariants_violated: List[str]
    architect_review_status: str = "PENDING_ARCHITECT_REVIEW"
    schema_version: str = "sokol.migration.v1"
    caveat_notice: str = (
        "Structural similarity (NetLSD distance, spectral overlap) and absence of detected "
        "cycles are structural signals only, NOT formal proofs of semantic equivalence. "
        "Functional equivalence requires comprehensive differential testing across all production workload spaces."
    )

    def compute_checksum(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "baseline_program_id": self.baseline_program_id,
            "candidate_program_id": self.candidate_program_id,
            "baseline_hash": self.baseline_hash,
            "candidate_hash": self.candidate_hash,
            "structural_signals": self.structural_signals.to_dict(),
            "equivalence_rate": round(self.equivalence_rate, 4),
            "domain_invariants_violated": sorted(self.domain_invariants_violated),
            "epistemic_status": self.epistemic_status,
        }
        return _sha256(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "checksum": self.compute_checksum(),
            "baseline_program_id": self.baseline_program_id,
            "candidate_program_id": self.candidate_program_id,
            "baseline_hash": self.baseline_hash,
            "candidate_hash": self.candidate_hash,
            "observed_at_utc": self.observed_at_utc,
            "epistemic_status": self.epistemic_status,
            "architect_review_status": self.architect_review_status,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "equivalence_rate": round(self.equivalence_rate, 4),
            "structural_signals": self.structural_signals.to_dict(),
            "test_runs": [tr.to_dict() for tr in self.test_runs],
            "domain_invariants_evaluated": self.domain_invariants_evaluated,
            "domain_invariants_violated": list(self.domain_invariants_violated),
            "caveat_notice": self.caveat_notice,
        }

    def to_markdown_report(self) -> str:
        lines = [
            f"# Migration Verification Report: `{self.baseline_program_id}` vs `{self.candidate_program_id}`",
            "",
            f"> **Schema:** `{self.schema_version}` | **Evidence ID:** `{self.evidence_id}`",
            f"> **Epistemic Status:** `{self.epistemic_status}` | **Review Gate:** `{self.architect_review_status}`",
            f"> **Observed at:** `{self.observed_at_utc}`",
            "",
            "### Epistemic Invariant & Caveat Notice",
            f"> {self.caveat_notice}",
            "",
            "## 1. Differential Execution Summary",
            "",
            f"- **Workload Test Suite Pass Rate:** `{self.passed_tests}/{self.total_tests}` (`{self.equivalence_rate * 100:.1f}%`)",
            f"- **Domain Invariants Evaluated:** `{self.domain_invariants_evaluated}`",
            f"- **Domain Invariant Violations:** `{len(self.domain_invariants_violated)}`",
            "",
            "| Metric | Value | Reference / Meaning |",
            "| :--- | :---: | :--- |",
            f"| **Equivalence Rate** | `{self.equivalence_rate * 100:.1f}%` | Fraction of test cases with zero output variable divergence |",
            f"| **NetLSD Spectral Distance** | `{self.structural_signals.netlsd_distance:.6f}` | Size-invariant heat trace divergence ($D_{{NetLSD}}$) |",
            f"| **Fiedler Eigenvalue Shift** | `{self.structural_signals.fiedler_delta:+.6f}` | Algebraic connectivity change (structural bottleneck shift) |",
            f"| **Cymatic Overlap** | `{self.structural_signals.cymatic_similarity:.4f}` | Chladni modal surface cosine correlation |",
            f"| **Cycle Topology Preserved** | `{'YES' if self.structural_signals.cycle_topology_preserved else 'NO'}` | Consistency of cyclic dependency structure |",
            f"| **Deadlock Introduced** | `{'YES' if (self.structural_signals.candidate_has_deadlock and not self.structural_signals.baseline_has_deadlock) else 'NO'}` | Static cycle hazard comparison |",
            "",
            "---",
            "",
            "## 2. Differential Test Runs",
            "",
            "| Test ID | Status | Baseline Steps | Candidate Steps | Divergence Point | Invariant Violations |",
            "| :--- | :---: | :---: | :---: | :---: | :--- |",
        ]

        for tr in self.test_runs:
            div_step = f"Step {tr.trace_diverged_at_step}" if tr.trace_diverged_at_step is not None else "None"
            inv_str = ", ".join(tr.invariant_violations) if tr.invariant_violations else "None"
            lines.append(
                f"| `{tr.test_id}` | `{tr.status}` | {tr.baseline_steps} | {tr.candidate_steps} | {div_step} | {inv_str} |"
            )

        if any(tr.affected_variables for tr in self.test_runs):
            lines.extend([
                "",
                "### Detailed Variable Divergence Breakdown",
                "",
            ])
            for tr in self.test_runs:
                if tr.affected_variables:
                    lines.append(f"#### Test `{tr.test_id}` Divergences:")
                    for var_name, diff in tr.affected_variables.items():
                        lines.append(f"- **{var_name}:** Baseline=`{diff.get('baseline')}` $\\to$ Candidate=`{diff.get('candidate')}`")

        if self.domain_invariants_violated:
            lines.extend([
                "",
                "### ⚠️ Domain Invariant Violations",
                "",
            ])
            for inv in self.domain_invariants_violated:
                lines.append(f"- ❌ Violation: `{inv}`")

        lines.extend([
            "",
            "---",
            "",
            "## 3. Structural Graph Topology Comparison",
            "",
            f"- **Baseline Graph:** {self.structural_signals.baseline_node_count} nodes, {self.structural_signals.baseline_edge_count} edges",
            f"- **Candidate Graph:** {self.structural_signals.candidate_node_count} nodes, {self.structural_signals.candidate_edge_count} edges",
            f"- **Baseline Deadlock Status:** `{'DEADLOCK DETECTED' if self.structural_signals.baseline_has_deadlock else 'NONE'}`",
            f"- **Candidate Deadlock Status:** `{'DEADLOCK DETECTED' if self.structural_signals.candidate_has_deadlock else 'NONE'}`",
        ])

        return "\n".join(lines)


class MigrationVerifier:
    """
    Migration Verifier & Differential Testing Engine (sokol.migration.v1).
    Evaluates semantic divergence and structural consistency between baseline and modernized programs.
    """

    SCHEMA_VERSION = "sokol.migration.v1"

    def __init__(self, lattice_size: int = 32, copybooks: Optional[Dict[str, str]] = None):
        self.lattice_size = lattice_size
        self.copybooks = copybooks
        self.comparator = ProgramComparator(lattice_size=lattice_size, copybooks=copybooks)
        self.runtime = CobolRuntime()

    def verify(
        self,
        baseline_source: str,
        candidate_source: str,
        test_cases: Optional[List[DifferentialTestCase]] = None,
        invariants: Optional[List[DomainInvariant]] = None,
        max_steps: int = 500,
    ) -> MigrationEvidence:
        """
        Executes end-to-end migration verification:
        1. Compares structural graph topology (NetLSD, Fiedler, Chladni, cycles).
        2. Executes differential test cases via CobolRuntime.
        3. Validates domain invariants on terminal states.
        4. Synthesizes an evidence document with explicit epistemic status.
        """
        validate_source_size(baseline_source)
        validate_source_size(candidate_source)

        baseline_hash = hashlib.sha256(baseline_source.encode("utf-8")).hexdigest()
        candidate_hash = hashlib.sha256(candidate_source.encode("utf-8")).hexdigest()

        # 1. Structural Comparison
        comp_res = self.comparator.compare(baseline_source, candidate_source)
        metrics = comp_res.get("metrics", {})
        netlsd_dist = float(metrics.get("spectral_distance_netlsd", 0.0))
        fiedler_delta = float(metrics.get("fiedler_delta", 0.0))
        fiedler_norm_delta = float(metrics.get("fiedler_norm_delta", 0.0))
        cymatic_sim = float(metrics.get("cymatic_cross_similarity", 0.0))

        details_a = comp_res.get("program_a_details", {})
        details_b = comp_res.get("program_b_details", {})
        cycles_a = details_a.get("cycles", {})
        cycles_b = details_b.get("cycles", {})
        stats_a = details_a.get("stats", {})
        stats_b = details_b.get("stats", {})

        cycle_top_preserved = (
            cycles_a.get("has_deadlock") == cycles_b.get("has_deadlock")
            and cycles_a.get("cycle_count") == cycles_b.get("cycle_count")
        )

        signals = StructuralSignals(
            netlsd_distance=netlsd_dist,
            fiedler_delta=fiedler_delta,
            fiedler_norm_delta=fiedler_norm_delta,
            cymatic_similarity=cymatic_sim,
            cycle_topology_preserved=cycle_top_preserved,
            baseline_has_deadlock=bool(cycles_a.get("has_deadlock", False)),
            candidate_has_deadlock=bool(cycles_b.get("has_deadlock", False)),
            baseline_node_count=stats_a.get("num_nodes", 0),
            candidate_node_count=stats_b.get("num_nodes", 0),
            baseline_edge_count=stats_a.get("num_edges", 0),
            candidate_edge_count=stats_b.get("num_edges", 0),
        )

        # 2. Differential Test Runs
        effective_cases = list(test_cases) if test_cases else [
            DifferentialTestCase(test_id="default-tc01", description="Default initial state test")
        ]

        effective_invariants = list(invariants) if invariants else []
        invariant_map = {inv.name: inv for inv in effective_invariants}

        test_runs: List[DifferentialTestRun] = []
        violated_invariants_set: Set[str] = set()

        for tc in effective_cases:
            try:
                base_state = self.runtime.run(baseline_source, initial_overrides=tc.input_overrides, max_steps=max_steps)
                cand_state = self.runtime.run(candidate_source, initial_overrides=tc.input_overrides, max_steps=max_steps)

                # Variable comparisons
                affected_vars: Dict[str, Dict[str, Any]] = {}
                all_keys = set(base_state.variables.keys()) | set(cand_state.variables.keys())

                # If specific expected output vars were defined, check those; otherwise check all
                keys_to_compare = set(tc.expected_output_vars.keys()) if tc.expected_output_vars else all_keys

                for k in sorted(list(keys_to_compare)):
                    bv = base_state.variables.get(k)
                    cv = cand_state.variables.get(k)
                    if bv != cv:
                        affected_vars[k] = {"baseline": bv, "candidate": cv}

                # Trace divergence
                diverged_step = None
                min_len = min(len(base_state.trace), len(cand_state.trace))
                for s_i in range(min_len):
                    if base_state.trace[s_i] != cand_state.trace[s_i]:
                        diverged_step = s_i
                        break
                if diverged_step is None and len(base_state.trace) != len(cand_state.trace):
                    diverged_step = min_len

                # Check invariants on candidate state
                inv_violations: List[str] = []
                for inv_name in tc.invariants:
                    if inv_name in invariant_map:
                        inv = invariant_map[inv_name]
                        holds = bool(self.runtime._eval_expr(inv.expression, cand_state.variables))
                        if not holds:
                            v_msg = f"{inv.name} ({inv.expression}) failed in candidate state"
                            inv_violations.append(v_msg)
                            violated_invariants_set.add(v_msg)

                # Status determination
                is_equiv = (len(affected_vars) == 0) and (len(inv_violations) == 0)
                if base_state.timed_out or cand_state.timed_out:
                    status = "TIMEOUT"
                    is_equiv = False
                elif inv_violations:
                    status = "INVARIANT_VIOLATION"
                elif affected_vars:
                    status = "DIVERGED"
                else:
                    status = "PASS"

                test_runs.append(DifferentialTestRun(
                    test_id=tc.test_id,
                    baseline_variables=base_state.variables,
                    candidate_variables=cand_state.variables,
                    affected_variables=affected_vars,
                    baseline_steps=base_state.steps,
                    candidate_steps=cand_state.steps,
                    trace_diverged_at_step=diverged_step,
                    passed_equivalence=is_equiv,
                    invariant_violations=inv_violations,
                    status=status,
                ))

            except Exception as exc:
                test_runs.append(DifferentialTestRun(
                    test_id=tc.test_id,
                    baseline_variables={},
                    candidate_variables={},
                    affected_variables={"RUNTIME_ERROR": {"baseline": "", "candidate": str(exc)}},
                    baseline_steps=0,
                    candidate_steps=0,
                    trace_diverged_at_step=0,
                    passed_equivalence=False,
                    invariant_violations=[f"Execution exception: {str(exc)}"],
                    status="ERROR",
                ))

        total_tests = len(test_runs)
        passed_tests = sum(1 for tr in test_runs if tr.passed_equivalence)
        equiv_rate = (passed_tests / total_tests) if total_tests > 0 else 0.0

        # Epistemic status
        if total_tests == 0:
            epistemic_status = "STRUCTURAL_ONLY"
        elif passed_tests == total_tests:
            epistemic_status = "OBSERVED_VERIFIED"
        else:
            epistemic_status = "OBSERVED_DIVERGED"

        now_utc = datetime.now(timezone.utc).isoformat()
        evidence_id = f"migeve-{hashlib.sha256(f'{baseline_hash}:{candidate_hash}:{now_utc}'.encode('utf-8')).hexdigest()[:12]}"

        prog_id_a = str(comp_res.get("program_a") or "BASELINE")
        prog_id_b = str(comp_res.get("program_b") or "CANDIDATE")

        return MigrationEvidence(
            evidence_id=evidence_id,
            baseline_program_id=prog_id_a,
            candidate_program_id=prog_id_b,
            baseline_hash=baseline_hash,
            candidate_hash=candidate_hash,
            observed_at_utc=now_utc,
            epistemic_status=epistemic_status,
            structural_signals=signals,
            test_runs=test_runs,
            total_tests=total_tests,
            passed_tests=passed_tests,
            equivalence_rate=equiv_rate,
            domain_invariants_evaluated=len(effective_invariants),
            domain_invariants_violated=sorted(list(violated_invariants_set)),
            architect_review_status="PENDING_ARCHITECT_REVIEW",
        )
