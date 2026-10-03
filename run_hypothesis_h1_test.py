"""
Hypothesis H1 Experimental Evaluation Runner.
Executes the mutation testing battery on all canonical COBOL benchmark programs,
computes precision@k, recall@k, MAP, and MRR for Diffusion vs. BFS vs. Random,
and renders the verdict according to the pre-set falsification criterion.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mathy.mutation_benchmark import MutationBenchmark


def main():
    print("=" * 72)
    print(" REZONATOR: HYPOTHESIS H1 EMPIRICAL BENCHMARK EXPERIMENT")
    print(" Evaluation of Directed Heat Diffusion vs. Slicing Baselines")
    print("=" * 72)

    bench = MutationBenchmark()
    start_time = time.time()
    results = bench.run_full_benchmark()
    elapsed = time.time() - start_time

    if "error" in results:
        print(f"Error executing benchmark: {results['error']}")
        sys.exit(1)

    print(f"\n[CORPUS DISCOVERY & MUTATION GENERATION]")
    print(f"  Total Programs Evaluated:           {results['total_programs']}")
    print(f"  Total Mutations Generated:          {results['total_mutations_generated']}")
    print(f"  Valid Behavioral Experiments:       {results['valid_behavioral_experiments']}")
    print(f"  Execution Time:                     {elapsed:.2f} s")

    cmp = results["comparison"]
    print(f"\n" + "-" * 72)
    print(f" STATISTICAL EVALUATION METRICS:")
    print(f" {'Metric':<16} | {'Diffusion':<12} | {'BFS (Baseline B)':<18} | {'Random (Baseline A)':<20}")
    print(f"-" * 72)

    p1 = cmp["precision@1"]
    p3 = cmp["precision@3"]
    p5 = cmp["precision@5"]
    map_m = cmp["map"]
    mrr_m = cmp["mrr"]

    print(f" {'Precision@1':<16} | {p1['diffusion'] * 100:>10.2f}% | {p1['bfs'] * 100:>16.2f}% | {p1['random'] * 100:>18.2f}%")
    print(f" {'Precision@3':<16} | {p3['diffusion'] * 100:>10.2f}% | {p3['bfs'] * 100:>16.2f}% | {p3['random'] * 100:>18.2f}%")
    print(f" {'Precision@5':<16} | {p5['diffusion'] * 100:>10.2f}% | {p5['bfs'] * 100:>16.2f}% | {p5['random'] * 100:>18.2f}%")
    print(f" {'MAP (Mean AP)':<16} | {map_m['diffusion']:>11.4f} | {map_m['bfs']:>17.4f} | {map_m['random']:>19.4f}")
    print(f" {'MRR (Mean RR)':<16} | {mrr_m['diffusion']:>11.4f} | {mrr_m['bfs']:>17.4f} | {mrr_m['random']:>19.4f}")
    print(f"-" * 72)

    verdict = results["hypothesis_h1_verdict"]
    print(f"\n[HYPOTHESIS H1 VERDICT]:")
    print(f"  Experiments Count:                  {verdict['experiments_count']} (threshold: >= 30)")
    print(f"  Delta Precision@1 vs BFS:           {verdict['delta_precision@1_pp']:+.2f} percentage points")
    print(f"  Delta Precision@3 vs BFS:           {verdict['delta_precision@3_pp']:+.2f} percentage points")
    print(f"  Pre-set Criterion:                  {verdict['criterion_description']}")
    print(f"  Final Decision:                     {verdict['verdict']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
