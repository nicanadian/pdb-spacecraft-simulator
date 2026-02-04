"""Validate overrides against the IR graph to detect stale references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.modelgen.ir.schema import IRGraph


@dataclass
class ValidationIssue:
    """A validation issue found in overrides."""

    level: str  # "warning" or "error"
    message: str
    override_key: str = ""


def validate_overrides(graph: IRGraph, overrides: dict[str, Any]) -> list[ValidationIssue]:
    """Check every node/edge ID in overrides against the IR graph.

    Returns a list of issues (stale references, missing targets, etc.).
    """
    issues = []
    node_ids = {n.id for n in graph.nodes}
    edge_ids = {e.id for e in graph.edges}

    # Check node overrides
    node_overrides = overrides.get("nodes", {})
    if node_overrides:
        for node_id in node_overrides:
            if node_id not in node_ids:
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"Stale node override: '{node_id}' not found in IR graph",
                        override_key=f"nodes.{node_id}",
                    )
                )

    # Check hidden nodes
    hidden = overrides.get("hidden", [])
    for node_id in hidden:
        if node_id not in node_ids:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=f"Stale hidden node: '{node_id}' not found in IR graph",
                    override_key=f"hidden.{node_id}",
                )
            )

    # Check extra edges
    extra_edges = overrides.get("edges", [])
    for i, edge_data in enumerate(extra_edges):
        source = edge_data.get("source", "")
        target = edge_data.get("target", "")
        if source and source not in node_ids:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=f"Stale edge source: '{source}' not found in IR graph",
                    override_key=f"edges[{i}].source",
                )
            )
        if target and target not in node_ids:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=f"Stale edge target: '{target}' not found in IR graph",
                    override_key=f"edges[{i}].target",
                )
            )

    return issues
