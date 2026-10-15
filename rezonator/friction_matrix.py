"""
Database & Transactional Friction Matrix (sokol.friction.v1).
Analyzes PortfolioGraph to compute pairwise distributed transaction penalties,
shared DB2 table write-conflicts, JCL step couplings, and hard migration barriers.
"""

from __future__ import annotations

import collections
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from rezonator.portfolio_graph import PortfolioGraph


@dataclass
class PairwiseFriction:
    program_a: str
    program_b: str
    total_friction: float
    friction_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    shared_tables: List[str] = field(default_factory=list)
    shared_datasets: List[str] = field(default_factory=list)
    shared_jcl_jobs: List[str] = field(default_factory=list)
    direct_calls_count: int = 0
    is_hard_barrier: bool = False
    barrier_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_a": self.program_a,
            "program_b": self.program_b,
            "total_friction": round(self.total_friction, 2),
            "friction_level": self.friction_level,
            "shared_tables": list(self.shared_tables),
            "shared_datasets": list(self.shared_datasets),
            "shared_jcl_jobs": list(self.shared_jcl_jobs),
            "direct_calls_count": self.direct_calls_count,
            "is_hard_barrier": self.is_hard_barrier,
            "barrier_reason": self.barrier_reason,
        }


class DatabaseTransactionFrictionMatrix:
    """
    Evaluates distributed transaction cost and data-tier entanglement
    between all pairs of programs in an enterprise portfolio.
    """

    SCHEMA_VERSION = "sokol.friction.v1"

    def __init__(
        self,
        weight_db2_shared: float = 3.0,
        weight_dataset_shared: float = 2.0,
        weight_jcl_shared_job: float = 3.5,
        weight_direct_call: float = 2.0,
    ):
        self.weight_db2_shared = weight_db2_shared
        self.weight_dataset_shared = weight_dataset_shared
        self.weight_jcl_shared_job = weight_jcl_shared_job
        self.weight_direct_call = weight_direct_call

    def compute(self, portfolio_graph: PortfolioGraph) -> Dict[str, Any]:
        """
        Computes pairwise friction, classifies barrier levels,
        and aggregates architectural entanglement metrics.
        """
        programs = sorted(list(portfolio_graph.programs))
        n_progs = len(programs)

        # 1. Map resources to programs
        # table -> set of programs
        table_to_progs: Dict[str, Set[str]] = collections.defaultdict(set)
        # dataset -> set of programs
        dataset_to_progs: Dict[str, Set[str]] = collections.defaultdict(set)
        # job -> set of programs
        job_to_progs: Dict[str, Set[str]] = collections.defaultdict(set)
        # program -> set of called programs
        direct_calls: Dict[str, Set[str]] = collections.defaultdict(set)

        # step -> programs executed
        step_to_progs: Dict[str, Set[str]] = collections.defaultdict(set)
        # step -> datasets accessed
        step_to_dsns: Dict[str, Set[str]] = collections.defaultdict(set)

        for edge in portfolio_graph.edges:
            src = edge.source
            tgt = edge.target
            etype = edge.edge_type

            # Program -> Table
            if src.startswith("PGM:") and tgt.startswith("TABLE:"):
                pid = src[4:]
                tbl = tgt[6:]
                table_to_progs[tbl].add(pid)

            # Program -> Dataset
            elif src.startswith("PGM:") and tgt.startswith("DSN:"):
                pid = src[4:]
                dsn = tgt[4:]
                dataset_to_progs[dsn].add(pid)

            # Step -> Dataset
            elif src.startswith("STEP:") and tgt.startswith("DSN:"):
                dsn = tgt[4:]
                step_to_dsns[src].add(dsn)

            # Step -> Program (JCL Execution)
            elif etype in ("STEP_EXEC", "JCL_EXEC") and src.startswith("STEP:") and (tgt.startswith("PGM:") or tgt.startswith("EXT_PGM:")):
                pid = tgt.split(":", 1)[1]
                step_to_progs[src].add(pid)

                # find job owning this step
                step_node = portfolio_graph.nodes.get(src)
                job_id = None
                if step_node and step_node.metadata:
                    job_id = step_node.metadata.get("job_id") or step_node.metadata.get("job_name")
                if not job_id:
                    # src is STEP:{job.job_name}.{step.step_name}
                    step_body = src[5:]
                    job_id = step_body.split(".")[0] if "." in step_body else step_body
                if job_id:
                    job_to_progs[job_id].add(pid)

            # Direct Calls
            elif etype.startswith("CALL_") or etype.startswith("CICS_"):
                if src.startswith("PGM:") and tgt.startswith("PGM:"):
                    p_src = src[4:]
                    p_tgt = tgt[4:]
                    direct_calls[p_src].add(p_tgt)

        # Propagate step-level datasets to programs executing in those steps
        for step, progs in step_to_progs.items():
            for dsn in step_to_dsns.get(step, set()):
                for p in progs:
                    dataset_to_progs[dsn].add(p)

        # 2. Compute pairwise friction between all distinct pairs of programs
        pairwise_results: List[PairwiseFriction] = []
        hard_barriers_count = 0
        total_couplings = 0

        for i in range(n_progs):
            p_a = programs[i]
            for j in range(i + 1, n_progs):
                p_b = programs[j]

                shared_tbls = [
                    tbl for tbl, p_set in table_to_progs.items()
                    if p_a in p_set and p_b in p_set
                ]
                shared_dsns = [
                    dsn for dsn, p_set in dataset_to_progs.items()
                    if p_a in p_set and p_b in p_set
                ]
                shared_jobs = [
                    job for job, p_set in job_to_progs.items()
                    if p_a in p_set and p_b in p_set
                ]

                has_calls = (
                    (1 if p_b in direct_calls[p_a] else 0) +
                    (1 if p_a in direct_calls[p_b] else 0)
                )

                score = (
                    self.weight_db2_shared * len(shared_tbls)
                    + self.weight_dataset_shared * len(shared_dsns)
                    + self.weight_jcl_shared_job * len(shared_jobs)
                    + self.weight_direct_call * has_calls
                )

                if score == 0:
                    continue

                total_couplings += 1

                # Classify friction level and barriers
                is_barrier = False
                barrier_reason = ""

                if len(shared_tbls) >= 2 or (len(shared_tbls) >= 1 and len(shared_jobs) >= 1):
                    is_barrier = True
                    barrier_reason = (
                        f"High-risk distributed state conflict: shares {len(shared_tbls)} DB2 table(s) "
                        f"across JCL workflow."
                    )
                    hard_barriers_count += 1
                    level = "CRITICAL"
                elif score >= 6.0:
                    level = "HIGH"
                elif score >= 3.0:
                    level = "MEDIUM"
                else:
                    level = "LOW"

                pairwise_results.append(PairwiseFriction(
                    program_a=p_a,
                    program_b=p_b,
                    total_friction=score,
                    friction_level=level,
                    shared_tables=sorted(shared_tbls),
                    shared_datasets=sorted(shared_dsns),
                    shared_jcl_jobs=sorted(shared_jobs),
                    direct_calls_count=has_calls,
                    is_hard_barrier=is_barrier,
                    barrier_reason=barrier_reason,
                ))

        # Sort by total friction descending
        pairwise_results.sort(key=lambda x: -x.total_friction)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "manifest_id": portfolio_graph.manifest_id,
            "program_count": n_progs,
            "coupled_pairs_count": total_couplings,
            "hard_barriers_count": hard_barriers_count,
            "pairwise_friction": [pf.to_dict() for pf in pairwise_results],
        }

    def to_markdown(self, friction_data: Dict[str, Any]) -> str:
        """Renders the friction analysis into an executive Markdown report."""
        lines = [
            f"# Database & Transactional Friction Matrix ({friction_data.get('schema_version', self.SCHEMA_VERSION)})",
            "",
            "> **Epistemic Invariant:** Friction scores quantify shared physical assets (DB2 tables, VSAM files, JCL jobs). "
            "They highlight distributed transaction anti-patterns when decomposing monolits into microservices.",
            "",
            "## 1. Executive Friction Summary",
            "",
            f"- **Portfolio Programs Analyzed:** `{friction_data.get('program_count', 0)}`",
            f"- **Coupled Program Pairs:** `{friction_data.get('coupled_pairs_count', 0)}`",
            f"- **Hard Migration Barriers Identified:** `{friction_data.get('hard_barriers_count', 0)}`",
            "",
            "---",
            "",
            "## 2. Program-to-Program Friction Register",
            "",
            "| Program A | Program B | Friction Score | Level | Hard Barrier | Shared Resources & Drivers |",
            "| :--- | :--- | :---: | :---: | :---: | :--- |",
        ]

        pairwise = friction_data.get("pairwise_friction", [])
        if not pairwise:
            lines.append("| *None* | *None* | 0.00 | LOW | NO | *No cross-program friction detected.* |")
        else:
            for item in pairwise[:25]:  # Top 25 coupled pairs
                barrier_tag = "⛔ **YES**" if item["is_hard_barrier"] else "NO"
                drivers = []
                if item["shared_tables"]:
                    drivers.append(f"DB2: {', '.join(item['shared_tables'])}")
                if item["shared_datasets"]:
                    drivers.append(f"DSN: {', '.join(item['shared_datasets'])}")
                if item["shared_jcl_jobs"]:
                    drivers.append(f"JCL: {', '.join(item['shared_jcl_jobs'])}")
                if item["direct_calls_count"] > 0:
                    drivers.append(f"Calls: {item['direct_calls_count']}")
                driver_str = "; ".join(drivers) if drivers else "*Implicit*"

                lines.append(
                    f"| `{item['program_a']}` | `{item['program_b']}` | `{item['total_friction']:.2f}` | "
                    f"`{item['friction_level']}` | {barrier_tag} | {driver_str} |"
                )

            if len(pairwise) > 25:
                lines.append(f"| *...* | *...* | *...* | *...* | *...* | *(+{len(pairwise) - 25} lower-friction pairs omitted)* |")

        # Section 3: Hard barriers breakdown
        barriers = [p for p in pairwise if p["is_hard_barrier"]]
        if barriers:
            lines.extend([
                "",
                "---",
                "",
                "## 3. ⛔ Hard Migration Barriers (Action Required)",
                "",
                "> These pairs cannot be separated into independent microservices without introducing distributed 2-Phase Commit (2PC) or distributed locking. "
                "They MUST either be grouped into the same bounded context or refactored with an asynchronous Saga/Event-Carried State pattern.",
                "",
            ])
            for b in barriers:
                lines.append(f"- **`{b['program_a']}` ↔ `{b['program_b']}`**: {b['barrier_reason']}")
                if b["shared_tables"]:
                    lines.append(f"  - Shared Tables: `{', '.join(b['shared_tables'])}`")

        return "\n".join(lines)
