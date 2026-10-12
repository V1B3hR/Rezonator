"""Versioned cryptographic provenance for Rezonator analysis results."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from typing import Any, Dict, Mapping, Optional

from rezonator import __version__
from rezonator.analysis_config import (
    SOLVER_SEED,
    VARIABLE_READ_EDGE_WEIGHT,
    VARIABLE_WRITE_EDGE_WEIGHT,
)


MANIFEST_SCHEMA_VERSION = "1.0"
DEPENDENCY_DISTRIBUTIONS = ("numpy", "scipy", "networkx", "torch", "cobolparser")


def _sha256(source_code: str) -> str:
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _copybook_manifest(copybooks: Optional[Mapping[str, str]]) -> list:
    entries = []
    seen_names = set()
    for name, content in (copybooks or {}).items():
        if not isinstance(name, str) or not isinstance(content, str):
            raise TypeError("copybooks must map string names to string contents")
        normalized_name = name.strip().strip("'\"").upper()
        if not normalized_name:
            raise ValueError("copybook names cannot be empty")
        if normalized_name in seen_names:
            raise ValueError(f"duplicate copybook name after normalization: {normalized_name}")
        seen_names.add(normalized_name)
        entries.append({"name": normalized_name, "sha256": _sha256(content)})
    return sorted(entries, key=lambda entry: entry["name"])


def dependency_versions() -> Dict[str, Optional[str]]:
    """Return installed numerical/analysis dependency versions, including absence."""
    versions = {}
    for distribution in DEPENDENCY_DISTRIBUTIONS:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    versions["python"] = platform.python_version()
    versions["platform"] = platform.platform()
    return versions


def graph_digest(graph_data: Mapping[str, Any], include_variables: bool = True) -> str:
    """Hash the canonical weighted parsed topology and GraphField variable expansion.

    Source text, labels, and locations are intentionally excluded: they are
    covered by source/copybook hashes and source-origin references. Node IDs,
    node types, edge types, endpoints, weights, and variable dependency edges
    define this graph snapshot.
    """
    raw_nodes = list(graph_data.get("nodes", []))
    raw_edges = list(graph_data.get("edges", []))
    variables = list(graph_data.get("variables", []))
    node_rows = [
        (str(node["id"]), str(node.get("node_type", "")))
        for node in raw_nodes
    ]
    edge_rows = [
        (
            str(edge.get("edge_type", "")),
            str(edge["source"]),
            str(edge["target"]),
            float(edge.get("weight", 1.0)),
        )
        for edge in raw_edges
    ]
    if include_variables:
        declared_variables = {str(variable["name"]) for variable in variables}
        for variable in variables:
            name = str(variable["name"])
            node_rows.append((f"var_{name}", "var"))
        for node in raw_nodes:
            node_id = str(node["id"])
            for name in node.get("reads", []):
                if str(name) not in declared_variables:
                    continue
                edge_rows.append((
                    "dfg_read", f"var_{name}", node_id,
                    VARIABLE_READ_EDGE_WEIGHT,
                ))
            for name in node.get("writes", []):
                if str(name) not in declared_variables:
                    continue
                edge_rows.append((
                    "dfg_write", node_id, f"var_{name}",
                    VARIABLE_WRITE_EDGE_WEIGHT,
                ))
    # Tuple rows and incremental hashing avoid holding both a large dict graph
    # and its complete serialized JSON in memory at the configured graph limit.
    # Edge tuple order is (edge_type, source, target, weight), canonical by key.
    node_rows.sort()
    edge_rows.sort()
    hasher = hashlib.sha256()
    hasher.update(b'{"edges":[')
    for index, (edge_type, source, target, weight) in enumerate(edge_rows):
        if index:
            hasher.update(b",")
        hasher.update(_canonical_json({
            "edge_type": edge_type,
            "source": source,
            "target": target,
            "weight": weight,
        }))
    hasher.update(b'],"nodes":[')
    for index, (node_id, node_type) in enumerate(node_rows):
        if index:
            hasher.update(b",")
        hasher.update(_canonical_json({"id": node_id, "node_type": node_type}))
    hasher.update(b"]}")
    return hasher.hexdigest()


def _provenance(
    source_hashes: Dict[str, str],
    *,
    analysis_options: Optional[Mapping[str, Any]],
    copybooks: Optional[Mapping[str, str]],
    graph_data: Optional[Mapping[str, Any]] = None,
    graph_data_a: Optional[Mapping[str, Any]] = None,
    graph_data_b: Optional[Mapping[str, Any]] = None,
) -> Dict[str, object]:
    options = dict(analysis_options or {})
    copies = _copybook_manifest(copybooks)
    versions = dependency_versions()
    include_variables = bool(options.get("graph", {}).get("include_variables", True))
    graph_digests = {}
    if graph_data is not None:
        graph_digests["graph"] = graph_digest(graph_data, include_variables=include_variables)
    if graph_data_a is not None:
        graph_digests["graph_a"] = graph_digest(graph_data_a, include_variables=include_variables)
    if graph_data_b is not None:
        graph_digests["graph_b"] = graph_digest(graph_data_b, include_variables=include_variables)
    fingerprint_payload = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "source_hashes": source_hashes,
        "copybooks": copies,
        "analysis_options": options,
        "dependency_versions": versions,
        "rezonator_version": __version__,
        "graph_digests": graph_digests,
    }
    result = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "source_hashes": source_hashes,
        "copybooks": copies,
        "analysis_options": options,
        "dependency_versions": versions,
        "analysis_fingerprint": hashlib.sha256(_canonical_json(fingerprint_payload)).hexdigest(),
        "rezonator_version": __version__,
        "solver_seed": SOLVER_SEED,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if len(source_hashes) == 1:
        result["source_sha256"] = next(iter(source_hashes.values()))
    result.update({
        "graph_digest" if name == "graph" else f"graph_digest_{name.removeprefix('graph_')}": digest
        for name, digest in graph_digests.items()
    })
    return result


def source_provenance(
    source_code: str,
    *,
    analysis_options: Optional[Mapping[str, Any]] = None,
    copybooks: Optional[Mapping[str, str]] = None,
    graph_data: Optional[Mapping[str, Any]] = None,
) -> Dict[str, object]:
    """Return an auditable manifest for one input and its effective options."""
    source_hash = _sha256(source_code)
    result = _provenance(
        {"source": source_hash}, analysis_options=analysis_options,
        copybooks=copybooks, graph_data=graph_data,
    )
    result["source_sha256"] = source_hash
    return result


def comparison_provenance(
    source_a: str,
    source_b: str,
    *,
    analysis_options: Optional[Mapping[str, Any]] = None,
    copybooks: Optional[Mapping[str, str]] = None,
    graph_data_a: Optional[Mapping[str, Any]] = None,
    graph_data_b: Optional[Mapping[str, Any]] = None,
) -> Dict[str, object]:
    """Return auditable metadata for both sides of a comparison."""
    source_hashes = {"source_a": _sha256(source_a), "source_b": _sha256(source_b)}
    result = _provenance(
        source_hashes,
        analysis_options=analysis_options,
        copybooks=copybooks,
        graph_data_a=graph_data_a,
        graph_data_b=graph_data_b,
    )
    result["source_a_sha256"] = source_hashes["source_a"]
    result["source_b_sha256"] = source_hashes["source_b"]
    return result
