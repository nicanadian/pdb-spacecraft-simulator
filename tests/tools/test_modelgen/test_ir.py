"""Tests for IR builder, serializer, and schema."""

import json
from pathlib import Path

import pytest

from tools.modelgen.ir.schema import IREdge, IRGraph, IRGroup, IRInvariant, IRNode
from tools.modelgen.ir.serializer import serialize_graph, serialize_graph_to_dict
from tools.modelgen.ir.builder import IRBuilder


class TestIRSchema:
    def test_graph_node_lookup(self):
        graph = IRGraph(
            nodes=[
                IRNode(id="a.B", name="B", kind="component"),
                IRNode(id="a.C", name="C", kind="data_type"),
            ]
        )
        assert graph.node_by_id("a.B") is not None
        assert graph.node_by_id("a.B").name == "B"
        assert graph.node_by_id("unknown") is None

    def test_graph_edge_queries(self):
        graph = IRGraph(
            edges=[
                IREdge(id="a--imports--b", source="a", target="b", relation="imports"),
                IREdge(id="c--imports--a", source="c", target="a", relation="imports"),
            ]
        )
        assert len(graph.edges_from("a")) == 1
        assert len(graph.edges_to("a")) == 1


class TestSerializer:
    def test_deterministic_output(self):
        graph = IRGraph(
            nodes=[
                IRNode(id="z.Z", name="Z", kind="enum"),
                IRNode(id="a.A", name="A", kind="component"),
            ],
            edges=[
                IREdge(id="z--imports--a", source="z.Z", target="a.A", relation="imports"),
            ],
            groups=[
                IRGroup(id="g1", name="Group 1", color="#ff0000"),
            ],
        )
        json1 = serialize_graph(graph)
        json2 = serialize_graph(graph)
        assert json1 == json2

        # Verify nodes are sorted by ID
        data = json.loads(json1)
        node_ids = [n["id"] for n in data["nodes"]]
        assert node_ids == sorted(node_ids)

    def test_hidden_nodes_excluded(self):
        graph = IRGraph(
            nodes=[
                IRNode(id="a.A", name="A", kind="component"),
                IRNode(id="b.B", name="B", kind="data_type", hidden=True),
            ]
        )
        data = serialize_graph_to_dict(graph)
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == "a.A"

    def test_empty_fields_omitted(self):
        graph = IRGraph(
            nodes=[
                IRNode(id="a.A", name="A", kind="component"),
            ]
        )
        data = serialize_graph_to_dict(graph)
        node = data["nodes"][0]
        # Empty lists, strings, dicts should not appear
        assert "bases" not in node
        assert "fields" not in node
        assert "docstring" not in node


class TestIRBuilder:
    def test_build_on_codebase(self):
        """Integration test: build IR from the real codebase."""
        root = Path(".").resolve()
        builder = IRBuilder(root)
        graph = builder.build(scan_paths=["sim", "cli", "sim_mcp"])

        # Should have reasonable numbers
        assert len(graph.nodes) > 20, f"Expected >20 nodes, got {len(graph.nodes)}"
        assert len(graph.edges) > 30, f"Expected >30 edges, got {len(graph.edges)}"
        assert len(graph.invariants) > 5, f"Expected >5 invariants, got {len(graph.invariants)}"

        # Check for key expected nodes
        node_names = {n.name for n in graph.nodes}
        assert "SimConfig" in node_names
        assert "SimResults" in node_names
        assert "InitialState" in node_names
        assert "Fidelity" in node_names

        # Check groups are populated
        groups_used = {n.group for n in graph.nodes}
        assert "core_types" in groups_used
        assert "models" in groups_used

    def test_deterministic_build(self):
        """Two builds with same input produce identical output."""
        root = Path(".").resolve()
        builder1 = IRBuilder(root)
        graph1 = builder1.build(scan_paths=["sim"])

        builder2 = IRBuilder(root)
        graph2 = builder2.build(scan_paths=["sim"])

        json1 = serialize_graph(graph1)
        json2 = serialize_graph(graph2)
        assert json1 == json2, "Build output is not deterministic"

    def test_git_sha_in_metadata(self):
        root = Path(".").resolve()
        builder = IRBuilder(root)
        graph = builder.build(scan_paths=["sim"])
        assert "git_sha" in graph.metadata
        assert graph.metadata["git_sha"] != ""
