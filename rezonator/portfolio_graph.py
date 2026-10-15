"""
Multi-Program Application Portfolio Graph (Filar F5).
Builds cross-program dependency models from explicit Portfolio Manifests,
resolving COBOL CALL, CICS LINK/XCTL, JCL jobs/steps/DDs, and shared DB2 tables/datasets.
Computes sparse reachability, transitive blast-radius propagation, and portfolio coupling.
"""

from __future__ import annotations

import collections
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import scipy.sparse as sp

from rezonator.call_resolver import CallResolver, ProgramCall, ProgramResourceAccess
from rezonator.jcl_parser import JclJob, JclParser
from rezonator.portfolio_manifest import PortfolioManifest


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass
class PortfolioNode:
    id: str
    label: str
    node_type: str  # "program", "external_program", "job", "step", "dataset", "db2_table"
    epistemic_status: str = "OBSERVED"  # "OBSERVED", "INFERRED", "UNRESOLVED"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            "epistemic_status": self.epistemic_status,
            "metadata": dict(self.metadata),
        }


@dataclass
class PortfolioEdge:
    source: str
    target: str
    edge_type: str
    weight: float = 1.0
    label: str = ""
    epistemic_status: str = "OBSERVED"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "label": self.label,
            "epistemic_status": self.epistemic_status,
            "metadata": dict(self.metadata),
        }


@dataclass
class PortfolioBlastRadius:
    target_node: str
    node_type: str
    direct_outgoing: List[str] = field(default_factory=list)
    direct_incoming: List[str] = field(default_factory=list)
    transitive_downstream: List[str] = field(default_factory=list)
    transitive_upstream: List[str] = field(default_factory=list)
    downstream_impact_count: int = 0
    upstream_dependency_count: int = 0
    impact_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_node": self.target_node,
            "node_type": self.node_type,
            "direct_outgoing": list(self.direct_outgoing),
            "direct_incoming": list(self.direct_incoming),
            "transitive_downstream": list(self.transitive_downstream),
            "transitive_upstream": list(self.transitive_upstream),
            "downstream_impact_count": self.downstream_impact_count,
            "upstream_dependency_count": self.upstream_dependency_count,
            "impact_ratio": round(self.impact_ratio, 4),
        }


