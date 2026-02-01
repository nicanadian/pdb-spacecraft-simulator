"""Pytest configuration and fixtures for GMAT validation tests."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from validation.gmat.executor import GMATExecutor, check_gmat_installation


# Check GMAT availability at module import
_gmat_info = check_gmat_installation()
GMAT_AVAILABLE = _gmat_info["available"]
GMAT_PATH = _gmat_info.get("path")
GMAT_VERSION = _gmat_info.get("version")

# Skip marker for tests requiring GMAT
requires_gmat = pytest.mark.skipif(
    not GMAT_AVAILABLE,
    reason="GMAT not installed. Set GMAT_ROOT environment variable or install GMAT."
)

# =============================================================================
# Tier markers for selective test execution
# =============================================================================
# Run tier A only: pytest -m tier_a validation/tests/test_gmat_cases.py
# Run tier B only: pytest -m tier_b validation/tests/test_gmat_cases.py

tier_a = pytest.mark.tier_a  # CI fast checks
tier_b = pytest.mark.tier_b  # Nightly ops checks


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "tier_a: Tier A tests (CI fast checks)"
    )
    config.addinivalue_line(
        "markers", "tier_b: Tier B tests (nightly ops checks)"
    )
    config.addinivalue_line(
        "markers", "requires_gmat: Tests that require GMAT installation"
    )


@pytest.fixture(scope="session")
def gmat_executor():
    """
    Session-scoped GMAT executor fixture.

    Skips tests if GMAT is not available.
    """
    if not GMAT_AVAILABLE:
        pytest.skip("GMAT not installed. Set GMAT_ROOT environment variable.")

    return GMATExecutor()


@pytest.fixture(scope="session")
def gmat_info():
    """
    GMAT installation info fixture.

    Returns dict with available, path, version keys.
    """
    return _gmat_info


@pytest.fixture
def sample_scenario_config():
    """
    Create a sample ScenarioConfig for testing.

    Returns:
        ScenarioConfig with default test values
    """
    from validation.gmat.generator import ScenarioConfig

    return ScenarioConfig(
        scenario_id="test_scenario",
        scenario_name="Test Scenario",
        epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
        duration_hours=1.0,  # Short duration for tests
        sma_km=6878.137,
        inc_deg=53.0,
    )


@pytest.fixture
def sample_ephemeris_df():
    """
    Create a sample ephemeris DataFrame for testing.

    Returns:
        DataFrame with ephemeris data
    """
    import pandas as pd
    import numpy as np
    from datetime import timedelta

    num_points = 61  # 1 hour at 1-minute intervals
    base_time = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    times = [base_time + timedelta(minutes=i) for i in range(num_points)]

    # Circular orbit at 500 km altitude
    r_mag = 6878.137  # km
    v_mag = 7.612     # km/s
    period_s = 5669.3 # seconds for this orbit

    # Simple circular motion in XY plane
    angles = np.linspace(0, 2 * np.pi * 3600 / period_s, num_points)

    return pd.DataFrame({
        "time": times,
        "x_km": r_mag * np.cos(angles),
        "y_km": r_mag * np.sin(angles),
        "z_km": np.zeros(num_points),
        "vx_km_s": -v_mag * np.sin(angles),
        "vy_km_s": v_mag * np.cos(angles),
        "vz_km_s": np.zeros(num_points),
    })


@pytest.fixture
def baseline_manager(tmp_path):
    """
    Create a baseline manager with temporary storage directory.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        GMATBaselineManager using temp directory
    """
    from validation.gmat.baseline_manager import GMATBaselineManager

    return GMATBaselineManager(baselines_dir=tmp_path / "baselines")


@pytest.fixture
def tolerance_config():
    """
    Create default tolerance configuration.

    Returns:
        GMATToleranceConfig with default values
    """
    from validation.gmat.tolerance_config import GMATToleranceConfig

    return GMATToleranceConfig()


@pytest.fixture
def sample_baseline(sample_scenario_config, sample_ephemeris_df):
    """
    Create a sample GMATBaseline for testing.

    Returns:
        GMATBaseline with sample data
    """
    from validation.gmat.baseline_manager import create_baseline_from_ephemeris

    return create_baseline_from_ephemeris(
        scenario_id="test_scenario",
        scenario_config=sample_scenario_config,
        ephemeris_df=sample_ephemeris_df,
        gmat_version="R2022a (test)",
    )


# =============================================================================
# GMAT Case Registry Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def case_registry():
    """
    Load the GMAT case registry.

    Returns:
        Dict mapping case_id to CaseDefinition
    """
    from validation.gmat.case_registry import CASE_REGISTRY
    return CASE_REGISTRY


@pytest.fixture(scope="session")
def tier_a_cases():
    """
    Get Tier A case IDs.

    Returns:
        List of Tier A case IDs
    """
    from validation.gmat.case_registry import CaseTier, list_case_ids
    return list_case_ids(CaseTier.A)


@pytest.fixture(scope="session")
def tier_b_cases():
    """
    Get Tier B case IDs.

    Returns:
        List of Tier B case IDs
    """
    from validation.gmat.case_registry import CaseTier, list_case_ids
    return list_case_ids(CaseTier.B)


@pytest.fixture
def case_runner(tmp_path):
    """
    Create a CaseRunner with temporary output directory.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        CaseRunner instance
    """
    from validation.gmat.harness.run_case import CaseRunner
    return CaseRunner(output_dir=tmp_path / "output")


@pytest.fixture
def truth_generator(tmp_path):
    """
    Create a TruthGenerator with temporary baselines directory.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        TruthGenerator instance
    """
    from validation.gmat.harness.generate_truth import TruthGenerator
    return TruthGenerator(baselines_dir=tmp_path / "baselines")
