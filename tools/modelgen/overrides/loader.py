"""Load and apply YAML overrides to IR graphs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tools.modelgen.ir.schema import IREdge, IRGraph


def load_overrides(path: Path) -> dict[str, Any]:
    """Load overrides from a YAML file.

    Expected format:
    ```yaml
    nodes:
      sim.models.power.PowerModel:
        display_name: "Power Model"
        description: "Battery SOC and solar generation tracking"
      sim.engine.simulate:
        display_name: "simulate()"
    edges:
      - source: sim.engine.simulate
        target: sim.activities.base.ActivityHandler
        relation: uses
        metadata:
          note: "Runtime dispatch via handler registry"
    hidden:
      - sim.core.types.Quaternion
    ```
    """
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data or {}


def apply_overrides(graph: IRGraph, overrides: dict[str, Any]) -> IRGraph:
    """Apply overrides to an IR graph in-place and return it.

    Args:
        graph: The IR graph to modify.
        overrides: Parsed override data.

    Returns:
        The modified graph.
    """
    # Apply node overrides
    node_overrides = overrides.get("nodes", {})
    if node_overrides:
        node_lookup = {n.id: n for n in graph.nodes}
        for node_id, props in node_overrides.items():
            node = node_lookup.get(node_id)
            if node:
                if "display_name" in props:
                    node.display_name = props["display_name"]
                if "description" in props:
                    node.description = props["description"]
                if "group" in props:
                    node.group = props["group"]
                if "metadata" in props:
                    node.metadata.update(props["metadata"])

    # Apply hidden nodes
    hidden = overrides.get("hidden", [])
    if hidden:
        for node in graph.nodes:
            if node.id in hidden:
                node.hidden = True
        # Also remove edges to/from hidden nodes
        hidden_set = set(hidden)
        graph.edges = [
            e
            for e in graph.edges
            if e.source not in hidden_set and e.target not in hidden_set
        ]

    # Add extra edges
    extra_edges = overrides.get("edges", [])
    if extra_edges:
        existing_ids = {e.id for e in graph.edges}
        for edge_data in extra_edges:
            source = edge_data.get("source", "")
            target = edge_data.get("target", "")
            relation = edge_data.get("relation", "uses")
            edge_id = f"{source}--{relation}--{target}"
            if edge_id not in existing_ids:
                graph.edges.append(
                    IREdge(
                        id=edge_id,
                        source=source,
                        target=target,
                        relation=relation,
                        metadata=edge_data.get("metadata", {}),
                    )
                )

    return graph
