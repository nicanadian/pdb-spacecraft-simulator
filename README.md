# PDB Spacecraft Simulator

Schedule-driven spacecraft mission simulation stack for LEO/VLEO constellations. Integrates with NASA Aerie/PLANDEV schedules and supports three fidelity modes (LOW/MEDIUM/HIGH). Simulates Hall-effect electric propulsion, attitude profiles, power/storage, S/X/Ka link budgets, ground contacts, onboard processing/storage flows, and atmospheric drag.

## Features

- **Three Fidelity Modes**: LOW (SGP4), MEDIUM (Basilisk), HIGH (Basilisk full)
- **NASA Aerie Integration**: Import/export plans with anchor chain resolution
- **CesiumJS Visualization**: Web-based 3D mission viewer with SolidJS
- **MCP Server**: AI integration via Model Context Protocol
- **GMAT Validation**: Regression testing against GMAT truth files
- **Comprehensive Activity Support**: Orbit lowering, imaging, downlink, station keeping, and more

## Installation

```bash
# Install in development mode
pip install -e .

# With development dependencies
pip install -e ".[dev]"

# With validation dependencies (for GMAT comparison)
pip install -e ".[dev,validation]"
```

## Quick Start

```bash
# Run simulation with normalized plan
simrun run --plan examples/operational_day_plan.json

# Run with Aerie-exported plan (auto-detected)
simrun run --plan examples/aerie_export.json

# Explicit format specification
simrun run --plan examples/aerie_export.json --format aerie

# With options
simrun run --plan examples/eo_imaging_plan.json \
    --altitude 500 \
    --inclination 53 \
    --fidelity LOW
```

## Plan Formats

The simulator supports two plan formats:

### Normalized Format

The simulator's native format with absolute timestamps:

```json
{
  "spacecraft_id": "SC001",
  "plan_id": "plan_001",
  "activities": [
    {
      "activity_id": "1",
      "activity_type": "eo_collect",
      "start_time": "2025-01-15T01:00:00+00:00",
      "end_time": "2025-01-15T01:15:00+00:00",
      "parameters": {
        "target_lat_deg": 40.7
      }
    }
  ]
}
```

### Aerie/PLANDEV Format

NASA Aerie export format with relative offsets and anchor chains:

```json
{
  "plan_id": 123,
  "name": "Mission Plan",
  "start_time": "2025-01-15T00:00:00Z",
  "duration": "P1D",
  "activities": [
    {
      "id": 1,
      "type": "eo_collect",
      "name": "Target Imaging",
      "anchor_id": null,
      "anchored_to_start": true,
      "start_offset": "PT1H",
      "arguments": {
        "duration": "PT15M",
        "target_lat_deg": 40.7
      },
      "metadata": {},
      "tags": ["imaging"]
    }
  ]
}
```

## Aerie Integration

### Exporting from Aerie

1. In Aerie, navigate to your plan
2. Export as JSON via the plan menu or API
3. Save the exported file

### Running Aerie Exports

The simulator auto-detects Aerie format:

```bash
simrun run --plan aerie_export.json
```

Or specify explicitly:

```bash
simrun run --plan aerie_export.json --format aerie
```

### Field Mapping

| Aerie Field | Normalized Field | Notes |
|-------------|------------------|-------|
| `id` | `activity_id` | Converted to string |
| `type` | `activity_type` | Direct mapping |
| `start_offset` | `start_time` | Resolved from plan start + anchors |
| `arguments` | `parameters` | Direct mapping (duration removed) |
| `arguments.duration` | `end_time` | Computed from start + duration |
| `anchor_id` | N/A | Used to resolve temporal dependencies |
| `metadata`, `tags` | `parameters._aerie_*` | Preserved for traceability |

### Anchor Resolution

Aerie activities can be anchored to other activities:

- `anchor_id: null` - Anchored to plan start
- `anchor_id: 1, anchored_to_start: true` - Starts relative to activity 1's start
- `anchor_id: 1, anchored_to_start: false` - Starts relative to activity 1's end

The parser resolves anchor chains using topological sort to compute absolute times.

### Duration Handling

Activity durations are determined in order:

