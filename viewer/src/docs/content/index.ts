/**
 * Documentation Content - Derived from codebase interfaces
 */

import type { DocSection, DocEndpoint, DocCommand, DocTool, DocSearchResult } from '../types';

// ============================================
// NAVIGATION STRUCTURE
// ============================================

export const docSections: DocSection[] = [
  {
    id: 'overview',
    title: 'Overview',
    icon: '🏠',
    children: [
      { id: 'overview-intro', title: 'Introduction' },
      { id: 'overview-concepts', title: 'Key Concepts' },
      { id: 'overview-quickstart', title: 'Quickstart' },
    ],
  },
  {
    id: 'interfaces',
    title: 'Interfaces',
    icon: '⚡',
    children: [
      { id: 'interfaces-rest', title: 'REST API (MCP HTTP)' },
      { id: 'interfaces-mcp', title: 'MCP Tools' },
      { id: 'interfaces-graphql', title: 'Aerie GraphQL' },
      { id: 'interfaces-cli', title: 'CLI (simrun)' },
    ],
  },
  {
    id: 'user-manual',
    title: 'User Manual',
    icon: '📖',
    children: [
      { id: 'manual-simulation', title: 'Running Simulations' },
      { id: 'manual-viewer', title: 'Using the Viewer' },
      { id: 'manual-aerie', title: 'Aerie Integration' },
      { id: 'manual-troubleshooting', title: 'Troubleshooting' },
    ],
  },
  {
    id: 'changelog',
    title: 'Changelog',
    icon: '📋',
  },
];

// ============================================
// REST API ENDPOINTS (MCP HTTP Server)
// ============================================

export const restEndpoints: DocEndpoint[] = [
  {
    method: 'GET',
    path: '/health',
    description: 'Health check endpoint. Returns server status and version information.',
    response: {
      status: 200,
      description: 'Server is healthy',
      example: `{
  "status": "healthy",
  "service": "mcp-http-server",
  "version": "1.0.0"
}`,
    },
  },
  {
    method: 'GET',
    path: '/tools',
    description: 'List all available MCP tools with their input schemas.',
    response: {
      status: 200,
      description: 'List of tools',
      example: `{
  "tools": [
    {
      "name": "run_simulation",
      "description": "Run a spacecraft simulation",
      "inputSchema": {
        "type": "object",
        "properties": {
          "plan_path": { "type": "string" },
          "fidelity": { "type": "string", "enum": ["LOW", "MEDIUM", "HIGH"] }
        },
        "required": ["plan_path"]
      }
    }
  ]
}`,
    },
  },
  {
    method: 'POST',
    path: '/tools/simulate',
    description: 'Run a simulation with an inline plan definition. This is the primary endpoint for executing simulations.',
    requestBody: {
      contentType: 'application/json',
      schema: 'SimulateRequest',
      example: `{
  "plan": {
    "spacecraft_id": "SC001",
    "plan_id": "test_plan",
    "activities": [
      {
        "activity_id": "act_001",
        "activity_type": "idle",
        "start_time": "2025-01-15T00:00:00Z",
        "end_time": "2025-01-15T02:00:00Z",
        "parameters": {}
      }
    ]
  },
  "initial_state": {
    "epoch": "2025-01-15T00:00:00Z",
    "position_eci": [6778.137, 0.0, 0.0],
    "velocity_eci": [0.0, 7.6686, 0.0],
    "mass_kg": 500.0
  },
  "fidelity": "LOW",
  "output_dir": "runs/my_simulation"
}`,
    },
    response: {
      status: 200,
      description: 'Simulation completed successfully',
      example: `{
  "success": true,
  "plan_id": "test_plan",
  "output_dir": "runs/my_simulation",
  "summary": {
    "duration_s": 7200,
    "event_count": 3
  },
  "final_state": {
    "epoch": "2025-01-15T02:00:00+00:00",
    "position_eci": [-6245.32, 2891.45, 1234.56],
    "velocity_eci": [-2.34, -6.89, 1.23],
    "mass_kg": 499.8
  }
}`,
    },
  },
  {
    method: 'POST',
    path: '/tools/{tool_name}',
    description: 'Invoke a specific MCP tool by name. The request body contains the tool arguments.',
    parameters: [
      {
        name: 'tool_name',
        type: 'string',
        required: true,
        description: 'Name of the tool to invoke (e.g., run_simulation, get_run_status)',
      },
    ],
    response: {
      status: 200,
      description: 'Tool invocation result (varies by tool)',
    },
    example: {
      description: 'Get status of a simulation run',
      request: `curl -X POST "http://localhost:8765/tools/get_run_status" \\
  -H "Content-Type: application/json" \\
  -d '{"run_id": "20250115_120000_LOW"}'`,
      response: `{
  "found": true,
  "run_id": "20250115_120000_LOW",
  "status": "completed",
  "fidelity": "LOW",
  "has_violations": false
}`,
    },
  },
];

