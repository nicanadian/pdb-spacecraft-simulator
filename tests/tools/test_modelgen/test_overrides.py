"""Tests for override loading, application, and validation."""

from pathlib import Path

import pytest

from tools.modelgen.ir.schema import IREdge, IRGraph, IRNode
from tools.modelgen.overrides.loader import apply_overrides, load_overrides
from tools.modelgen.overrides.validator import validate_overrides


def _make_graph():
    return IRGraph(
        nodes=[
            IRNode(id="sim.core.types.SimConfig", name="SimConfig", kind="data_type"),
            IRNode(id="sim.engine.simulate", name="simulate", kind="function"),
            IRNode(id="sim.models.power.PowerModel", name="PowerModel", kind="component"),
        ],
        edges=[
            IREdge(
                id="sim.engine.simulate--imports--sim.core.types.SimConfig",
                source="sim.engine.simulate",
                target="sim.core.types.SimConfig",
                relation="imports",
            ),
        ],
    )


class TestOverrideLoader:
    def test_apply_display_names(self):
        graph = _make_graph()
        overrides = {
            "nodes": {
                "sim.core.types.SimConfig": {
                    "display_name": "SimConfig (Pydantic)",
                    "description": "Configuration object",
                },
            },
        }
        apply_overrides(graph, overrides)
        node = graph.node_by_id("sim.core.types.SimConfig")
        assert node is not None
        assert node.display_name == "SimConfig (Pydantic)"
        assert node.description == "Configuration object"

    def test_apply_hidden_nodes(self):
        graph = _make_graph()
        overrides = {
            "hidden": ["sim.models.power.PowerModel"],
        }
        apply_overrides(graph, overrides)

        power = graph.node_by_id("sim.models.power.PowerModel")
        assert power is not None
        assert power.hidden is True

        # Edges to/from hidden nodes should be removed
        for e in graph.edges:
            assert e.source != "sim.models.power.PowerModel"
            assert e.target != "sim.models.power.PowerModel"

    def test_apply_extra_edges(self):
        graph = _make_graph()
        overrides = {
            "edges": [
                {
                    "source": "sim.engine.simulate",
                    "target": "sim.models.power.PowerModel",
                    "relation": "uses",
                    "metadata": {"note": "test"},
                },
            ],
        }
        apply_overrides(graph, overrides)
        assert len(graph.edges) == 2
        new_edge = [e for e in graph.edges if e.relation == "uses"]
        assert len(new_edge) == 1
        assert new_edge[0].metadata.get("note") == "test"

    def test_load_nonexistent_file(self):
        result = load_overrides(Path("/nonexistent/file.yml"))
        assert result == {}


class TestOverrideValidator:
    def test_valid_overrides(self):
        graph = _make_graph()
        overrides = {
            "nodes": {
                "sim.core.types.SimConfig": {"display_name": "Config"},
            },
        }
        issues = validate_overrides(graph, overrides)
        assert len(issues) == 0

    def test_stale_node_override(self):
        graph = _make_graph()
        overrides = {
            "nodes": {
                "sim.nonexistent.Foo": {"display_name": "Foo"},
            },
        }
        issues = validate_overrides(graph, overrides)
        assert len(issues) == 1
        assert "stale" in issues[0].message.lower()

    def test_stale_hidden_node(self):
        graph = _make_graph()
        overrides = {
            "hidden": ["sim.nonexistent.Bar"],
        }
        issues = validate_overrides(graph, overrides)
        assert len(issues) == 1

    def test_stale_edge_source(self):
        graph = _make_graph()
        overrides = {
            "edges": [
                {
                    "source": "sim.nonexistent.Baz",
                    "target": "sim.engine.simulate",
                    "relation": "uses",
                },
            ],
        }
        issues = validate_overrides(graph, overrides)
        assert len(issues) == 1
        assert "source" in issues[0].message.lower()
