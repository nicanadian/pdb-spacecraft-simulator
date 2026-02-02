"""End-to-end (ETE) validation test suite.

Integrates all services: UI (Viewer), Aerie, Basilisk, GMAT (reference), and MCP.

Test Structure
==============

Test Files:
    test_smoke.py              - Quick smoke tests (<60s)
    test_pipeline.py           - Simulation pipeline tests
    test_gmat_comparison.py    - GMAT truth comparison tests
    test_viewer_validation.py  - UI visualization tests
    test_aerie_integration.py  - Aerie GraphQL integration
    test_mcp_integration.py    - MCP server tool tests
    test_eclipse_contacts.py   - Eclipse and contact window tests
    test_baseline_regression.py - Baseline regression tests
    test_full_pipeline.py      - Complete end-to-end tests

Test Tiers
==========

    - ete_smoke: Quick smoke tests (<60s)
        * Core module imports
        * Basic connectivity
        * Physics invariant checks

    - ete_tier_a: Standard validation (<300s)
        * Pipeline execution
        * GMAT comparison (subset)
        * Viewer loading
        * Format validation

    - ete_tier_b: Extended validation (<1800s)
        * Full GMAT comparison suite
        * Workspace cycling
        * Performance checks
        * Extended physics validation

Fixtures
========

    reference_epoch      - Deterministic epoch (2024-01-01T12:00:00Z)
    tolerance_config     - GMAT tolerance configuration
    completed_run        - Real simulation output (not synthetic)
    physics_validator    - Physics invariant checker
    viewer_page          - Playwright page object for viewer
    aerie_services       - Aerie Docker service manager
    mcp_client           - MCP server client

Usage
=====

    # Run smoke tests only
    pytest tests/ete/ -m "ete_smoke" -v

    # Run Tier A tests
    pytest tests/ete/ -m "ete_tier_a" -v

    # Run Tier B tests (nightly)
    pytest tests/ete/ -m "ete_tier_b" -v

    # Run all ETE tests
    pytest tests/ete/ -v --tb=short

    # Run with services
    make aerie-up
    cd viewer && npm run dev &
    pytest tests/ete/ -v

Environment Variables
====================

    AERIE_GRAPHQL_URL  - Aerie GraphQL endpoint (default: http://localhost:8080/v1/graphql)
    VIEWER_URL         - Viewer URL (default: http://localhost:3002)
    MCP_SERVER_URL     - MCP server URL (default: http://localhost:8765)
"""