// ============================================
// MCP TOOLS
// ============================================

export const mcpTools: DocTool[] = [
  {
    name: 'run_simulation',
    description: 'Run a spacecraft simulation from a plan file.',
    inputs: [
      { name: 'plan_path', type: 'string', required: true, description: 'Path to the plan JSON file' },
      { name: 'fidelity', type: 'string', required: false, default: 'LOW', description: 'Simulation fidelity (LOW, MEDIUM, HIGH)' },
      { name: 'config_overrides', type: 'object', required: false, description: 'Optional configuration overrides' },
    ],
    outputs: [
      { name: 'success', type: 'boolean', required: true, description: 'Whether simulation completed' },
      { name: 'run_id', type: 'string', required: true, description: 'Unique run identifier' },
      { name: 'output_dir', type: 'string', required: true, description: 'Path to output directory' },
      { name: 'has_violations', type: 'boolean', required: true, description: 'Whether any constraints were violated' },
    ],
  },
  {
    name: 'get_run_status',
    description: 'Get the status of a simulation run.',
    inputs: [
      { name: 'run_id', type: 'string', required: true, description: 'Run identifier' },
    ],
    outputs: [
      { name: 'found', type: 'boolean', required: true, description: 'Whether run was found' },
      { name: 'status', type: 'string', required: true, description: 'Run status (pending, running, completed, failed)' },
      { name: 'fidelity', type: 'string', required: true, description: 'Simulation fidelity level' },
    ],
  },
  {
    name: 'get_run_results',
    description: 'Get detailed results from a completed simulation run.',
    inputs: [
      { name: 'run_id', type: 'string', required: true, description: 'Run identifier' },
    ],
    outputs: [
      { name: 'manifest', type: 'object', required: true, description: 'Run manifest with metadata' },
      { name: 'summary', type: 'object', required: true, description: 'Summary statistics and KPIs' },
      { name: 'events', type: 'array', required: true, description: 'List of events and violations' },
      { name: 'artifacts', type: 'object', required: true, description: 'Paths to output files' },
    ],
  },
  {
    name: 'list_runs',
    description: 'List available simulation runs.',
    inputs: [
      { name: 'limit', type: 'integer', required: false, default: '10', description: 'Maximum number of runs to return' },
    ],
    outputs: [
      { name: 'runs', type: 'array', required: true, description: 'List of run summaries' },
      { name: 'total', type: 'integer', required: true, description: 'Total number of runs available' },
    ],
  },
  {
    name: 'aerie_status',
    description: 'Check the health and configuration of Aerie services.',
    inputs: [],
    outputs: [
      { name: 'healthy', type: 'boolean', required: true, description: 'Whether Aerie is accessible' },
      { name: 'graphql_url', type: 'string', required: true, description: 'GraphQL endpoint URL' },
      { name: 'mission_models', type: 'array', required: true, description: 'Available mission models' },
    ],
  },
  {
    name: 'create_plan',
    description: 'Create a new plan in Aerie from a scenario definition.',
    inputs: [
      { name: 'scenario_path', type: 'string', required: true, description: 'Path to scenario YAML file' },
      { name: 'plan_name', type: 'string', required: true, description: 'Name for the new plan' },
      { name: 'model_id', type: 'integer', required: true, description: 'Aerie mission model ID' },
    ],
    outputs: [
      { name: 'success', type: 'boolean', required: true, description: 'Whether plan was created' },
      { name: 'plan_id', type: 'integer', required: true, description: 'Aerie plan ID' },
      { name: 'activities_created', type: 'integer', required: true, description: 'Number of activities added' },
    ],
  },
  {
    name: 'export_plan',
    description: 'Export a plan from Aerie to simulator format.',
    inputs: [
      { name: 'plan_id', type: 'integer', required: true, description: 'Aerie plan ID to export' },
      { name: 'output_dir', type: 'string', required: false, description: 'Output directory path' },
    ],
    outputs: [
      { name: 'plan_file', type: 'string', required: true, description: 'Path to exported plan file' },
      { name: 'activity_count', type: 'integer', required: true, description: 'Number of activities exported' },
    ],
  },
  {
    name: 'generate_viz',
    description: 'Generate visualization files (CZML, events) for a simulation run.',
    inputs: [
      { name: 'run_id', type: 'string', required: true, description: 'Run identifier' },
    ],
    outputs: [
      { name: 'artifacts', type: 'object', required: true, description: 'Generated file paths' },
    ],
  },
  {
    name: 'compare_runs',
    description: 'Compare two simulation runs and compute difference metrics.',
    inputs: [
      { name: 'run_a_id', type: 'string', required: true, description: 'First run identifier' },
      { name: 'run_b_id', type: 'string', required: true, description: 'Second run identifier' },
    ],
    outputs: [
      { name: 'position_rmse_km', type: 'number', required: true, description: 'Position RMSE in kilometers' },
      { name: 'altitude_rmse_km', type: 'number', required: true, description: 'Altitude RMSE in kilometers' },
      { name: 'comparable', type: 'boolean', required: true, description: 'Whether runs are comparable' },
    ],
  },
];

