"""Unit tests for each extractor using small Python snippet strings."""

import ast
from pathlib import Path

import pytest

from tools.modelgen.extractors.base import SymbolKind, EdgeRelation
from tools.modelgen.extractors.class_extractor import ClassExtractor
from tools.modelgen.extractors.import_extractor import ImportExtractor
from tools.modelgen.extractors.abc_extractor import ABCExtractor
from tools.modelgen.extractors.registry_extractor import RegistryExtractor
from tools.modelgen.extractors.invariant_extractor import InvariantExtractor


ROOT = Path(".")


class TestClassExtractor:
    def test_dataclass_detection(self):
        source = '''
from dataclasses import dataclass

@dataclass
class MyData:
    x: int
    y: float = 0.0
'''
        ext = ClassExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        symbols = ext.get_symbols()
        assert len(symbols) == 1
        s = symbols[0]
        assert s.name == "MyData"
        assert s.kind == SymbolKind.DATA_TYPE
        assert s.qualified_name == "test_module.MyData"
        assert len(s.fields) == 2
        assert s.fields[0].name == "x"

    def test_enum_detection(self):
        source = '''
from enum import Enum

class Color(str, Enum):
    RED = "red"
    GREEN = "green"
'''
        ext = ClassExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        symbols = ext.get_symbols()
        assert len(symbols) == 1
        assert symbols[0].kind == SymbolKind.ENUM

    def test_abc_detection(self):
        source = '''
from abc import ABC, abstractmethod

class MyInterface(ABC):
    @abstractmethod
    def do_something(self) -> str:
        pass

    @abstractmethod
    def do_another(self, x: int) -> None:
        pass
'''
        ext = ClassExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        symbols = ext.get_symbols()
        assert len(symbols) == 1
        assert symbols[0].kind == SymbolKind.INTERFACE
        methods = symbols[0].methods
        assert len(methods) == 2
        assert methods[0].is_abstract

    def test_pydantic_model_detection(self):
        source = '''
from pydantic import BaseModel

class Config(BaseModel):
    name: str
    value: int = 42
'''
        ext = ClassExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        symbols = ext.get_symbols()
        assert len(symbols) == 1
        assert symbols[0].kind == SymbolKind.DATA_TYPE

    def test_component_detection(self):
        source = '''
class Engine:
    def start(self): pass
    def stop(self): pass
    def run(self, plan): pass
    def reset(self): pass
'''
        ext = ClassExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        symbols = ext.get_symbols()
        assert len(symbols) == 1
        assert symbols[0].kind == SymbolKind.COMPONENT

    def test_docstring_extraction(self):
        source = '''
class Foo:
    """This is the docstring."""
    x: int = 1
'''
        ext = ClassExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        assert ext.get_symbols()[0].docstring == "This is the docstring."


class TestImportExtractor:
    def test_module_level_imports(self):
        source = '''
from sim.core.types import InitialState
from sim.models.power import PowerModel
import numpy as np
'''
        ext = ImportExtractor(ROOT, ["sim"])
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        edges = ext.get_edges()
        # Should only have internal imports (not numpy)
        assert len(edges) == 2
        assert all(e.relation == EdgeRelation.IMPORTS for e in edges)
        assert not any(e.is_lazy for e in edges)

    def test_lazy_imports(self):
        source = '''
class Handler:
    def process(self):
        from sim.models.power import PowerModel
        return PowerModel()
'''
        ext = ImportExtractor(ROOT, ["sim"])
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        edges = ext.get_edges()
        assert len(edges) == 1
        assert edges[0].relation == EdgeRelation.LAZY_IMPORTS
        assert edges[0].is_lazy

    def test_filters_external_imports(self):
        source = '''
import numpy as np
import pandas as pd
from sim.core.types import Event
'''
        ext = ImportExtractor(ROOT, ["sim"])
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        edges = ext.get_edges()
        assert len(edges) == 1
        assert edges[0].target == "sim.core.types.Event"


class TestABCExtractor:
    def test_implements_detection(self):
        source_abc = '''
from abc import ABC, abstractmethod

class BaseHandler(ABC):
    @abstractmethod
    def handle(self): pass
'''
        source_impl = '''
class ConcreteHandler(BaseHandler):
    def handle(self):
        return "done"
'''
        ext = ABCExtractor(ROOT)

        tree1 = ast.parse(source_abc)
        ext.extract(Path("base.py"), tree1, "mod.base")

        tree2 = ast.parse(source_impl)
        ext.extract(Path("impl.py"), tree2, "mod.impl")

        ext.resolve()
        edges = ext.get_edges()
        assert len(edges) == 1
        assert edges[0].source == "mod.impl.ConcreteHandler"
        assert edges[0].target == "mod.base.BaseHandler"
        assert edges[0].relation == EdgeRelation.IMPLEMENTS


class TestRegistryExtractor:
    def test_register_handler_detection(self):
        source = '''
register_handler(DownlinkHandler())
register_handler(IdleHandler())
'''
        ext = RegistryExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "sim.activities")
        edges = ext.get_edges()
        assert len(edges) == 2
        assert edges[0].relation == EdgeRelation.REGISTERED_IN


class TestInvariantExtractor:
    def test_assert_extraction(self):
        source = '''
def validate(x):
    assert x >= 0, "x must be non-negative"
'''
        ext = InvariantExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        invs = ext.get_invariants()
        assert len(invs) >= 1

    def test_post_init_validator(self):
        source = '''
class State:
    def __post_init__(self):
        if not 0.0 <= self.soc <= 1.0:
            raise ValueError(f"soc must be in [0, 1], got {self.soc}")
'''
        ext = InvariantExtractor(ROOT)
        tree = ast.parse(source)
        ext.extract(Path("test.py"), tree, "test_module")
        invs = ext.get_invariants()
        assert len(invs) == 1
        assert "soc" in invs[0].description.lower() or "0, 1" in invs[0].description

    def test_claude_md_extraction(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        md.write_text("""
# Test

## Validation Invariants

Code must enforce:
- SOC in [0, 1]
- Storage never negative
- Monotonic time axis
""")
        ext = InvariantExtractor(ROOT)
        ext.extract_from_claude_md(md)
        invs = ext.get_invariants()
        assert len(invs) == 3
        assert invs[0].source == "claude_md"
        assert invs[0].severity == "must"
