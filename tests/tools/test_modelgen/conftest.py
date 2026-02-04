"""Shared fixtures for modelgen tests."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-mark viewer E2E tests."""
    for item in items:
        if "test_viewer_e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e_viewer)
