"""
Mutation Benchmark & Hypothesis H1 Testing Engine for Rezonator.
Systematically evaluates whether Directed Heat Diffusion u(t) = exp((P^T - I)t) u_0
predicts genuinely affected statements better than:
  (a) Random order in forward slice
  (b) Classical BFS hop distance in forward slice

Computes Precision@k, Recall@k, MAP, and MRR across a corpus of COBOL programs.
Enforces the pre-set falsification criterion (Diffusion beats BFS by >= 10 p.p.).
"""

import glob
import os
import re
import numpy as np
from typing import Dict, List, Set, Any, Tuple, Optional

from rezonator.ast_graph_builder import CobolASTGraphBuilder
from rezonator.cobol_runtime import CobolRuntime
from rezonator.program_slicer import ProgramSlicer
from rezonator.diffusion_ranker import DiffusionRanker


class MutationCase:
    def __init__(self, program_name: str, seed_node_id: str, orig_code: str, mut_code: str, description: str):
        self.program_name = program_name
        self.seed_node_id = seed_node_id
        self.orig_code = orig_code
        self.mut_code = mut_code
        self.description = description


class MutationBenchmark:
    """
    Automated experimental benchmark for evaluating Hypothesis H1.
    """

    def __init__(self, examples_dir: Optional[str] = None):
        self.examples_dir = examples_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
        self.builder = CobolASTGraphBuilder()
        self.runtime = CobolRuntime()

    def generate_mutations(self, program_name: str, source_code: str, graph_data: Dict[str, Any]) -> List[MutationCase]:
        """
        Discovers all semantically valid statement mutation candidates for a given program.
        """
        mutations: List[MutationCase] = []
        nodes = graph_data.get("nodes", [])

        for node in nodes:
            nid = node["id"]
            code = node.get("code", "")
            up = code.upper()

            # 1. Mutate Arithmetic operators: SUBTRACT <-> ADD
            if up.startswith("SUBTRACT ") or up.startswith("SUB "):
                m = re.match(r'(?:SUBTRACT|SUB)\s+(.+?)\s+FROM\s+(.+)', code, re.IGNORECASE)
                if m:
                    src, dest = m.group(1).strip(), m.group(2).strip()
                    mut_code = f"ADD {src} TO {dest}"
                    mutations.append(MutationCase(program_name, nid, code, mut_code, f"Invert SUBTRACT to ADD: {dest}"))

            elif up.startswith("ADD "):
                m = re.match(r'ADD\s+(.+?)\s+TO\s+(.+)', code, re.IGNORECASE)
                if m:
                    src, dest = m.group(1).strip(), m.group(2).strip()
                    mut_code = f"SUBTRACT {src} FROM {dest}"
                    mutations.append(MutationCase(program_name, nid, code, mut_code, f"Invert ADD to SUBTRACT: {dest}"))

            # 2. Mutate Relational Condition in IF: <= <-> >, = <-> !=, > <-> <=
            elif node["node_type"] == "branch" and up.startswith("IF "):
                cond_body = code[3:].strip()
                if "<=" in cond_body:
                    mut_code = "IF " + cond_body.replace("<=", ">", 1)
                    mutations.append(MutationCase(program_name, nid, code, mut_code, "Invert condition <= to >"))
                elif ">=" in cond_body:
                    mut_code = "IF " + cond_body.replace(">=", "<", 1)
                    mutations.append(MutationCase(program_name, nid, code, mut_code, "Invert condition >= to <"))
                elif " = " in cond_body:
                    mut_code = "IF " + cond_body.replace(" = ", " != ", 1)
                    mutations.append(MutationCase(program_name, nid, code, mut_code, "Invert condition = to !="))
                elif " > " in cond_body:
                    mut_code = "IF " + cond_body.replace(" > ", " <= ", 1)
                    mutations.append(MutationCase(program_name, nid, code, mut_code, "Invert condition > to <="))
                elif " < " in cond_body:
                    mut_code = "IF " + cond_body.replace(" < ", " >= ", 1)
                    mutations.append(MutationCase(program_name, nid, code, mut_code, "Invert condition < to >="))

            # 3. Mutate COMPUTE expressions: * <-> /, + <-> -
            elif up.startswith("COMPUTE "):
                m = re.match(r'COMPUTE\s+([A-Za-z0-9_-]+)\s*=\s*(.+)', code, re.IGNORECASE)
                if m:
                    dest, expr = m.group(1).strip(), m.group(2).strip()
                    if " * " in expr:
                        mut_expr = expr.replace(" * ", " / ", 1)
                        mutations.append(MutationCase(program_name, nid, code, f"COMPUTE {dest} = {mut_expr}", "Mutate * to / in COMPUTE"))
                    elif " + " in expr:
                        mut_expr = expr.replace(" + ", " - ", 1)
                        mutations.append(MutationCase(program_name, nid, code, f"COMPUTE {dest} = {mut_expr}", "Mutate + to - in COMPUTE"))
                    elif " - " in expr:
                        mut_expr = expr.replace(" - ", " + ", 1)
                        mutations.append(MutationCase(program_name, nid, code, f"COMPUTE {dest} = {mut_expr}", "Mutate - to + in COMPUTE"))

            # 4. Mutate Constants in MOVE statements
            elif up.startswith("MOVE "):
                m = re.match(r'MOVE\s+(.+?)\s+TO\s+(.+)', code, re.IGNORECASE)
                if m:
                    src, dest = m.group(1).strip(), m.group(2).strip()
                    src_clean = src.strip('"').strip("'")
                    if src_clean == "OKAY":
                        mut_code = f'MOVE "FAIL" TO {dest}'
                        mutations.append(MutationCase(program_name, nid, code, mut_code, f'Mutate MOVE "OKAY" to "FAIL"'))
                    elif src_clean == "FAIL":
                        mut_code = f'MOVE "OKAY" TO {dest}'
                        mutations.append(MutationCase(program_name, nid, code, mut_code, f'Mutate MOVE "FAIL" to "OKAY"'))
                    elif src_clean.isdigit():
                        mut_val = int(src_clean) + 5
                        mut_code = f'MOVE {mut_val} TO {dest}'
                        mutations.append(MutationCase(program_name, nid, code, mut_code, f'Mutate MOVE integer constant'))

        return mutations

    def execute_and_evaluate_mutation(self, source_code: str, mut: MutationCase) -> Optional[Dict[str, Any]]:
        """
        Executes baseline and mutant, determines ground truth affected set G,
        and computes Precision@k, Recall@k, MAP, and MRR for Diffusion, BFS, and Random.
        """
        # 1. Parse baseline
        try:
            base_graph = self.builder.build_from_source(source_code)
        except Exception:
            return None

        # 2. Apply mutation to source text
        # Try exact replacement
        if mut.orig_code not in source_code:
            # Try fuzzy replacement on statement pattern
            orig_pattern = re.escape(mut.orig_code).replace(r'\ ', r'\s+')
            if not re.search(orig_pattern, source_code, re.IGNORECASE):
                return None
            mutated_code = re.sub(orig_pattern, mut.mut_code, source_code, count=1, flags=re.IGNORECASE)
        else:
            mutated_code = source_code.replace(mut.orig_code, mut.mut_code, 1)

        # 3. Execute baseline and mutated programs
        try:
            base_run = self.runtime.run(source_code, max_steps=100)
            mut_run = self.runtime.run(mutated_code, max_steps=100)
        except Exception:
            return None

        # 4. Check if mutant produced any behavioral difference
        diff_vars = {k for k in base_run.variables if base_run.variables[k] != mut_run.variables.get(k)}
        diff_trace = base_run.trace != mut_run.trace

        if not diff_vars and not diff_trace:
            # Stillborn / unkilled mutant
            return None

        # 5. Determine Ground Truth set of affected downstream nodes G
        ground_truth: Set[str] = set()
        
        # Any node whose execution frequency differs
        base_counts = {}
        for nid in base_run.trace:
            base_counts[nid] = base_counts.get(nid, 0) + 1
        mut_counts = {}
        for nid in mut_run.trace:
            mut_counts[nid] = mut_counts.get(nid, 0) + 1

        all_traced = set(base_counts.keys()) | set(mut_counts.keys())
        for nid in all_traced:
            if base_counts.get(nid, 0) != mut_counts.get(nid, 0):
                ground_truth.add(nid)

        # Any node that writes a variable that changed
        for node in base_graph.get("nodes", []):
            nid = node["id"]
            writes = set(node.get("writes", []))
            if writes & diff_vars:
                ground_truth.add(nid)

        # We evaluate prediction of DOWNSTREAM affected nodes (exclude seed itself)
        ground_truth.discard(mut.seed_node_id)

        if not ground_truth:
            return None

        # 6. Compute Slicing and Rankings
        slicer = ProgramSlicer(base_graph)
        forward_slice = slicer.compute_forward_slice(mut.seed_node_id)
        forward_slice.discard(mut.seed_node_id)

        if not forward_slice:
            return None

        # Rankers
        rank_bfs = slicer.rank_by_bfs(mut.seed_node_id, forward_slice)
        rank_rand = slicer.rank_by_random(mut.seed_node_id, forward_slice, seed=123)

        diff_ranker = DiffusionRanker(base_graph)
        rank_diff = diff_ranker.rank_by_diffusion(mut.seed_node_id, forward_slice, t=1.5)

        # 7. Evaluate Metrics
        def compute_metrics(ranking: List[str], ground_truth: Set[str]) -> Dict[str, float]:
            metrics = {}
            for k in [1, 3, 5]:
                top_k = set(ranking[:k])
                p_k = len(top_k & ground_truth) / max(1, min(k, len(ranking)))
                r_k = len(top_k & ground_truth) / max(1, len(ground_truth))
                metrics[f"precision@{k}"] = p_k
                metrics[f"recall@{k}"] = r_k

            # Average Precision (AP)
            hits = 0
            sum_p = 0.0
            for rank_idx, cand in enumerate(ranking, 1):
                if cand in ground_truth:
                    hits += 1
                    sum_p += hits / rank_idx
            metrics["ap"] = sum_p / max(1, len(ground_truth))

            # Reciprocal Rank (RR)
            rr = 0.0
            for rank_idx, cand in enumerate(ranking, 1):
                if cand in ground_truth:
                    rr = 1.0 / rank_idx
                    break
            metrics["rr"] = rr
            return metrics

        metrics_diff = compute_metrics(rank_diff, ground_truth)
        metrics_bfs = compute_metrics(rank_bfs, ground_truth)
        metrics_rand = compute_metrics(rank_rand, ground_truth)

        return {
            "program": mut.program_name,
            "seed_node": mut.seed_node_id,
            "description": mut.description,
            "slice_size": len(forward_slice),
            "ground_truth_size": len(ground_truth),
            "ground_truth_in_slice": len(ground_truth & forward_slice),
            "metrics": {
                "diffusion": metrics_diff,
                "bfs": metrics_bfs,
                "random": metrics_rand
            }
        }

    def run_full_benchmark(self) -> Dict[str, Any]:
        """
        Discovers all programs in examples/, runs the full mutation experiment battery,
        and aggregates statistical results against Hypothesis H1.
        """
        cbl_files = sorted(glob.glob(os.path.join(self.examples_dir, "*.cbl")))
        all_results = []
        total_discovered_mutations = 0

        for fpath in cbl_files:
            fname = os.path.basename(fpath)
            with open(fpath, "r", encoding="utf-8") as f:
                code = f.read()

            try:
                g = self.builder.build_from_source(code)
            except Exception:
                continue

            mutations = self.generate_mutations(fname, code, g)
            total_discovered_mutations += len(mutations)

            for mut in mutations:
                res = self.execute_and_evaluate_mutation(code, mut)
                if res is not None:
                    all_results.append(res)

        # Aggregate metrics
        num_valid = len(all_results)
        if num_valid == 0:
            return {"error": "No valid behavioral mutations produced in corpus."}

        def average_metric(method: str, metric_name: str) -> float:
            vals = [r["metrics"][method][metric_name] for r in all_results]
            return float(np.mean(vals))

        summary = {
            "total_programs": len(cbl_files),
            "total_mutations_generated": total_discovered_mutations,
            "valid_behavioral_experiments": num_valid,
            "comparison": {
                "precision@1": {
                    "diffusion": average_metric("diffusion", "precision@1"),
                    "bfs": average_metric("bfs", "precision@1"),
                    "random": average_metric("random", "precision@1"),
                },
                "precision@3": {
                    "diffusion": average_metric("diffusion", "precision@3"),
                    "bfs": average_metric("bfs", "precision@3"),
                    "random": average_metric("random", "precision@3"),
                },
                "precision@5": {
                    "diffusion": average_metric("diffusion", "precision@5"),
                    "bfs": average_metric("bfs", "precision@5"),
                    "random": average_metric("random", "precision@5"),
                },
                "map": {
                    "diffusion": average_metric("diffusion", "ap"),
                    "bfs": average_metric("bfs", "ap"),
                    "random": average_metric("random", "ap"),
                },
                "mrr": {
                    "diffusion": average_metric("diffusion", "rr"),
                    "bfs": average_metric("bfs", "rr"),
                    "random": average_metric("random", "rr"),
                }
            },
            "individual_experiments": all_results
        }

        # Check Hypothesis H1 Falsification Criterion:
        # "Diffusion beats BFS by >= 10 p.p. in precision@k (specifically precision@3 or precision@1)"
        p1_diff = summary["comparison"]["precision@1"]["diffusion"]
        p1_bfs = summary["comparison"]["precision@1"]["bfs"]
        p3_diff = summary["comparison"]["precision@3"]["diffusion"]
        p3_bfs = summary["comparison"]["precision@3"]["bfs"]

        delta_p1 = (p1_diff - p1_bfs) * 100.0
        delta_p3 = (p3_diff - p3_bfs) * 100.0

        beats_by_10pp = delta_p3 >= 10.0 or delta_p1 >= 10.0
        criterion_met = (num_valid >= 30) and beats_by_10pp

        summary["hypothesis_h1_verdict"] = {
            "criterion_description": "Diffusion beats BFS-in-slice by >= 10.0 percentage points with >= 30 experiments",
            "experiments_count": num_valid,
            "delta_precision@1_pp": round(delta_p1, 2),
            "delta_precision@3_pp": round(delta_p3, 2),
            "beats_by_10_percentage_points": beats_by_10pp,
            "hypothesis_h1_confirmed": criterion_met,
            "verdict": "CONFIRMED" if criterion_met else ("FALSIFIED_CRITERION_NOT_MET" if num_valid >= 30 else "INCONCLUSIVE_INSUFFICIENT_SAMPLES")
        }

        return summary
