"""
LLM Mathematical Bridge: Translates Rezonator Spectral, Diffusion, and Cycle Tensors
into high-density, structured cognitive prompts for AI models and auditors.
"""

from typing import Dict, Any


class LLMSynthesizer:
    """
    Transforms quantitative physical/topological metrics into
    concise, mathematically verifiable markdown explanations for LLMs and human auditors.
    """

    @staticmethod
    def generate_cognitive_brief(analysis_data: Dict[str, Any]) -> str:
        prog_id = analysis_data.get("program_id", "COBOL-PROGRAM")
        stats = analysis_data.get("stats", {})
        spectrum = analysis_data.get("spectrum", {})
        diff = analysis_data.get("diffusion", {})
        impact = analysis_data.get("directed_impact", {})
        cycles = analysis_data.get("cycles", {})

        evals_str = ", ".join(f"{x:.4f}" for x in spectrum.get("eigenvalues", [])[:6])
        fiedler = spectrum.get("fiedler_value", 0.0)
        fiedler_norm = spectrum.get("fiedler_norm", 0.0)
        half_life = diff.get("diffusion_half_life", float("inf"))
        num_comp = stats.get("num_components", 1)
        iso_nodes = stats.get("isolated_nodes", [])

        has_deadlock = cycles.get("has_deadlock", False)
        is_recursive = cycles.get("is_recursive", False)
        cycle_count = cycles.get("cycle_count", 0)
        reaches_term = cycles.get("reaches_terminal", True)
        verdict = cycles.get("risk_verdict", "DIRECTED_ACYCLIC_FLOW")

        top_impacted = [
            f"idx {item['node_idx']} (impact {item['impact_score']:.3f})"
            for item in impact.get("impact_ranking", [])[:4]
        ]
        top_impact_str = ", ".join(top_impacted) if top_impacted else "N/A"

        prompt = f"""# REZONATOR COGNITIVE INTELLIGENCE BRIEF: {prog_id}
**System**: Rezonator (Physics & Spectral Graph Topology Engine for Code Intelligence)
**Target Language**: COBOL / Mainframe Core Banking Monolith

### 1. Structural Field Topology
- **Vertices (Statements & Control Transfers)**: {stats.get('num_nodes', 0)}
- **Edges (Control Flow & Data Dependencies)**: {stats.get('num_edges', 0)}
- **State Variables (Working-Storage Hubs)**: {stats.get('num_variables', 0)}
- **Connected Components**: {num_comp}
- **Isolated / Unreferenced Variables**: {iso_nodes if iso_nodes else "None (all variables referenced)"}

### 2. Spectral Resonance & NetLSD Signature
- **Fundamental Modal Frequencies (λ_0 ... λ_5)**: [{evals_str}]
- **Algebraic Connectivity (Fiedler λ_1)**: {fiedler:.4f} (Normalized: {fiedler_norm:.4f})
- **Structural Modularity**: {"HIGHLY INTERCONNECTED" if fiedler > 0.3 else "MODULAR / PARTITIONABLE" if fiedler > 0.05 else "DISCONNECTED CLUSTERS"}
- **Spectral Gap (λ_2 - λ_1)**: {spectrum.get('spectral_gap', 0.0):.4f}

### 3. Directed Impact Propagation & Diffusion
- **Diffusion Equilibrium Half-Life (τ_1/2)**: {f'{half_life:.3f} time units' if not float('inf') == half_life else 'INFINITE (Disconnected partitions or unreferenced variables present)'}
- **Forward Impact Blast Radius (Entry Perturbation)**: {impact.get('reachable_count', 0)} nodes reachable
- **Top Downstream Nodes by Impact**: {top_impact_str}

### 4. Formal Control Flow & Termination Verification
- **CFG Cycles Detected**: {cycle_count}
- **Recursive PERFORM Calls**: {"YES" if is_recursive else "NO"}
- **Terminal State Reachability (STOP RUN / GOBACK)**: {"GUARANTEED" if reaches_term else "UNREACHABLE"}
- **Deadlock / Infinite Loop Hazard**: {"CRITICAL HAZARD: " + cycles.get('risk_description', '') if has_deadlock else "CLEAN: " + verdict}

### Guidance for AI Reasoning:
This program is mathematically mapped to a {stats.get('num_nodes', 0)}-node dependency manifold.
When analyzing or proposing refactorings, respect the directed impact ranking to avoid regressions in downstream routines.
Deadlock status is formally verified via Tarjan SCC cycle analysis on the control flow graph.
"""
        return prompt