// ============================================
// CLI COMMANDS
// ============================================

export const cliCommands: DocCommand[] = [
  {
    name: 'simrun',
    description: 'Spacecraft mission simulator CLI. Run simulations, manage Aerie integration, and generate visualizations.',
    usage: 'simrun [OPTIONS] COMMAND [ARGS]...',
    flags: [
      { name: 'verbose', short: 'v', type: 'flag', required: false, description: 'Enable verbose output' },
    ],
    subcommands: [
      {
        name: 'simrun run',
        description: 'Run a simulation with the specified plan file.',
        usage: 'simrun run --plan <PATH> [OPTIONS]',
        flags: [
          { name: 'plan', short: 'p', type: 'PATH', required: true, description: 'Path to plan JSON file' },
          { name: 'config', short: 'c', type: 'PATH', required: false, description: 'Path to config YAML file' },
          { name: 'tle', short: 't', type: 'PATH', required: false, description: 'Path to TLE file' },
          { name: 'altitude', short: 'a', type: 'FLOAT', required: false, default: '500.0', description: 'Initial altitude in km' },
          { name: 'inclination', short: 'i', type: 'FLOAT', required: false, default: '53.0', description: 'Orbit inclination in degrees' },
          { name: 'fidelity', short: 'f', type: 'CHOICE', required: false, default: 'LOW', description: 'Simulation fidelity (LOW, MEDIUM, HIGH)' },
          { name: 'output', short: 'o', type: 'PATH', required: false, default: 'runs', description: 'Output directory' },
          { name: 'format', type: 'CHOICE', required: false, default: 'auto', description: 'Plan format (auto, aerie, normalized)' },
        ],
        examples: [
          'simrun run --plan examples/operational_day_plan.json',
          'simrun run --plan examples/aerie_export.json --fidelity MEDIUM',
          'simrun run -p my_plan.json -a 400 -i 97.4 -f HIGH -o runs/leo_test',
        ],
      },
      {
        name: 'simrun aerie',
        description: 'Aerie mission planning integration commands.',
        usage: 'simrun aerie COMMAND [ARGS]...',
        subcommands: [
          {
            name: 'simrun aerie status',
            description: 'Check Aerie service health and list available mission models.',
            usage: 'simrun aerie status',
            examples: ['simrun aerie status'],
          },
          {
            name: 'simrun aerie plan',
            description: 'Create a new plan in Aerie from a scenario file.',
            usage: 'simrun aerie plan --scenario <PATH> [OPTIONS]',
            flags: [
              { name: 'scenario', short: 's', type: 'PATH', required: true, description: 'Path to scenario YAML file' },
              { name: 'name', short: 'n', type: 'TEXT', required: false, description: 'Override plan name' },
              { name: 'model-id', short: 'm', type: 'INT', required: false, default: '1', description: 'Aerie mission model ID' },
              { name: 'replace', short: 'r', type: 'flag', required: false, description: 'Replace existing plan with same name' },
            ],
            examples: [
              'simrun aerie plan --scenario validation/scenarios/ssr_baseline.yaml',
              'simrun aerie plan -s my_scenario.yaml -n "Test Plan" -m 2 -r',
            ],
          },
          {
            name: 'simrun aerie schedule',
            description: 'Run the Aerie scheduler on a plan.',
            usage: 'simrun aerie schedule [OPTIONS]',
            flags: [
              { name: 'plan', short: 'p', type: 'TEXT', required: false, description: 'Plan name' },
              { name: 'plan-id', short: 'i', type: 'INT', required: false, description: 'Plan ID (alternative to name)' },
              { name: 'timeout', short: 't', type: 'INT', required: false, default: '300', description: 'Timeout in seconds' },
              { name: 'no-wait', type: 'flag', required: false, description: 'Do not wait for completion' },
            ],
            examples: [
              'simrun aerie schedule --plan my_plan',
              'simrun aerie schedule -i 123 --no-wait',
            ],
          },
          {
            name: 'simrun aerie export',
            description: 'Export a plan from Aerie to simulator format.',
            usage: 'simrun aerie export [OPTIONS]',
            flags: [
              { name: 'plan', short: 'p', type: 'TEXT', required: false, description: 'Plan name' },
              { name: 'plan-id', short: 'i', type: 'INT', required: false, description: 'Plan ID' },
              { name: 'output', short: 'o', type: 'PATH', required: false, description: 'Output directory' },
              { name: 'include-resources', short: 'r', type: 'flag', required: false, description: 'Include resource profiles' },
              { name: 'dataset-id', short: 'd', type: 'INT', required: false, description: 'Simulation dataset ID' },
            ],
            examples: [
              'simrun aerie export --plan my_plan --output exports/my_plan',
              'simrun aerie export -i 123 -r -d 456',
            ],
          },
        ],
      },
      {
        name: 'simrun viz',
        description: 'Visualization generation and serving commands.',
        usage: 'simrun viz COMMAND [ARGS]...',
        subcommands: [
          {
            name: 'simrun viz generate',
            description: 'Generate visualization files (CZML, events) for a simulation run.',
            usage: 'simrun viz generate --run <PATH> [OPTIONS]',
            flags: [
              { name: 'run', short: 'r', type: 'PATH', required: true, description: 'Path to run directory' },
              { name: 'satellite-name', short: 'n', type: 'TEXT', required: false, default: 'Satellite', description: 'Display name for satellite' },
            ],
            examples: [
              'simrun viz generate --run runs/20250115_120000_LOW',
              'simrun viz generate -r runs/my_run -n "LEO-SAT-1"',
            ],
          },
          {
            name: 'simrun viz serve',
            description: 'Serve visualization files via HTTP server.',
            usage: 'simrun viz serve --run <PATH> [OPTIONS]',
            flags: [
              { name: 'run', short: 'r', type: 'PATH', required: true, description: 'Path to run directory' },
              { name: 'port', short: 'p', type: 'INT', required: false, default: '8000', description: 'Server port' },
              { name: 'open', type: 'flag', required: false, description: 'Open browser automatically' },
            ],
            examples: [
              'simrun viz serve --run runs/my_run --open',
              'simrun viz serve -r runs/my_run -p 9000',
            ],
          },
          {
            name: 'simrun viz compare',
            description: 'Generate comparison visualization for two runs.',
            usage: 'simrun viz compare --run-a <PATH> --run-b <PATH> [OPTIONS]',
            flags: [
              { name: 'run-a', short: 'a', type: 'PATH', required: true, description: 'First run directory' },
              { name: 'run-b', short: 'b', type: 'PATH', required: true, description: 'Second run directory' },
              { name: 'output', short: 'o', type: 'PATH', required: false, description: 'Output directory' },
            ],
            examples: [
              'simrun viz compare --run-a runs/baseline --run-b runs/modified',
            ],
          },
        ],
      },
      {
        name: 'simrun delta-v',
        description: 'Calculate delta-V required for orbit change.',
        usage: 'simrun delta-v [OPTIONS]',
        flags: [
          { name: 'altitude-start', short: 'as', type: 'FLOAT', required: false, default: '500.0', description: 'Starting altitude in km' },
          { name: 'altitude-end', short: 'ae', type: 'FLOAT', required: false, default: '400.0', description: 'Target altitude in km' },
        ],
        examples: [
          'simrun delta-v --altitude-start 500 --altitude-end 350',
          'simrun delta-v -as 600 -ae 400',
        ],
      },
      {
        name: 'simrun generate-tle',
        description: 'Generate a synthetic TLE for testing.',
        usage: 'simrun generate-tle --altitude <KM> --inclination <DEG> [OPTIONS]',
        flags: [
          { name: 'altitude', short: 'a', type: 'FLOAT', required: true, description: 'Orbital altitude in km' },
          { name: 'inclination', short: 'i', type: 'FLOAT', required: true, description: 'Inclination in degrees' },
          { name: 'epoch', short: 'e', type: 'TEXT', required: false, description: 'Epoch (ISO format)' },
          { name: 'output', short: 'o', type: 'PATH', required: false, description: 'Output file path' },
        ],
        examples: [
          'simrun generate-tle --altitude 500 --inclination 53',
          'simrun generate-tle -a 400 -i 97.4 -o my_tle.txt',
        ],
      },
      {
        name: 'simrun sensor-geometry',
        description: 'Calculate EO sensor geometry parameters (GSD, swath width).',
        usage: 'simrun sensor-geometry [OPTIONS]',
        flags: [
          { name: 'altitude', short: 'a', type: 'FLOAT', required: false, default: '500.0', description: 'Altitude in km' },
          { name: 'focal-length', short: 'f', type: 'FLOAT', required: false, default: '1000.0', description: 'Focal length in mm' },
          { name: 'pixel-size', short: 'p', type: 'FLOAT', required: false, default: '10.0', description: 'Pixel size in micrometers' },
        ],
        examples: [
          'simrun sensor-geometry --altitude 400 --focal-length 800',
          'simrun sensor-geometry -a 500 -f 1200 -p 8.5',
        ],
      },
    ],
  },
];

