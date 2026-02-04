"""Detect handler registry patterns (register_handler/get_handler)."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.modelgen.extractors.base import (
    BaseExtractor,
    EdgeRelation,
    ExtractedSymbol,
    ImportEdge,
    SymbolKind,
)


class RegistryExtractor(BaseExtractor):
    """Detects register_handler()/get_handler() patterns and produces registered_in edges."""

    def __init__(self, root: Path, module_paths: list[str] | None = None):
        super().__init__(root, module_paths)
        self._edges: list[ImportEdge] = []
        self._symbols: list[ExtractedSymbol] = []
        # Track registries: module -> list of registered handler class names
        self._registrations: list[tuple[str, str, int]] = []  # (file, class_name, lineno)

    def extract(self, file_path: Path, tree: ast.Module, module_name: str) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in ("register_handler", "register"):
                    # Extract the argument - usually a class instantiation
                    if node.args:
                        arg = node.args[0]
                        handler_name = self._extract_handler_name(arg)
                        if handler_name:
                            self._registrations.append(
                                (module_name, handler_name, node.lineno)
                            )
                            self._edges.append(
                                ImportEdge(
                                    source=handler_name,
                                    target=f"{module_name}._handlers",
                                    relation=EdgeRelation.REGISTERED_IN,
                                    file_path=str(file_path),
                                    line_number=node.lineno,
                                )
                            )

    def get_symbols(self) -> list[ExtractedSymbol]:
        return list(self._symbols)

    def get_edges(self) -> list[ImportEdge]:
        return list(self._edges)

    def _get_call_name(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    def _extract_handler_name(self, node: ast.AST) -> str | None:
        """Extract handler class name from registration call argument."""
        if isinstance(node, ast.Call):
            # register_handler(SomeHandler())
            if isinstance(node.func, ast.Name):
                return node.func.id
            if isinstance(node.func, ast.Attribute):
                return node.func.attr
        elif isinstance(node, ast.Name):
            # register_handler(some_handler_instance)
            return node.id
        return None
