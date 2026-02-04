"""Extract classes, dataclasses, Pydantic models, and enums from AST."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.modelgen.extractors.base import (
    BaseExtractor,
    ExtractedSymbol,
    FieldInfo,
    ImportEdge,
    MethodInfo,
    SymbolKind,
)


class ClassExtractor(BaseExtractor):
    """Extracts class definitions and categorizes them."""

    def __init__(self, root: Path, module_paths: list[str] | None = None):
        super().__init__(root, module_paths)
        self._symbols: list[ExtractedSymbol] = []
        self._edges: list[ImportEdge] = []

    def extract(self, file_path: Path, tree: ast.Module, module_name: str) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._extract_class(node, file_path, module_name)

    def get_symbols(self) -> list[ExtractedSymbol]:
        return list(self._symbols)

    def get_edges(self) -> list[ImportEdge]:
        return list(self._edges)

    def _extract_class(
        self, node: ast.ClassDef, file_path: Path, module_name: str
    ) -> None:
        qualified_name = f"{module_name}.{node.name}"
        bases = self._get_base_names(node)
        decorators = self._get_decorators(node)
        docstring = self._get_docstring(node)

        kind = self._classify(node, bases, decorators)
        fields = self._extract_fields(node, kind)
        methods = self._extract_methods(node)

        symbol = ExtractedSymbol(
            qualified_name=qualified_name,
            name=node.name,
            kind=kind,
            module_path=module_name,
            file_path=str(file_path),
            line_number=node.lineno,
            docstring=docstring,
            bases=bases,
            fields=fields,
            methods=methods,
            decorators=decorators,
        )
        self._symbols.append(symbol)

    def _classify(
        self, node: ast.ClassDef, bases: list[str], decorators: list[str]
    ) -> SymbolKind:
        # Enum check
        if any(b in ("Enum", "str, Enum", "IntEnum", "StrEnum") for b in bases):
            return SymbolKind.ENUM

        # ABC / interface check
        has_abc_base = any(b in ("ABC",) for b in bases)
        has_abstract = any(
            self._is_abstract_method(item)
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        if has_abc_base or has_abstract:
            return SymbolKind.INTERFACE

        # Pydantic BaseModel check
        if any(b in ("BaseModel",) for b in bases):
            return SymbolKind.DATA_TYPE

        # Dataclass check
        if "dataclass" in decorators:
            # Heuristic: if it has 3+ public methods, it's a component
            public_methods = self._count_public_methods(node)
            if public_methods >= 3:
                return SymbolKind.COMPONENT
            return SymbolKind.DATA_TYPE

        # Regular class: 3+ public methods → component, else data_type
        public_methods = self._count_public_methods(node)
        if public_methods >= 3:
            return SymbolKind.COMPONENT
        return SymbolKind.DATA_TYPE

    def _count_public_methods(self, node: ast.ClassDef) -> int:
        count = 0
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not item.name.startswith("_"):
                    count += 1
        return count

    def _is_abstract_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
                return True
        return False

    def _get_base_names(self, node: ast.ClassDef) -> list[str]:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))
            elif isinstance(base, ast.Subscript):
                bases.append(ast.unparse(base))
        # Handle multiple bases as comma-separated for enum pattern
        if len(node.bases) >= 2:
            combined = ", ".join(bases)
            # Keep individual bases too
            return [combined] + bases
        return bases

    def _extract_fields(self, node: ast.ClassDef, kind: SymbolKind) -> list[FieldInfo]:
        fields = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_info = FieldInfo(
                    name=item.target.id,
                    type_annotation=self._annotation_to_str(item.annotation),
                    default=ast.unparse(item.value) if item.value else "",
                    is_optional="Optional" in self._annotation_to_str(item.annotation),
                )
                fields.append(field_info)

            # Handle assignments in __init__ for regular classes
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == "__init__":
                    for stmt in ast.walk(item):
                        if (
                            isinstance(stmt, ast.AnnAssign)
                            and isinstance(stmt.target, ast.Attribute)
                            and isinstance(stmt.target.value, ast.Name)
                            and stmt.target.value.id == "self"
                        ):
                            fields.append(
                                FieldInfo(
                                    name=stmt.target.attr,
                                    type_annotation=self._annotation_to_str(stmt.annotation),
                                )
                            )

        # For Pydantic models, also check for Field() assignments
        if kind == SymbolKind.DATA_TYPE:
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    # Already captured above
                    pass

        return fields

    def _extract_methods(self, node: ast.ClassDef) -> list[MethodInfo]:
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = self._get_decorators(item)
                is_abstract = self._is_abstract_method(item)
                is_property = "property" in decorators or "abstractmethod" in decorators and any(
                    isinstance(d, ast.Name) and d.id == "property"
                    for d in item.decorator_list
                )
                is_classmethod = "classmethod" in decorators
                is_staticmethod = "staticmethod" in decorators

                params = []
                for arg in item.args.args:
                    if arg.arg != "self" and arg.arg != "cls":
                        params.append(arg.arg)

                method = MethodInfo(
                    name=item.name,
                    is_abstract=is_abstract,
                    is_property=is_property,
                    is_classmethod=is_classmethod,
                    is_staticmethod=is_staticmethod,
                    parameters=params,
                    return_type=self._annotation_to_str(item.returns),
                    docstring=self._get_docstring(item),
                )
                methods.append(method)
        return methods
