"""
Architecture Review Board (ARB) Monolith Decomposition Dossier Generator (sokol.arb_dossier.v1).
Consolidates Portfolio Manifest, Graph Topology, Cheeger Spectral Cuts, and
Database Transaction Friction into an auditable dossier for Enterprise Architecture Committees.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rezonator.friction_matrix import DatabaseTransactionFrictionMatrix
from rezonator.partition_recommender import PartitionCandidate, PartitionRecommender
from rezonator.portfolio_graph import PortfolioGraph


@dataclass
class MigrationWave:
    wave_number: int
    name: str
    target_programs: List[str]
    description: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    prerequisites: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave_number": self.wave_number,
            "name": self.name,
            "target_programs": list(self.target_programs),
            "description": self.description,
            "risk_level": self.risk_level,
            "prerequisites": list(self.prerequisites),
        }


class ArbDossierGenerator:
    """
    Generates an executive, auditable Bank-Grade Monolith Decomposition Dossier
    for Enterprise Architecture Review Boards (ARB).
    """

    SCHEMA_VERSION = "sokol.arb_dossier.v1"

    def __init__(
        self,
        recommender: Optional[PartitionRecommender] = None,
        friction_evaluator: Optional[DatabaseTransactionFrictionMatrix] = None,
    ):
        self.recommender = recommender or PartitionRecommender()
        self.friction_evaluator = friction_evaluator or DatabaseTransactionFrictionMatrix()

    def generate_dossier(
        self,
        portfolio_graph: PortfolioGraph,
        candidates: Optional[List[PartitionCandidate]] = None,
        friction_data: Optional[Dict[str, Any]] = None,
        system_name: str = "Core Mainframe System",
        target_cloud_platform: str = "Cloud-Native Hybrid Microservices",
    ) -> Dict[str, Any]:
        """
        Synthesizes all layers into the official ARB Monolith Decomposition Dossier.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Compute partitions if not supplied
        if candidates is None:
            candidates = self.recommender.recommend_portfolio_partitions(portfolio_graph, top_k=3)

        # Compute friction if not supplied
        if friction_data is None:
            friction_data = self.friction_evaluator.compute(portfolio_graph)

        n_progs = len(portfolio_graph.programs)
        hard_barriers = friction_data.get("hard_barriers_count", 0)

        # Calculate Separability Index (0 to 100%)
        best_cand = candidates[0] if candidates else None
        best_phi = best_cand.conductance if best_cand else 1.0

        # Separability index penalty based on conductance and hard barriers
        base_sep = max(0.0, 100.0 * (1.0 - best_phi))
        barrier_penalty = min(50.0, hard_barriers * 10.0)
        separability_index = max(10.0, round(base_sep - barrier_penalty, 1))

        # Risk Grade
        if separability_index >= 80.0:
            risk_grade = "A (High Separability, Clean Boundaries)"
        elif separability_index >= 60.0:
            risk_grade = "B (Moderate Coupling, Manageable Sagas)"
        elif separability_index >= 40.0:
            risk_grade = "C (Significant Data Friction, Shared Tables)"
        else:
            risk_grade = "D (Highly Entangled Monolith, High Risk)"

        # Plan Strangler Fig Migration Waves
        waves = self._plan_migration_waves(portfolio_graph, candidates, friction_data)

        dossier_data = {
            "schema_version": self.SCHEMA_VERSION,
            "dossier_id": f"arb:dossier:{hashlib.sha256((portfolio_graph.manifest_id + now_iso).encode()).hexdigest()[:16]}",
            "system_name": system_name,
            "target_cloud_platform": target_cloud_platform,
            "generated_at_utc": now_iso,
            "manifest_id": portfolio_graph.manifest_id,
            "governance_status": "PENDING_ARCHITECT_REVIEW",
            "executive_assessment": {
                "program_count": n_progs,
                "total_nodes": len(portfolio_graph.nodes),
                "total_edges": len(portfolio_graph.edges),
                "separability_index": separability_index,
                "risk_grade": risk_grade,
                "best_cut_conductance": best_phi,
                "hard_migration_barriers": hard_barriers,
            },
            "recommended_partitions": [c.to_dict() for c in candidates],
            "friction_summary": {
                "coupled_pairs": friction_data.get("coupled_pairs_count", 0),
                "hard_barriers": hard_barriers,
            },
            "migration_waves": [w.to_dict() for w in waves],
        }

        return dossier_data

    def _plan_migration_waves(
        self,
        portfolio_graph: PortfolioGraph,
        candidates: List[PartitionCandidate],
        friction_data: Dict[str, Any],
    ) -> List[MigrationWave]:
        """
        Determines sequential migration waves using Strangler Fig Pattern:
        Wave 1: Autonomous Leaf Programs (no DB2 write conflicts, lowest blast radius)
        Wave 2: Bounded Context Subsystems
        Wave 3: Core Transactional Ledger Kernel
        """
        programs = sorted(list(portfolio_graph.programs))
        if not programs:
            return []

        # Find barrier programs
        barrier_progs: Set[str] = set()
        for pf in friction_data.get("pairwise_friction", []):
            if pf.get("is_hard_barrier"):
                barrier_progs.add(pf["program_a"])
                barrier_progs.add(pf["program_b"])

        # Find blast radius scores
        blast_by_prog: Dict[str, int] = {}
        for p in programs:
            node_id = f"PGM:{p}"
            br = portfolio_graph.compute_blast_radius(node_id)
            blast_by_prog[p] = br.downstream_impact_count

        # Classify into 3 waves
        wave_1_progs = [p for p in programs if p not in barrier_progs and blast_by_prog.get(p, 0) <= 1]
        wave_3_progs = [p for p in programs if p in barrier_progs or blast_by_prog.get(p, 0) >= 5]
        wave_2_progs = [p for p in programs if p not in wave_1_progs and p not in wave_3_progs]

        # Balance if needed
        if not wave_1_progs and wave_2_progs:
            wave_1_progs.append(wave_2_progs.pop(0))
        if not wave_3_progs and wave_2_progs:
            wave_3_progs.append(wave_2_progs.pop(-1))

        return [
            MigrationWave(
                wave_number=1,
                name="Pilot Wave: Autonomous Edge Services",
                target_programs=wave_1_progs,
                description="Low blast-radius and query-only programs with zero hard DB2 write conflicts. Low risk early wins.",
                risk_level="LOW",
                prerequisites=["Read-only replica or Event-driven ingest adapter"],
            ),
            MigrationWave(
                wave_number=2,
                name="Expansion Wave: Bounded Domain Subsystems",
                target_programs=wave_2_progs,
                description="Programs with moderate coupling that can be extracted cleanly under Cheeger spectral cut boundaries.",
                risk_level="MEDIUM",
                prerequisites=["Wave 1 deployment stability", "API Gateway & Strangler Fig reverse proxy"],
            ),
            MigrationWave(
                wave_number=3,
                name="Core Wave: Transactional Ledger & Shared DB2 Kernel",
                target_programs=wave_3_progs,
                description="High-friction transactional core with shared DB2 state and batch step chaining. Requires Saga/Event sourcing.",
                risk_level="HIGH",
                prerequisites=["Distributed transaction / Saga pattern infrastructure", "Database schema decomposition"],
            ),
        ]

    def to_markdown(self, dossier: Dict[str, Any]) -> str:
        """Renders the dossier into a formal Architecture Review Board document."""
        ea = dossier["executive_assessment"]
        lines = [
            f"# Monolith Decomposition Dossier (ARB-DOC-{dossier['dossier_id'][-8:]})",
            f"**Target System:** `{dossier['system_name']}`  ",
            f"**Target Architecture:** `{dossier['target_cloud_platform']}`  ",
            f"**Governance Status:** `{dossier['governance_status']}`  ",
            f"**Evaluation Timestamp:** `{dossier['generated_at_utc']}`  ",
            f"**Manifest ID:** `{dossier['manifest_id']}`",
            "",
            "> **Epistemic Invariant:** This dossier is generated deterministically from topological Laplacians, "
            "Cheeger conductance bounds, and physical database ownership. All target boundaries remain subject to human architectural approval.",
            "",
            "---",
            "",
            "## 1. Executive Summary & Separability Scorecard",
            "",
            "| Assessment Dimension | Metric Value | Architectural Significance |",
            "| :--- | :---: | :--- |",
            f"| **Overall Separability Index** | **`{ea['separability_index']}%`** | Composite score of modularity and cut cleanliness |",
            f"| **Decomposition Risk Grade** | **`{ea['risk_grade']}`** | Recommended risk profile for target migration |",
            f"| **Best Cut Conductance (phi)** | `{ea['best_cut_conductance']:.4f}` | Topological ease of graph boundary separation |",
            f"| **Portfolio Programs** | `{ea['program_count']}` | Number of distinct COBOL source units |",
            f"| **Graph Complexity** | `{ea['total_nodes']} nodes / {ea['total_edges']} edges` | Unified CFG/DFG/JCL/DB2 topology volume |",
            f"| **Hard Migration Barriers** | **`{ea['hard_migration_barriers']}`** | Pairs requiring distributed transaction refactoring |",
            "",
            "---",
            "",
            "## 2. Top-Ranked Microservice Decomposition Candidates (Filar F6)",
            "",
        ]

        for idx, cand in enumerate(dossier.get("recommended_partitions", []), 1):
            lines.extend([
                f"### 2.{idx} Candidate Service Boundary: `{cand['name']}` (ID: `{cand['candidate_id']}`)",
                f"- **Conductance (phi):** `{cand['conductance']:.4f}` (Discrete Cheeger Range: `[{cand['cheeger_bound_lower']:.3f}, {cand['cheeger_bound_upper']:.3f}]`)",
                f"- **Uncertainty Score:** `{cand['uncertainty_score'] * 100:.1f}%`",
                f"- **Service Partition A ({cand['partition_a_size']} programs):** `{', '.join(cand['partition_a'][:6])}{' ...' if cand['partition_a_size'] > 6 else ''}`",
                f"- **Service Partition B ({cand['partition_b_size']} programs):** `{', '.join(cand['partition_b'][:6])}{' ...' if cand['partition_b_size'] > 6 else ''}`",
                f"- **Rationale:** {cand['rationale']}",
            ])
            if cand.get("shared_tables"):
                lines.append(f"- ⚠️ **Shared DB2 Tables:** `{', '.join(cand['shared_tables'])}`")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 3. Strangler Fig Phased Migration Roadmap",
            "",
        ] + [
            f"### Wave {w['wave_number']}: {w['name']} (`{w['risk_level']}` Risk)\n"
            f"- **Target Programs ({len(w['target_programs'])}):** `{', '.join(w['target_programs']) if w['target_programs'] else '*None*'}`\n"
            f"- **Description:** {w['description']}\n"
            f"- **Prerequisites:** {', '.join(w['prerequisites'])}\n"
            for w in dossier.get("migration_waves", [])
        ])

        lines.extend([
            "---",
            "",
            "## 4. Formal Architecture Review Board (ARB) Sign-Off Block",
            "",
            "```text",
            "╔═══════════════════════════════════════════════════════════════════════════════════╗",
            "║                      BANK ARCHITECTURE REVIEW BOARD (ARB)                         ║",
            "╠═══════════════════════════════════════════════════════════════════════════════════╣",
            "║ System Name:    " + f"{dossier['system_name']:<65}" + " ║",
            "║ Dossier ID:     " + f"{dossier['dossier_id']:<65}" + " ║",
            "║ Review Decision: [  ] APPROVED  [  ] APPROVED WITH STIPULATIONS  [  ] REJECTED    ║",
            "║                                                                                   ║",
            "║ Lead Enterprise Architect: ___________________________ Date: ____________________ ║",
            "║ Chief Information Security Officer: __________________ Date: ____________________ ║",
            "║ Mainframe Operations Lead: ___________________________ Date: ____________________ ║",
            "╚═══════════════════════════════════════════════════════════════════════════════════╝",
            "```",
        ])

        return "\n".join(lines)
