import glob
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mathy.ast_graph_builder import CobolASTGraphBuilder
from mathy.graph_field import GraphField
from mathy.cycle_detector import CycleDetector
from mathy.diamond_yant import DiamondYantSpectralEngine
from mathy.pinn_diffusion import PINNGraphDiffusionEngine
from mathy.program_comparator import ProgramComparator

def main():
    builder = CobolASTGraphBuilder()
    spectral = DiamondYantSpectralEngine(lattice_size=16)
    diffusion = PINNGraphDiffusionEngine(alpha=0.5)

    for path in sorted(glob.glob('examples/*.cbl')):
        with open(path) as f:
            code = f.read()
        data = builder.build_from_source(code)
        prog_id = data["program_id"]
        field = GraphField(data, symmetrize=True, include_variables=True)
        cycles = CycleDetector(data).analyze()
        spectrum = spectral.compute_spectrum(field.L, L_norm=field.L_norm, num_modes=8)

        print(f"=== {prog_id} ===")
        print(f"  Nodes: {field.num_nodes} (stmts: {len(data['nodes'])}, vars: {len(data['variables'])})")
        print(f"  Edges: {len(field.edges)} (CFG+DFG raw: {len(data['edges'])})")
        print(f"  Connected components: {field.num_components} | Isolated: {field.isolated_nodes}")
        print(f"  Tarjan Cycles: {cycles['cycle_count']} | Deadlock: {cycles['has_deadlock']} | Verdict: {cycles['risk_verdict']}")
        print(f"  Fiedler value (lambda_1 unnorm): {spectrum['fiedler_value']:.4f}")
        print(f"  Normalized lambda_1: {spectrum['fiedler_norm']:.4f}")

if __name__ == '__main__':
    main()
