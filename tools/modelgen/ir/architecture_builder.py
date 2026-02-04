"""Build UAF-lite ArchModel from IRGraph + architecture_layers.yml config."""

from __future__ import annotations

import re
from typing import Any

from tools.modelgen.ir.schema import (
    ArchEdge,
    ArchModel,
    ArchNode,
    IRGraph,
    Requirement,
    RequirementLink,
    ViewpointDef,
)


# Map IRNode.kind to L3 arch_type
_KIND_TO_ARCH_TYPE = {
    "component": "Component",
    "interface": "Interface",
    "data_type": "DataContract",
    "function": "Subsystem",
    "handler": "Component",
    "enum": "DataContract",
    "module": "CodeModule",
}

# Map IREdge.relation to arch connector type
_RELATION_TO_CONNECTOR = {
    "imports": "uses",
    "lazy_imports": "uses",
    "implements": "uses",
    "uses": "calls",
    "registered_in": "subscribes",
    "inherits": "uses",
}


class ArchitectureBuilder:
    """Builds an ArchModel from an IRGraph and architecture layer configuration."""

    def __init__(self, ir_graph: IRGraph, arch_config: dict[str, Any]) -> None:
        self._ir = ir_graph
        self._config = arch_config
        self._arch_nodes: list[ArchNode] = []
        self._arch_edges: list[ArchEdge] = []
        self._requirements: list[Requirement] = []
        self._requirement_links: list[RequirementLink] = []
        self._viewpoints: list[ViewpointDef] = []
        self._node_index: dict[str, ArchNode] = {}
        # Map from IRNode.id -> L3 ArchNode.id (for those that got elevated)
        self._ir_to_l3: dict[str, str] = {}
        # Map from IRNode.id -> L2 domain id
        self._ir_to_domain: dict[str, str] = {}
        # Map from L2 domain id -> domain name (Logical, Operational, etc.)
        self._domain_name_by_l2: dict[str, str] = {}

    def build(self) -> ArchModel:
        """Execute the full build pipeline and return the ArchModel."""
        self._build_l0()
        self._build_l1()
        self._build_l2()
        self._build_l3()
        self._build_l4()
        self._build_containment_edges()
        self._build_connector_edges()
        self._build_requirements()
        self._merge_invariants_to_requirements()
        self._build_viewpoints()

        metadata = dict(self._config.get("metadata", {}))
        metadata["meta_model_version"] = self._config.get(
            "meta_model_version", "uaf-lite-0.1"
        )

        return ArchModel(
            ir_graph=self._ir,
            arch_nodes=self._arch_nodes,
            arch_edges=self._arch_edges,
            requirements=self._requirements,
            requirement_links=self._requirement_links,
            viewpoints=self._viewpoints,
            metadata=metadata,
        )

    def _add_node(self, node: ArchNode) -> None:
        self._arch_nodes.append(node)
        self._node_index[node.id] = node

    def _add_edge(self, edge: ArchEdge) -> None:
        self._arch_edges.append(edge)

    # ------------------------------------------------------------------
    # L0: Enterprise + External Actors
    # ------------------------------------------------------------------

    def _build_l0(self) -> None:
        enterprise = self._config.get("enterprise", {})
        ent_node = ArchNode(
            id=enterprise.get("id", "L0:enterprise"),
            name=enterprise.get("name", "Enterprise"),
            level="L0",
            arch_type="Enterprise",
            description=enterprise.get("description", ""),
        )
        self._add_node(ent_node)

        for actor in enterprise.get("external_actors", []):
            a_node = ArchNode(
                id=actor["id"],
                name=actor.get("name", ""),
                level="L0",
                arch_type=actor.get("arch_type", "ExternalActor"),
                parent_id=ent_node.id,
                description=actor.get("description", ""),
                metadata={
                    k: v
                    for k, v in actor.items()
                    if k not in ("id", "name", "arch_type", "description")
                },
            )
            self._add_node(a_node)

    # ------------------------------------------------------------------
    # L1: Segments
    # ------------------------------------------------------------------

    def _build_l1(self) -> None:
        enterprise_id = self._config.get("enterprise", {}).get("id", "L0:enterprise")
        for seg in self._config.get("segments", []):
            s_node = ArchNode(
                id=seg["id"],
                name=seg.get("name", ""),
                level="L1",
                arch_type="Segment",
                parent_id=enterprise_id,
                description=seg.get("description", ""),
                metadata={
                    k: v
                    for k, v in seg.items()
                    if k not in ("id", "name", "description")
                },
            )
            self._add_node(s_node)

    # ------------------------------------------------------------------
    # L2: Domains
    # ------------------------------------------------------------------

    def _build_l2(self) -> None:
        for dom in self._config.get("domains", []):
            domain_name = dom.get("domain", "")
            d_node = ArchNode(
                id=dom["id"],
                name=dom["id"].split(":")[-1],
                level="L2",
                arch_type="Domain",
                parent_id=dom.get("segment", ""),
                domain=domain_name,
            )
            self._add_node(d_node)
            # Remember domain name for L3/L4 inheritance
            self._domain_name_by_l2[dom["id"]] = domain_name

    # ------------------------------------------------------------------
    # L3: Elevated code nodes
    # ------------------------------------------------------------------

    def _build_l3(self) -> None:
        code_mapping = self._config.get("code_mapping", [])
        elevation = self._config.get("elevation", {})
        force_elevate = set(elevation.get("force_elevate", []))
        suppress_kinds = set(elevation.get("suppress_kinds", []))
        suppress_patterns = elevation.get("suppress_name_patterns", [])
        min_complexity = elevation.get("min_complexity", 2)

        for ir_node in self._ir.nodes:
            if ir_node.hidden:
                continue

            # Find matching domain
            domain_id = self._match_domain(ir_node.module_path or ir_node.id, code_mapping)
            if not domain_id:
                continue
            self._ir_to_domain[ir_node.id] = domain_id

            # Determine if this node should be elevated to L3
            should_elevate = False

            if ir_node.id in force_elevate:
                should_elevate = True
            elif ir_node.kind in suppress_kinds:
                continue
            elif any(
                re.search(pat, ir_node.name) for pat in suppress_patterns
            ):
                continue
            else:
                # Check elevation flag from code_mapping
                mapping_entry = self._find_mapping_entry(
                    ir_node.module_path or ir_node.id, code_mapping
                )
                if mapping_entry and mapping_entry.get("elevate"):
                    should_elevate = True
                else:
                    # Check complexity
                    complexity = len(ir_node.fields or []) + len(ir_node.methods or [])
                    if complexity >= min_complexity:
                        should_elevate = True

            if should_elevate:
                arch_type = _KIND_TO_ARCH_TYPE.get(ir_node.kind, "Component")
                l3_id = f"L3:{ir_node.id}"
                l3_node = ArchNode(
                    id=l3_id,
                    name=ir_node.display_name or ir_node.name,
                    level="L3",
                    arch_type=arch_type,
                    parent_id=domain_id,
                    domain=self._domain_name_by_l2.get(domain_id, ""),
                    ir_node_ref=ir_node.id,
                    description=ir_node.description or ir_node.docstring or "",
                )
                self._add_node(l3_node)
                self._ir_to_l3[ir_node.id] = l3_id

    # ------------------------------------------------------------------
    # L4: All code nodes
    # ------------------------------------------------------------------

    def _build_l4(self) -> None:
        for ir_node in self._ir.nodes:
            if ir_node.hidden:
                continue

            # Determine parent: L3 if elevated, else L2 domain, else skip
            parent = self._ir_to_l3.get(ir_node.id)
            if not parent:
                parent = self._ir_to_domain.get(ir_node.id)
            if not parent:
                continue

            arch_type = "CodeSymbol" if ir_node.kind != "module" else "CodeModule"
            l4_id = f"L4:{ir_node.id}"
            # Inherit domain from L2 ancestor
            domain_id = self._ir_to_domain.get(ir_node.id, "")
            l4_node = ArchNode(
                id=l4_id,
                name=ir_node.name,
                level="L4",
                arch_type=arch_type,
                parent_id=parent,
                domain=self._domain_name_by_l2.get(domain_id, ""),
                ir_node_ref=ir_node.id,
            )
            self._add_node(l4_node)

    # ------------------------------------------------------------------
    # Containment edges + children lists
    # ------------------------------------------------------------------

    def _build_containment_edges(self) -> None:
        for node in self._arch_nodes:
            if node.parent_id and node.parent_id in self._node_index:
                parent = self._node_index[node.parent_id]
                parent.children.append(node.id)
                edge = ArchEdge(
                    id=f"contains:{node.parent_id}--{node.id}",
                    source=node.parent_id,
                    target=node.id,
                    relation="contains",
                )
                self._add_edge(edge)

    # ------------------------------------------------------------------
    # Connector edges (from IR edges)
    # ------------------------------------------------------------------

    def _build_connector_edges(self) -> None:
        for ir_edge in self._ir.edges:
            # Map to L3 nodes if available, else skip
            src = self._ir_to_l3.get(ir_edge.source)
            tgt = self._ir_to_l3.get(ir_edge.target)
            if not src or not tgt:
                continue
            if src == tgt:
                continue

            connector = _RELATION_TO_CONNECTOR.get(ir_edge.relation, "uses")
            edge_id = f"{connector}:{src}--{tgt}"
            # Avoid duplicates
            if any(e.id == edge_id for e in self._arch_edges):
                continue

            self._add_edge(
                ArchEdge(
                    id=edge_id,
                    source=src,
                    target=tgt,
                    relation=connector,
                )
            )

    # ------------------------------------------------------------------
    # Requirements
    # ------------------------------------------------------------------

    def _build_requirements(self) -> None:
        for req_data in self._config.get("requirements", []):
            req = Requirement(
                id=req_data["id"],
                title=req_data.get("title", ""),
                req_type=req_data.get("req_type", "Need"),
                level=req_data.get("level", ""),
                description=req_data.get("description", ""),
                parent_id=req_data.get("parent", ""),
                children=req_data.get("children", []),
                source="config",
            )
            self._requirements.append(req)

            # Create allocation links
            for target_id in req_data.get("allocated_to", []):
                link = RequirementLink(
                    id=f"alloc:{req.id}--{target_id}",
                    requirement_id=req.id,
                    target_id=target_id,
                    relation="allocatedTo",
                )
                self._requirement_links.append(link)

            # Create parent links
            if req.parent_id:
                link = RequirementLink(
                    id=f"parent:{req.parent_id}--{req.id}",
                    requirement_id=req.parent_id,
                    target_id=req.id,
                    relation="parentOf",
                )
                self._requirement_links.append(link)

    # ------------------------------------------------------------------
    # Merge IRInvariant -> Requirements
    # ------------------------------------------------------------------

    def _merge_invariants_to_requirements(self) -> None:
        for inv in self._ir.invariants:
            # Determine requirement type from severity
            if inv.severity == "must":
                req_type = "InterfaceContract"
            elif inv.severity == "should":
                req_type = "QualityAttribute"
            else:
                req_type = "VerificationRequirement"

            req = Requirement(
                id=f"INV:{inv.id}",
                title=inv.description[:80] if inv.description else inv.id,
                req_type=req_type,
                level="L2",
                description=inv.description,
                source=inv.source,
                source_location=f"{inv.file_path}:{inv.line_number}"
                if inv.file_path
                else "",
            )
            self._requirements.append(req)

            # Link to related L3 nodes
            for related in inv.related_nodes or []:
                l3_id = self._ir_to_l3.get(related)
                if l3_id:
                    link = RequirementLink(
                        id=f"satisfiedBy:{req.id}--{l3_id}",
                        requirement_id=req.id,
                        target_id=l3_id,
                        relation="satisfiedBy",
                    )
                    self._requirement_links.append(link)

    # ------------------------------------------------------------------
    # Viewpoints
    # ------------------------------------------------------------------

    def _build_viewpoints(self) -> None:
        for vp_data in self._config.get("viewpoints", []):
            vp = ViewpointDef(
                id=vp_data["id"],
                name=vp_data.get("name", ""),
                include_layers=vp_data.get("include_layers", []),
                domain=vp_data.get("domain", ""),
                connector_types=vp_data.get("connector_types", []),
                default_collapse=vp_data.get("default_collapse", []),
                overlays=vp_data.get("overlays", []),
            )
            self._viewpoints.append(vp)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_domain(
        module_path: str, code_mapping: list[dict[str, Any]]
    ) -> str | None:
        """Find the first matching code_mapping entry for a module path."""
        for entry in code_mapping:
            prefix = entry.get("prefix", "")
            if module_path.startswith(prefix):
                return entry.get("domain", "")
        return None

    @staticmethod
    def _find_mapping_entry(
        module_path: str, code_mapping: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Find the first matching code_mapping entry dict."""
        for entry in code_mapping:
            prefix = entry.get("prefix", "")
            if module_path.startswith(prefix):
                return entry
        return None
