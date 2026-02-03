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

### MEDIUM Fidelity
- Basilisk numerical propagation
- Simplified drag with cached indices
- Rate-limited attitude control
- Continuous EP thrust modeling
- 60-second time step default

### HIGH Fidelity
- Basilisk high-fidelity propagation
- Higher time resolution (10-second steps)
- Better atmosphere inputs (NRLMSISE-00)
- EP constraints modeling
- Full attitude dynamics

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

3. **downlink**: Telemetry/data downlink
   - Ground station contact scheduling
   - Data rate vs elevation modeling
   - S/X/Ka band link budgets
   - MEDIUM fidelity variant with detailed link modeling

4. **station_keeping**: Orbit maintenance
   - Semi-major axis corrections
   - Eccentricity management
   - Propellant-optimized maneuvers

5. **momentum_desat**: Momentum wheel desaturation
   - Thruster-based momentum management
   - Propellant consumption tracking

6. **collision_avoidance**: Collision avoidance maneuvers
   - Conjunction assessment response
   - Delta-V budgeting

7. **safe_mode**: Safe mode operations
   - Power-safe configuration
   - Attitude hold modes

8. **idle**: No-operation periods
   - Background power consumption
   - Quiescent state modeling

9. **charging**: Battery charging
   - Solar panel pointing optimization
   - SOC management

## Directory Structure

```
sim/
├── core/               # Core types and utilities
│   ├── types.py        # Data structures (Fidelity, EventType, PlanInput, etc.)
│   ├── config.py       # Configuration management
│   ├── time_utils.py   # Time utilities
│   └── manifest.py     # Run manifest tracking
├── models/             # Physical models
│   ├── propagator_base.py  # Abstract propagator interface
│   ├── orbit.py            # SGP4 propagation (LOW)
│   ├── basilisk_propagator.py  # Basilisk (MEDIUM/HIGH)
│   ├── atmosphere.py       # Atmospheric drag
│   ├── propulsion.py       # Electric propulsion
│   ├── power.py            # Battery SOC and solar
│   ├── storage.py          # Data storage
│   ├── imaging.py          # EO sensor modeling
│   ├── access.py           # Ground station visibility
│   └── spacecraft_mode.py  # Operational modes
├── activities/         # Activity handlers (9 types)
│   ├── base.py         # Abstract handler interface
│   ├── orbit_lower.py  # Orbit lowering
│   ├── eo_collect.py   # Imaging collection
│   ├── downlink.py     # Data downlink
│   ├── station_keeping.py
│   ├── momentum_desat.py
│   ├── collision_avoidance.py
│   └── safe_mode.py
├── runners/            # Execution engines
│   ├── basilisk_runner.py  # Basilisk propagation
│   └── activity_mappers.py
├── io/                 # Input/output
│   ├── aerie_parser.py     # Aerie format parsing
│   ├── aerie_client.py     # Aerie API client
│   └── aerie_queries.py    # GraphQL queries
├── viz/                # Visualization output
│   ├── czml_generator.py   # CesiumJS CZML format
│   ├── events_formatter.py
│   ├── manifest_generator.py
│   └── diff.py             # Run comparison
├── engine.py           # Main simulate() function
└── cache.py            # Disk-based caching

cli/
└── simrun.py           # CLI with run, aerie, delta-v, viz commands

viewer/                 # Web-based mission viewer
├── src/
│   ├── App.tsx         # Main SolidJS application
│   ├── components/     # UI components
│   ├── workspaces/     # Mission workspaces (5 views)
│   ├── services/       # API clients
│   └── stores/         # State management
├── package.json        # Node.js dependencies
└── vite.config.ts      # Vite build config

sim_mcp/                # MCP server for AI integration
├── server.py           # Stdio-based MCP server
├── http_server.py      # HTTP bridge for testing
└── tools/              # Tool implementations

validation/             # GMAT truth comparison
├── gmat/
│   ├── case_registry.py    # Test case registry
│   ├── baseline_manager.py # Baseline management
│   ├── executor.py         # GMAT script execution
│   └── cases/              # 18+ validation cases
├── baselines/          # Reference truth data
└── scenarios/          # Validation scenarios

tests/
├── test_aerie_parser.py
├── test_storage.py
├── test_viz.py
└── ete/                # End-to-end tests
    ├── test_smoke.py
    ├── test_pipeline.py
    ├── test_gmat_comparison.py
    ├── test_viewer_validation.py
    └── pages/          # Playwright page objects
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

## Mission Viewer

Web-based visualization using SolidJS and CesiumJS:

### Workspaces
1. **Mission Overview** - KPIs, alerts, timeline, 3D orbit view
2. **Maneuver Planning** - Delta-V budgets, thrust arcs
3. **VLEO Drag** - Atmospheric effects, altitude decay
4. **Anomaly Response** - Constraint violations, safe mode
5. **Payload Ops** - Imaging, downlink scheduling

### Data Flow
```
Simulation Run → viz/ directory → Viewer loads via HTTP
                 ├── orbit.czml      # 3D trajectory
                 ├── events.json     # Timeline markers
                 └── manifest.json   # Run metadata
```

## MCP Server Integration

Model Context Protocol server for AI assistant integration:

### Available Tools
- `run_simulation` - Execute simulations with inline plans
- `get_run_status` / `get_run_results` - Query run state
- `list_runs` - List available simulation runs
- `aerie_status` - Check Aerie service health
- `create_plan` / `export_plan` - Aerie plan management
- `generate_viz` - Create visualization artifacts
- `compare_runs` - Diff two simulation runs

### Servers
- **stdio server** (`sim_mcp/server.py`) - For Claude Code integration
- **HTTP server** (`sim_mcp/http_server.py`) - For testing and web integration

## Validation Framework

GMAT-based truth comparison for regression testing:

### Test Cases (18+)
- **R01-R11**: Orbital mechanics and maneuver accuracy
- **N01-N03**: VLEO drag and atmospheric modeling
- **Eclipse timing**: Shadow entry/exit validation

### Tolerances
- Position RMS: < 10 km
- Velocity RMS: < 10 m/s
- Altitude RMS: < 5 km
- Eclipse timing: < 30 seconds

### ETE Test Tiers
- **Smoke** (`ete_smoke`): <60s, basic connectivity
- **Tier A** (`ete_tier_a`): <5min, core functionality
- **Tier B** (`ete_tier_b`): <30min, extended validation
