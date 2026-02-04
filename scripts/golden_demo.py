#!/usr/bin/env python3
"""Golden demo scenario: end-to-end validation with seed data.

Runs a curated scenario that exercises the full modelgen pipeline
and verifies expected outputs. Useful for:
- Product demos
- Regression sanity checks
- Onboarding verification

Usage:
    python scripts/golden_demo.py
    make golden-demo
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from tools.modelgen.config import load_config
    from tools.modelgen.ir.builder import IRBuilder
    from tools.modelgen.ir.serializer import serialize_graph
    from tools.modelgen.overrides.loader import apply_overrides, load_overrides
    from tools.modelgen.overrides.validator import validate_overrides
    from tools.modelgen.generators.json_export import export_json

    print("=" * 60)
    print("GOLDEN DEMO: Architecture Model Generator")
    print("=" * 60)
    print()

    # Step 1: Load config
    print("[1/7] Loading configuration...")
    mappings_path = ROOT / "spec" / "mappings.yml"
    config = load_config(mappings_path)
    print(f"  Scan paths: {config.get('scan_paths', [])}")
    print(f"  Groups: {len(config.get('groups', {}))}")
    print()

    # Step 2: Extract
    print("[2/7] Extracting architecture from source code...")
    builder = IRBuilder(ROOT, config)
    graph = builder.build()
    print(f"  Nodes: {len(graph.nodes)}")
    print(f"  Edges: {len(graph.edges)}")
    print(f"  Invariants: {len(graph.invariants)}")
    print(f"  Groups used: {len({n.group for n in graph.nodes})}")
    print()

    # Step 3: Validate counts
    print("[3/7] Validating extraction quality...")
    checks = [
        (len(graph.nodes) >= 25, f"Node count ({len(graph.nodes)}) >= 25"),
        (len(graph.edges) >= 30, f"Edge count ({len(graph.edges)}) >= 30"),
        (len(graph.invariants) >= 5, f"Invariant count ({len(graph.invariants)}) >= 5"),
    ]

    # Check key node names
    node_names = {n.name for n in graph.nodes}
    key_nodes = ["SimConfig", "SimResults", "InitialState", "Fidelity", "PowerModel", "ActivityHandler"]
    for name in key_nodes:
        checks.append((name in node_names, f"Key node '{name}' present"))

    # Check groups
    groups_used = {n.group for n in graph.nodes}
    key_groups = ["core_types", "models", "activities", "engine"]
    for g in key_groups:
        checks.append((g in groups_used, f"Group '{g}' has nodes"))

    # Check CLAUDE.md invariants
    claude_invs = [i for i in graph.invariants if i.source == "claude_md"]
    checks.append((len(claude_invs) >= 5, f"CLAUDE.md invariants ({len(claude_invs)}) >= 5"))

    passed = 0
    failed = 0
    for ok, desc in checks:
        status = "PASS" if ok else "FAIL"
        symbol = "  \u2713" if ok else "  \u2717"
        print(f"  {symbol} {desc}: {status}")
        if ok:
            passed += 1
        else:
            failed += 1
    print()

    # Step 4: Test determinism
    print("[4/7] Testing deterministic output...")
    json1 = serialize_graph(graph)
    builder2 = IRBuilder(ROOT, config)
    graph2 = builder2.build()
    json2 = serialize_graph(graph2)
    is_deterministic = json1 == json2
    print(f"  {'PASS' if is_deterministic else 'FAIL'}: Two extractions produce identical output")
    if not is_deterministic:
        failed += 1
    else:
        passed += 1
    print()

    # Step 5: Apply overrides
    print("[5/7] Applying overrides...")
    overrides_path = ROOT / "spec" / "overrides.yml"
    overrides = load_overrides(overrides_path)
    graph = apply_overrides(graph, overrides)
    print(f"  Override categories: {list(overrides.keys())}")
    print()

    # Step 6: Validate overrides
    print("[6/7] Validating overrides (staleness check)...")
    overrides = load_overrides(overrides_path)
    issues = validate_overrides(graph, overrides)
    if issues:
        for issue in issues:
            print(f"  [{issue.level.upper()}] {issue.message}")
        failed += len([i for i in issues if i.level == "error"])
    else:
        print("  All overrides valid")
        passed += 1
    print()

    # Step 7: Export
    print("[7/7] Exporting model.json...")
    out_dir = ROOT / "build" / "modelgen"
    out_file = export_json(graph, out_dir)
    model_data = json.loads(out_file.read_text())
    print(f"  Output: {out_file}")
    print(f"  Visible nodes: {len(model_data['nodes'])}")
    print(f"  Edges: {len(model_data['edges'])}")
    print(f"  Schema version: {model_data.get('schema_version', 'unknown')}")
    print()

    # Summary
    print("=" * 60)
    total = passed + failed
    if failed == 0:
        print(f"GOLDEN DEMO PASSED ({passed}/{total} checks)")
    else:
        print(f"GOLDEN DEMO FAILED ({failed}/{total} checks failed)")
    print("=" * 60)

    # Print kind distribution
    print()
    print("Node distribution by kind:")
    kinds: dict[str, int] = {}
    for n in graph.nodes:
        if not n.hidden:
            kinds[n.kind] = kinds.get(n.kind, 0) + 1
    for kind, count in sorted(kinds.items()):
        print(f"  {kind}: {count}")

    print()
    print("Node distribution by group:")
    group_counts: dict[str, int] = {}
    for n in graph.nodes:
        if not n.hidden:
            group_counts[n.group] = group_counts.get(n.group, 0) + 1
    for group, count in sorted(group_counts.items()):
        print(f"  {group}: {count}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
