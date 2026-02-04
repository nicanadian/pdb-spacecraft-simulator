"""Extract invariants from assert statements, validators, and CLAUDE.md."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tools.modelgen.extractors.base import (
    BaseExtractor,
    ExtractedSymbol,
    ImportEdge,
    InvariantInfo,
)


class InvariantExtractor(BaseExtractor):
    """Extracts invariants from code assertions, validators, and CLAUDE.md."""

    def __init__(self, root: Path, module_paths: list[str] | None = None):
        super().__init__(root, module_paths)
        self._invariants: list[InvariantInfo] = []
        self._id_counter = 0

    def extract(self, file_path: Path, tree: ast.Module, module_name: str) -> None:
        for node in ast.walk(tree):
            # Assert statements
            if isinstance(node, ast.Assert):
                desc = self._assert_to_description(node)
                if desc:
                    self._add_invariant(
                        description=desc,
                        severity="must",
                        source="code",
                        file_path=str(file_path),
                        line_number=node.lineno,
                        related_components=[module_name],
                    )

            # Raise ValueError in __post_init__ or validators
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ("__post_init__", "validate", "__init__"):
                    self._extract_from_validator(node, file_path, module_name)

    def extract_from_claude_md(self, claude_md_path: Path) -> None:
        """Extract invariants from the Validation Invariants section of CLAUDE.md."""
        if not claude_md_path.exists():
            return
        text = claude_md_path.read_text()

        # Find the "Validation Invariants" section
        pattern = r"##\s*Validation Invariants\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            # Try "Domain Constraints" as fallback
            pattern = r"##\s*Domain Constraints\s*\n(.*?)(?=\n##|\Z)"
            match = re.search(pattern, text, re.DOTALL)
        if not match:
            return

        section = match.group(1)
        # Parse bullet points
        for line in section.strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                desc = line[2:].strip()
                if desc:
                    self._add_invariant(
                        description=desc,
                        severity="must",
                        source="claude_md",
                        file_path=str(claude_md_path),
                        line_number=0,
                        related_components=self._guess_related_components(desc),
                    )

    def get_symbols(self) -> list[ExtractedSymbol]:
        return []

    def get_edges(self) -> list[ImportEdge]:
        return []

    def get_invariants(self) -> list[InvariantInfo]:
        return list(self._invariants)

    def _add_invariant(
        self,
        description: str,
        severity: str,
        source: str,
        file_path: str,
        line_number: int,
        related_components: list[str],
    ) -> None:
        self._id_counter += 1
        inv_id = f"INV-{self._id_counter:03d}"
        self._invariants.append(
            InvariantInfo(
                id=inv_id,
                description=description,
                severity=severity,
                source=source,
                file_path=file_path,
                line_number=line_number,
                related_components=related_components,
            )
        )

    def _assert_to_description(self, node: ast.Assert) -> str:
        """Convert an assert statement to a human-readable description."""
        try:
            test_str = ast.unparse(node.test)
            if node.msg:
                msg_str = ast.unparse(node.msg)
                return f"{test_str} ({msg_str})"
            return test_str
        except Exception:
            return ""

    def _extract_from_validator(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        module_name: str,
    ) -> None:
        """Extract invariants from raise ValueError patterns in validators."""
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                if isinstance(child.exc, ast.Call):
                    func = child.exc.func
                    if isinstance(func, ast.Name) and func.id == "ValueError":
                        if child.exc.args:
                            try:
                                # Try to extract the format string
                                desc = self._extract_error_message(child.exc.args[0])
                                if desc:
                                    self._add_invariant(
                                        description=desc,
                                        severity="must",
                                        source="code",
                                        file_path=str(file_path),
                                        line_number=child.lineno,
                                        related_components=[module_name],
                                    )
                            except Exception:
                                pass

    def _extract_error_message(self, node: ast.AST) -> str:
        """Extract a readable message from a ValueError argument."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            # f-string: extract the static parts
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                else:
                    parts.append("{...}")
            return "".join(parts)
        # Fallback: unparse
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _guess_related_components(self, description: str) -> list[str]:
        """Guess related component names from an invariant description."""
        components = []
        keywords = {
            "SOC": ["sim.models.power"],
            "soc": ["sim.models.power"],
            "battery": ["sim.models.power"],
            "storage": ["sim.models.storage"],
            "propellant": ["sim.models.propulsion"],
            "time": ["sim.engine"],
            "AOS": ["sim.models.access"],
            "LOS": ["sim.models.access"],
            "downlink": ["sim.activities.downlink"],
            "eclipse": ["sim.models.power"],
            "generation": ["sim.models.power"],
        }
        for keyword, comps in keywords.items():
            if keyword in description:
                components.extend(comps)
        return list(set(components))
