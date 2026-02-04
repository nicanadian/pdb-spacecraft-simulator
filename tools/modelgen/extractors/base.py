"""Base extractor ABC and shared data structures."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class SymbolKind(str, Enum):
    """Kind of extracted symbol."""

    COMPONENT = "component"
    DATA_TYPE = "data_type"
    ENUM = "enum"
    INTERFACE = "interface"
    FUNCTION = "function"
    HANDLER = "handler"
    MODULE = "module"


class EdgeRelation(str, Enum):
    """Relation type for edges."""

    IMPORTS = "imports"
    LAZY_IMPORTS = "lazy_imports"
    IMPLEMENTS = "implements"
    REGISTERED_IN = "registered_in"
    INHERITS = "inherits"
    USES = "uses"


@dataclass
class FieldInfo:
    """Information about a class field."""

    name: str
    type_annotation: str = ""
    default: str = ""
    is_optional: bool = False


@dataclass
class MethodInfo:
    """Information about a class method."""

    name: str
    is_abstract: bool = False
    is_property: bool = False
    is_classmethod: bool = False
    is_staticmethod: bool = False
    parameters: list[str] = field(default_factory=list)
    return_type: str = ""
    docstring: str = ""


@dataclass
class ExtractedSymbol:
    """A symbol extracted from source code."""

    qualified_name: str
    name: str
    kind: SymbolKind
    module_path: str  # e.g., "sim.core.types"
    file_path: str  # relative file path
    line_number: int = 0
    docstring: str = ""
    bases: list[str] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportEdge:
    """An import relationship between modules/symbols."""

    source: str  # qualified name of importing module/class
    target: str  # qualified name of imported symbol
    relation: EdgeRelation = EdgeRelation.IMPORTS
    is_lazy: bool = False
    file_path: str = ""
    line_number: int = 0


@dataclass
class InvariantInfo:
    """An extracted invariant/constraint."""

    id: str
    description: str
    severity: str = "must"  # must, should, info
    source: str = "code"  # code, claude_md
    file_path: str = ""
    line_number: int = 0
    related_components: list[str] = field(default_factory=list)


class BaseExtractor(ABC):
    """Abstract base for all extractors."""

    def __init__(self, root: Path, module_paths: list[str] | None = None):
        self.root = root
        self.module_paths = module_paths or []

    @abstractmethod
    def extract(self, file_path: Path, tree: ast.Module, module_name: str) -> None:
        """Extract information from a parsed AST.

        Args:
            file_path: Path to the source file (relative to root).
            tree: Parsed AST module.
            module_name: Dotted module name (e.g., 'sim.core.types').
        """
        ...

    @abstractmethod
    def get_symbols(self) -> list[ExtractedSymbol]:
        """Return all extracted symbols."""
        ...

    @abstractmethod
    def get_edges(self) -> list[ImportEdge]:
        """Return all extracted edges."""
        ...

    def get_invariants(self) -> list[InvariantInfo]:
        """Return extracted invariants (default: none)."""
        return []

    def _get_docstring(self, node: ast.AST) -> str:
        """Extract docstring from an AST node."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, (ast.Constant, ast.Str))
            ):
                val = node.body[0].value
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    return val.value.strip()
        return ""

    def _get_decorators(self, node: ast.ClassDef | ast.FunctionDef) -> list[str]:
        """Extract decorator names from a node."""
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(ast.dump(dec))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)
        return decorators

    def _annotation_to_str(self, node: Optional[ast.AST]) -> str:
        """Convert an annotation AST node to a string representation."""
        if node is None:
            return ""
        return ast.unparse(node)
