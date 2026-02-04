"""Export IR graph as SysML v2 textual notation (optional secondary output)."""

from __future__ import annotations

from pathlib import Path

from tools.modelgen.ir.schema import IRGraph


def export_sysml(graph: IRGraph, output_path: Path) -> Path:
    """Export the IR graph as SysML v2 text.

    Args:
        graph: The IR graph to export.
        output_path: Directory to write model.sysml into.

    Returns:
        Path to the written file.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    out_file = output_path / "model.sysml"

    lines = []
    lines.append("// Auto-generated SysML v2 model")
    lines.append(f"// Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")
    lines.append("")

    # Package per group
    groups_used = {n.group for n in graph.nodes if not n.hidden}
    group_lookup = {g.id: g for g in graph.groups}

    for group_id in sorted(groups_used):
        group = group_lookup.get(group_id)
        group_name = group.name if group else group_id
        lines.append(f"package '{group_name}' {{")
        lines.append("")

        group_nodes = sorted(
            [n for n in graph.nodes if n.group == group_id and not n.hidden],
            key=lambda n: n.id,
        )

        for node in group_nodes:
            kind_kw = _kind_to_sysml(node.kind)
            lines.append(f"  {kind_kw} '{node.display_name or node.name}' {{")
            if node.docstring:
                doc_line = node.docstring.split("\n")[0][:80]
                lines.append(f'    doc /* {doc_line} */')

            for field_dict in node.fields:
                fname = field_dict.get("name", "")
                ftype = field_dict.get("type", "")
                if fname:
                    lines.append(f"    attribute {fname} : {ftype or 'Any'};")

            for method_dict in node.methods:
                mname = method_dict.get("name", "")
                if mname and not mname.startswith("_"):
                    ret = method_dict.get("return_type", "")
                    lines.append(f"    perform action {mname}() : {ret or 'void'};")

            lines.append("  }")
            lines.append("")

        lines.append("}")
        lines.append("")

    # Connections
    lines.append("// Connections")
    for edge in sorted(graph.edges, key=lambda e: e.id):
        lines.append(f"connection '{edge.relation}' from '{edge.source}' to '{edge.target}';")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


def _kind_to_sysml(kind: str) -> str:
    """Map IR node kind to SysML keyword."""
    mapping = {
        "component": "part def",
        "data_type": "attribute def",
        "enum": "enum def",
        "interface": "port def",
        "function": "action def",
        "handler": "part def",
        "module": "package",
    }
    return mapping.get(kind, "part def")
