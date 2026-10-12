"""Structured, source-linked audit reports for deterministic analyses."""

import math
from typing import Any, Dict, List, Mapping

from rezonator.provenance import graph_digest


AUDIT_REPORT_SCHEMA_VERSION = "1.0"
MAX_INLINE_SOURCE_REFERENCES = 100


def _source_reference(node: Mapping[str, Any]) -> Dict[str, Any]:
    location = node.get("location") or {}
    origin = node.get("source_origin") or {}
    return {
        "node_id": node.get("id"),
        "source_origin": origin or None,
        "line": origin.get("line", location.get("line", node.get("line"))),
        "column": location.get("column"),
        "paragraph": node.get("paragraph"),
    }


def _metric(name: str, value: Any, definition: str, limitation: str = "") -> Dict[str, Any]:
    if value is None:
        status = "unavailable"
    elif isinstance(value, float) and not math.isfinite(value):
        status = "positive_infinity" if value > 0 else "non_finite"
        value = None
    else:
        status = "finite"
    return {
        "name": name,
        "value": value,
        "value_status": status,
        "definition": definition,
        "limitation": limitation,
    }


def _inline_code(value: Any) -> str:
    escaped = str(value).replace("\\", "\\\\").replace("`", "\\`")
    return "`" + escaped + "`"


def _markdown_text(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "\\|")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("*", "\\*")
        .replace("_", "\\_")
    )


