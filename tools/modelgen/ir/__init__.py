"""Intermediate Representation for architecture models."""

from tools.modelgen.ir.schema import (
    ArchEdge,
    ArchModel,
    ArchNode,
    ArchitectureLevel,
    IREdge,
    IRGraph,
    IRGroup,
    IRInvariant,
    IRNode,
    Requirement,
    RequirementLink,
    ViewpointDef,
)
from tools.modelgen.ir.builder import IRBuilder
from tools.modelgen.ir.serializer import serialize_graph

__all__ = [
    "ArchEdge",
    "ArchModel",
    "ArchNode",
    "ArchitectureLevel",
    "IREdge",
    "IRGraph",
    "IRGroup",
    "IRInvariant",
    "IRNode",
    "IRBuilder",
    "Requirement",
    "RequirementLink",
    "ViewpointDef",
    "serialize_graph",
]
