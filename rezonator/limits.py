"""Central resource limits for untrusted COBOL analysis inputs."""

MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_GRAPH_NODES = 50_000
MAX_GRAPH_EDGES = 200_000

# Explicit dense matrix exports remain available for legacy/small-graph use;
# normal GraphField operators are sparse CSR and are not subject to this cap.
MAX_DENSE_MATRIX_NODES = 2_048
# PINN training constructs a dense N-dimensional neural output and is not the
# sparse, end-to-end analysis path. Keep that experimental mode separately bounded.
MAX_PINN_NODES = 2_048
MAX_RUNTIME_STEPS = 100_000
MAX_EXPRESSION_CHARS = 4_096
MAX_EXPRESSION_AST_NODES = 256


class ResourceLimitError(ValueError):
    """Raised when an analysis would exceed a declared safety budget."""

    status_code = 413
    error_code = "resource_limit_exceeded"


class GraphLimitError(ResourceLimitError):
    """Raised when a parsed graph exceeds a safe analysis budget."""

    error_code = "graph_limit_exceeded"


def validate_source_size(source_code: str) -> int:
    """Validate and return UTF-8 byte size of an analysis source string."""
    if not isinstance(source_code, str):
        raise ValueError("source_code must be a string")
    size = len(source_code.encode("utf-8"))
    if size > MAX_SOURCE_BYTES:
        raise ResourceLimitError(
            f"Source payload exceeds {MAX_SOURCE_BYTES} bytes: {size}"
        )
    return size


def validate_graph_payload(parsed_data: dict, include_variables: bool = True) -> None:
    """Reject graph payloads before expensive matrix allocation or solvers."""
    node_count = len(parsed_data.get("nodes", []))
    if include_variables:
        node_count += len(parsed_data.get("variables", []))
    edge_count = len(parsed_data.get("edges", []))

    if node_count > MAX_GRAPH_NODES:
        raise GraphLimitError(
            f"Graph node limit exceeded: {node_count} > {MAX_GRAPH_NODES}"
        )
    if edge_count > MAX_GRAPH_EDGES:
        raise GraphLimitError(
            f"Graph edge limit exceeded: {edge_count} > {MAX_GRAPH_EDGES}"
        )
