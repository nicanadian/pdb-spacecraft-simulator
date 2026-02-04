"""IR schema: IRNode, IREdge, IRGraph, IRGroup, IRInvariant."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IRNode:
    """A node in the architecture graph."""

    id: str  # qualified name, e.g., "sim.models.power.PowerModel"
    name: str  # short name, e.g., "PowerModel"
    kind: str  # component, data_type, enum, interface, function, handler
    group: str = ""  # group ID for coloring/filtering
    module_path: str = ""
    file_path: str = ""
    line_number: int = 0
    docstring: str = ""
    display_name: str = ""  # override name for UI
    description: str = ""  # override description for UI
    bases: list[str] = field(default_factory=list)
    fields: list[dict[str, Any]] = field(default_factory=list)
    methods: list[dict[str, Any]] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    hidden: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IREdge:
    """An edge in the architecture graph."""

    id: str  # "{source}--{relation}--{target}"
    source: str  # node ID
    target: str  # node ID
    relation: str  # imports, lazy_imports, implements, registered_in, inherits, uses
    is_lazy: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IRGroup:
    """A group for visual organization."""

    id: str
    name: str
    color: str = "#6b7280"  # default slate
    description: str = ""
    module_patterns: list[str] = field(default_factory=list)


@dataclass
class IRInvariant:
    """An architecture invariant/constraint."""

    id: str
    description: str
    severity: str = "must"  # must, should, info
    source: str = "code"  # code, claude_md
    file_path: str = ""
    line_number: int = 0
    related_nodes: list[str] = field(default_factory=list)


@dataclass
class IRGraph:
    """Complete architecture graph."""

    nodes: list[IRNode] = field(default_factory=list)
    edges: list[IREdge] = field(default_factory=list)
    groups: list[IRGroup] = field(default_factory=list)
    invariants: list[IRInvariant] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def node_by_id(self, node_id: str) -> Optional[IRNode]:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def edges_from(self, node_id: str) -> list[IREdge]:
        return [e for e in self.edges if e.source == node_id]

    def edges_to(self, node_id: str) -> list[IREdge]:
        return [e for e in self.edges if e.target == node_id]