class PortfolioGraph:
    """
    Unified multi-program dependency graph representation (sokol.portfolio.graph.v1).
    Encapsulates cross-program invocation topology, JCL workflows, shared datasets,
    and DB2 table coupling with sparse reachability and blast radius metrics.
    """

    SCHEMA_VERSION = "sokol.portfolio.graph.v1"

    def __init__(
        self,
        manifest_id: str,
        nodes: Optional[Dict[str, PortfolioNode]] = None,
        edges: Optional[List[PortfolioEdge]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.manifest_id = manifest_id
        self.nodes: Dict[str, PortfolioNode] = dict(nodes or {})
        self.edges: List[PortfolioEdge] = list(edges or [])
        self.metadata: Dict[str, Any] = dict(metadata or {})
        self._adj_cache: Optional[Tuple[sp.csr_matrix, Dict[str, int], List[str]]] = None

    @property
    def programs(self) -> List[str]:
        """Returns sorted list of distinct program IDs registered in this portfolio graph."""
        return sorted([n.label for n in self.nodes.values() if n.node_type == "program"])

    def get_node(self, node_id: str) -> Optional[PortfolioNode]:
        return self.nodes.get(node_id)

    def compute_adjacency_matrix(self) -> Tuple[sp.csr_matrix, Dict[str, int], List[str]]:
        """Constructs a SciPy CSR directed adjacency matrix."""
        if self._adj_cache is not None:
            return self._adj_cache

        node_ids = sorted(list(self.nodes.keys()))
        n = len(node_ids)
        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}

        rows: List[int] = []
        cols: List[int] = []
        data: List[float] = []

        for edge in self.edges:
            src = edge.source
            dst = edge.target
            if src in node_to_idx and dst in node_to_idx:
                rows.append(node_to_idx[src])
                cols.append(node_to_idx[dst])
                data.append(edge.weight)

        if n > 0:
            adj = sp.csr_matrix((data, (rows, cols)), shape=(n, n), dtype=np.float64)
        else:
            adj = sp.csr_matrix((0, 0), dtype=np.float64)

        self._adj_cache = (adj, node_to_idx, node_ids)
        return self._adj_cache

    def compute_blast_radius(self, node_id: str) -> PortfolioBlastRadius:
        """
        Computes direct 1-hop dependencies and full transitive downstream reachability
        as well as upstream callers for a specific portfolio node.
        """
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' does not exist in portfolio graph")

        target_node = self.nodes[node_id]

        # Build forward and backward adjacency lists for deterministic BFS
        forward_adj: Dict[str, List[str]] = collections.defaultdict(list)
        reverse_adj: Dict[str, List[str]] = collections.defaultdict(list)

        for edge in self.edges:
            forward_adj[edge.source].append(edge.target)
            reverse_adj[edge.target].append(edge.source)

        # Direct 1-hop
        direct_out = sorted(list(set(forward_adj.get(node_id, []))))
        direct_in = sorted(list(set(reverse_adj.get(node_id, []))))

        # Transitive downstream reachability (BFS)
        downstream: Set[str] = set()
        queue = collections.deque(direct_out)
        while queue:
            curr = queue.popleft()
            if curr not in downstream and curr != node_id:
                downstream.add(curr)
                for nxt in forward_adj.get(curr, []):
                    if nxt not in downstream and nxt != node_id:
                        queue.append(nxt)

        # Transitive upstream dependencies (BFS)
        upstream: Set[str] = set()
        queue_up = collections.deque(direct_in)
        while queue_up:
            curr = queue_up.popleft()
            if curr not in upstream and curr != node_id:
                upstream.add(curr)
                for prev in reverse_adj.get(curr, []):
                    if prev not in upstream and prev != node_id:
                        queue_up.append(prev)

        total_nodes = len(self.nodes)
        impact_ratio = (len(downstream) / max(1, total_nodes - 1)) if total_nodes > 1 else 0.0

        return PortfolioBlastRadius(
            target_node=node_id,
            node_type=target_node.node_type,
            direct_outgoing=direct_out,
            direct_incoming=direct_in,
            transitive_downstream=sorted(list(downstream)),
            transitive_upstream=sorted(list(upstream)),
            downstream_impact_count=len(downstream),
            upstream_dependency_count=len(upstream),
            impact_ratio=impact_ratio,
        )

    def find_inter_program_cycles(self) -> List[List[str]]:
        """Identifies circular call or invocation cycles between programs."""
        # Restrict graph to program-to-program call edges
        prog_adj: Dict[str, List[str]] = collections.defaultdict(list)
        call_edge_types = {"CALL_RESOLVED", "CICS_LINK", "CICS_XCTL"}

        for edge in self.edges:
            if edge.edge_type in call_edge_types:
                if edge.source in self.nodes and edge.target in self.nodes:
                    prog_adj[edge.source].append(edge.target)

        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: List[str] = []

        def dfs(node: str):
            visited.add(node)
            rec_stack.append(node)

            for neighbor in prog_adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Cycle found
                    cycle_start = rec_stack.index(neighbor)
                    cycle_path = rec_stack[cycle_start:] + [neighbor]
                    cycles.append(cycle_path)

            rec_stack.pop()

        for node in sorted(list(self.nodes.keys())):
            if self.nodes[node].node_type == "program" and node not in visited:
                dfs(node)

        return cycles

    def compute_metrics(self) -> Dict[str, Any]:
        """Calculates portfolio-wide topology metrics and coupling counts."""
        type_counts: Dict[str, int] = collections.defaultdict(int)
        for n in self.nodes.values():
            type_counts[n.node_type] += 1

        call_edges = [
            e for e in self.edges
            if e.edge_type in ("CALL_RESOLVED", "CALL_UNRESOLVED", "CALL_DYNAMIC", "CICS_LINK", "CICS_XCTL")
        ]
        total_calls = len(call_edges)
        resolved_calls = sum(1 for e in call_edges if e.edge_type in ("CALL_RESOLVED", "CICS_LINK", "CICS_XCTL") and not e.metadata.get("is_dynamic") and e.epistemic_status == "OBSERVED")
        unresolved_static = sum(1 for e in call_edges if e.edge_type == "CALL_UNRESOLVED")
        dynamic_calls = sum(1 for e in call_edges if e.edge_type == "CALL_DYNAMIC" or e.metadata.get("is_dynamic"))
        resolution_ratio = (resolved_calls / total_calls) if total_calls > 0 else 1.0

        # Shared DB2 tables (tables accessed by >= 2 programs)
        table_to_programs: Dict[str, Set[str]] = collections.defaultdict(set)
        for edge in self.edges:
            if edge.edge_type in ("PGM_SQL_READ", "PGM_SQL_WRITE"):
                table_to_programs[edge.target].add(edge.source)

        shared_tables: List[Dict[str, Any]] = []
        for tbl_id, progs in sorted(table_to_programs.items()):
            if len(progs) >= 2:
                tbl_node = self.nodes.get(tbl_id)
                tbl_label = tbl_node.label if tbl_node else tbl_id
                shared_tables.append({
                    "table_id": tbl_id,
                    "table_name": tbl_label,
                    "program_count": len(progs),
                    "programs": sorted(list(progs)),
                })

        # Shared Datasets (datasets accessed by >= 2 steps or programs)
        dsn_to_accessors: Dict[str, Set[str]] = collections.defaultdict(set)
        for edge in self.edges:
            if edge.edge_type in ("PGM_READ_DSN", "PGM_WRITE_DSN", "STEP_READ_DSN", "STEP_WRITE_DSN"):
                dsn_to_accessors[edge.target].add(edge.source)

        shared_datasets: List[Dict[str, Any]] = []
        for dsn_id, accessors in sorted(dsn_to_accessors.items()):
            if len(accessors) >= 2:
                dsn_node = self.nodes.get(dsn_id)
                dsn_label = dsn_node.label if dsn_node else dsn_id
                shared_datasets.append({
                    "dataset_id": dsn_id,
                    "dsn": dsn_label,
                    "accessor_count": len(accessors),
                    "accessors": sorted(list(accessors)),
                })

        # Cross-program coupling: count shared resources between each program pair (P1, P2)
        program_nodes = sorted([nid for nid, n in self.nodes.items() if n.node_type == "program"])
        pairwise_coupling: List[Dict[str, Any]] = []
        for i in range(len(program_nodes)):
            for j in range(i + 1, len(program_nodes)):
                p1 = program_nodes[i]
                p2 = program_nodes[j]

                # Shared tables
                p1_tables = {e.target for e in self.edges if e.source == p1 and e.edge_type in ("PGM_SQL_READ", "PGM_SQL_WRITE")}
                p2_tables = {e.target for e in self.edges if e.source == p2 and e.edge_type in ("PGM_SQL_READ", "PGM_SQL_WRITE")}
                common_tables = p1_tables & p2_tables

                # Shared datasets
                p1_dsns = {e.target for e in self.edges if e.source == p1 and e.edge_type in ("PGM_READ_DSN", "PGM_WRITE_DSN")}
                p2_dsns = {e.target for e in self.edges if e.source == p2 and e.edge_type in ("PGM_READ_DSN", "PGM_WRITE_DSN")}
                common_dsns = p1_dsns & p2_dsns

                # Direct calls
                calls_p1_p2 = [e for e in self.edges if e.source == p1 and e.target == p2]
                calls_p2_p1 = [e for e in self.edges if e.source == p2 and e.target == p1]

                coupling_score = len(common_tables) * 2 + len(common_dsns) + len(calls_p1_p2) + len(calls_p2_p1)
                if coupling_score > 0:
                    pairwise_coupling.append({
                        "program_a": p1,
                        "program_b": p2,
                        "coupling_score": coupling_score,
                        "shared_tables": sorted(list(common_tables)),
                        "shared_datasets": sorted(list(common_dsns)),
                        "direct_calls_a_to_b": len(calls_p1_p2),
                        "direct_calls_b_to_a": len(calls_p2_p1),
                    })

        cycles = self.find_inter_program_cycles()

        return {
            "node_counts": dict(type_counts),
            "edge_count": len(self.edges),
            "call_metrics": {
                "total_calls": total_calls,
                "resolved_calls": resolved_calls,
                "unresolved_static_calls": unresolved_static,
                "dynamic_calls": dynamic_calls,
                "call_resolution_ratio": round(resolution_ratio, 4),
            },
            "shared_tables_count": len(shared_tables),
            "shared_tables": shared_tables,
            "shared_datasets_count": len(shared_datasets),
            "shared_datasets": shared_datasets,
            "pairwise_coupling": sorted(pairwise_coupling, key=lambda x: x["coupling_score"], reverse=True),
            "inter_program_cycles": cycles,
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generates comprehensive structured audit and blast-radius report."""
        metrics = self.compute_metrics()

        # Compute blast radius for all programs
        program_radii: List[Dict[str, Any]] = []
        for nid, node in sorted(self.nodes.items()):
            if node.node_type == "program":
                radius = self.compute_blast_radius(nid)
                program_radii.append(radius.to_dict())

        return {
            "schema_version": self.SCHEMA_VERSION,
            "manifest_id": self.manifest_id,
            "metrics": metrics,
            "program_blast_radius": program_radii,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
        }

    def to_markdown_report(self) -> str:
        """Renders an executive and technical Markdown report with evidence and tables."""
        report = self.generate_report()
        metrics = report["metrics"]
        calls = metrics["call_metrics"]
        nodes = metrics["node_counts"]

        lines = [
            "# Application Portfolio Graph Report (Filar F5)",
            "",
            "> **Epistemic Status:** 🟢 **DELIVERED** — Multi-Program Dependency Map & Blast Radius.",
            f"> **Manifest ID:** `{self.manifest_id}`",
            "",
            "## 1. Portfolio Inventory Summary",
            "",
            "| Entity Type | Observed Count | Notes |",
            "| :--- | :--- | :--- |",
            f"| **COBOL Programs** | `{nodes.get('program', 0)}` | In-scope programs defined in manifest |",
            f"| **JCL Batch Jobs** | `{nodes.get('job', 0)}` | Workflows parsed from JCL streams |",
            f"| **JCL Job Steps** | `{nodes.get('step', 0)}` | Step execution units with `PGM=` / `COND=` |",
            f"| **Datasets / Files** | `{nodes.get('dataset', 0)}` | Sequential, VSAM, and temporary datasets |",
            f"| **DB2 Relational Tables** | `{nodes.get('db2_table', 0)}` | Tables accessed via `EXEC SQL` CRUD |",
            f"| **External / Unresolved Programs** | `{nodes.get('external_program', 0)}` | Preserved unknown boundaries |",
            "",
            "---",
            "",
            "## 2. Inter-Program Call Resolution Coverage",
            "",
            f"- **Total Invocations Observed:** `{calls['total_calls']}`",
            f"- **Resolved to In-Scope Programs:** `{calls['resolved_calls']}`",
            f"- **Unresolved Static Targets:** `{calls['unresolved_static_calls']}` (Missing catalog / external modules)",
            f"- **Dynamic Targets (Variables):** `{calls['dynamic_calls']}` (Preserved explicit unknown edges; no guessing)",
            f"- **Resolution Ratio:** `{calls['call_resolution_ratio'] * 100:.1f}%`",
            "",
            "---",
            "",
            "## 3. Shared Resource Coupling & Hotspots",
            "",
        ]

        if metrics["shared_tables"]:
            lines.extend([
                "### 3.1 Shared DB2 Tables",
                "",
                "| Table Name | Accessing Programs Count | Accessing Programs |",
                "| :--- | :--- | :--- |",
            ])
            for st in metrics["shared_tables"]:
                progs_fmt = ", ".join(f"`{p}`" for p in st["programs"])
                lines.append(f"| `{st['table_name']}` | `{st['program_count']}` | {progs_fmt} |")
            lines.append("")
        else:
            lines.extend(["*No shared DB2 tables observed across multiple programs.*", ""])

        if metrics["shared_datasets"]:
            lines.extend([
                "### 3.2 Shared Datasets / Files",
                "",
                "| Dataset Name (DSN) | Accessors Count | Accessors (Steps / Programs) |",
                "| :--- | :--- | :--- |",
            ])
            for sd in metrics["shared_datasets"]:
                acc_fmt = ", ".join(f"`{a}`" for a in sd["accessors"])
                lines.append(f"| `{sd['dsn']}` | `{sd['accessor_count']}` | {acc_fmt} |")
            lines.append("")
        else:
            lines.extend(["*No shared datasets observed across multiple steps/programs.*", ""])

        lines.extend([
            "---",
            "",
            "## 4. Multi-Program Blast Radius Analysis",
            "",
            "| Program ID | Downstream Reachable | Upstream Callers | Impact Ratio | Direct Callees / Resources |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])

        for br in report["program_blast_radius"]:
            out_preview = ", ".join(br["direct_outgoing"][:3])
            if len(br["direct_outgoing"]) > 3:
                out_preview += f" (+{len(br['direct_outgoing']) - 3} more)"
            out_cell = f"`{out_preview}`" if out_preview else "*None*"
            lines.append(
                f"| `{br['target_node']}` | `{br['downstream_impact_count']}` | "
                f"`{br['upstream_dependency_count']}` | `{br['impact_ratio'] * 100:.1f}%` | {out_cell} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 5. Architectural Cycles & Recommendations",
            "",
        ])
        if metrics["inter_program_cycles"]:
            lines.append("⚠️ **Inter-program cyclic call chains detected:**")
            for cyc in metrics["inter_program_cycles"]:
                lines.append(f"- `{' -> '.join(cyc)}`")
        else:
            lines.append("🟢 **No recursive inter-program call cycles detected.**")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "manifest_id": self.manifest_id,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "metadata": dict(self.metadata),
        }


class PortfolioGraphBuilder:
    """
    Constructs a unified PortfolioGraph from an explicit PortfolioManifest,
    parsing JCL streams, resolving COBOL and CICS calls, and joining shared resources.
    """

    def __init__(self, jcl_parser: Optional[JclParser] = None, call_resolver: Optional[CallResolver] = None):
        self.jcl_parser = jcl_parser or JclParser()
        self.call_resolver = call_resolver or CallResolver()

    def build(self, manifest: PortfolioManifest) -> PortfolioGraph:
        nodes: Dict[str, PortfolioNode] = {}
        edges: List[PortfolioEdge] = []

        # 1. Register COBOL Programs from manifest
        for prog in manifest.programs:
            node_id = f"PGM:{prog.program_id}"
            nodes[node_id] = PortfolioNode(
                id=node_id,
                label=prog.program_id,
                node_type="program",
                epistemic_status="OBSERVED",
                metadata={"source_path": prog.source_path, "metadata": prog.metadata},
            )

        # 2. Register Known Datasets from manifest
        for ds in manifest.known_datasets:
            node_id = f"DSN:{ds.dsn}"
            nodes[node_id] = PortfolioNode(
                id=node_id,
                label=ds.dsn,
                node_type="dataset",
                epistemic_status="OBSERVED" if ds.catalog_status == "CATALOGED" else "UNRESOLVED",
                metadata=ds.to_dict(),
            )

        # 3. Register Known Tables from manifest
        for tbl in manifest.known_tables:
            node_id = f"TABLE:{tbl.table_name}"
            nodes[node_id] = PortfolioNode(
                id=node_id,
                label=tbl.table_name,
                node_type="db2_table",
                epistemic_status="OBSERVED" if tbl.catalog_status == "CATALOGED" else "UNRESOLVED",
                metadata=tbl.to_dict(),
            )

        # 4. Parse JCL Jobs & Steps
        for jcl_entry in manifest.jobs:
            text = jcl_entry.source_text
            if not text and jcl_entry.source_path:
                try:
                    with open(jcl_entry.source_path, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except Exception:
                    text = ""

            parsed_jobs = self.jcl_parser.parse(text or "")
            for job in parsed_jobs:
                job_id = f"JOB:{job.job_name}"
                nodes[job_id] = PortfolioNode(
                    id=job_id,
                    label=job.job_name,
                    node_type="job",
                    epistemic_status="OBSERVED",
                    metadata=job.to_dict(),
                )

                prev_step_id: Optional[str] = None
                for step in job.steps:
                    step_id = f"STEP:{job.job_name}.{step.step_name}"
                    nodes[step_id] = PortfolioNode(
                        id=step_id,
                        label=f"{job.job_name}.{step.step_name}",
                        node_type="step",
                        epistemic_status="OBSERVED",
                        metadata=step.to_dict(),
                    )

                    # Edge: JOB -> STEP
                    edges.append(PortfolioEdge(
                        source=job_id,
                        target=step_id,
                        edge_type="JOB_STEP",
                        label="CONTAINS",
                    ))

                    # Edge: Sequential STEP -> STEP
                    if prev_step_id:
                        edges.append(PortfolioEdge(
                            source=prev_step_id,
                            target=step_id,
                            edge_type="STEP_SEQUENCE",
                            label="NEXT",
                        ))
                    prev_step_id = step_id

                    # Edge: STEP -> PROGRAM (EXEC PGM=...)
                    if step.program_name:
                        pgm_target_id = f"PGM:{step.program_name}"
                        if pgm_target_id not in nodes:
                            # Try prefix / suffix match
                            matched_pid = None
                            for existing_pid in [p.program_id for p in manifest.programs]:
                                if existing_pid == step.program_name or existing_pid.startswith(step.program_name) or step.program_name.startswith(existing_pid):
                                    matched_pid = existing_pid
                                    break
                            if matched_pid:
                                pgm_target_id = f"PGM:{matched_pid}"
                            else:
                                # External / unresolved program target
                                ext_id = f"EXT_PGM:{step.program_name}"
                                nodes[ext_id] = PortfolioNode(
                                    id=ext_id,
                                    label=step.program_name,
                                    node_type="external_program",
                                    epistemic_status="UNRESOLVED",
                                )
                                pgm_target_id = ext_id

                        edges.append(PortfolioEdge(
                            source=step_id,
                            target=pgm_target_id,
                            edge_type="STEP_EXEC",
                            label=f"EXEC {step.program_name}",
                        ))

                    # DD Statements
                    for dd in step.dds:
                        if dd.dsn:
                            dsn_id = f"DSN:{dd.dsn}"
                            if dsn_id not in nodes:
                                nodes[dsn_id] = PortfolioNode(
                                    id=dsn_id,
                                    label=dd.dsn,
                                    node_type="dataset",
                                    epistemic_status="OBSERVED",
                                    metadata=dd.to_dict(),
                                )

                            edge_type = "STEP_READ_DSN" if dd.access_intent in ("READ", "READ_WRITE") else "STEP_WRITE_DSN"
                            edges.append(PortfolioEdge(
                                source=step_id,
                                target=dsn_id,
                                edge_type=edge_type,
                                label=f"DD:{dd.dd_name} ({dd.access_intent})",
                                metadata=dd.to_dict(),
                            ))

        # 5. Resolve Inter-Program Calls and Resource Accesses
        calls_by_prog, accesses_by_prog = self.call_resolver.resolve_portfolio(manifest)

        for caller_pid, calls in calls_by_prog.items():
            caller_node_id = f"PGM:{caller_pid}"
            for call in calls:
                if call.resolution_status == "RESOLVED" and call.resolved_target:
                    target_node_id = f"PGM:{call.resolved_target}"
                    edge_type = "CALL_RESOLVED"
                    if call.call_type.startswith("CICS_"):
                        edge_type = call.call_type
                    edges.append(PortfolioEdge(
                        source=caller_node_id,
                        target=target_node_id,
                        edge_type=edge_type,
                        label=f"CALL {call.resolved_target}",
                        epistemic_status="OBSERVED",
                        metadata=call.to_dict(),
                    ))
                else:
                    # Unresolved external or dynamic call
                    ext_id = f"EXT_PGM:{call.target_name}"
                    if ext_id not in nodes:
                        nodes[ext_id] = PortfolioNode(
                            id=ext_id,
                            label=call.target_name,
                            node_type="external_program",
                            epistemic_status="UNRESOLVED",
                            metadata={"is_dynamic": call.is_dynamic},
                        )

                    edge_type = "CALL_DYNAMIC" if call.is_dynamic else "CALL_UNRESOLVED"
                    if call.call_type.startswith("CICS_"):
                        edge_type = call.call_type

                    edges.append(PortfolioEdge(
                        source=caller_node_id,
                        target=ext_id,
                        edge_type=edge_type,
                        label=f"{edge_type} {call.target_name}",
                        epistemic_status="UNRESOLVED",
                        metadata=call.to_dict(),
                    ))

        # 6. Connect Resource Accesses (DB2 tables & Datasets)
        for pid, accesses in accesses_by_prog.items():
            prog_node_id = f"PGM:{pid}"
            for acc in accesses:
                if acc.resource_type == "DB2_TABLE":
                    tbl_id = f"TABLE:{acc.resource_name}"
                    if tbl_id not in nodes:
                        nodes[tbl_id] = PortfolioNode(
                            id=tbl_id,
                            label=acc.resource_name,
                            node_type="db2_table",
                            epistemic_status="OBSERVED",
                        )
                    edge_type = "PGM_SQL_WRITE" if acc.access_mode == "WRITE" else "PGM_SQL_READ"
                    edges.append(PortfolioEdge(
                        source=prog_node_id,
                        target=tbl_id,
                        edge_type=edge_type,
                        label=f"SQL {acc.operation}",
                        metadata=acc.to_dict(),
                    ))

                elif acc.resource_type == "FILE_DATASET":
                    dsn_id = f"DSN:{acc.resource_name}"
                    if dsn_id not in nodes:
                        nodes[dsn_id] = PortfolioNode(
                            id=dsn_id,
                            label=acc.resource_name,
                            node_type="dataset",
                            epistemic_status="OBSERVED",
                        )
                    edge_type = "PGM_WRITE_DSN" if acc.access_mode in ("WRITE", "READ_WRITE") else "PGM_READ_DSN"
                    edges.append(PortfolioEdge(
                        source=prog_node_id,
                        target=dsn_id,
                        edge_type=edge_type,
                        label=f"FILE {acc.operation}",
                        metadata=acc.to_dict(),
                    ))

        return PortfolioGraph(
            manifest_id=manifest.manifest_id,
            nodes=nodes,
            edges=edges,
            metadata={"manifest_name": manifest.name},
        )
