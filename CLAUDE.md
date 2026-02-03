# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Schedule-driven spacecraft mission simulation stack for LEO/VLEO constellations. Integrates with Aerie (PLANDEV) schedules and supports three fidelity modes (LOW/MEDIUM/HIGH). Simulates Hall-effect electric propulsion, attitude profiles, power/storage, S/X/Ka link budgets, ground contacts, onboard processing/storage flows, and atmospheric drag.

## Build & Development Commands

```bash
# Install in development mode
pip install -e .

# Install with all dependencies
pip install -e ".[dev,validation]"

# Run tests
pytest                              # All unit tests
pytest tests/ete/ -v                # ETE tests
pytest tests/ete/ -m "ete_smoke"    # Smoke tests only

# Run CLI
simrun --help
simrun run --plan examples/operational_day_plan.json

# Start viewer
cd viewer && npm run dev

# Start MCP HTTP server
python -m sim_mcp.http_server --port 8765

# Aerie integration
make aerie-up       # Start Aerie Docker stack
make aerie-health   # Check health
simrun aerie status # CLI status check
```

## Architecture

### Core Contract

The canonical simulation API:
```python
simulate(plan, initial_state, fidelity, config) -> results
```

Key data structures:
- `PlanInput`: Activities from Aerie export or normalized format
- `InitialState`: From TLE or state vector
- `SimConfig`: Typed configuration objects with hash support for caching
- `SimResults`: Contains profiles (timeseries), events (violations), artifacts (viz files), final_state (for chaining)

### Fidelity Modes

- **LOW**: SGP4/TLE propagation, coarse drag, parametric models. Fast for what-if analysis.
- **MEDIUM**: Basilisk numerical propagation, simplified drag with cached indices, rate-limited attitude, continuous EP thrust.
- **HIGH**: Basilisk high-fidelity with feature flags for higher time resolution, better atmosphere inputs, EP constraints.

### Model Interfaces (all swappable)

OrbitPropagator, AttitudeModel, ThrustModel, AtmosphereModel, AccessModel, LinkModel, PowerModel, StorageModel, ProcessingModel

### Directory Structure

```
sim/               # Core simulation library
├── core/          # Data types (types.py), config, time utilities
├── models/        # Physical models (orbit, power, propulsion, atmosphere, etc.)
├── activities/    # Activity handlers (9 types implemented)
├── runners/       # Basilisk execution engine
├── io/            # Aerie parser and GraphQL client
├── viz/           # CZML generator, events formatter
├── engine.py      # Main simulate() function
└── cache.py       # Disk-based caching layer

cli/               # CLI entrypoints (simrun)
viewer/            # SolidJS + CesiumJS web visualization UI
sim_mcp/           # MCP server for AI integration
├── server.py      # Stdio-based MCP server
├── http_server.py # HTTP bridge for testing
└── tools/         # Simulation, Aerie, and viz tools

validation/        # GMAT truth comparison and regression
├── gmat/          # GMAT integration (cases, templates, parser)
├── baselines/     # Reference truth data
└── scenarios/     # Validation scenario definitions

tests/             # Test suite
├── ete/           # End-to-end tests (Playwright, GMAT comparison)
└── sim_mcp/       # MCP server tests

examples/          # Demo plans and configurations
docs/              # Architecture and strategy documentation
runs/              # Simulation output directory
```

### Run Output Structure

```
runs/<timestamp>_<runid>/
  summary.json          # KPIs, counts, constraint violations
  profiles.parquet      # Time-indexed resource profiles
  ephemeris.parquet     # Position/velocity/attitude
  access_windows.json   # AOS/LOS per station
  passes.json           # Per-pass link metrics
  events.json           # Constraint violations
  viz/                  # Tudat/Cesium-ready exports
```

## Key Implementation Notes

- Use typed config objects (pydantic/dataclasses) with config hashing for cache keys
- Cache geometry primitives: eclipse intervals, station access windows, rate-vs-elevation lookup
- Cache keyed by: spacecraft_id, epoch range, orbit model, config hash
- Disk-based persistent cache layer (can be disabled)
- Determinism required: fixed inputs produce reproducible results
- Seeded randomness only (e.g., Ka weather availability model)
- Time axis standardized to UTC

## Domain Constraints

- Orbits: LEO/VLEO, inclinations 45°, 53°, and SSO
- Propulsion: Hall-effect EP (power-limited thrust, Isp, duty cycle)
- Comms: S/X/Ka bands with rate-vs-elevation and link margin
- Plans: Activity schedules exported from Aerie/PLANDEV

## Validation Invariants

Code must enforce:
- SOC in [0, 1]
- Storage never negative
- Monotonic time axis
- AOS < LOS for all passes
- Downlinked volume <= available storage
- Propellant never negative
- Eclipse implies generation=0 (LOW fidelity)
