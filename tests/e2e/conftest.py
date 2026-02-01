"""Pytest configuration for E2E tests."""

import os

import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test requiring Aerie"
    )


@pytest.fixture(scope="session")
def aerie_url():
    """Get Aerie UI URL from environment or use default."""
    return os.environ.get("AERIE_UI_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def graphql_url():
    """Get GraphQL endpoint URL from environment or use default."""
    return os.environ.get("AERIE_GRAPHQL_URL", "http://localhost:9000/v1/graphql")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for Playwright."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "record_video_dir": "test-results/videos/",
    }


@pytest.fixture
def aerie_page(page, aerie_url):
    """Navigate to Aerie and return configured page."""
    from tests.e2e.pages.aerie import AeriePage

    aerie = AeriePage(page, aerie_url)
    return aerie


def pytest_collection_modifyitems(config, items):
    """Mark all tests in e2e directory as e2e tests."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