def build_audit_report(analysis: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a JSON-serializable audit report from ProgramComparator output."""
    parsed = analysis.get("parsed") or {}
    nodes = list(parsed.get("nodes", []))
    edges = list(parsed.get("edges", []))
    variables = list(parsed.get("variables", []))
    nodes_by_id = {str(node.get("id")): node for node in nodes if node.get("id") is not None}
    coverage = dict(parsed.get("parser_coverage") or {})
    unsupported = list(parsed.get("unsupported_statements", []))
    cycles = dict(analysis.get("cycles") or {})
    provenance = dict(analysis.get("provenance") or {})

    all_read_count = sum(len(node.get("reads", [])) for node in nodes)
    all_write_count = sum(len(node.get("writes", [])) for node in nodes)
    expanded_node_count = len(nodes) + len(variables)
    expanded_edge_count = len(edges) + all_read_count + all_write_count
    digest = provenance.get("graph_digest") or graph_digest(parsed)

    source_reference_catalog: Dict[str, Dict[str, Any]] = {}
    findings: List[Dict[str, Any]] = []
    cycle_evidence_node_ids = set()

    def register_nodes(node_ids: List[str]) -> List[str]:
        registered = []
        for node_id in node_ids:
            key = str(node_id)
            if key in nodes_by_id:
                source_reference_catalog.setdefault(key, _source_reference(nodes_by_id[key]))
                registered.append(key)
        return registered

    for item in unsupported:
        node_id = str(item.get("id", ""))
        if node_id in nodes_by_id:
            register_nodes([node_id])
            source_ids = [node_id]
            origin = _source_reference(nodes_by_id[node_id])
        else:
            origin = {
                "node_id": item.get("id"),
                "source_origin": item.get("source_origin"),
                "line": (item.get("location") or {}).get("line"),
                "paragraph": item.get("paragraph"),
            }
            source_ids = []
        findings.append({
            "id": f"unsupported:{node_id or len(findings)}",
            "kind": "unsupported_statement",
            "severity": "coverage_gap",
            "message": f"Statement verb {item.get('verb', 'UNKNOWN')} is outside the modeled subset.",
            "code": item.get("code"),
            "source_node_ids": source_ids,
            "source_origin": origin.get("source_origin"),
            "source_line": origin.get("line"),
            "paragraph": origin.get("paragraph"),
        })

    for cycle_index, cycle in enumerate(cycles.get("cycles", []), start=1):
        node_ids = register_nodes(list(cycle.get("nodes", [])))
        cycle_evidence_node_ids.update(node_ids)
        findings.append({
            "id": f"cycle:{cycle_index}",
            "kind": "reported_control_flow_cycle",
            "severity": "review",
            "message": "A representative cycle was enumerated in the parsed control-flow graph.",
            "source_node_ids": node_ids,
            "cycle_length": cycle.get("length"),
            "is_recursive_call": bool(cycle.get("is_recursive_call")),
            "branch_guard_vars": list(cycle.get("branch_guard_vars", [])),
            "unmodified_guard_vars": list(cycle.get("unmodified_guard_vars", [])),
            "is_invariant_hazard": bool(cycle.get("is_invariant_hazard")),
        })

    for scc in cycles.get("sccs", []):
        if not scc.get("is_trapped"):
            continue
        node_ids = register_nodes(list(scc.get("nodes", [])))
        cycle_evidence_node_ids.update(node_ids)
        findings.append({
            "id": f"trapped_scc:{scc.get('scc_id', 'unknown')}",
            "kind": "trapped_control_flow_component",
            "severity": "review",
            "message": "This non-trivial SCC has no path to a recognized terminal in the parsed CFG.",
            "source_node_ids": node_ids,
            "node_count": scc.get("node_count"),
            "can_escape_to_terminal": False,
        })

    if cycles.get("has_deadlock"):
        findings.append({
            "id": "cycle-analysis:heuristic-hazard",
            "kind": "cycle_analysis_heuristic",
            "severity": "review",
            "message": cycles.get("risk_description", "Static analysis reported a cycle hazard."),
            "source_node_ids": sorted(cycle_evidence_node_ids),
            "risk_verdict": cycles.get("risk_verdict"),
        })

    spectrum = analysis.get("spectrum") or {}
    diffusion = analysis.get("diffusion") or {}
    metrics = [
        _metric(
            "parser_coverage_ratio", coverage.get("coverage_ratio"),
            "supported_statements / total_statements; equals 1.0 when no modeled statement nodes exist.",
            "Measures classification in the current parser contract, not semantic or dialect completeness.",
        ),
        _metric(
            "unsupported_statement_count", coverage.get("unsupported_statements", len(unsupported)),
            "Number of materialized statement nodes classified as outside the modeled subset.",
            "Does not count syntax that a parser fails to recognize as a statement at all.",
        ),
        _metric(
            "graph_node_count", expanded_node_count,
            "Parsed statement nodes plus declared variables represented as synthetic graph nodes.",
        ),
        _metric(
            "graph_edge_count", expanded_edge_count,
            "Parsed edges plus GraphField variable read/write edges; parallel edges are counted separately.",
            "The digest records edge type and weight; downstream sparse assembly may sum parallel endpoints.",
        ),
        _metric(
            "fiedler_value", spectrum.get("fiedler_value"),
            "Second-smallest eigenvalue reported for the symmetric graph Laplacian.",
            "Structural metric of this parsed graph, not a measure of business correctness.",
        ),
        _metric(
            "diffusion_half_life", diffusion.get("diffusion_half_life"),
            "ln(2) / (alpha * Fiedler value), when the reported Fiedler value exceeds the solver threshold.",
            "Model-derived graph signal; it is not elapsed runtime or observed execution time.",
        ),
        _metric(
            "enumerated_cycle_count", cycles.get("cycle_count", 0),
            "Number of simple cycles returned by the bounded in-SCC enumerator.",
            "This is not necessarily the total number of cycles; inspect cycle_budget_exhausted.",
        ),
        _metric(
            "non_trivial_scc_count", cycles.get("non_trivial_scc_count", cycles.get("scc_count", 0)),
            "Count of strongly connected components containing multiple nodes or a self-loop.",
        ),
        _metric(
            "trapped_scc_count", cycles.get("trapped_scc_count", 0),
            "Non-trivial SCCs from which no recognized terminal is reachable in the parsed CFG.",
            "Static graph reachability only; it does not prove runtime nontermination.",
        ),
        _metric(
            "reaches_terminal", bool(cycles.get("reaches_terminal", False)),
            "Whether the selected entry node has a graph path to a recognized STOP RUN/GOBACK node.",
            "A path's existence does not mean every execution reaches a terminal.",
        ),
    ]

    assumptions = [
        {
            "id": "cfg-scope",
            "statement": "Cycle and SCC results use only cfg_* edges in the graph produced by the current parser.",
            "consequence": "Unsupported statements retain sequence and selected data reads, but their full control-flow semantics are not modeled.",
        },
        {
            "id": "terminal-reachability",
            "statement": "A trapped SCC means no path in this static CFG reaches a node recognized as STOP RUN or GOBACK.",
            "consequence": "This is a structural reachability fact, not a proof that a real COBOL execution cannot terminate.",
        },
        {
            "id": "bounded-cycle-enumeration",
            "statement": f"Cycle extraction is capped at {cycles.get('max_cycles_per_scc', 25)} cycles per SCC and {cycles.get('total_cycle_budget', 100)} total.",
            "consequence": "When cycle_budget_exhausted is true, the reported cycles are a bounded sample, not a complete inventory.",
        },
        {
            "id": "data-flow-guards",
            "statement": "Invariant-guard checks compare parsed branch reads with writes collected from nodes in each enumerated cycle.",
            "consequence": "This is a syntactic heuristic; aliasing, external state, arithmetic semantics, and all runtime paths are not proven.",
        },
        {
            "id": "dfg-scope",
            "statement": "Data-dependency evidence is the parser's modeled def-use/read-write graph for this source snapshot.",
            "consequence": "It is not a runtime trace and may be incomplete where syntax or language semantics are unsupported.",
        },
    ]

    return {
        "audit_report_schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "program_id": analysis.get("program_id", parsed.get("program_id", "UNKNOWN-PROGRAM")),
        "provenance": provenance,
        "graph": {
            "digest_algorithm": "sha256",
            "graph_digest": digest,
            "digest_scope": "sorted node IDs/types and weighted typed edges, including declared-variable read/write edges",
            "node_count": expanded_node_count,
            "edge_count": expanded_edge_count,
            "parsed_node_count": len(nodes),
            "parsed_edge_count": len(edges),
            "variable_count": len(variables),
        },
        "parser": {
            "engine": parsed.get("parser_engine", "unknown"),
            "coverage": coverage,
            "unsupported_statements": unsupported,
        },
        "cycle_analysis": {
            "summary": {
                key: cycles.get(key)
                for key in (
                    "has_cycles", "has_deadlock", "is_recursive", "cycle_count",
                    "scc_count", "non_trivial_scc_count", "trapped_scc_count",
                    "trapped_cycle_count", "invariant_hazard_count",
                    "cycle_budget_exhausted", "reaches_terminal", "risk_verdict",
                    "risk_description", "terminal_nodes", "max_cycles_per_scc",
                    "total_cycle_budget",
                ) if key in cycles
            },
            "assumptions": assumptions,
        },
        "metrics": metrics,
        "findings": findings,
        "source_references": sorted(
            source_reference_catalog.values(),
            key=lambda ref: (str(ref.get("node_id")), str(ref.get("source_origin"))),
        ),
        "limitations": [
            "The report describes Rezonator's deterministic parsed-graph analysis, not execution of native COBOL.",
            "Parser coverage is not a claim of dialect or semantic completeness; inspect unsupported statements and source origins.",
            "Graph topology and spectral metrics do not establish behavioral equivalence, safety, or termination.",
            "Source node identifiers are snapshot-local and may change after source edits; rerun analysis for a new snapshot.",
        ],
    }


def audit_report_to_markdown(report: Mapping[str, Any]) -> str:
    """Render the structured audit report as reviewer-oriented Markdown."""
    provenance = report.get("provenance", {})
    parser = report.get("parser", {})
    coverage = parser.get("coverage", {})
    graph = report.get("graph", {})
    cycles = report.get("cycle_analysis", {})
    lines = [
        f"# Rezonator audit report — {_inline_code(report.get('program_id', 'UNKNOWN-PROGRAM'))}",
        "",
        f"- Report schema: {_inline_code(report.get('audit_report_schema_version', AUDIT_REPORT_SCHEMA_VERSION))}",
        f"- Rezonator: {_inline_code(provenance.get('rezonator_version', 'unknown'))}",
        f"- Analysis fingerprint: {_inline_code(provenance.get('analysis_fingerprint', 'unavailable'))}",
        f"- Graph SHA-256: {_inline_code(graph.get('graph_digest', 'unavailable'))}",
        f"- Generated: {_inline_code(provenance.get('timestamp_utc', 'unknown'))}",
        "",
        "## Input and provenance",
        "",
        f"- Source SHA-256: {_inline_code(provenance.get('source_sha256', 'unavailable'))}",
        f"- Copybooks: {len(provenance.get('copybooks', []))}",
        f"- Analysis options: {_inline_code(provenance.get('analysis_options', {}))}",
        f"- Dependency versions: {_inline_code(provenance.get('dependency_versions', {}))}",
        "",
        "## Graph scope",
        "",
        f"{graph.get('node_count', 0)} nodes ({graph.get('parsed_node_count', 0)} parsed + {graph.get('variable_count', 0)} variables), ",
        f"{graph.get('edge_count', 0)} weighted edges; digest scope: {graph.get('digest_scope', 'unspecified')}.",
        "",
        "## Parser coverage",
        "",
        f"- Parser engine: {_inline_code(parser.get('engine', 'unknown'))}",
        f"- Total modeled statements: {coverage.get('total_statements', 'unknown')}",
        f"- Supported: {coverage.get('supported_statements', 'unknown')}",
        f"- Unsupported: {coverage.get('unsupported_statements', len(parser.get('unsupported_statements', [])))}",
        f"- Coverage ratio: {coverage.get('coverage_ratio', 'unknown')} (classification coverage only; not semantic completeness)",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Definition | Limitation |",
        "|---|---:|---|---|",
    ]
    for metric in report.get("metrics", []):
        value = metric.get("value")
        if value is None:
            value = metric.get("value_status", "not available")
        lines.append(
            f"| {metric.get('name')} | {value} | {metric.get('definition', '').replace('|', '\\|')} | "
            f"{metric.get('limitation', '').replace('|', '\\|')} |"
        )

    lines.extend(["", "## Findings", ""])
    findings = report.get("findings", [])
    if not findings:
        lines.append("No unsupported statements or bounded cycle/SCC findings were emitted.")
    else:
        for finding in findings:
            anchor_ids = finding.get("source_node_ids", [])
            anchor_text = ", ".join(_inline_code(node_id) for node_id in anchor_ids[:MAX_INLINE_SOURCE_REFERENCES])
            if len(anchor_ids) > MAX_INLINE_SOURCE_REFERENCES:
                anchor_text += f" … ({len(anchor_ids)} source nodes total; see source-reference catalog)"
            lines.append(f"### {finding.get('id')} — {finding.get('kind')}")
            lines.append("")
            lines.append(f"- Severity: `{finding.get('severity', 'review')}`")
            lines.append(f"- Evidence: {_markdown_text(finding.get('message', ''))}")
            if finding.get("code"):
                lines.append(f"- Source statement: {_inline_code(finding['code'])}")
            if finding.get("source_line") is not None:
                lines.append(f"- Source line: {finding['source_line']}")
            if anchor_text:
                lines.append(f"- Source node IDs: {anchor_text}")
            lines.append("")

    lines.extend(["## Cycle-analysis assumptions", ""])
    for assumption in cycles.get("assumptions", []):
        lines.extend([
            f"- **{assumption.get('id')}** — {assumption.get('statement')} ",
            f"  Consequence: {assumption.get('consequence')}",
        ])
    lines.extend(["", "## Source-reference catalog", ""])
    references = report.get("source_references", [])
    if not references:
        lines.append("No source references were needed for the emitted findings.")
    else:
        for reference in references:
            origin = reference.get("source_origin") or {}
            if isinstance(origin, dict):
                source = origin.get("source", "unknown")
                line = origin.get("line", reference.get("line", "unknown"))
                stack = " → ".join(origin.get("copybook_stack", []))
                replacements = origin.get("replacements", [])
                suffix = f"; copybook stack: {_inline_code(stack)}" if stack else ""
                if replacements:
                    suffix += f"; replacements: {_inline_code(replacements)}"
                lines.append(f"- {_inline_code(reference.get('node_id'))} — {_inline_code(f'{source}:{line}')}{suffix}")
            else:
                lines.append(
                    f"- {_inline_code(reference.get('node_id'))} — line {_inline_code(reference.get('line', 'unknown'))}, "
                    f"paragraph {_inline_code(reference.get('paragraph', 'unknown'))}"
                )

    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report.get("limitations", []))
    lines.append("")
    return "\n".join(lines)
