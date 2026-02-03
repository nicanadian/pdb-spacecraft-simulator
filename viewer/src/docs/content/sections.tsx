/**
 * Documentation Content Sections
 */

import { Component, For, Show } from 'solid-js';
import { CodeBlock } from '../components/CodeBlock';
import { EndpointDoc } from '../components/EndpointDoc';
import { CommandDoc } from '../components/CommandDoc';
import { restEndpoints, mcpTools, cliCommands } from './index';

// ============================================
// OVERVIEW SECTIONS
// ============================================

export const OverviewIntro: Component = () => (
  <section class="doc-section" id="overview-intro">
    <h2>Introduction</h2>
    <p>
      The PDB Spacecraft Simulator is a schedule-driven mission simulation stack for LEO/VLEO
      constellations. It integrates with NASA Aerie/PLANDEV schedules and supports three fidelity
      modes for different use cases.
    </p>

    <h3>What It Does</h3>
    <ul>
      <li><strong>Simulates spacecraft missions</strong> — Propagates orbits, models power/storage,
          calculates ground contacts, and tracks constraint violations.</li>
      <li><strong>Integrates with Aerie</strong> — Import plans from NASA's Aerie mission planning
          system, run simulations, and export results.</li>
      <li><strong>Supports multiple fidelities</strong> — From fast SGP4-based LOW fidelity for
          what-if analysis to Basilisk-powered HIGH fidelity for detailed mission planning.</li>
      <li><strong>Visualizes results</strong> — View simulation outputs in a 3D CesiumJS-based
          viewer with timeline, alerts, and workspace-specific views.</li>
    </ul>

    <h3>Key Capabilities</h3>
    <div class="capability-grid">
      <div class="capability-card">
        <span class="capability-icon">🛰️</span>
        <h4>Orbit Propagation</h4>
        <p>SGP4 (LOW) or Basilisk numerical (MEDIUM/HIGH) propagation with atmospheric drag modeling.</p>
      </div>
      <div class="capability-card">
        <span class="capability-icon">🔋</span>
        <h4>Power & Storage</h4>
        <p>Battery SOC tracking, solar generation (with eclipse), onboard data storage management.</p>
      </div>
      <div class="capability-card">
        <span class="capability-icon">📡</span>
        <h4>Ground Contacts</h4>
        <p>Visibility windows, AOS/LOS times, elevation-dependent data rates for S/X/Ka bands.</p>
      </div>
      <div class="capability-card">
        <span class="capability-icon">🎯</span>
        <h4>Activity Execution</h4>
        <p>9 activity types including orbit lowering, imaging, downlink, and station keeping.</p>
      </div>
    </div>

    <style>{`
      .capability-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: var(--space-4);
        margin-top: var(--space-4);
      }

      .capability-card {
        padding: var(--space-4);
        background: var(--slate-800);
        border-radius: var(--radius-md);
        border: 1px solid var(--slate-700);
      }

      .capability-icon {
        font-size: 24px;
        margin-bottom: var(--space-2);
        display: block;
      }

      .capability-card h4 {
        margin: 0 0 var(--space-2) 0;
        color: var(--ghost-slate);
        font-size: var(--text-sm);
      }

      .capability-card p {
        margin: 0;
        color: var(--slate-400);
        font-size: var(--text-sm);
        line-height: 1.5;
      }
    `}</style>
  </section>
);

