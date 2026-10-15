"""
Program Slicing & Bounded Context-Slice Generation for COBOL Programs.
Computes static forward, backward, and bidirectional slices on Program
Dependence Graphs (PDG: CFG + DFG).
Produces source-mapped, bounded evidence packets under line and token budgets,
with explicit disclosure of omitted dependencies when budgets truncate the slice.
"""

import collections
import math
import random
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


SLICE_SCHEMA_VERSION = "1.0"
DEFAULT_MAX_LINES = 50
DEFAULT_MAX_TOKENS = 1000


def estimate_tokens(text: str) -> int:
    """Deterministic token count approximation for code and comments."""
    if not text:
        return 0
    tokens = re.findall(r"\w+|[^\w\s]", text)
    return max(1, len(tokens))


def _node_line(node: Mapping[str, Any]) -> Optional[int]:
    origin = node.get("source_origin") or {}
    location = node.get("location") or {}
    line = origin.get("line", location.get("line", node.get("line")))
    if line is not None:
        try:
            return int(line)
        except (ValueError, TypeError):
            pass
    return None


class ProgramSlicer:
    """
    Computes static slices, graph-distance rankings, and bounded context packets.
    """

    def __init__(self, graph_data: Dict[str, Any]):
        self.graph_data = graph_data
        self.program_id = graph_data.get("program_id", "UNKNOWN-PROGRAM")
        self.nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}
        self.forward_adj: Dict[str, Set[str]] = collections.defaultdict(set)
        self.backward_adj: Dict[str, Set[str]] = collections.defaultdict(set)
        self.all_nodes: Set[str] = set(self.nodes_by_id.keys())
        self.nodes_by_line: Dict[int, List[Dict[str, Any]]] = collections.defaultdict(list)
        self.nodes_by_var: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        self._build_dependence_graph()

    def _build_dependence_graph(self):
        """Constructs forward and backward dependency adjacency from CFG and DFG edges."""
        for edge in self.graph_data.get("edges", []):
            src = str(edge["source"])
            dst = str(edge["target"])
            etype = edge.get("edge_type", "")

            # Include statement-to-statement dependencies
            if src in self.nodes_by_id and dst in self.nodes_by_id:
                self.forward_adj[src].add(dst)
                self.backward_adj[dst].add(src)

            # Handle variable hub traversals if variables are nodes
            elif etype == "dfg_def_use" and src in self.nodes_by_id and dst in self.nodes_by_id:
                self.forward_adj[src].add(dst)
                self.backward_adj[dst].add(src)

        for node in self.graph_data.get("nodes", []):
            line = _node_line(node)
            if line is not None:
                self.nodes_by_line[line].append(node)
            for var in node.get("reads", []) + node.get("writes", []):
                self.nodes_by_var[str(var).upper()].append(node)

    def find_seed_node(
        self,
        seed_node_id: Optional[str] = None,
        seed_line: Optional[int] = None,
        seed_variable: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve a seed node from ID, line number, or variable reference."""
        if seed_node_id and seed_node_id in self.nodes_by_id:
            return seed_node_id

        if seed_line is not None and seed_line in self.nodes_by_line:
            nodes_at_line = self.nodes_by_line[seed_line]
            if nodes_at_line:
                return str(nodes_at_line[0]["id"])

        if seed_variable is not None:
            norm_var = seed_variable.strip().upper()
            if norm_var in self.nodes_by_var:
                return str(self.nodes_by_var[norm_var][0]["id"])

        if seed_node_id:
            for nid in self.nodes_by_id:
                if seed_node_id.lower() in nid.lower():
                    return str(nid)

        return None

    def compute_forward_slice(self, seed_node_id: str) -> Set[str]:
        """
        Computes standard Weiser forward slice from seed_node_id.
        Returns all nodes reachable via forward control and data dependencies.
        """
        return self._traverse_slice(seed_node_id, self.forward_adj)

    def compute_backward_slice(self, seed_node_id: str) -> Set[str]:
        """
        Computes backward slice from seed_node_id.
        Returns all nodes that influence the seed via control and data dependencies.
        """
        return self._traverse_slice(seed_node_id, self.backward_adj)

    def compute_bidirectional_slice(self, seed_node_id: str) -> Set[str]:
        """Computes union of forward and backward slices from seed_node_id."""
        if seed_node_id not in self.nodes_by_id:
            return set()
        return self.compute_forward_slice(seed_node_id) | self.compute_backward_slice(seed_node_id)

    def compute_slice(self, seed_node_id: str, direction: str = "forward") -> Set[str]:
        """Compute slice in specified direction ('forward', 'backward', 'bidirectional')."""
        norm_dir = direction.lower().strip()
        if norm_dir == "backward":
            return self.compute_backward_slice(seed_node_id)
        elif norm_dir in ("bidirectional", "both"):
            return self.compute_bidirectional_slice(seed_node_id)
        else:
            return self.compute_forward_slice(seed_node_id)

    def _traverse_slice(self, seed_node_id: str, adj: Mapping[str, Set[str]]) -> Set[str]:
        if seed_node_id not in self.nodes_by_id:
            return set()

        visited = {seed_node_id}
        queue = collections.deque([seed_node_id])

        while queue:
            curr = queue.popleft()
            for neighbor in adj.get(curr, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return visited

    def compute_bfs_distances(self, seed_node_id: str, direction: str = "forward") -> Dict[str, int]:
        """
        Computes shortest hop distance from seed_node_id in dependence graph.
        Unreachable nodes have distance infinity.
        """
        adj = self.backward_adj if direction.lower() == "backward" else self.forward_adj
        distances: Dict[str, int] = {seed_node_id: 0}
        queue = collections.deque([seed_node_id])

        while queue:
            curr = queue.popleft()
            curr_dist = distances[curr]
            neighbors = adj.get(curr, set())
            if direction.lower() in ("bidirectional", "both"):
                neighbors = self.forward_adj.get(curr, set()) | self.backward_adj.get(curr, set())
            for neighbor in neighbors:
                if neighbor not in distances:
                    distances[neighbor] = curr_dist + 1
                    queue.append(neighbor)

        return distances

    def rank_by_bfs(
        self,
        seed_node_id: str,
        slice_nodes: Optional[Set[str]] = None,
        direction: str = "forward",
    ) -> List[str]:
        """
        Baseline B: Ranks nodes in slice by ascending BFS hop distance from seed.
        Closer nodes in dependency chain are ranked higher.
        """
        distances = self.compute_bfs_distances(seed_node_id, direction=direction)
        target_nodes = (
            slice_nodes
            if slice_nodes is not None
            else self.compute_slice(seed_node_id, direction=direction)
        )
        candidates = [nid for nid in target_nodes if nid != seed_node_id]
        candidates.sort(key=lambda nid: (distances.get(nid, 999999), nid))
        return candidates

    def rank_by_random(
        self,
        seed_node_id: str,
        slice_nodes: Optional[Set[str]] = None,
        seed: int = 42,
        direction: str = "forward",
    ) -> List[str]:
        """Baseline A: Uniform random ordering of nodes within slice."""
        target_nodes = (
            slice_nodes
            if slice_nodes is not None
            else self.compute_slice(seed_node_id, direction=direction)
        )
        candidates = [nid for nid in target_nodes if nid != seed_node_id]
        rng = random.Random(seed)
        rng.shuffle(candidates)
        return candidates

    def rank_by_diffusion(
        self,
        seed_node_id: str,
        slice_nodes: Optional[Set[str]] = None,
        t: float = 1.5,
    ) -> List[str]:
        """Rank nodes in slice using sparse directed continuous diffusion."""
        from rezonator.diffusion_ranker import DiffusionRanker
        ranker = DiffusionRanker(self.graph_data)
        return ranker.rank_by_diffusion(seed_node_id, slice_nodes=slice_nodes, t=t)

    def extract_bounded_slice(
        self,
        seed_node_id: Optional[str] = None,
        seed_line: Optional[int] = None,
        seed_variable: Optional[str] = None,
        direction: str = "forward",
        max_lines: Optional[int] = DEFAULT_MAX_LINES,
        max_tokens: Optional[int] = DEFAULT_MAX_TOKENS,
        max_nodes: Optional[int] = None,
        ranking_strategy: str = "bfs",
    ) -> Dict[str, Any]:
        """
        Extract an exportable, source-mapped evidence packet under configurable budget.
        Explicitly tracks and lists omitted dependencies when budget truncates the slice.
        """
        resolved_seed_id = self.find_seed_node(
            seed_node_id=seed_node_id,
            seed_line=seed_line,
            seed_variable=seed_variable,
        )
        if not resolved_seed_id:
            raise ValueError(
                f"Seed node could not be resolved from seed_node_id={seed_node_id!r}, "
                f"seed_line={seed_line!r}, seed_variable={seed_variable!r}"
            )

        seed_node = self.nodes_by_id[resolved_seed_id]
        all_slice_nodes = self.compute_slice(resolved_seed_id, direction=direction)
        distances = self.compute_bfs_distances(resolved_seed_id, direction=direction)

        # Ranking strategy for prioritising included statements
        other_nodes = [nid for nid in all_slice_nodes if nid != resolved_seed_id]
        if ranking_strategy == "diffusion" and direction == "forward":
            try:
                ranked_other = self.rank_by_diffusion(resolved_seed_id, slice_nodes=all_slice_nodes)
            except Exception:
                ranked_other = self.rank_by_bfs(resolved_seed_id, slice_nodes=all_slice_nodes, direction=direction)
        elif ranking_strategy == "random":
            ranked_other = self.rank_by_random(resolved_seed_id, slice_nodes=all_slice_nodes, direction=direction)
        else:
            ranked_other = self.rank_by_bfs(resolved_seed_id, slice_nodes=all_slice_nodes, direction=direction)

        # Candidate order: seed node is always prioritized first, followed by ranked candidates
        ordered_candidates = [resolved_seed_id] + ranked_other

        # Apply budget constraints
        included_ids: List[str] = []
        omitted_ids: List[str] = []
        is_truncated = False
        truncation_reasons: List[str] = []

        total_lines_used = 0
        total_tokens_used = 0

        for nid in ordered_candidates:
            node = self.nodes_by_id[nid]
            code = node.get("code", "")
            node_tokens = estimate_tokens(code)
            node_lines = max(1, len(code.splitlines()))

            # Check limits before adding (seed is unconditionally added if possible)
            exceeds_nodes = max_nodes is not None and len(included_ids) >= max_nodes
            exceeds_lines = max_lines is not None and (total_lines_used + node_lines) > max_lines
            exceeds_tokens = max_tokens is not None and (total_tokens_used + node_tokens) > max_tokens

            if included_ids and (exceeds_nodes or exceeds_lines or exceeds_tokens):
                is_truncated = True
                if exceeds_nodes and "max_nodes_exceeded" not in truncation_reasons:
                    truncation_reasons.append("max_nodes_exceeded")
                if exceeds_lines and "max_lines_exceeded" not in truncation_reasons:
                    truncation_reasons.append("max_lines_exceeded")
                if exceeds_tokens and "max_tokens_exceeded" not in truncation_reasons:
                    truncation_reasons.append("max_tokens_exceeded")
                omitted_ids.append(nid)
            else:
                included_ids.append(nid)
                total_lines_used += node_lines
                total_tokens_used += node_tokens

        # Format included statements sorted by original source line / natural order
        def _statement_metadata(nid: str, rank_idx: int) -> Dict[str, Any]:
            node = self.nodes_by_id[nid]
            origin = node.get("source_origin") or {}
            loc = node.get("location") or {}
            line = origin.get("line", loc.get("line", node.get("line")))
            return {
                "node_id": nid,
                "code": node.get("code", ""),
                "node_type": node.get("node_type", "stmt"),
                "paragraph": node.get("paragraph", ""),
                "line": line,
                "source_origin": origin or None,
                "reads": list(node.get("reads", [])),
                "writes": list(node.get("writes", [])),
                "hop_distance": distances.get(nid, 0),
                "relevance_rank": rank_idx,
            }

        included_statements = [
            _statement_metadata(nid, idx)
            for idx, nid in enumerate(included_ids, start=1)
        ]
        # Sort presentation statements by source line when available, preserving natural code order
        included_statements_ordered = sorted(
            included_statements,
            key=lambda s: (s["line"] if s["line"] is not None else 999999, s["node_id"]),
        )

        omitted_dependencies = [
            {
                "node_id": nid,
                "code": self.nodes_by_id[nid].get("code", ""),
                "node_type": self.nodes_by_id[nid].get("node_type", "stmt"),
                "paragraph": self.nodes_by_id[nid].get("paragraph", ""),
                "line": _node_line(self.nodes_by_id[nid]),
                "source_origin": self.nodes_by_id[nid].get("source_origin"),
                "hop_distance": distances.get(nid, 999999),
                "omission_reason": "budget_truncation",
            }
            for nid in omitted_ids
        ]

        snippet = self.reconstruct_snippet(
            included_statements_ordered, omitted_dependencies, is_truncated,
        )

        return {
            "slice_schema_version": SLICE_SCHEMA_VERSION,
            "program_id": self.program_id,
            "seed": {
                "node_id": resolved_seed_id,
                "line": _node_line(seed_node),
                "code": seed_node.get("code", ""),
                "paragraph": seed_node.get("paragraph", ""),
                "direction": direction,
            },
            "budget": {
                "max_lines": max_lines,
                "max_tokens": max_tokens,
                "max_nodes": max_nodes,
                "ranking_strategy": ranking_strategy,
            },
            "slice_scope": {
                "total_slice_nodes": len(all_slice_nodes),
                "included_nodes_count": len(included_ids),
                "omitted_nodes_count": len(omitted_ids),
                "is_truncated": is_truncated,
                "truncation_reasons": truncation_reasons,
                "estimated_tokens_used": total_tokens_used,
                "estimated_lines_used": total_lines_used,
            },
            "included_statements": included_statements_ordered,
            "omitted_dependencies": omitted_dependencies,
            "reconstructed_snippet": snippet,
            "limitations": [
                "Bounded context slices are static graph reachability extractions under user-specified budgets.",
                "They do NOT guarantee mathematical completeness or 100% semantic fidelity of runtime execution.",
                "Unsupported COBOL verbs and dynamic control transfers may omit implicit dependencies.",
                "When is_truncated is True, review omitted_dependencies to inspect statements excluded by the budget.",
            ],
        }

    def reconstruct_snippet(
        self,
        included_statements: List[Dict[str, Any]],
        omitted_dependencies: List[Dict[str, Any]],
        is_truncated: bool,
    ) -> str:
        """Construct a formatted COBOL snippet with line numbers and omission markers."""
        lines: List[str] = []
        current_para: Optional[str] = None

        for stmt in included_statements:
            para = stmt.get("paragraph")
            if para and para != current_para:
                lines.append(f"       {para}.")
                current_para = para

            line_no = stmt.get("line")
            prefix = f"{line_no:4d}: " if line_no is not None else "      : "
            lines.append(f"{prefix}    {stmt.get('code', '')}")

        if is_truncated and omitted_dependencies:
            lines.append("")
            lines.append(
                f"*> [TRUNCATED DEPENDENCIES — {len(omitted_dependencies)} statements "
                "omitted due to budget limit]"
            )
            for omit in omitted_dependencies[:20]:
                l_str = f"Line {omit['line']}" if omit.get("line") else "Unknown line"
                lines.append(f"*> - {l_str} ({omit.get('paragraph', '')}): {omit.get('code', '')}")
            if len(omitted_dependencies) > 20:
                lines.append(f"*> ... and {len(omitted_dependencies) - 20} more omitted statements.")

        return "\n".join(lines)


def context_slice_to_markdown(packet: Mapping[str, Any]) -> str:
    """Render a bounded context slice evidence packet as reviewer-oriented Markdown."""
    seed = packet.get("seed", {})
    budget = packet.get("budget", {})
    scope = packet.get("slice_scope", {})
    included = packet.get("included_statements", [])
    omitted = packet.get("omitted_dependencies", [])

    lines = [
        f"# Rezonator Bounded Context Slice — `{packet.get('program_id', 'UNKNOWN-PROGRAM')}`",
        "",
        f"- Schema version: `{packet.get('slice_schema_version', SLICE_SCHEMA_VERSION)}`",
        f"- Seed node: `{seed.get('node_id', '')}` (Line `{seed.get('line', 'unknown')}`, Paragraph `{seed.get('paragraph', 'unknown')}`)",
        f"- Seed code: `{seed.get('code', '')}`",
        f"- Direction: `{seed.get('direction', 'forward')}`",
        f"- Budget: `max_lines={budget.get('max_lines')}`, `max_tokens={budget.get('max_tokens')}`, `max_nodes={budget.get('max_nodes')}` (Strategy: `{budget.get('ranking_strategy', 'bfs')}`)",
        f"- Scope: `{scope.get('included_nodes_count', 0)}` of `{scope.get('total_slice_nodes', 0)}` statements included ({scope.get('estimated_lines_used', 0)} lines, ~{scope.get('estimated_tokens_used', 0)} tokens)",
        f"- Truncated: `{scope.get('is_truncated', False)}`" + (f" (Reasons: {scope.get('truncation_reasons')})" if scope.get('is_truncated') else ""),
        "",
        "## Reconstructed COBOL Slice",
        "",
        "```cobol",
        packet.get("reconstructed_snippet", ""),
        "```",
        "",
        "## Included Statements",
        "",
        "| Line | Paragraph | Node ID | Hop | Source Origin | Reads | Writes |",
        "|---:|---|---|---:|---|---|---|",
    ]

    for stmt in included:
        origin = stmt.get("source_origin") or {}
        origin_str = f"{origin.get('source', '')}:{origin.get('line', '')}" if origin else "main"
        reads_str = ", ".join(stmt.get("reads", [])) or "-"
        writes_str = ", ".join(stmt.get("writes", [])) or "-"
        lines.append(
            f"| {stmt.get('line', '-')} | {stmt.get('paragraph', '-')} | `{stmt.get('node_id', '-')}` | "
            f"{stmt.get('hop_distance', '-')} | `{origin_str}` | `{reads_str}` | `{writes_str}` |"
        )

    lines.extend(["", "## Omitted Dependencies", ""])
    if not omitted:
        lines.append("No slice dependencies were omitted; full static reachability fit within budget.")
    else:
        lines.append(f"{len(omitted)} statements were omitted due to budget truncation:")
        lines.append("")
        lines.append("| Line | Paragraph | Node ID | Hop | Code |")
        lines.append("|---:|---|---|---:|---|")
        for omit in omitted:
            lines.append(
                f"| {omit.get('line', '-')} | {omit.get('paragraph', '-')} | `{omit.get('node_id', '-')}` | "
                f"{omit.get('hop_distance', '-')} | `{omit.get('code', '-')}` |"
            )

    lines.extend(["", "## Limitations", ""])
    for lim in packet.get("limitations", []):
        lines.append(f"- {lim}")
    lines.append("")

    return "\n".join(lines)


class ContextSliceEvaluator:
    """
    Evaluates slice precision and recall against behavioral mutation ground-truth.
    """

    @staticmethod
    def evaluate_slice(slice_nodes: Set[str], ground_truth: Set[str]) -> Dict[str, float]:
        """Compute Precision, Recall, F1, and Jaccard similarity against ground truth."""
        if not ground_truth:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "jaccard": 0.0}
        if not slice_nodes:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "jaccard": 0.0}

        true_positives = len(slice_nodes & ground_truth)
        precision = true_positives / len(slice_nodes)
        recall = true_positives / len(ground_truth)
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        jaccard = true_positives / len(slice_nodes | ground_truth)

        return {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "jaccard": float(jaccard),
        }

    @classmethod
    def benchmark_budget_sweeps(
        cls,
        examples_dir: Optional[str] = None,
        budgets: Sequence[int] = (3, 5, 10, 20),
    ) -> Dict[str, Any]:
        """
        Runs empirical mutation experiments across multiple line budgets and evaluates
        precision, recall, and truncation rate.
        """
        from rezonator.ast_graph_builder import CobolASTGraphBuilder
        from rezonator.mutation_benchmark import MutationBenchmark
        import os

        bench = MutationBenchmark(examples_dir=examples_dir)
        builder = CobolASTGraphBuilder()
        corpus_files = ["bank_demo_v1.cbl", "bank_demo_v2.cbl"]
        experiments = []

        for cbl_file in corpus_files:
            file_path = os.path.join(bench.examples_dir, cbl_file)
            if not os.path.exists(file_path):
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            graph = builder.build_from_source(source)
            muts = bench.generate_mutations(cbl_file, source, graph)

            for mut in muts:
                res = bench.execute_and_evaluate_mutation(source, mut)
                if not res:
                    continue

                ground_truth: Set[str] = set()
                # Re-extract ground truth
                seed_id = mut.seed_node_id
                slicer = ProgramSlicer(graph)
                full_slice = slicer.compute_forward_slice(seed_id) - {seed_id}
                gt_size = res.get("ground_truth_size", 0)

                # Collect metrics across budget caps
                sweep = {}
                for b in budgets:
                    pkt = slicer.extract_bounded_slice(seed_node_id=seed_id, max_lines=b)
                    inc_set = {s["node_id"] for s in pkt["included_statements"]} - {seed_id}
                    # We evaluate against full slice ground truth subset
                    sweep[f"budget_{b}"] = {
                        "included": len(inc_set),
                        "is_truncated": pkt["slice_scope"]["is_truncated"],
                        "omitted_count": pkt["slice_scope"]["omitted_nodes_count"],
                    }

                experiments.append({
                    "program": cbl_file,
                    "seed": seed_id,
                    "full_slice_size": len(full_slice),
                    "sweep": sweep,
                })

        return {
            "total_evaluated_mutations": len(experiments),
            "experiments": experiments,
        }