1. `arguments.duration` (ISO 8601 format, e.g., "PT15M")
2. `arguments.duration_s` (seconds as number)
3. Activity-type-specific defaults:
   - `eo_collect`: 15 minutes
   - `downlink`: 15 minutes
   - `orbit_lower`: 1 hour
   - `momentum_desat`: 30 minutes
   - `station_keeping`: 30 minutes
   - Default: 30 minutes

## Simulation Fidelity

- **LOW**: SGP4/TLE propagation, coarse drag, parametric models
- **MEDIUM**: Numerical propagation, simplified drag, rate-limited attitude
- **HIGH**: High-fidelity propagation, detailed atmosphere, EP constraints

## CLI Commands

```bash
# Run simulation
simrun run --plan <file> [options]

# Calculate delta-V for orbit change
simrun delta-v --altitude-start 500 --altitude-end 400

# Generate synthetic TLE
simrun generate-tle --altitude 500 --inclination 53

# Calculate sensor geometry
simrun sensor-geometry --altitude 500 --focal-length 1000
```

## Output Structure

Simulation runs produce:

```
runs/<timestamp>_<runid>/
  summary.json          # KPIs, constraint violations
  profiles.parquet      # Time-indexed resource profiles
  ephemeris.parquet     # Position/velocity/attitude
  access_windows.json   # AOS/LOS per station
  passes.json           # Per-pass link metrics
  events.json           # Constraint violations
  viz/                  # Visualization exports
```

## Mission Viewer

The web-based mission visualization viewer uses CesiumJS and SolidJS:

```bash
# Start viewer development server
cd viewer
npm install
npm run dev
# Open http://localhost:3002?run=../runs/<run_id>
```

Features:
- 3D orbit visualization with CesiumJS
- Multiple workspaces: Mission Overview, Maneuver Planning, VLEO Drag, Anomaly Response, Payload Ops
- Timeline with activity and event markers
- Real-time playback controls
- Alert and constraint violation display

## MCP Server

Model Context Protocol server for AI integration:

```bash
# Start MCP HTTP server (for testing)
python -m sim_mcp.http_server --port 8765

# Tools available:
# - run_simulation: Execute simulations
# - get_run_status/results: Query run state
# - list_runs: List available runs
# - aerie_status: Check Aerie health
# - generate_viz: Create visualization
# - compare_runs: Diff two simulation runs
```

## Development

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/ --ignore=tests/ete

# Run ETE (end-to-end) tests
pytest tests/ete/ -v

# Run ETE smoke tests (fast)
pytest tests/ete/ -m "ete_smoke" -v

# Run with coverage
pytest --cov=sim

# Run GMAT validation
python validation/run_validation.py
```

## Aerie Integration

```bash
# Check Aerie status
simrun aerie status

# Export plan from Aerie
simrun aerie export --plan-id 123 --output plan.json

# Full Aerie workflow
make aerie-up           # Start Aerie services
make aerie-health       # Check health
make aerie-down         # Stop services
```

## Examples

See the `examples/` directory for sample plans:

- `operational_day_plan.json` - Full operational day (normalized format)
- `aerie_export.json` - Aerie export example with anchor chains
- `eo_imaging_plan.json` - Earth observation imaging mission
- `orbit_lowering_plan.json` - Orbit lowering maneuver sequence
- `station_keeping_plan.json` - Station keeping operations
- `anomaly_response_plan.json` - Anomaly response scenario
- `constellation_contact_plan.json` - Multi-satellite contacts

## Project Structure

```
sim/                # Core simulation library
├── core/           # Data types and configuration
├── models/         # Physical models (orbit, power, propulsion, etc.)
├── activities/     # Activity handlers (9 types)
├── runners/        # Execution engines (Basilisk)
├── io/             # Aerie parser and client
├── viz/            # CZML and visualization output
└── engine.py       # Main simulate() function

cli/                # Command-line interface
viewer/             # SolidJS + CesiumJS web viewer
sim_mcp/            # MCP server for AI integration
validation/         # GMAT truth comparison and regression tests
tests/              # Unit tests and ETE test suite
examples/           # Sample plans and configurations
runs/               # Simulation output directory
```