export const OverviewConcepts: Component = () => (
  <section class="doc-section" id="overview-concepts">
    <h2>Key Concepts</h2>

    <h3>Fidelity Modes</h3>
    <table class="concept-table">
      <thead>
        <tr>
          <th>Mode</th>
          <th>Propagator</th>
          <th>Time Step</th>
          <th>Use Case</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><code>LOW</code></td>
          <td>SGP4/TLE</td>
          <td>60s</td>
          <td>Quick what-if analysis, CI/CD testing</td>
        </tr>
        <tr>
          <td><code>MEDIUM</code></td>
          <td>Basilisk</td>
          <td>60s</td>
          <td>Detailed planning, cross-fidelity validation</td>
        </tr>
        <tr>
          <td><code>HIGH</code></td>
          <td>Basilisk</td>
          <td>10s</td>
          <td>High-accuracy analysis, GMAT comparison</td>
        </tr>
      </tbody>
    </table>

    <h3>Plan Formats</h3>
    <p>The simulator accepts two plan formats:</p>

    <h4>Normalized Format</h4>
    <p>The native format with absolute timestamps:</p>
    <CodeBlock
      language="json"
      code={`{
  "spacecraft_id": "SC001",
  "plan_id": "ops_day_001",
  "activities": [
    {
      "activity_id": "1",
      "activity_type": "eo_collect",
      "start_time": "2025-01-15T01:00:00Z",
      "end_time": "2025-01-15T01:15:00Z",
      "parameters": { "target_lat_deg": 40.7 }
    }
  ]
}`}
    />

    <h4>Aerie/PLANDEV Format</h4>
    <p>Exported from Aerie with relative offsets and anchor chains:</p>
    <CodeBlock
      language="json"
      code={`{
  "plan_id": 123,
  "name": "Mission Plan",
  "start_time": "2025-01-15T00:00:00Z",
  "duration": "P1D",
  "activities": [
    {
      "id": 1,
      "type": "eo_collect",
      "anchor_id": null,
      "start_offset": "PT1H",
      "arguments": { "duration": "PT15M" }
    }
  ]
}`}
    />

    <h3>Activity Types</h3>
    <table class="concept-table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        <tr><td><code>orbit_lower</code></td><td>Electric propulsion orbit lowering maneuver</td></tr>
        <tr><td><code>eo_collect</code></td><td>Electro-optical imaging collection</td></tr>
        <tr><td><code>downlink</code></td><td>Telemetry/data downlink to ground station</td></tr>
        <tr><td><code>station_keeping</code></td><td>Orbit maintenance maneuver</td></tr>
        <tr><td><code>momentum_desat</code></td><td>Momentum wheel desaturation</td></tr>
        <tr><td><code>collision_avoidance</code></td><td>Conjunction avoidance maneuver</td></tr>
        <tr><td><code>safe_mode</code></td><td>Safe mode operations</td></tr>
        <tr><td><code>idle</code></td><td>No-operation period</td></tr>
        <tr><td><code>charging</code></td><td>Battery charging period</td></tr>
      </tbody>
    </table>

    <style>{`
      .concept-table {
        width: 100%;
        border-collapse: collapse;
        margin: var(--space-4) 0;
        font-size: var(--text-sm);
      }

      .concept-table th,
      .concept-table td {
        padding: var(--space-3);
        text-align: left;
        border-bottom: 1px solid var(--slate-700);
      }

      .concept-table th {
        background: var(--slate-800);
        color: var(--ghost-slate);
        font-weight: var(--font-semibold);
      }

      .concept-table td {
        color: var(--slate-300);
      }

      .concept-table code {
        background: var(--slate-700);
        padding: 2px 6px;
        border-radius: var(--radius-sm);
        font-size: var(--text-xs);
      }
    `}</style>
  </section>
);

export const OverviewQuickstart: Component = () => (
  <section class="doc-section" id="overview-quickstart">
    <h2>Quickstart</h2>

    <h3>1. Install the Simulator</h3>
    <CodeBlock
      language="bash"
      code={`# Clone the repository
git clone https://github.com/your-org/pdb-spacecraft-simulator.git
cd pdb-spacecraft-simulator

# Install in development mode
pip install -e ".[dev]"

# Verify installation
simrun --help`}
    />

    <h3>2. Run Your First Simulation</h3>
    <CodeBlock
      language="bash"
      code={`# Run with example plan
simrun run --plan examples/operational_day_plan.json

# View the output
ls -la runs/`}
    />

    <h3>3. View Results in the Viewer</h3>
    <CodeBlock
      language="bash"
      code={`# Start the viewer
cd viewer
npm install
npm run dev

# Open in browser
# http://localhost:3002?run=../runs/<your-run-id>`}
    />

    <h3>4. (Optional) Start the MCP Server</h3>
    <CodeBlock
      language="bash"
      code={`# Start HTTP server for API access
python -m sim_mcp.http_server --port 8765

# Test the health endpoint
curl http://localhost:8765/health`}
    />
  </section>
);

// ============================================
// INTERFACE SECTIONS
// ============================================

export const InterfacesRest: Component = () => (
  <section class="doc-section" id="interfaces-rest">
    <h2>REST API (MCP HTTP Server)</h2>
    <p>
      The MCP HTTP server provides a REST interface to the simulation tools.
      Start it with: <code>python -m sim_mcp.http_server --port 8765</code>
    </p>

    <h3>Base URL</h3>
    <CodeBlock code="http://localhost:8765" language="text" />

    <h3>Endpoints</h3>
    <For each={restEndpoints}>
      {(endpoint) => <EndpointDoc endpoint={endpoint} />}
    </For>
  </section>
);

