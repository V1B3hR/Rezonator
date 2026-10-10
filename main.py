#!/usr/bin/env python3
"""
Rezonator: Physics & Spectral Topology Engine for Code Intelligence.
Unified CLI entry point for analysis, comparison, verification, and interactive web studio.
"""

import argparse
import json
import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from rezonator.cobol_parser import CobolParser
from rezonator.program_comparator import ProgramComparator
from rezonator.llm_synthesizer import LLMSynthesizer
from rezonator.server import run_server


def cmd_demo():
    from verify_experiment import main as run_verify
    run_verify()


def cmd_analyze(file_path: str):
    if not os.path.isfile(file_path):
        print(f"Error: File not found at {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    comparator = ProgramComparator()
    res = comparator.analyze_single(code)
    cycles = res["cycles"]

    print("=" * 65)
    print(f" REZONATOR TOPOLOGICAL ANALYSIS: {res['program_id']}")
    print("=" * 65)
    print(f"Nodes: {res['stats']['num_nodes']} | Edges: {res['stats']['num_edges']} | Vars: {res['stats']['num_variables']}")
    print(f"Connected Components: {res['stats']['num_components']}")
    print(f"Eigenvalues: {[round(x, 4) for x in res['spectrum']['eigenvalues'][:6]]}")
    print(f"Algebraic Connectivity (Fiedler λ1): {res['spectrum']['fiedler_value']:.4f}")
    print(f"Diffusion Equilibrium Half-Life: {res['diffusion']['diffusion_half_life']:.4f}s")
    print(f"Forward Blast Radius (reachable): {res['directed_impact']['reachable_count']} nodes")
    print(f"Cycle & Deadlock Status: {cycles['risk_verdict']}")
    if cycles["has_deadlock"]:
        print(f"  WARNING: {cycles['risk_description']}")
    print("=" * 65)


def cmd_compare(file_a: str, file_b: str):
    if not os.path.isfile(file_a) or not os.path.isfile(file_b):
        print("Error: One or both files not found", file=sys.stderr)
        sys.exit(1)

    with open(file_a, "r", encoding="utf-8") as f:
        code_a = f.read()
    with open(file_b, "r", encoding="utf-8") as f:
        code_b = f.read()

    comparator = ProgramComparator()
    cmp = comparator.compare(code_a, code_b)

    m = cmp["metrics"]
    print("=" * 65)
    print(f" REZONATOR DIFFERENTIAL RADAR: {cmp['program_a']} vs {cmp['program_b']}")
    print("=" * 65)
    print(f"NetLSD Topological Distance:  {m['spectral_distance_netlsd']:.4f}")
    print(f"Δ Fiedler Connectivity:        {m['fiedler_delta']:+.4f}")
    print(f"Cymatic Cross-Similarity:     {m['cymatic_cross_similarity'] * 100:.2f}%")
    print(f"Refactoring Fidelity Score:   {m['refactoring_health_score']:.1f} / 100")
    print(f"Deadlock Introduced:          {'YES' if m['deadlock_introduced'] else 'NO'}")
    print(f"Verdict: {cmp['verdict']}")
    print("=" * 65)


def cmd_brief(file_path: str):
    if not os.path.isfile(file_path):
        print(f"Error: File not found at {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    comparator = ProgramComparator()
    res = comparator.analyze_single(code)
    brief = LLMSynthesizer.generate_cognitive_brief(res)
    print(brief)


def main():
    parser = argparse.ArgumentParser(
        description="Rezonator: Physics & Spectral Topology Engine for Code Intelligence"
    )
    parser.add_argument("--demo", action="store_true", help="Run verification proof-of-concept experiment")
    parser.add_argument("--serve", action="store_true", help="Start the local Web Studio & REST API")
    parser.add_argument("--port", type=int, default=8080, help="Web studio port (default: 8080)")
    parser.add_argument("--remote", action="store_true", help="Bind the API externally; requires --token")
    parser.add_argument("--token", type=str, help="Bearer token required by --remote")
    parser.add_argument("--file", type=str, help="Analyze single COBOL source file")
    parser.add_argument("--compare", nargs=2, metavar=("FILE1", "FILE2"), help="Compare two COBOL source files")
    parser.add_argument("--brief", type=str, help="Generate LLM cognitive prompt brief for a file")

    args = parser.parse_args()

    if args.demo:
        cmd_demo()
    elif args.serve:
        if args.remote and not args.token:
            parser.error("--remote requires --token")
        run_server(
            port=args.port,
            mode="remote" if args.remote else "local",
            token=args.token,
        )
    elif args.file:
        cmd_analyze(args.file)
    elif args.compare:
        cmd_compare(args.compare[0], args.compare[1])
    elif args.brief:
        cmd_brief(args.brief)
    else:
        print("Rezonator: No arguments specified. Running default demo...\n")
        cmd_demo()
        print("\nTip: Run 'python main.py --serve' to launch the interactive Web Studio at http://127.0.0.1:8080")


if __name__ == "__main__":
    main()
