# Spacecraft Simulator Architecture

## Overview

The PDB Spacecraft Simulator is a schedule-driven spacecraft mission simulation stack designed for LEO/VLEO constellations. It supports three fidelity modes and simulates electric propulsion, power/storage, imaging, and ground station access.

## Core Contract

The canonical simulation API:

```python
simulate(plan, initial_state, fidelity, config) -> results
```

### Key Data Structures

- **PlanInput**: Activities from Aerie export or normalized format
- **InitialState**: From TLE or state vector
- **SimConfig**: Typed configuration objects with hash support for caching
- **SimResults**: Contains profiles (timeseries), events (violations), artifacts (viz files), final_state (for chaining)

## Fidelity Modes

### LOW Fidelity
- SGP4/TLE propagation
- Coarse drag modeling
- Parametric power/thermal models
- Fast execution for what-if analysis

### MEDIUM Fidelity (planned)
- Basilisk numerical propagation
- Simplified drag with cached indices
- Rate-limited attitude control
- Continuous EP thrust modeling

### HIGH Fidelity (planned)
- Basilisk high-fidelity propagation
- Higher time resolution
- Better atmosphere inputs
- EP constraints modeling

## Model Interfaces

All models are designed to be swappable:

- **OrbitPropagator**: Orbit propagation (SGP4 for LOW)
- **AttitudeModel**: Spacecraft attitude control
- **ThrustModel**: Electric propulsion
- **AtmosphereModel**: Atmospheric drag
- **AccessModel**: Ground station visibility
- **LinkModel**: S/X/Ka link budgets
- **PowerModel**: Battery SOC, solar generation
- **StorageModel**: Onboard data storage
- **ProcessingModel**: Onboard data processing

## Activity System

Activities are processed by registered handlers:

```python
class ActivityHandler(ABC):
    @property
    def activity_type(self) -> str: ...

    def process(self, activity, state, ephemeris, config) -> ActivityResult: ...
```

### Implemented Activities

1. **orbit_lower**: Electric propulsion orbit lowering
   - Duty-cycled thrusting (configurable arcs per orbit)
   - Power-constrained thrust scheduling
   - Propellant tracking with rocket equation

2. **eo_collect**: Electro-optical imaging
   - Point target collection
   - Cross-track/along-track pointing constraints
   - GSD and data volume calculations

## Directory Structure

```
sim/
├── core/           # Core types and utilities
│   ├── types.py    # Data structures
│   ├── time_utils.py
│   └── config.py
├── models/         # Physical models
│   ├── orbit.py    # SGP4 propagation
│   ├── atmosphere.py
│   ├── propulsion.py
│   ├── power.py
│   ├── imaging.py
│   └── access.py
├── activities/     # Activity handlers
│   ├── base.py
│   ├── orbit_lower.py
│   └── eo_collect.py
├── engine.py       # Main simulate() function
└── cache.py        # Disk-based caching

cli/
└── simrun.py       # CLI entrypoint

tests/
├── test_orbit.py
├── test_propulsion.py
├── test_imaging.py
└── test_integration.py
```

## Run Output Structure

```
runs/<timestamp>_<runid>/
├── summary.json          # KPIs, counts, constraint violations
├── profiles.parquet      # Time-indexed resource profiles
├── ephemeris.parquet     # Position/velocity/attitude
├── access_windows.json   # AOS/LOS per station
├── eclipse_windows.json  # Eclipse periods
├── events.json           # Constraint violations
└── viz/                  # Visualization exports
```

## Validation Invariants

The simulation enforces:
- SOC in [0, 1]
- Storage never negative
- Monotonic time axis
- AOS < LOS for all passes
- Downlinked volume <= available storage
- Propellant never negative
- Eclipse implies generation=0 (LOW fidelity)

## Caching Strategy

- Cache keyed by: spacecraft_id, epoch range, orbit model, config hash
- Geometry primitives cached: eclipse intervals, station access windows
- Disk-based persistent cache layer (can be disabled)

## Determinism

- Fixed inputs produce reproducible results
- Seeded randomness only (e.g., Ka weather availability model)
- Time axis standardized to UTC
