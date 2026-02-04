"""Extract import relationships from AST."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.modelgen.extractors.base import (
    BaseExtractor,
    EdgeRelation,
    ExtractedSymbol,
    ImportEdge,
)


class ImportExtractor(BaseExtractor):
    """Extracts import statements and classifies them as eager or lazy."""

    def __init__(self, root: Path, module_paths: list[str] | None = None):
        super().__init__(root, module_paths)
        self._edges: list[ImportEdge] = []
        self._project_prefixes = module_paths or ["sim", "cli", "sim_mcp", "tools"]

    def extract(self, file_path: Path, tree: ast.Module, module_name: str) -> None:
        # Module-level imports (eager)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                self._process_import(node, module_name, str(file_path), is_lazy=False)
            elif isinstance(node, ast.ImportFrom):
                self._process_import_from(node, module_name, str(file_path), is_lazy=False)

        # In-function imports (lazy)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Import):
                        self._process_import(
                            child, module_name, str(file_path), is_lazy=True
                        )
                    elif isinstance(child, ast.ImportFrom):
                        self._process_import_from(
                            child, module_name, str(file_path), is_lazy=True
                        )

    def get_symbols(self) -> list[ExtractedSymbol]:
        return []

    def get_edges(self) -> list[ImportEdge]:
        return list(self._edges)

    def _is_project_internal(self, module: str) -> bool:
        """Check if a module is project-internal."""
        return any(module.startswith(prefix) for prefix in self._project_prefixes)

    def _process_import(
        self, node: ast.Import, source_module: str, file_path: str, is_lazy: bool
    ) -> None:
        for alias in node.names:
            if self._is_project_internal(alias.name):
                self._edges.append(
                    ImportEdge(
                        source=source_module,
                        target=alias.name,
                        relation=EdgeRelation.LAZY_IMPORTS if is_lazy else EdgeRelation.IMPORTS,
                        is_lazy=is_lazy,
                        file_path=file_path,
                        line_number=node.lineno,
                    )
                )

    def _process_import_from(
        self, node: ast.ImportFrom, source_module: str, file_path: str, is_lazy: bool
    ) -> None:
        if node.module is None:
            return
        if not self._is_project_internal(node.module):
            return
        for alias in node.names:
            target = f"{node.module}.{alias.name}"
            self._edges.append(
                ImportEdge(
                    source=source_module,
                    target=target,
                    relation=EdgeRelation.LAZY_IMPORTS if is_lazy else EdgeRelation.IMPORTS,
                    is_lazy=is_lazy,
                    file_path=file_path,
                    line_number=node.lineno,
                )
            )
