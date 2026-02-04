"""Extract ABC interfaces and resolve concrete implementations."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.modelgen.extractors.base import (
    BaseExtractor,
    EdgeRelation,
    ExtractedSymbol,
    ImportEdge,
)


class ABCExtractor(BaseExtractor):
    """Finds ABC interfaces and resolves which concrete classes implement them.

    This extractor works in two passes:
    1. First pass: collect all classes and their bases.
    2. After all files are processed, resolve implements edges.
    """

    def __init__(self, root: Path, module_paths: list[str] | None = None):
        super().__init__(root, module_paths)
        self._classes: dict[str, list[str]] = {}  # qualified_name -> base names
        self._abc_classes: set[str] = set()
        self._edges: list[ImportEdge] = []
        # Map short name -> list of qualified names for resolution
        self._name_to_qualified: dict[str, list[str]] = {}

    def extract(self, file_path: Path, tree: ast.Module, module_name: str) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                qualified = f"{module_name}.{node.name}"
                bases = self._get_base_names_raw(node)
                self._classes[qualified] = bases

                # Track short -> qualified mapping
                self._name_to_qualified.setdefault(node.name, []).append(qualified)

                # Detect ABC
                is_abc = any(b in ("ABC",) for b in bases)
                has_abstract = any(
                    self._is_abstract_method(item)
                    for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                if is_abc or has_abstract:
                    self._abc_classes.add(qualified)

    def get_symbols(self) -> list[ExtractedSymbol]:
        return []

    def get_edges(self) -> list[ImportEdge]:
        return list(self._edges)

    def resolve(self) -> None:
        """Resolve implements edges after all files have been processed.

        Call this after all extract() calls are complete.
        """
        for cls_qname, bases in self._classes.items():
            if cls_qname in self._abc_classes:
                continue
            for base_name in bases:
                # Try to resolve base to an ABC
                resolved = self._resolve_name(base_name)
                if resolved and resolved in self._abc_classes:
                    self._edges.append(
                        ImportEdge(
                            source=cls_qname,
                            target=resolved,
                            relation=EdgeRelation.IMPLEMENTS,
                        )
                    )

    def _resolve_name(self, name: str) -> str | None:
        """Resolve a short class name to a qualified name."""
        # Direct match in qualified names
        if name in self._classes:
            return name
        # Look up by short name
        candidates = self._name_to_qualified.get(name, [])
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            # Prefer ABC classes
            abc_candidates = [c for c in candidates if c in self._abc_classes]
            if len(abc_candidates) == 1:
                return abc_candidates[0]
            # Return first match
            return candidates[0]
        return None

    def _get_base_names_raw(self, node: ast.ClassDef) -> list[str]:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        return bases

    def _is_abstract_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
                return True
        return False
