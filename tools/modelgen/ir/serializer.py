"""Deterministic JSON export for IR graphs and ArchModels."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from tools.modelgen.ir.schema import ArchModel, IRGraph


def serialize_graph(graph: IRGraph) -> str:
    """Serialize an IRGraph to deterministic JSON.

    Produces stable output by:
    - Sorting nodes by ID
    - Sorting edges by ID
    - Sorting groups by ID
    - Sorting invariants by ID
    - Using sort_keys=True for all dicts
    """
    data = _graph_to_dict(graph)
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def serialize_graph_to_dict(graph: IRGraph) -> dict[str, Any]:
    """Serialize an IRGraph to a dict (for further processing)."""
    return _graph_to_dict(graph)


def _graph_to_dict(graph: IRGraph) -> dict[str, Any]:
    """Convert IRGraph to a sorted, deterministic dict."""
    nodes = sorted(
        [_node_to_dict(n) for n in graph.nodes if not n.hidden],
        key=lambda x: x["id"],
    )
    edges = sorted(
        [_edge_to_dict(e) for e in graph.edges],
        key=lambda x: x["id"],
    )
    groups = sorted(
        [asdict(g) for g in graph.groups],
        key=lambda x: x["id"],
    )
    invariants = sorted(
        [asdict(i) for i in graph.invariants],
        key=lambda x: x["id"],
    )
    metadata = dict(sorted(graph.metadata.items()))

    return {
        "edges": edges,
        "groups": groups,
        "invariants": invariants,
        "metadata": metadata,
        "nodes": nodes,
        "schema_version": "1.0",
    }


def _node_to_dict(node) -> dict[str, Any]:
    """Convert an IRNode to a dict, omitting empty fields."""
    d = asdict(node)
    # Remove empty/default fields to keep output clean
    clean = {}
    for key, value in sorted(d.items()):
        if key == "hidden":
            continue
        if value == "" or value == [] or value == {} or value is False:
            continue
        if key == "line_number" and value == 0:
            continue
        clean[key] = value
    return clean


def _edge_to_dict(edge) -> dict[str, Any]:
    """Convert an IREdge to a dict."""
    d = asdict(edge)
    clean = {}
    for key, value in sorted(d.items()):
        if value == "" or value == {} or value is False:
            continue
        clean[key] = value
    return clean


# ---------------------------------------------------------------------------
# v2 ArchModel serialization
# ---------------------------------------------------------------------------


def serialize_arch_model(model: ArchModel) -> str:
    """Serialize an ArchModel to deterministic v2 JSON."""
    data = serialize_arch_model_to_dict(model)
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def serialize_arch_model_to_dict(model: ArchModel) -> dict[str, Any]:
    """Serialize an ArchModel to a dict."""
    ir_graph_dict = _graph_to_dict(model.ir_graph)

    arch_nodes = sorted(
        [_clean_dict(asdict(n)) for n in model.arch_nodes],
        key=lambda x: x["id"],
    )
    arch_edges = sorted(
        [_clean_dict(asdict(e)) for e in model.arch_edges],
        key=lambda x: x["id"],
    )
    requirements = sorted(
        [_clean_dict(asdict(r)) for r in model.requirements],
        key=lambda x: x["id"],
    )
    requirement_links = sorted(
        [_clean_dict(asdict(lk)) for lk in model.requirement_links],
        key=lambda x: x["id"],
    )
    viewpoints = [_clean_dict(asdict(v)) for v in model.viewpoints]

    metadata = dict(sorted(model.metadata.items())) if model.metadata else {}

    return {
        "architecture": {
            "edges": arch_edges,
            "nodes": arch_nodes,
        },
        "ir_graph": ir_graph_dict,
        "meta_model_version": metadata.pop("meta_model_version", "uaf-lite-0.1"),
        "metadata": metadata,
        "requirements": {
            "items": requirements,
            "links": requirement_links,
        },
        "schema_version": "2.0",
        "viewpoints": viewpoints,
    }


def _clean_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Remove empty/default fields from a dict."""
    clean = {}
    for key, value in sorted(d.items()):
        if value == "" or value == [] or value == {} or value is False:
            continue
        if key == "line_number" and value == 0:
            continue
        clean[key] = value
    return clean
