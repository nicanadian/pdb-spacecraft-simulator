"""Export IR graph as viewer-ready JSON."""

from __future__ import annotations

from pathlib import Path

from tools.modelgen.ir.schema import IRGraph
from tools.modelgen.ir.serializer import serialize_graph


def export_json(graph: IRGraph, output_path: Path) -> Path:
    """Export the IR graph as model.json for the viewer.

    Args:
        graph: The IR graph to export.
        output_path: Directory to write model.json into.

    Returns:
        Path to the written file.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    out_file = output_path / "model.json"
    json_str = serialize_graph(graph)
    out_file.write_text(json_str, encoding="utf-8")
    return out_file
