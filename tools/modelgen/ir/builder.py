"""Assemble extractor outputs into an IR graph."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from tools.modelgen.extractors.base import (
    EdgeRelation,
    ExtractedSymbol,
    ImportEdge,
    InvariantInfo,
)
from tools.modelgen.extractors.class_extractor import ClassExtractor
from tools.modelgen.extractors.import_extractor import ImportExtractor
from tools.modelgen.extractors.abc_extractor import ABCExtractor
from tools.modelgen.extractors.registry_extractor import RegistryExtractor
from tools.modelgen.extractors.invariant_extractor import InvariantExtractor
from tools.modelgen.ir.schema import IREdge, IRGraph, IRGroup, IRInvariant, IRNode


class IRBuilder:
    """Orchestrates extraction and builds the IR graph."""

    def __init__(self, root: Path, config: dict | None = None):
        self.root = root
        self.config = config or {}
        self._groups: list[IRGroup] = []
        self._load_groups()

    def build(self, scan_paths: list[str] | None = None, exclude_paths: list[str] | None = None) -> IRGraph:
        """Run all extractors and assemble the IR graph.

        Args:
            scan_paths: List of directory paths relative to root to scan.
            exclude_paths: List of path patterns to exclude.

        Returns:
            Complete IRGraph.
        """
        if scan_paths is None:
            scan_paths = self.config.get("scan_paths", ["sim", "cli", "sim_mcp"])
        if exclude_paths is None:
            exclude_paths = self.config.get("exclude_paths", ["__pycache__", ".pyc"])

        # Initialize extractors
        project_prefixes = self.config.get("project_prefixes", ["sim", "cli", "sim_mcp", "tools"])
        class_ext = ClassExtractor(self.root, project_prefixes)
        import_ext = ImportExtractor(self.root, project_prefixes)
        abc_ext = ABCExtractor(self.root, project_prefixes)
        registry_ext = RegistryExtractor(self.root, project_prefixes)
        invariant_ext = InvariantExtractor(self.root, project_prefixes)

        # Collect all Python files
        py_files = self._collect_files(scan_paths, exclude_paths)

        # Run extractors on each file
        for file_path in sorted(py_files):
            rel_path = file_path.relative_to(self.root)
            module_name = self._path_to_module(rel_path)
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(rel_path))
            except (SyntaxError, UnicodeDecodeError):
                continue

            class_ext.extract(rel_path, tree, module_name)
            import_ext.extract(rel_path, tree, module_name)
            abc_ext.extract(rel_path, tree, module_name)
            registry_ext.extract(rel_path, tree, module_name)
            invariant_ext.extract(rel_path, tree, module_name)

        # Post-processing: resolve ABC implementations
        abc_ext.resolve()

        # Extract invariants from CLAUDE.md
        claude_md = self.root / "CLAUDE.md"
        invariant_ext.extract_from_claude_md(claude_md)

        # Also check for standalone functions (simulate)
        func_symbols = self._extract_standalone_functions(py_files)

        # Assemble graph
        graph = self._assemble(
            symbols=class_ext.get_symbols() + func_symbols,
            import_edges=import_ext.get_edges(),
            abc_edges=abc_ext.get_edges(),
            registry_edges=registry_ext.get_edges(),
            invariants=invariant_ext.get_invariants(),
        )

        # Add metadata
        graph.metadata["git_sha"] = self._get_git_sha()
        graph.metadata["root"] = str(self.root)
        graph.metadata["scan_paths"] = scan_paths

        return graph

    def _collect_files(self, scan_paths: list[str], exclude_paths: list[str]) -> list[Path]:
        """Collect all Python files from scan paths."""
        files = []
        for sp in scan_paths:
            scan_dir = self.root / sp
            if not scan_dir.exists():
                continue
            for py_file in scan_dir.rglob("*.py"):
                rel = str(py_file.relative_to(self.root))
                if any(exc in rel for exc in exclude_paths):
                    continue
                files.append(py_file)
        return sorted(files)

    def _path_to_module(self, rel_path: Path) -> str:
        """Convert a relative file path to a module name."""
        parts = list(rel_path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].replace(".py", "")
        return ".".join(parts)

    def _extract_standalone_functions(self, py_files: list[Path]) -> list[ExtractedSymbol]:
        """Extract key standalone functions (e.g., simulate)."""
        from tools.modelgen.extractors.base import SymbolKind

        symbols = []
        target_functions = {"simulate", "main"}

        for file_path in py_files:
            rel_path = file_path.relative_to(self.root)
            module_name = self._path_to_module(rel_path)
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(rel_path))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef) and node.name in target_functions:
                    # Skip if it's just a CLI click command wrapper named main
                    if node.name == "main" and "sim.engine" not in module_name:
                        continue
                    docstring = ""
                    if (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    ):
                        docstring = node.body[0].value.value.strip()

                    symbols.append(
                        ExtractedSymbol(
                            qualified_name=f"{module_name}.{node.name}",
                            name=node.name,
                            kind=SymbolKind.FUNCTION,
                            module_path=module_name,
                            file_path=str(rel_path),
                            line_number=node.lineno,
                            docstring=docstring,
                        )
                    )
        return symbols

    def _assemble(
        self,
        symbols: list[ExtractedSymbol],
        import_edges: list[ImportEdge],
        abc_edges: list[ImportEdge],
        registry_edges: list[ImportEdge],
        invariants: list[InvariantInfo],
    ) -> IRGraph:
        """Assemble all extracted data into an IRGraph."""
        # Build node lookup
        node_ids = set()
        nodes = []
        for sym in symbols:
            if sym.qualified_name in node_ids:
                continue
            node_ids.add(sym.qualified_name)
            group = self._assign_group(sym.module_path)
            node = IRNode(
                id=sym.qualified_name,
                name=sym.name,
                kind=sym.kind.value,
                group=group,
                module_path=sym.module_path,
                file_path=sym.file_path,
                line_number=sym.line_number,
                docstring=sym.docstring,
                bases=sym.bases,
                fields=[
                    {
                        "name": f.name,
                        "type": f.type_annotation,
                        "default": f.default,
                        "optional": f.is_optional,
                    }
                    for f in sym.fields
                ],
                methods=[
                    {
                        "name": m.name,
                        "abstract": m.is_abstract,
                        "property": m.is_property,
                        "params": m.parameters,
                        "return_type": m.return_type,
                        "docstring": m.docstring,
                    }
                    for m in sym.methods
                ],
                decorators=sym.decorators,
            )
            nodes.append(node)

        # Build edges, filtering to known nodes
        edges = []
        edge_ids = set()

        all_edges = import_edges + abc_edges + registry_edges
        for imp in all_edges:
            # Resolve target to a known node
            target_id = self._resolve_edge_target(imp.target, node_ids)
            source_id = self._resolve_edge_source(imp.source, node_ids)
            if not target_id or not source_id:
                continue
            if source_id == target_id:
                continue

            edge_id = f"{source_id}--{imp.relation.value}--{target_id}"
            if edge_id in edge_ids:
                continue
            edge_ids.add(edge_id)

            edges.append(
                IREdge(
                    id=edge_id,
                    source=source_id,
                    target=target_id,
                    relation=imp.relation.value,
                    is_lazy=imp.is_lazy,
                )
            )

        # Build invariants
        ir_invariants = []
        for inv in invariants:
            # Resolve related components to node IDs
            related = []
            for comp in inv.related_components:
                resolved = self._resolve_edge_target(comp, node_ids)
                if resolved:
                    related.append(resolved)

            ir_invariants.append(
                IRInvariant(
                    id=inv.id,
                    description=inv.description,
                    severity=inv.severity,
                    source=inv.source,
                    file_path=inv.file_path,
                    line_number=inv.line_number,
                    related_nodes=related,
                )
            )

        return IRGraph(
            nodes=nodes,
            edges=edges,
            groups=self._groups,
            invariants=ir_invariants,
            metadata={},
        )

    def _assign_group(self, module_path: str) -> str:
        """Assign a group ID based on module path."""
        for group in self._groups:
            for pattern in group.module_patterns:
                if module_path.startswith(pattern) or module_path == pattern:
                    return group.id
        return "infrastructure"

    def _resolve_edge_target(self, target: str, node_ids: set[str]) -> str | None:
        """Resolve an edge target to a known node ID."""
        if target in node_ids:
            return target
        # Try prefix match (import of module, class inside module)
        # Use sorted iteration for determinism
        candidates = []
        for nid in sorted(node_ids):
            if nid == target:
                return nid
            if nid.startswith(target + "."):
                candidates.append(nid)
            # Check if target ends with the node's short name
            parts = nid.rsplit(".", 1)
            if len(parts) == 2 and target.endswith("." + parts[1]):
                candidates.append(nid)
        return candidates[0] if candidates else None

    def _resolve_edge_source(self, source: str, node_ids: set[str]) -> str | None:
        """Resolve an edge source to a known node ID.

        For module-level sources, picks the first node alphabetically
        in that module to ensure determinism.
        """
        if source in node_ids:
            return source
        # Find the first node (alphabetically) whose qualified name starts with source
        candidates = sorted(nid for nid in node_ids if nid.startswith(source + "."))
        return candidates[0] if candidates else None

    def _get_git_sha(self) -> str:
        """Get current git SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.root,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _load_groups(self) -> None:
        """Load group definitions from config."""
        groups_config = self.config.get("groups", {})
        if groups_config:
            for gid, gdata in groups_config.items():
                self._groups.append(
                    IRGroup(
                        id=gid,
                        name=gdata.get("name", gid),
                        color=gdata.get("color", "#6b7280"),
                        description=gdata.get("description", ""),
                        module_patterns=gdata.get("module_patterns", []),
                    )
                )
        else:
            # Default groups for this codebase
            self._groups = [
                IRGroup(
                    id="engine",
                    name="Engine",
                    color="#ef4444",
                    description="Core simulation engine",
                    module_patterns=["sim.engine", "sim.cache"],
                ),
                IRGroup(
                    id="core_types",
                    name="Core Types",
                    color="#a855f7",
                    description="Core data structures and configuration",
                    module_patterns=["sim.core"],
                ),
                IRGroup(
                    id="models",
                    name="Physical Models",
                    color="#06b6d4",
                    description="Physical simulation models",
                    module_patterns=["sim.models"],
                ),
                IRGroup(
                    id="activities",
                    name="Activity Handlers",
                    color="#22c55e",
                    description="Activity handler implementations",
                    module_patterns=["sim.activities"],
                ),
                IRGroup(
                    id="io",
                    name="I/O",
                    color="#f59e0b",
                    description="Input/output and external integrations",
                    module_patterns=["sim.io"],
                ),
                IRGroup(
                    id="viz",
                    name="Visualization",
                    color="#ec4899",
                    description="Visualization and output formatting",
                    module_patterns=["sim.viz"],
                ),
                IRGroup(
                    id="cli",
                    name="CLI",
                    color="#6366f1",
                    description="Command-line interface",
                    module_patterns=["cli"],
                ),
                IRGroup(
                    id="mcp",
                    name="MCP",
                    color="#8b5cf6",
                    description="MCP server integration",
                    module_patterns=["sim_mcp"],
                ),
                IRGroup(
                    id="infrastructure",
                    name="Infrastructure",
                    color="#64748b",
                    description="Infrastructure and utilities",
                    module_patterns=["tools", "scripts"],
                ),
            ]
