"""Cross-fidelity validation module."""
from validation.cross_fidelity.comparator import CrossFidelityComparator
from validation.cross_fidelity.metrics import (
    compute_position_delta,
    compute_contact_timing_delta,
    compute_eclipse_timing_delta,
)

__all__ = [
    "CrossFidelityComparator",
    "compute_position_delta",
    "compute_contact_timing_delta",
    "compute_eclipse_timing_delta",
]
