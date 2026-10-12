"""Effective defaults for the deterministic analysis pipeline."""

SOLVER_SEED = 42
SPARSE_CUTOFF = 100
NETLSD_HUTCHINSON_SAMPLES = 15
NETLSD_TIME_MIN = 1e-2
NETLSD_TIME_MAX = 1e2
NETLSD_TIME_SCALES = 25
SPARSE_EIGENSOLVER_TOLERANCE = 1e-8
SPARSE_EIGENSOLVER_SHIFT = -1e-4
SPARSE_EIGENSOLVER_MIN_ITERATIONS = 1_000
SPARSE_EIGENSOLVER_ITERATIONS_PER_NODE = 10
SPECTRAL_NUM_MODES = 12
DIFFUSION_ALPHA = 0.5
DIFFUSION_TIME_STEPS = 20
DIFFUSION_T_MAX = 2.0
DIFFUSION_HALF_LIFE_EIGENVALUE_THRESHOLD = 1e-4
DIFFUSION_COLD_NODE_THRESHOLD = 0.01
DIRECTED_IMPACT_TIME = 1.5
DIRECTED_IMPACT_THRESHOLD = 1e-4
VARIABLE_READ_EDGE_WEIGHT = 1.2
VARIABLE_WRITE_EDGE_WEIGHT = 1.5
CYCLE_MAX_PER_SCC = 25
CYCLE_TOTAL_BUDGET = 100


def effective_analysis_options(lattice_size: int) -> dict:
    """Return the explicit options used by ProgramComparator.analyze_single."""
    return {
        "parser": {
            "engine_chain": ["CobolASTGraphBuilder", "regex_fallback"],
            "copybook_input": "explicit_name_to_source_mapping",
        },
        "graph": {
            "symmetrize": True,
            "include_variables": True,
            "variable_read_edge_weight": VARIABLE_READ_EDGE_WEIGHT,
            "variable_write_edge_weight": VARIABLE_WRITE_EDGE_WEIGHT,
        },
        "spectral": {
            "lattice_size": lattice_size,
            "num_modes": SPECTRAL_NUM_MODES,
            "sparse_cutoff": SPARSE_CUTOFF,
            "solver_seed": SOLVER_SEED,
            "netlsd_hutchinson_samples": NETLSD_HUTCHINSON_SAMPLES,
            "netlsd_time_scales": {
                "min": NETLSD_TIME_MIN,
                "max": NETLSD_TIME_MAX,
                "count": NETLSD_TIME_SCALES,
            },
            "sparse_eigensolver": {
                "tolerance": SPARSE_EIGENSOLVER_TOLERANCE,
                "shift": SPARSE_EIGENSOLVER_SHIFT,
                "minimum_iterations": SPARSE_EIGENSOLVER_MIN_ITERATIONS,
                "iterations_per_node": SPARSE_EIGENSOLVER_ITERATIONS_PER_NODE,
            },
        },
        "diffusion": {
            "alpha": DIFFUSION_ALPHA,
            "time_steps": DIFFUSION_TIME_STEPS,
            "t_max": DIFFUSION_T_MAX,
            "half_life_eigenvalue_threshold": DIFFUSION_HALF_LIFE_EIGENVALUE_THRESHOLD,
            "cold_node_threshold_ratio": DIFFUSION_COLD_NODE_THRESHOLD,
            "directed_impact_time": DIRECTED_IMPACT_TIME,
            "directed_impact_threshold": DIRECTED_IMPACT_THRESHOLD,
        },
        "cycles": {
            "max_cycles_per_scc": CYCLE_MAX_PER_SCC,
            "total_cycle_budget": CYCLE_TOTAL_BUDGET,
        },
    }
