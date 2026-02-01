"""GMAT test harness for regression test case execution.

This module provides:
- run_case: Execute a single GMAT regression case
- generate_truth: Generate truth files from GMAT outputs
- compare_truth: Compare simulator results against GMAT truth
- sim_adapter: Convert GMAT cases to simulator inputs
- scenario_runner: Run GMAT-defined scenarios through the simulator
"""

from .run_case import run_case, run_tier, CaseRunner
from .generate_truth import generate_truth, TruthGenerator
from .compare_truth import compare_truth, TruthComparator, ComparisonResult, SimulatorState
from .sim_adapter import GmatToSimAdapter, SimScenario
from .scenario_runner import (
    run_scenario,
    run_all_scenarios,
    ScenarioRunner,
    ScenarioResult,
)

__all__ = [
    # GMAT execution
    "run_case",
    "run_tier",
    "CaseRunner",
    # Truth generation
    "generate_truth",
    "TruthGenerator",
    # Truth comparison
    "compare_truth",
    "TruthComparator",
    "ComparisonResult",
    "SimulatorState",
    # Simulator integration
    "GmatToSimAdapter",
    "SimScenario",
    "run_scenario",
    "run_all_scenarios",
    "ScenarioRunner",
    "ScenarioResult",
]