// ============================================
// SEARCH INDEX
// ============================================

export const buildSearchIndex = (): DocSearchResult[] => {
  const results: DocSearchResult[] = [];

  // Add sections
  const addSection = (section: DocSection, parentPath: string = '') => {
    const path = parentPath ? `${parentPath} > ${section.title}` : section.title;
    results.push({
      sectionId: section.id,
      title: section.title,
      content: path,
      anchor: section.id,
      type: 'section',
    });
    section.children?.forEach(child => addSection(child, path));
  };
  docSections.forEach(s => addSection(s));

  // Add REST endpoints
  restEndpoints.forEach(ep => {
    results.push({
      sectionId: 'interfaces-rest',
      title: `${ep.method} ${ep.path}`,
      content: ep.description,
      anchor: ep.path.replace(/[^a-zA-Z0-9]/g, '-'),
      type: 'endpoint',
    });
  });

  // Add MCP tools
  mcpTools.forEach(tool => {
    results.push({
      sectionId: 'interfaces-mcp',
      title: tool.name,
      content: tool.description,
      anchor: tool.name,
      type: 'tool',
    });
  });

  // Add CLI commands
  const addCommand = (cmd: DocCommand) => {
    results.push({
      sectionId: 'interfaces-cli',
      title: cmd.name,
      content: cmd.description,
      anchor: cmd.name.replace(/\s+/g, '-'),
      type: 'command',
    });
    cmd.subcommands?.forEach(addCommand);
  };
  cliCommands.forEach(addCommand);

  return results;
};
