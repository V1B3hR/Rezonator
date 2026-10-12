"""
REZONATOR: Comprehensive Performance & Scaling Benchmark Suite.
Measures:
1. End-to-end AST Graph Construction & Topological Spectral Solvers across all 10 COBOL examples.
2. Sparse Matrix & Lanczos/Krylov kernels on synthetic path graphs (N = 100 to 10,000).
3. Sparse end-to-end generated COBOL comparator runs (N = 2,050 and 5,001).
4. Mutation Testing & Hypothesis H1 Evaluation (Directed Diffusion vs. Slicing Baselines).
"""

import json
import time
import tracemalloc
import glob
import os
import sys
import numpy as np
import scipy.sparse as sp

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from rezonator.ast_graph_builder import CobolASTGraphBuilder
from rezonator.graph_field import GraphField
from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.pinn_diffusion import PINNGraphDiffusionEngine
from rezonator.cycle_detector import CycleDetector
from rezonator.mutation_benchmark import MutationBenchmark
from rezonator.program_comparator import ProgramComparator


def benchmark_cobol_corpus():
    print("=" * 76)
    print(" 1. REZONATOR COBOL CORPUS END-TO-END PARSING & TOPOLOGY BENCHMARK")
    print("=" * 76)
    print(f" {'Program':<22} | {'Nodes':<6} | {'Edges':<6} | {'Cycles':<6} | {'Parse (ms)':<10} | {'Laplacian (ms)':<14} | {'Spectrum (ms)'}")
    print("-" * 76)

    builder = CobolASTGraphBuilder()
    spectral_engine = DiamondYantSpectralEngine(lattice_size=16)

    total_time = 0.0
    examples = sorted(glob.glob(os.path.join("examples", "*.cbl")))

    for ex in examples:
        name = os.path.basename(ex).replace(".cbl", "")
        with open(ex, "r", encoding="utf-8") as f:
            code = f.read()

        t0 = time.perf_counter()
        data = builder.build_from_source(code)
        t_parse = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        field = GraphField(data, symmetrize=True, include_variables=True)
        cycles = CycleDetector(data).analyze()
        t_field = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        spectrum = spectral_engine.compute_spectrum(field.L, L_norm=field.L_norm, num_modes=6)
        t_spec = (time.perf_counter() - t0) * 1000

        prog_time = t_parse + t_field + t_spec
        total_time += prog_time

        c_count = cycles["cycle_count"]
        print(f" {name:<22} | {field.num_nodes:<6} | {len(field.edges):<6} | {c_count:<6} | {t_parse:8.2f} ms | {t_field:12.2f} ms | {t_spec:10.2f} ms")

    print("-" * 76)
    print(f" Total Corpus Analysis Time: {total_time:.2f} ms across {len(examples)} programs\n")


def benchmark_sparse_scaling():
    print("=" * 76)
    print(" 2. REZONATOR SPARSE LANCZOS & KRYLOV KERNEL SCALING BENCHMARK")
    print("=" * 76)
    print(f" {'Matrix Size (N)':<16} | {'Non-zeros (E)':<14} | {'Shift-Invert Lanczos':<22} | {'Krylov expm Trajectory'}")
    print("-" * 76)

    engine_spec = DiamondYantSpectralEngine(lattice_size=16)
    engine_diff = PINNGraphDiffusionEngine(alpha=0.5)

    for n in [100, 500, 1000, 5000, 10000]:
        # Tridiagonal path graph Laplacian
        main_diag = 2.0 * np.ones(n)
        main_diag[0] = 1.0
        main_diag[-1] = 1.0
        off_diag = -1.0 * np.ones(n - 1)
        L_sp = sp.diags([off_diag, main_diag, off_diag], [-1, 0, 1], shape=(n, n), format='csr')

        # Lanczos eigensolver timing
        t0 = time.perf_counter()
        spec = engine_spec.compute_spectrum(L_sp, L_norm=L_sp, num_modes=6)
        t_spec = (time.perf_counter() - t0) * 1000

        # Krylov diffusion trajectory timing (10 time steps)
        u0 = np.zeros(n)
        u0[0] = 1.0
        t0 = time.perf_counter()
        diff = engine_diff.solve_analytical(L_sp, u0, time_steps=10, t_max=1.0)
        t_diff = (time.perf_counter() - t0) * 1000

        nnz = L_sp.nnz
        print(f" N = {n:<12} | E = {nnz:<10} | {t_spec:18.2f} ms | {t_diff:18.2f} ms")

    print("-" * 76)
    print(" Synthetic sparse-kernel timings recorded through N = 10,000; this is not end-to-end COBOL capacity.\n")


