"""Click CLI for modelgen: extract, build, serve, check."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import click

from tools.modelgen.config import load_architecture_config, load_config
from tools.modelgen.ir.builder import IRBuilder
from tools.modelgen.ir.serializer import serialize_arch_model, serialize_graph
from tools.modelgen.overrides.loader import apply_overrides, load_overrides
from tools.modelgen.overrides.validator import validate_overrides
from tools.modelgen.generators.json_export import export_json
from tools.modelgen.logging import get_logger, new_correlation_id, timed_operation


@click.group()
@click.version_option(version="0.1.0", prog_name="modelgen")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--json-logs", is_flag=True, help="Output structured JSON logs.")
def modelgen(verbose: bool, json_logs: bool):
    """Code-first architecture model generator."""
    import logging

    new_correlation_id()
    level = logging.DEBUG if verbose else logging.INFO
    log = get_logger("cli", structured=json_logs)
    log.setLevel(level)


@modelgen.command()
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Project root directory.",
)
@click.option(
    "--mappings",
    type=click.Path(path_type=Path),
    default="spec/mappings.yml",
    help="Path to mappings.yml configuration.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default="build/modelgen/ir.json",
    help="Output path for IR JSON.",
)
@click.option(
    "--architecture",
    type=click.Path(path_type=Path),
    default="spec/architecture_layers.yml",
    help="Path to architecture_layers.yml for v2 output.",
)
def extract(root: Path, mappings: Path, output: Path, architecture: Path):
    """Extract architecture from source code into IR JSON."""
    log = get_logger("cli")
    root = root.resolve()
    mappings_path = root / mappings if not mappings.is_absolute() else mappings

    click.echo(f"Loading config from {mappings_path}")
    config = load_config(mappings_path)

    click.echo(f"Scanning {root} ...")
    with timed_operation(log, "extraction") as ctx:
        builder = IRBuilder(root, config)
        graph = builder.build()
        ctx["node_count"] = len(graph.nodes)
        ctx["edge_count"] = len(graph.edges)

    click.echo(
        f"Extracted: {len(graph.nodes)} nodes, {len(graph.edges)} edges, "
        f"{len(graph.invariants)} invariants"
    )

    # Write output
    output_path = root / output if not output.is_absolute() else output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try v2 architecture output
    arch_path = root / architecture if not architecture.is_absolute() else architecture
    arch_config = load_architecture_config(arch_path)

    if arch_config:
        from tools.modelgen.ir.architecture_builder import ArchitectureBuilder

        click.echo(f"Building architecture model from {arch_path}")
        arch_builder = ArchitectureBuilder(graph, arch_config)
        arch_model = arch_builder.build()
        json_str = serialize_arch_model(arch_model)
        click.echo(
            f"Architecture: {len(arch_model.arch_nodes)} arch nodes, "
            f"{len(arch_model.arch_edges)} arch edges, "
            f"{len(arch_model.requirements)} requirements"
        )
    else:
        click.echo("No architecture_layers.yml found, producing v1 output")
        json_str = serialize_graph(graph)

    output_path.write_text(json_str, encoding="utf-8")
    click.echo(f"Written: {output_path}")

    # Summary by kind
    kinds = {}
    for n in graph.nodes:
        kinds[n.kind] = kinds.get(n.kind, 0) + 1
    for kind, count in sorted(kinds.items()):
        click.echo(f"  {kind}: {count}")

    # Summary by group
    groups = {}
    for n in graph.nodes:
        groups[n.group] = groups.get(n.group, 0) + 1
    click.echo("Groups:")
    for group, count in sorted(groups.items()):
        click.echo(f"  {group}: {count}")


@modelgen.command()
@click.option(
    "--ir",
    type=click.Path(exists=True, path_type=Path),
    default="build/modelgen/ir.json",
    help="Path to IR JSON file.",
)
@click.option(
    "--overrides",
    type=click.Path(path_type=Path),
    default="spec/overrides.yml",
    help="Path to overrides YAML.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default="build/modelgen/",
    help="Output directory for model.json.",
)
def build(ir: Path, overrides: Path, output: Path):
    """Apply overrides to IR and produce model.json for the viewer."""
    click.echo(f"Loading IR from {ir}")
    ir_data = json.loads(ir.read_text())

    click.echo(f"Loading overrides from {overrides}")
    override_data = load_overrides(overrides)

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    out_file = output_path / "model.json"

    # Check for v2 architecture model format
    if ir_data.get("schema_version") == "2.0" and "architecture" in ir_data:
        # v2 format: preserve full architecture model
        click.echo("Detected v2 architecture model")

        # Apply overrides to the ir_graph portion
        if override_data and "ir_graph" in ir_data:
            graph = _json_to_graph(ir_data["ir_graph"])
            graph = apply_overrides(graph, override_data)
            click.echo("Applied overrides to ir_graph")

            # Serialize the updated ir_graph back into the model
            from tools.modelgen.ir.serializer import serialize_graph_to_dict
            ir_data["ir_graph"] = serialize_graph_to_dict(graph)

        # Write the full v2 model
        json_str = json.dumps(ir_data, indent=2, sort_keys=True, ensure_ascii=False)
        out_file.write_text(json_str, encoding="utf-8")
        click.echo(f"Written: {out_file}")

        arch_nodes = len(ir_data.get("architecture", {}).get("nodes", []))
        arch_edges = len(ir_data.get("architecture", {}).get("edges", []))
        ir_nodes = len(ir_data.get("ir_graph", {}).get("nodes", []))
        viewpoints = len(ir_data.get("viewpoints", []))
        reqs = len(ir_data.get("requirements", {}).get("items", []))
        click.echo(
            f"Model: {arch_nodes} arch nodes, {arch_edges} arch edges, "
            f"{ir_nodes} ir nodes, {viewpoints} viewpoints, {reqs} requirements"
        )
    else:
        # v1 format: legacy behavior
        click.echo("Detected v1 format (legacy)")
        graph = _json_to_graph(ir_data)

        if override_data:
            graph = apply_overrides(graph, override_data)
            click.echo("Applied overrides")

        # Export v1 format
        out_file = export_json(graph, output_path)
        click.echo(f"Written: {out_file}")

        visible = sum(1 for n in graph.nodes if not n.hidden)
        click.echo(f"Model: {visible} visible nodes, {len(graph.edges)} edges")


@modelgen.command()
@click.option(
    "--ir",
    type=click.Path(exists=True, path_type=Path),
    default="build/modelgen/ir.json",
    help="Path to IR JSON file.",
)
@click.option(
    "--overrides",
    type=click.Path(exists=True, path_type=Path),
    default="spec/overrides.yml",
    help="Path to overrides YAML.",
)
def check(ir: Path, overrides: Path):
    """Check overrides for stale references against the IR."""
    ir_data = json.loads(ir.read_text())
    graph = _json_to_graph(ir_data)

    override_data = load_overrides(overrides)
    if not override_data:
        click.echo("No overrides to check.")
        return

    issues = validate_overrides(graph, override_data)
    if not issues:
        click.secho("All overrides are valid.", fg="green")
        return

    for issue in issues:
        color = "yellow" if issue.level == "warning" else "red"
        click.secho(f"[{issue.level.upper()}] {issue.message}", fg=color)
        if issue.override_key:
            click.echo(f"  Key: {issue.override_key}")

    sys.exit(1)


@modelgen.command()
@click.option(
    "--dir",
    "serve_dir",
    type=click.Path(exists=True, path_type=Path),
    default="build/modelgen/",
    help="Directory containing model.json and viewer files.",
)
@click.option("--port", type=int, default=8090, help="Port for HTTP server.")
@click.option("--no-open", is_flag=True, help="Don't auto-open browser.")
def serve(serve_dir: Path, port: int, no_open: bool):
    """Serve the architecture viewer."""
    import http.server
    import os
    import threading
    import webbrowser

    serve_dir = serve_dir.resolve()

    # Check if viewer dist exists; if not, try to copy from modelui
    viewer_index = serve_dir / "index.html"
    if not viewer_index.exists():
        # Try to find built viewer
        modelui_dist = Path(__file__).parent.parent / "modelui" / "dist"
        if modelui_dist.exists():
            click.echo(f"Copying viewer from {modelui_dist}")
            for item in modelui_dist.iterdir():
                dest = serve_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
        else:
            click.echo("Warning: No viewer dist found. Serving model.json only.")
            click.echo("Build the viewer first: cd tools/modelui && npm run build")

    os.chdir(serve_dir)

    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer(("localhost", port), handler)

    url = f"http://localhost:{port}"
    click.echo(f"Serving at {url}")

    if not no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nShutting down.")
        server.shutdown()


def _json_to_graph(data: dict) -> "IRGraph":
    """Reconstruct an IRGraph from parsed JSON."""
    from tools.modelgen.ir.schema import IREdge, IRGraph, IRGroup, IRInvariant, IRNode

    # Handle v2 format: ir_graph is nested under "ir_graph" key
    if data.get("schema_version") == "2.0" and "ir_graph" in data:
        data = data["ir_graph"]

    nodes = []
    for nd in data.get("nodes", []):
        nodes.append(
            IRNode(
                id=nd["id"],
                name=nd.get("name", ""),
                kind=nd.get("kind", "component"),
                group=nd.get("group", ""),
                module_path=nd.get("module_path", ""),
                file_path=nd.get("file_path", ""),
                line_number=nd.get("line_number", 0),
                docstring=nd.get("docstring", ""),
                display_name=nd.get("display_name", ""),
                description=nd.get("description", ""),
                bases=nd.get("bases", []),
                fields=nd.get("fields", []),
                methods=nd.get("methods", []),
                decorators=nd.get("decorators", []),
                hidden=nd.get("hidden", False),
                metadata=nd.get("metadata", {}),
            )
        )

    edges = []
    for ed in data.get("edges", []):
        edges.append(
            IREdge(
                id=ed["id"],
                source=ed.get("source", ""),
                target=ed.get("target", ""),
                relation=ed.get("relation", "imports"),
                is_lazy=ed.get("is_lazy", False),
                metadata=ed.get("metadata", {}),
            )
        )

    groups = []
    for gd in data.get("groups", []):
        groups.append(
            IRGroup(
                id=gd["id"],
                name=gd.get("name", ""),
                color=gd.get("color", "#6b7280"),
                description=gd.get("description", ""),
                module_patterns=gd.get("module_patterns", []),
            )
        )

    invariants = []
    for inv in data.get("invariants", []):
        invariants.append(
            IRInvariant(
                id=inv["id"],
                description=inv.get("description", ""),
                severity=inv.get("severity", "must"),
                source=inv.get("source", "code"),
                file_path=inv.get("file_path", ""),
                line_number=inv.get("line_number", 0),
                related_nodes=inv.get("related_nodes", []),
            )
        )

    return IRGraph(
        nodes=nodes,
        edges=edges,
        groups=groups,
        invariants=invariants,
        metadata=data.get("metadata", {}),
    )


if __name__ == "__main__":
    modelgen()
