"""
Rezonator Verification Experiment: Empirical Differentiation of COBOL Programs.
Compares BANK-DEMO-V1 vs BANK-DEMO-V2 using Graph Laplacians, NetLSD Spectra,
Directed Impact Diffusion, and Formal Cycle/Deadlock Verification.
"""

import sys
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mathy.program_comparator import ProgramComparator
from mathy.llm_synthesizer import LLMSynthesizer


def main():
    print("=" * 70)
    print(" REZONATOR: VERIFICATION EXPERIMENT (BANK-DEMO-V1 vs BANK-DEMO-V2)")
    print("=" * 70)

    v1_path = os.path.join("examples", "bank_demo_v1.cbl")
    v2_path = os.path.join("examples", "bank_demo_v2.cbl")

    with open(v1_path, "r", encoding="utf-8") as f:
        code_v1 = f.read()

    with open(v2_path, "r", encoding="utf-8") as f:
        code_v2 = f.read()

    comparator = ProgramComparator(lattice_size=32)
    comparison = comparator.compare(code_v1, code_v2)

    v1_info = comparison["program_a_details"]
    v2_info = comparison["program_b_details"]
    metrics = comparison["metrics"]

    print(f"\n[PROGRAM A]: {comparison['program_a']}")
    print(f"  Nodes: {v1_info['stats']['num_nodes']} | Edges: {v1_info['stats']['num_edges']} | Vars: {v1_info['stats']['num_variables']}")
    print(f"  Connected Components: {v1_info['stats']['num_components']}")
    print(f"  Eigenvalues (lambda 0..5): {[round(x, 4) for x in v1_info['spectrum']['eigenvalues'][:6]]}")
    print(f"  Algebraic Connectivity (Fiedler lambda 1): {v1_info['spectrum']['fiedler_value']:.4f}")
    print(f"  Diffusion Half-Life: {v1_info['diffusion']['diffusion_half_life']:.4f} time units")
    print(f"  Forward Blast Radius (reachable nodes from entry): {v1_info['directed_impact']['reachable_count']}")
    print(f"  Cycle / Deadlock Status: {v1_info['cycles']['risk_verdict']}")

    print(f"\n[PROGRAM B]: {comparison['program_b']}")
    print(f"  Nodes: {v2_info['stats']['num_nodes']} | Edges: {v2_info['stats']['num_edges']} | Vars: {v2_info['stats']['num_variables']}")
    print(f"  Connected Components: {v2_info['stats']['num_components']}")
    print(f"  Eigenvalues (lambda 0..5): {[round(x, 4) for x in v2_info['spectrum']['eigenvalues'][:6]]}")
    print(f"  Algebraic Connectivity (Fiedler lambda 1): {v2_info['spectrum']['fiedler_value']:.4f}")
    print(f"  Diffusion Half-Life: {v2_info['diffusion']['diffusion_half_life']:.4f} time units")
    print(f"  Forward Blast Radius (reachable nodes from entry): {v2_info['directed_impact']['reachable_count']}")
    print(f"  Cycle / Deadlock Status: {v2_info['cycles']['risk_verdict']}")

    print("\n" + "-" * 70)
    print(" REZONATOR TOPOLOGICAL DIVERGENCE METRICS:")
    print("-" * 70)
    print(f"  NetLSD Topological Distance:        {metrics['spectral_distance_netlsd']:.4f}")
    print(f"  Fiedler Connectivity Delta:         {metrics['fiedler_delta']:+.4f}")
    print(f"  Normalized Fiedler Delta:           {metrics['fiedler_norm_delta']:+.4f}")
    print(f"  Cymatic Resonance Cross-Similarity: {metrics['cymatic_cross_similarity'] * 100.0:.2f}%")
    print(f"  Node Complexity Expansion:          {metrics['node_growth_ratio']:.2f}x")
    print(f"  Refactoring Fidelity Score:         {metrics['refactoring_health_score']:.1f} / 100")
    print(f"  Deadlock Introduced:                {'YES' if metrics['deadlock_introduced'] else 'NO'}")
    print(f"\n  VERDICT: {comparison['verdict']}")
    print("=" * 70)

    # Generate LLM brief for V2
    print("\n--- GENERATED LLM COGNITIVE BRIEF ---")
    brief = LLMSynthesizer.generate_cognitive_brief(v2_info)
    print(brief)


if __name__ == "__main__":
    main()
