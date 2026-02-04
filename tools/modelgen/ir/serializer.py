"""Deterministic JSON export for IR graphs."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from tools.modelgen.ir.schema import IRGraph


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
