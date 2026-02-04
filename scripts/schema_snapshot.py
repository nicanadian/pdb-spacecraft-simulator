#!/usr/bin/env python3
"""IR schema snapshot for drift detection.

Generates a structural snapshot of the IR JSON that captures:
- Node IDs and their kinds
- Edge IDs and their relations
- Group IDs
- Invariant IDs and sources

Use this to detect interface drift between what docs say and what code produces.

Usage:
    # Generate snapshot
    python scripts/schema_snapshot.py --ir build/modelgen/ir.json --output spec/ir_schema_snapshot.json

    # Check for drift
    python scripts/schema_snapshot.py --ir build/modelgen/ir.json --check spec/ir_schema_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def generate_snapshot(ir_path: Path) -> dict:
    """Generate a structural snapshot from IR JSON."""
    data = json.loads(ir_path.read_text())

    snapshot = {
        "schema_version": data.get("schema_version", "unknown"),
        "summary": {
            "node_count": len(data.get("nodes", [])),
            "edge_count": len(data.get("edges", [])),
            "group_count": len(data.get("groups", [])),
            "invariant_count": len(data.get("invariants", [])),
        },
        "node_ids": sorted(n["id"] for n in data.get("nodes", [])),
        "node_kinds": sorted(set(n.get("kind", "") for n in data.get("nodes", []))),
        "edge_relations": sorted(set(e.get("relation", "") for e in data.get("edges", []))),
        "group_ids": sorted(g["id"] for g in data.get("groups", [])),
        "invariant_sources": sorted(set(i.get("source", "") for i in data.get("invariants", []))),
        "nodes_by_kind": {},
        "nodes_by_group": {},
    }

    # Count by kind
    for n in data.get("nodes", []):
        kind = n.get("kind", "unknown")
        snapshot["nodes_by_kind"][kind] = snapshot["nodes_by_kind"].get(kind, 0) + 1

    # Count by group
    for n in data.get("nodes", []):
        group = n.get("group", "unknown")
        snapshot["nodes_by_group"][group] = snapshot["nodes_by_group"].get(group, 0) + 1

    return snapshot


def check_drift(ir_path: Path, snapshot_path: Path) -> list[str]:
    """Check current IR against a saved snapshot for structural drift.

    Returns list of drift descriptions (empty = no drift).
    """
    current = generate_snapshot(ir_path)
    saved = json.loads(snapshot_path.read_text())
    drifts = []

    # Check schema version
    if current["schema_version"] != saved.get("schema_version"):
        drifts.append(
            f"Schema version changed: {saved.get('schema_version')} -> {current['schema_version']}"
        )

    # Check node IDs: added or removed
    current_ids = set(current["node_ids"])
    saved_ids = set(saved.get("node_ids", []))
    added = current_ids - saved_ids
    removed = saved_ids - current_ids
    if added:
        drifts.append(f"Nodes added ({len(added)}): {', '.join(sorted(added)[:5])}{'...' if len(added) > 5 else ''}")
    if removed:
        drifts.append(f"Nodes removed ({len(removed)}): {', '.join(sorted(removed)[:5])}{'...' if len(removed) > 5 else ''}")

    # Check group IDs
    current_groups = set(current["group_ids"])
    saved_groups = set(saved.get("group_ids", []))
    if current_groups != saved_groups:
        drifts.append(f"Groups changed: added={current_groups - saved_groups}, removed={saved_groups - current_groups}")

    # Check node kinds
    if set(current["node_kinds"]) != set(saved.get("node_kinds", [])):
        drifts.append(f"Node kinds changed: {saved.get('node_kinds')} -> {current['node_kinds']}")

    # Check edge relations
    if set(current["edge_relations"]) != set(saved.get("edge_relations", [])):
        drifts.append(f"Edge relations changed: {saved.get('edge_relations')} -> {current['edge_relations']}")

    # Check significant count changes (>20% difference)
    for key in ["node_count", "edge_count", "invariant_count"]:
        cur = current["summary"].get(key, 0)
        sav = saved.get("summary", {}).get(key, 0)
        if sav > 0:
            pct = abs(cur - sav) / sav * 100
            if pct > 20:
                drifts.append(f"Significant {key} change: {sav} -> {cur} ({pct:.0f}% change)")

    return drifts


def main():
    parser = argparse.ArgumentParser(description="IR schema snapshot and drift detection")
    parser.add_argument("--ir", type=Path, required=True, help="Path to IR JSON file")
    parser.add_argument("--output", type=Path, help="Write snapshot to this path")
    parser.add_argument("--check", type=Path, help="Check against this snapshot")
    args = parser.parse_args()

    if args.output:
        snapshot = generate_snapshot(args.ir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
        print(f"Snapshot written to {args.output}")
        print(f"  Nodes: {snapshot['summary']['node_count']}")
        print(f"  Edges: {snapshot['summary']['edge_count']}")
        print(f"  Groups: {snapshot['summary']['group_count']}")
        print(f"  Invariants: {snapshot['summary']['invariant_count']}")
        return 0

    if args.check:
        if not args.check.exists():
            print(f"Error: snapshot not found at {args.check}")
            print("Run with --output first to create a baseline snapshot.")
            return 1

        drifts = check_drift(args.ir, args.check)
        if not drifts:
            print("No schema drift detected.")
            return 0
        else:
            print(f"Schema drift detected ({len(drifts)} issues):")
            for d in drifts:
                print(f"  - {d}")
            print()
            print("If these changes are intentional, regenerate the snapshot:")
            print(f"  python scripts/schema_snapshot.py --ir {args.ir} --output {args.check}")
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
