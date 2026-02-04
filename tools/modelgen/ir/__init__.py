"""Intermediate Representation for architecture models."""

from tools.modelgen.ir.schema import IREdge, IRGraph, IRGroup, IRInvariant, IRNode
from tools.modelgen.ir.builder import IRBuilder
from tools.modelgen.ir.serializer import serialize_graph

__all__ = [
    "IREdge",
    "IRGraph",
    "IRGroup",
    "IRInvariant",
    "IRNode",
    "IRBuilder",
    "serialize_graph",
]
