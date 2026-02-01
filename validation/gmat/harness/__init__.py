"""GMAT test harness for regression test case execution.

This module provides:
- run_case: Execute a single GMAT regression case
- generate_truth: Generate truth files from GMAT outputs
- compare_truth: Compare simulator results against GMAT truth
"""

from .run_case import run_case, run_tier, CaseRunner
from .generate_truth import generate_truth, TruthGenerator
from .compare_truth import compare_truth, TruthComparator, ComparisonResult

__all__ = [
    "run_case",
    "run_tier",
    "CaseRunner",
    "generate_truth",
    "TruthGenerator",
    "compare_truth",
    "TruthComparator",
    "ComparisonResult",
]