export const InterfacesMcp: Component = () => (
  <section class="doc-section" id="interfaces-mcp">
    <h2>MCP Tools</h2>
    <p>
      The Model Context Protocol (MCP) server exposes simulation capabilities as tools
      for AI assistants like Claude. These tools can be invoked via the MCP protocol
      or through the HTTP server.
    </p>

    <h3>Available Tools</h3>
    <For each={mcpTools}>
      {(tool) => (
        <div class="tool-doc" id={tool.name}>
          <div class="tool-header">
            <code class="tool-name">{tool.name}</code>
          </div>
          <p class="tool-description">{tool.description}</p>

          <Show when={tool.inputs.length > 0}>
            <h4>Inputs</h4>
            <table class="tool-params">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <For each={tool.inputs}>
                  {(param) => (
                    <tr>
                      <td><code>{param.name}</code></td>
                      <td><code class="type">{param.type}</code></td>
                      <td>{param.required ? '✓' : '—'}</td>
                      <td>{param.default ? <code>{param.default}</code> : '—'}</td>
                      <td>{param.description}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </Show>

          <Show when={tool.outputs.length > 0}>
            <h4>Outputs</h4>
            <table class="tool-params">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <For each={tool.outputs}>
                  {(param) => (
                    <tr>
                      <td><code>{param.name}</code></td>
                      <td><code class="type">{param.type}</code></td>
                      <td>{param.description}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </Show>
        </div>
      )}
    </For>

    <style>{`
      .tool-doc {
        padding: var(--space-5);
        background: var(--slate-800);
        border-radius: var(--radius-md);
        border: 1px solid var(--slate-700);
        margin-bottom: var(--space-4);
      }

      .tool-header {
        margin-bottom: var(--space-3);
      }

      .tool-name {
        font-family: var(--font-mono);
        font-size: var(--text-lg);
        color: var(--electric-teal);
        background: var(--slate-900);
        padding: var(--space-2) var(--space-3);
        border-radius: var(--radius-sm);
      }

      .tool-description {
        color: var(--slate-300);
        font-size: var(--text-sm);
        line-height: 1.6;
        margin-bottom: var(--space-4);
      }

      .tool-doc h4 {
        font-size: var(--text-sm);
        font-weight: var(--font-semibold);
        color: var(--ghost-slate);
        margin: var(--space-4) 0 var(--space-2) 0;
      }

      .tool-params {
        width: 100%;
        border-collapse: collapse;
        font-size: var(--text-sm);
      }

      .tool-params th,
      .tool-params td {
        padding: var(--space-2) var(--space-3);
        text-align: left;
        border-bottom: 1px solid var(--slate-700);
      }

      .tool-params th {
        color: var(--slate-400);
        font-weight: var(--font-medium);
        background: var(--slate-750);
      }

      .tool-params td {
        color: var(--slate-300);
      }

      .tool-params code {
        background: var(--slate-700);
        padding: 2px 6px;
        border-radius: var(--radius-sm);
        font-size: var(--text-xs);
      }

      .tool-params code.type {
        color: var(--electric-teal);
      }
    `}</style>
  </section>
);

export const InterfacesGraphql: Component = () => (
  <section class="doc-section" id="interfaces-graphql">
    <h2>Aerie GraphQL API</h2>
    <p>
      The simulator integrates with NASA Aerie via its GraphQL API. The Aerie client
      (<code>sim/io/aerie_client.py</code>) provides a Python interface to these operations.
    </p>

    <h3>Configuration</h3>
    <p>Set environment variables or use defaults:</p>
    <CodeBlock
      language="bash"
      code={`export AERIE_HOST=localhost
export AERIE_PORT=9000
export AERIE_USE_SSL=false
# Optional: export AERIE_AUTH_TOKEN=your_jwt_token`}
    />

    <h3>GraphQL Endpoint</h3>
    <CodeBlock code="http://localhost:8080/v1/graphql" language="text" />

    <h3>Key Operations</h3>

    <h4>Query: List Mission Models</h4>
    <CodeBlock
      language="graphql"
      code={`query GetMissionModels {
  mission_model {
    id
    name
    version
    description
  }
}`}
    />

    <h4>Query: Get Plan with Activities</h4>
    <CodeBlock
      language="graphql"
      code={`query GetPlan($planId: Int!) {
  plan_by_pk(id: $planId) {
    id
    name
    start_time
    duration
    activity_directives {
      id
      type
      start_offset
      arguments
      anchor_id
      anchored_to_start
    }
  }
}`}
    />

    <h4>Mutation: Create Plan</h4>
    <CodeBlock
      language="graphql"
      code={`mutation CreatePlan($plan: plan_insert_input!) {
  insert_plan_one(object: $plan) {
    id
    revision
  }
}`}
    />

    <h4>Mutation: Insert Activity</h4>
    <CodeBlock
      language="graphql"
      code={`mutation InsertActivity($activity: activity_directive_insert_input!) {
  insert_activity_directive_one(object: $activity) {
    id
  }
}`}
    />

    <div class="info-box">
      <strong>📘 Full Schema</strong>
      <p>
        For complete Aerie GraphQL schema documentation, see the
        <a href="https://nasa-ammos.github.io/aerie-docs/" target="_blank" rel="noopener">
          Aerie Documentation
        </a>.
      </p>
    </div>

    <style>{`
      .info-box {
        padding: var(--space-4);
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: var(--radius-md);
        margin-top: var(--space-4);
      }

      .info-box strong {
        color: var(--ghost-slate);
        display: block;
        margin-bottom: var(--space-2);
      }

      .info-box p {
        color: var(--slate-300);
        font-size: var(--text-sm);
        margin: 0;
      }

      .info-box a {
        color: var(--electric-teal);
        text-decoration: none;
      }

      .info-box a:hover {
        text-decoration: underline;
      }
    `}</style>
  </section>
);

export const InterfacesCli: Component = () => (
  <section class="doc-section" id="interfaces-cli">
    <h2>CLI (simrun)</h2>
    <p>
      The <code>simrun</code> command-line interface provides access to all simulator
      functionality: running simulations, Aerie integration, and visualization.
    </p>

    <h3>Installation</h3>
    <CodeBlock
      language="bash"
      code={`pip install -e .
simrun --help`}
    />

    <h3>Commands</h3>
    <For each={cliCommands}>
      {(cmd) => <CommandDoc command={cmd} />}
    </For>
  </section>
);

// ============================================
// USER MANUAL SECTIONS
// ============================================

export const ManualSimulation: Component = () => (
  <section class="doc-section" id="manual-simulation">
    <h2>Running Simulations</h2>

    <h3>Basic Workflow</h3>
    <ol>
      <li><strong>Prepare your plan</strong> — Create a JSON plan file or export from Aerie</li>
      <li><strong>Run the simulation</strong> — Use <code>simrun run</code> with your plan</li>
      <li><strong>Review outputs</strong> — Check the run directory for results</li>
      <li><strong>Visualize</strong> — Open results in the viewer or generate custom visualizations</li>
    </ol>

    <h3>Choosing Fidelity</h3>
    <p>Select fidelity based on your needs:</p>
    <ul>
      <li><strong>LOW</strong> — Fast execution (~10s for 24h simulation), good for initial planning and CI</li>
      <li><strong>MEDIUM</strong> — More accurate (~1-2min), good for detailed planning</li>
      <li><strong>HIGH</strong> — Most accurate (~5-10min), use for final validation against GMAT</li>
    </ul>

    <h3>Example: Run with Different Fidelities</h3>
    <CodeBlock
      language="bash"
      code={`# Quick analysis
simrun run --plan my_plan.json --fidelity LOW

# Detailed planning
simrun run --plan my_plan.json --fidelity MEDIUM

# Final validation
simrun run --plan my_plan.json --fidelity HIGH`}
    />

    <h3>Output Structure</h3>
    <p>Each simulation run produces:</p>
    <CodeBlock
      language="text"
      code={`runs/<timestamp>_<fidelity>/
├── run_manifest.json    # Run metadata and configuration
├── summary.json         # KPIs and statistics
├── profiles.parquet     # Time-indexed resource profiles
├── ephemeris.parquet    # Position/velocity timeseries
├── access_windows.json  # Ground station contacts
├── events.json          # Constraint violations
└── viz/
    ├── orbit.czml       # CesiumJS visualization
    └── events.json      # Formatted events for viewer`}
    />
  </section>
);

export const ManualViewer: Component = () => (
  <section class="doc-section" id="manual-viewer">
    <h2>Using the Viewer</h2>

    <h3>Starting the Viewer</h3>
    <CodeBlock
      language="bash"
      code={`cd viewer
npm install  # First time only
npm run dev

# Open: http://localhost:3002?run=../runs/<run-id>`}
    />

    <h3>Workspaces</h3>
    <p>The viewer provides 5 task-oriented workspaces:</p>
    <ul>
      <li><strong>Mission Overview</strong> — KPIs, alerts, timeline, and 3D orbit view</li>
      <li><strong>Maneuver Planning</strong> — Delta-V budgets, thrust arcs, what-if analysis</li>
      <li><strong>VLEO & Lifetime</strong> — Atmospheric drag effects, altitude decay</li>
      <li><strong>Anomaly Response</strong> — Constraint violations, root cause analysis</li>
      <li><strong>Payload Operations</strong> — Imaging collection, downlink scheduling</li>
    </ul>

    <h3>Timeline Controls</h3>
    <ul>
      <li><strong>Play/Pause</strong> — Start or stop time progression</li>
      <li><strong>Step</strong> — Advance by a small time increment</li>
      <li><strong>Jump</strong> — Skip to next significant event</li>
      <li><strong>Speed</strong> — Adjust playback speed (1x to 1000x)</li>
      <li><strong>Scrub</strong> — Click/drag on the timeline bar to seek</li>
    </ul>

    <h3>Alert System</h3>
    <p>Alerts are color-coded by severity:</p>
    <ul>
      <li><span style={{ color: '#3B82F6' }}>●</span> <strong>Info</strong> — Informational events</li>
      <li><span style={{ color: '#F59E0B' }}>●</span> <strong>Warning</strong> — Potential issues requiring attention</li>
      <li><span style={{ color: '#DC2626' }}>●</span> <strong>Failure</strong> — Critical constraint violations</li>
    </ul>
  </section>
);

export const ManualAerie: Component = () => (
  <section class="doc-section" id="manual-aerie">
    <h2>Aerie Integration</h2>

    <h3>Prerequisites</h3>
    <p>Ensure Aerie services are running:</p>
    <CodeBlock
      language="bash"
      code={`# One-time setup
make aerie-setup

# Start services
make aerie-up

# Verify health
simrun aerie status`}
    />

    <h3>Workflow: Aerie to Simulation</h3>
    <ol>
      <li>
        <strong>Create a plan in Aerie</strong>
        <CodeBlock
          language="bash"
          code={`simrun aerie plan --scenario validation/scenarios/ssr_baseline.yaml`}
        />
      </li>
      <li>
        <strong>Run the scheduler</strong>
        <CodeBlock
          language="bash"
          code={`simrun aerie schedule --plan ssr_baseline`}
        />
      </li>
      <li>
        <strong>Export the plan</strong>
        <CodeBlock
          language="bash"
          code={`simrun aerie export --plan ssr_baseline --output exports/ssr_baseline`}
        />
      </li>
      <li>
        <strong>Run simulation</strong>
        <CodeBlock
          language="bash"
          code={`simrun run --plan exports/ssr_baseline/plan.json --fidelity MEDIUM`}
        />
      </li>
    </ol>

    <h3>Anchor Chain Resolution</h3>
    <p>Aerie activities can reference each other via anchors:</p>
    <ul>
      <li><code>anchor_id: null</code> — Anchored to plan start</li>
      <li><code>anchor_id: 1, anchored_to_start: true</code> — Relative to activity 1's start</li>
      <li><code>anchor_id: 1, anchored_to_start: false</code> — Relative to activity 1's end</li>
    </ul>
    <p>The simulator automatically resolves these chains to absolute timestamps.</p>
  </section>
);

export const ManualTroubleshooting: Component = () => (
  <section class="doc-section" id="manual-troubleshooting">
    <h2>Troubleshooting</h2>

    <h3>Common Issues</h3>

    <div class="troubleshoot-item">
      <h4>Simulation fails with "No activities found"</h4>
      <p><strong>Cause:</strong> Plan file has no activities or wrong format detected.</p>
      <p><strong>Fix:</strong> Check plan file structure. Use <code>--format aerie</code> or
         <code>--format normalized</code> to explicitly set the format.</p>
    </div>

    <div class="troubleshoot-item">
      <h4>Aerie connection refused</h4>
      <p><strong>Cause:</strong> Aerie services not running or wrong port.</p>
      <p><strong>Fix:</strong> Run <code>make aerie-up</code> and check <code>simrun aerie status</code>.</p>
    </div>

    <div class="troubleshoot-item">
      <h4>Viewer shows "Error Loading"</h4>
      <p><strong>Cause:</strong> Run path not found or missing files.</p>
      <p><strong>Fix:</strong> Verify the run directory exists and contains <code>run_manifest.json</code>.</p>
    </div>

    <div class="troubleshoot-item">
      <h4>MEDIUM/HIGH fidelity fails</h4>
      <p><strong>Cause:</strong> Basilisk not installed or not found.</p>
      <p><strong>Fix:</strong> Install Basilisk: <code>pip install Basilisk</code></p>
    </div>

    <h3>Getting Help</h3>
    <ul>
      <li>Check <code>simrun --verbose</code> output for detailed logging</li>
      <li>Review run summary and events for constraint violations</li>
      <li>Open an issue on GitHub for bugs or feature requests</li>
    </ul>

    <style>{`
      .troubleshoot-item {
        padding: var(--space-4);
        background: var(--slate-800);
        border-radius: var(--radius-md);
        border: 1px solid var(--slate-700);
        margin-bottom: var(--space-3);
      }

      .troubleshoot-item h4 {
        margin: 0 0 var(--space-2) 0;
        color: var(--ghost-slate);
        font-size: var(--text-sm);
      }

      .troubleshoot-item p {
        margin: var(--space-2) 0 0 0;
        color: var(--slate-300);
        font-size: var(--text-sm);
      }

      .troubleshoot-item p strong {
        color: var(--slate-200);
      }

      .troubleshoot-item code {
        background: var(--slate-700);
        padding: 2px 6px;
        border-radius: var(--radius-sm);
        font-size: var(--text-xs);
      }
    `}</style>
  </section>
);

// ============================================
// CHANGELOG SECTION
// ============================================

export const ChangelogSection: Component = () => (
  <section class="doc-section" id="changelog">
    <h2>Changelog</h2>
    <p>
      Interface changes and version history. Breaking changes are marked with ⚠️.
    </p>

    <div class="changelog-entry">
      <h3>v0.1.0 (Current)</h3>
      <span class="changelog-date">February 2025</span>
      <ul>
        <li>Initial release with LOW/MEDIUM/HIGH fidelity support</li>
        <li>MCP HTTP server with 10 tools</li>
        <li>Aerie GraphQL integration</li>
        <li>CLI with simulation, Aerie, and visualization commands</li>
        <li>CesiumJS-based viewer with 5 workspaces</li>
        <li>GMAT regression testing framework</li>
      </ul>
    </div>

    <div class="changelog-tbd">
      <h3>Planned Changes</h3>
      <ul>
        <li><strong>TBD:</strong> WebSocket support for real-time simulation progress</li>
        <li><strong>TBD:</strong> Authentication for MCP HTTP server</li>
        <li><strong>TBD:</strong> OpenAPI specification generation</li>
      </ul>
    </div>

    <style>{`
      .changelog-entry {
        padding: var(--space-4);
        background: var(--slate-800);
        border-radius: var(--radius-md);
        border: 1px solid var(--slate-700);
        margin-bottom: var(--space-4);
      }

      .changelog-entry h3 {
        margin: 0;
        color: var(--ghost-slate);
        font-size: var(--text-base);
      }

      .changelog-date {
        font-size: var(--text-xs);
        color: var(--slate-500);
      }

      .changelog-entry ul {
        margin: var(--space-3) 0 0 0;
        padding-left: var(--space-5);
        color: var(--slate-300);
        font-size: var(--text-sm);
      }

      .changelog-entry li {
        margin-bottom: var(--space-1);
      }

      .changelog-tbd {
        padding: var(--space-4);
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: var(--radius-md);
      }

      .changelog-tbd h3 {
        margin: 0 0 var(--space-3) 0;
        color: var(--color-alert-warning);
        font-size: var(--text-sm);
      }

      .changelog-tbd ul {
        margin: 0;
        padding-left: var(--space-5);
        color: var(--slate-300);
        font-size: var(--text-sm);
      }
    `}</style>
  </section>
);
