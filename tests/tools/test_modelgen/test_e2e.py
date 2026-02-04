"""End-to-end test: extract + build pipeline."""

import json
from pathlib import Path

import pytest

from tools.modelgen.config import load_config
from tools.modelgen.ir.builder import IRBuilder
from tools.modelgen.ir.serializer import serialize_graph
from tools.modelgen.overrides.loader import apply_overrides, load_overrides
from tools.modelgen.overrides.validator import validate_overrides
from tools.modelgen.generators.json_export import export_json


class TestEndToEnd:
    def test_full_pipeline(self, tmp_path):
        """Run the full extract -> build pipeline and verify outputs."""
        root = Path(".").resolve()
        mappings_path = root / "spec" / "mappings.yml"
        overrides_path = root / "spec" / "overrides.yml"

        # Step 1: Load config
        config = load_config(mappings_path)
        assert "scan_paths" in config

        # Step 2: Extract
        builder = IRBuilder(root, config)
        graph = builder.build()

        # Verify extraction quality
        assert len(graph.nodes) >= 25, f"Expected >=25 nodes, got {len(graph.nodes)}"
        assert len(graph.edges) >= 30, f"Expected >=30 edges, got {len(graph.edges)}"
        assert len(graph.invariants) >= 5, f"Expected >=5 invariants, got {len(graph.invariants)}"

        # Check node kinds distribution
        kinds = {}
        for n in graph.nodes:
            kinds[n.kind] = kinds.get(n.kind, 0) + 1
        assert kinds.get("component", 0) >= 5, f"Expected >=5 components, got {kinds}"
        assert kinds.get("data_type", 0) >= 10, f"Expected >=10 data_types, got {kinds}"
        assert kinds.get("enum", 0) >= 3, f"Expected >=3 enums, got {kinds}"

        # Step 3: Serialize IR
        ir_json = serialize_graph(graph)
        ir_path = tmp_path / "ir.json"
        ir_path.write_text(ir_json)

        # Verify JSON is valid
        ir_data = json.loads(ir_json)
        assert "nodes" in ir_data
        assert "edges" in ir_data
        assert "schema_version" in ir_data

        # Step 4: Apply overrides
        overrides = load_overrides(overrides_path)
        if overrides:
            graph = apply_overrides(graph, overrides)

        # Step 5: Validate overrides
        overrides = load_overrides(overrides_path)
        issues = validate_overrides(graph, overrides)
        # All overrides in spec/overrides.yml should be valid
        stale = [i for i in issues if i.level == "error"]
        assert len(stale) == 0, f"Stale overrides found: {[i.message for i in stale]}"

        # Step 6: Export model.json
        out_file = export_json(graph, tmp_path)
        assert out_file.exists()

        model_data = json.loads(out_file.read_text())
        assert len(model_data["nodes"]) > 0
        assert len(model_data["edges"]) > 0

    def test_invariants_from_claude_md(self):
        """Verify CLAUDE.md invariants are extracted."""
        root = Path(".").resolve()
        builder = IRBuilder(root)
        graph = builder.build(scan_paths=["sim"])

        # Should have invariants from CLAUDE.md
        claude_md_invs = [i for i in graph.invariants if i.source == "claude_md"]
        assert len(claude_md_invs) >= 5, (
            f"Expected >=5 CLAUDE.md invariants, got {len(claude_md_invs)}: "
            f"{[i.description[:40] for i in claude_md_invs]}"
        )

        # Check specific invariants
        descriptions = [i.description for i in claude_md_invs]
        found_soc = any("SOC" in d for d in descriptions)
        found_storage = any("Storage" in d or "storage" in d for d in descriptions)
        assert found_soc, f"SOC invariant not found. Got: {descriptions}"
        assert found_storage, f"Storage invariant not found. Got: {descriptions}"

    def test_key_architecture_components(self):
        """Verify key components are extracted from the codebase."""
        root = Path(".").resolve()
        builder = IRBuilder(root)
        graph = builder.build(scan_paths=["sim", "cli"])

        node_ids = {n.id for n in graph.nodes}
        node_names = {n.name for n in graph.nodes}

        # Must-have types
        assert "Fidelity" in node_names, "Fidelity enum not found"
        assert "EventType" in node_names, "EventType enum not found"
        assert "SimConfig" in node_names, "SimConfig not found"
        assert "SimResults" in node_names, "SimResults not found"
        assert "InitialState" in node_names, "InitialState not found"

        # Must-have models
        assert "PowerModel" in node_names, "PowerModel not found"

        # Must-have activity handler base
        assert "ActivityHandler" in node_names, "ActivityHandler not found"

        # Check simulate function
        assert "simulate" in node_names, "simulate function not found"
