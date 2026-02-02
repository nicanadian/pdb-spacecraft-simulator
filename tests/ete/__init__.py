"""End-to-end (ETE) validation test suite.

Integrates all services: UI (Viewer), Aerie, Basilisk, GMAT (reference), and MCP.

Test Tiers:
    - ete_smoke: Quick smoke tests (<60s) - run on every PR
    - ete_tier_a: Standard validation (<300s) - run on every PR
    - ete_tier_b: Extended validation (<1800s) - run nightly

Usage:
    # Run smoke tests only
    pytest tests/ete/ -m "ete_smoke" -v

    # Run Tier A with services
    make aerie-up
    cd viewer && npm run dev &
    pytest tests/ete/ -m "ete_tier_a" -v

    # Run full suite
    pytest tests/ete/ -v --tb=short
"""
