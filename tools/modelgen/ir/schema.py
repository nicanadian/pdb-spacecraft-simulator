"""IR schema: IRNode, IREdge, IRGraph, IRGroup, IRInvariant + UAF-lite architecture types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
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


# ---------------------------------------------------------------------------
# UAF-lite architecture types (uaf-lite-0.1)
# ---------------------------------------------------------------------------


class ArchitectureLevel(str, Enum):
    """Architecture abstraction levels."""

    L0 = "L0"  # Enterprise/Mission Context
    L1 = "L1"  # Capability/Segment
    L2 = "L2"  # Domain
    L3 = "L3"  # Logical (code-derived)
    L4 = "L4"  # Implementation


@dataclass
class ArchNode:
    """A node in the layered architecture model."""

    id: str  # e.g. "L0:pdb_mission", "L1:sim_engine", "L3:sim.engine.simulate"
    name: str
    level: str  # L0-L4
    arch_type: str  # Enterprise, ExternalActor, Segment, Component, etc.
    parent_id: str = ""
    domain: str = ""  # L2 domain: Operational, Logical, Information, Interface, Technical, Verification
    description: str = ""
    ir_node_ref: str = ""  # For L3/L4: points back to IRNode.id
    children: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchEdge:
    """A relationship in the architecture model."""

    id: str
    source: str  # ArchNode.id
    target: str  # ArchNode.id
    relation: str  # contains, uses, calls, publishes, subscribes, reads, writes, deploysTo
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Requirement:
    """An architecture requirement."""

    id: str  # e.g. "REQ-L0-001"
    title: str
    req_type: str  # Need, CapabilityRequirement, ArchitectureConstraint, InterfaceContract, QualityAttribute, VerificationRequirement
    level: str = ""  # L0-L3
    description: str = ""
    parent_id: str = ""
    children: list[str] = field(default_factory=list)
    source: str = ""  # config, code, claude_md
    source_location: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RequirementLink:
    """Links a requirement to an architecture element."""

    id: str
    requirement_id: str
    target_id: str  # ArchNode.id or Requirement.id
    relation: str  # parentOf, refines, dependsOn, conflictsWith, allocatedTo, satisfiedBy, verifiedBy
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ViewpointDef:
    """Defines a viewpoint for filtering the architecture model."""

    id: str  # operational-context, capability-map, etc.
    name: str
    include_layers: list[str] = field(default_factory=list)  # ["L0", "L2"]
    domain: str = ""  # Filter to specific L2 domain
    connector_types: list[str] = field(default_factory=list)
    default_collapse: list[str] = field(default_factory=list)  # arch_types to collapse by default
    overlays: list[str] = field(default_factory=list)  # allocations, coverage
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchModel:
    """Complete architecture model combining IR graph with UAF-lite layers."""

    ir_graph: IRGraph
    arch_nodes: list[ArchNode] = field(default_factory=list)
    arch_edges: list[ArchEdge] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    requirement_links: list[RequirementLink] = field(default_factory=list)
    viewpoints: list[ViewpointDef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def nodes_at_level(self, level: str) -> list[ArchNode]:
        return [n for n in self.arch_nodes if n.level == level]

    def children_of(self, node_id: str) -> list[ArchNode]:
        return [n for n in self.arch_nodes if n.parent_id == node_id]

    def requirements_for_node(self, node_id: str) -> list[Requirement]:
        linked_req_ids = {
            lk.requirement_id
            for lk in self.requirement_links
            if lk.target_id == node_id
        }
        return [r for r in self.requirements if r.id in linked_req_ids]

    def nodes_for_viewpoint(self, viewpoint_id: str) -> list[ArchNode]:
        vp = next((v for v in self.viewpoints if v.id == viewpoint_id), None)
        if not vp:
            return []
        nodes = [n for n in self.arch_nodes if n.level in vp.include_layers]
        if vp.domain:
            nodes = [n for n in nodes if not n.domain or n.domain == vp.domain]
        return nodes
