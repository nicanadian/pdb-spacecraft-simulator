# Stability & Backward Compatibility

## Stability Tiers

### Stable (safe to depend on)

These interfaces are considered stable. Breaking changes will be documented and follow the deprecation policy.

| Interface | Description | Since |
|-----------|-------------|-------|
| `simulate(plan, initial_state, fidelity, config) -> results` | Core simulation API | v0.1.0 |
| `SimConfig`, `SimResults`, `InitialState`, `PlanInput` | Core data types | v0.1.0 |
| `Fidelity` enum (LOW, MEDIUM, HIGH) | Fidelity levels | v0.1.0 |
| `ActivityHandler` ABC | Activity handler interface | v0.1.0 |
| CLI: `simrun run --plan ... --fidelity ...` | Core CLI invocation | v0.1.0 |
| Run output: `summary.json`, `profiles.parquet`, `events.json` | Output file contract | v0.1.0 |
| IR JSON schema v1.0 | Modelgen IR output format | v0.1.0 |

### Experimental (may change without notice)

| Interface | Description | Notes |
|-----------|-------------|-------|
| `modelgen` CLI | Architecture model generator | API may change in minor versions |
| MCP server tools | AI integration tools | Schema may evolve |
| MEDIUM/HIGH fidelity Basilisk integration | Numerical propagation | Depends on Basilisk availability |
| SysML export | Optional secondary output | Format not finalized |
| `modelgen serve` viewer | Web-based architecture viewer | UI/UX subject to change |

### Internal (do not depend on)

| Interface | Description |
|-----------|-------------|
| `sim.cache` internals | Cache key format, storage layout |
| `sim.runners.*` | Basilisk runner internals |
| `tools.modelgen.extractors.*` | Extractor implementation details |
| `tools.modelgen.ir.builder._*` methods | Private builder methods |

## Deprecation Policy

1. **Stable interfaces**: At least one minor version of deprecation warning before removal. Deprecated features will log a warning and remain functional for at least one release cycle.

2. **Experimental interfaces**: May change or be removed in any release. No deprecation period required, but changes will be documented in release notes.

3. **Internal interfaces**: May change at any time without notice.

## Schema Versioning

The IR JSON schema uses semantic versioning:

- **Major** (e.g., 1.0 → 2.0): Breaking structural changes (renamed fields, removed sections)
- **Minor** (e.g., 1.0 → 1.1): Additive changes (new optional fields)
- **Patch**: Not used for schema versions

Current schema version: **1.0**

### Drift Detection

Use the schema snapshot tool to detect unintentional drift:

```bash
# Generate baseline
make schema-snapshot

# Check for drift (e.g., in CI)
make schema-check
```

## Validation Invariants

These invariants are enforced in code and must be maintained across all versions:

- SOC in [0, 1]
- Storage never negative
- Monotonic time axis
- AOS < LOS for all passes
- Downlinked volume <= available storage
- Propellant never negative
- Eclipse implies generation=0 (LOW fidelity)

See `CLAUDE.md` for the canonical list.