def benchmark_sparse_end_to_end():
    """Measure generated COBOL through the ordinary parser/comparator result path."""
    print("=" * 108)
    print(" 3. GENERATED COBOL SPARSE END-TO-END ANALYSIS (parse -> graph -> spectrum/diffusion -> result)")
    print("=" * 108)
    print(
        f" {'Statements':<12} | {'Nodes':<8} | {'Edges':<8} | {'Analysis ms':<12} | "
        f"{'JSON ms':<9} | {'JSON MiB':<9} | {'CSR ops MiB':<12} | {'Dense eq. MiB':<13} | {'Traced peak MiB'}"
    )
    print("-" * 108)

    comparator = ProgramComparator(lattice_size=8)
    for statement_count in (2_049, 5_000):
        lines = [
            "       IDENTIFICATION DIVISION.",
            "       PROGRAM-ID. SPARSE-BENCH.",
            "       PROCEDURE DIVISION.",
            "       MAIN-PARA.",
        ]
        lines.extend(f'           DISPLAY "BENCH-{i:06d}".' for i in range(statement_count))
        lines.append("           STOP RUN.")
        source = "\n".join(lines)

        started = time.perf_counter()
        result = comparator.analyze_single(source)
        analysis_ms = (time.perf_counter() - started) * 1_000.0

        started = time.perf_counter()
        serialized = json.dumps(result, separators=(",", ":")).encode("utf-8")
        json_ms = (time.perf_counter() - started) * 1_000.0

        # Measure allocator peak separately so tracing overhead does not
        # contaminate the reported ordinary wall-clock timings.
        tracemalloc.start()
        memory_result = comparator.analyze_single(source)
        json.dumps(memory_result, separators=(",", ":"))
        _, peak_traced = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        node_count = result["stats"]["num_nodes"]
        edge_count = result["stats"]["num_edges"]
        csr_mib = result["stats"]["operator_storage_bytes"] / (1024.0 ** 2)
        dense_mib = (5 * node_count * node_count * 8) / (1024.0 ** 2)
        print(
            f" {statement_count:<12} | {node_count:<8} | {edge_count:<8} | {analysis_ms:10.2f} | "
            f"{json_ms:7.2f} | {len(serialized)/(1024.0**2):7.2f} | {csr_mib:10.2f} | "
            f"{dense_mib:11.2f} | {peak_traced/(1024.0**2):14.2f}"
        )

    print("-" * 108)
    print(
        "Generated straight-line programs exercise the ordinary comparator path. CSR bytes cover the five "
        "persistent graph operators; tracemalloc peak covers Python-traced allocations (not all native RSS).\n"
    )


def benchmark_mutation_hypothesis():
    print("=" * 76)
    print(" 4. REZONATOR MUTATION TESTING & HYPOTHESIS H1 EMPIRICAL EVALUATION")
    print("=" * 76)
    bench = MutationBenchmark()
    t0 = time.perf_counter()
    res = bench.run_full_benchmark()
    elapsed = time.perf_counter() - t0

    cmp = res.get("comparison", {})
    verdict_info = res.get("hypothesis_h1_verdict", {})

    print(f" Total Programs Evaluated:     {res.get('total_programs', 0)}")
    print(f" Total Mutations Generated:    {res.get('total_mutations_generated', 0)}")
    print(f" Valid Behavioral Experiments: {res.get('valid_behavioral_experiments', 0)}")
    print(f" Total Benchmark Runtime:      {elapsed:.3f} s\n")

    print(f" {'Metric':<16} | {'Diffusion':<12} | {'BFS Baseline':<14} | {'Random Baseline'}")
    print("-" * 65)
    for m in ["precision@1", "precision@3", "precision@5", "map", "mrr"]:
        row = cmp.get(m, {})
        d_val = row.get("diffusion", 0.0)
        b_val = row.get("bfs", 0.0)
        r_val = row.get("random", 0.0)
        if "precision" in m:
            print(f" {m:<16} | {d_val*100:10.2f}% | {b_val*100:12.2f}% | {r_val*100:13.2f}%")
        else:
            print(f" {m.upper():<16} | {d_val:10.4f} | {b_val:12.4f} | {r_val:13.4f}")

    print("-" * 65)
    print(f" Final Scientific Verdict:     {verdict_info.get('verdict')}")
    print("=" * 76)


if __name__ == "__main__":
    benchmark_cobol_corpus()
    benchmark_sparse_scaling()
    benchmark_sparse_end_to_end()
    benchmark_mutation_hypothesis()
