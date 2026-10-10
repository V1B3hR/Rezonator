"""Central resource limits for untrusted COBOL analysis inputs."""

MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_GRAPH_NODES = 50_000
MAX_GRAPH_EDGES = 200_000

# GraphField currently materializes dense NumPy operators.  This separate
# ceiling prevents the symbolic 50k-node allowance from becoming an accidental
# multi-gigabyte matrix allocation.
MAX_DENSE_MATRIX_NODES = 2_048
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
