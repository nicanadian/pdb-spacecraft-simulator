"""MCP server for spacecraft simulator.

Exposes simulation, Aerie integration, and visualization tools via the
Model Context Protocol (MCP) for use by AI assistants.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None

from sim_mcp.tools.simulation import (
    run_simulation,
    get_run_status,
    get_run_results,
    list_runs,
)
from sim_mcp.tools.aerie import (
    aerie_status,
    create_plan,
    run_scheduler,
    export_plan,
)
from sim_mcp.tools.viz import (
    generate_viz,
    compare_runs,
)


logger = logging.getLogger(__name__)


@dataclass
class MCPConfig:
    """Configuration for MCP server."""

    runs_dir: str = "runs"
    aerie_host: str = "localhost"
    aerie_port: int = 9000
    enable_aerie: bool = True
    enable_viz: bool = True


class SimulatorMCPServer:
    """
    MCP server exposing spacecraft simulator tools.

    Tools available:
    - run_simulation: Run a simulation with specified plan and config
    - get_run_status: Check status of a simulation run
    - get_run_results: Retrieve results from completed run
    - list_runs: List available simulation runs
    - aerie_status: Check Aerie service health
    - create_plan: Create a new plan in Aerie
    - run_scheduler: Trigger Aerie scheduler
    - export_plan: Export plan from Aerie
    - generate_viz: Generate visualization artifacts
    - compare_runs: Compare two simulation runs
    """

    def __init__(self, config: Optional[MCPConfig] = None):
        if not MCP_AVAILABLE:
            raise ImportError(
                "MCP package not installed. Install with: pip install mcp"
            )

        self.config = config or MCPConfig()
        self.server = Server("pdb-spacecraft-simulator")
        self._list_tools_func = None
        self._setup_tools()

    async def list_tools(self) -> List[Tool]:
        """List available tools (for testing)."""
        if self._list_tools_func:
            return await self._list_tools_func()
        return []

    def _setup_tools(self) -> None:
        """Register all tools with the server."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            tools = [
                # Simulation tools
                Tool(
                    name="run_simulation",
                    description="Run a spacecraft simulation with the specified plan and configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plan_path": {
                                "type": "string",
                                "description": "Path to the plan file (JSON or YAML)",
                            },
                            "fidelity": {
                                "type": "string",
                                "enum": ["LOW", "MEDIUM", "HIGH"],
                                "description": "Simulation fidelity level",
                                "default": "LOW",
                            },
                            "config_overrides": {
                                "type": "object",
                                "description": "Optional configuration overrides",
                            },
                        },
                        "required": ["plan_path"],
                    },
                ),
                Tool(
                    name="get_run_status",
                    description="Get the status of a simulation run",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "run_id": {
                                "type": "string",
                                "description": "The run ID to check",
                            },
                        },
                        "required": ["run_id"],
                    },
                ),
                Tool(
                    name="get_run_results",
                    description="Get the results of a completed simulation run",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "run_id": {
                                "type": "string",
                                "description": "The run ID to retrieve",
                            },
                        },
                        "required": ["run_id"],
                    },
                ),
                Tool(
                    name="list_runs",
                    description="List available simulation runs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of runs to return",
                                "default": 10,
                            },
                        },
                    },
                ),
            ]

            # Add Aerie tools if enabled
            if self.config.enable_aerie:
                tools.extend([
                    Tool(
                        name="aerie_status",
                        description="Check Aerie service health and availability",
                        inputSchema={"type": "object", "properties": {}},
                    ),
                    Tool(
                        name="create_plan",
                        description="Create a new plan in Aerie from a scenario file",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "scenario_path": {
                                    "type": "string",
                                    "description": "Path to scenario definition file",
                                },
                                "plan_name": {
                                    "type": "string",
                                    "description": "Name for the new plan",
                                },
                                "model_id": {
                                    "type": "integer",
                                    "description": "Mission model ID to use",
                                },
                            },
                            "required": ["scenario_path", "plan_name", "model_id"],
                        },
                    ),
                    Tool(
                        name="run_scheduler",
                        description="Trigger the Aerie scheduler for a plan",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "plan_id": {
                                    "type": "integer",
                                    "description": "Plan ID to schedule",
                                },
                            },
                            "required": ["plan_id"],
                        },
                    ),
                    Tool(
                        name="export_plan",
                        description="Export a plan from Aerie",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "plan_id": {
                                    "type": "integer",
                                    "description": "Plan ID to export",
                                },
                                "output_dir": {
                                    "type": "string",
                                    "description": "Directory for exported files",
                                },
                            },
                            "required": ["plan_id"],
                        },
                    ),
                ])

            # Add viz tools if enabled
            if self.config.enable_viz:
                tools.extend([
                    Tool(
                        name="generate_viz",
                        description="Generate visualization artifacts for a simulation run",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "run_id": {
                                    "type": "string",
                                    "description": "Run ID to generate visualization for",
                                },
                            },
                            "required": ["run_id"],
                        },
                    ),
                    Tool(
                        name="compare_runs",
                        description="Compare two simulation runs and generate diff summary",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "run_a_id": {
                                    "type": "string",
                                    "description": "First run ID",
                                },
                                "run_b_id": {
                                    "type": "string",
                                    "description": "Second run ID",
                                },
                            },
                            "required": ["run_a_id", "run_b_id"],
                        },
                    ),
                ])

            return tools

        # Store reference for testing
        self._list_tools_func = list_tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                result = await self._dispatch_tool(name, arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.exception(f"Tool {name} failed")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "tool": name}),
                )]

    async def _dispatch_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatch tool call to appropriate handler."""
        runs_dir = Path(self.config.runs_dir)

        # Simulation tools
        if name == "run_simulation":
            return await run_simulation(
                plan_path=Path(arguments["plan_path"]),
                fidelity=arguments.get("fidelity", "LOW"),
                config_overrides=arguments.get("config_overrides"),
                runs_dir=runs_dir,
            )
        elif name == "get_run_status":
            return await get_run_status(
                run_id=arguments["run_id"],
                runs_dir=runs_dir,
            )
        elif name == "get_run_results":
            return await get_run_results(
                run_id=arguments["run_id"],
                runs_dir=runs_dir,
            )
        elif name == "list_runs":
            return await list_runs(
                runs_dir=runs_dir,
                limit=arguments.get("limit", 10),
            )

        # Aerie tools
        elif name == "aerie_status":
            return await aerie_status(
                host=self.config.aerie_host,
                port=self.config.aerie_port,
            )
        elif name == "create_plan":
            return await create_plan(
                scenario_path=Path(arguments["scenario_path"]),
                plan_name=arguments["plan_name"],
                model_id=arguments["model_id"],
                host=self.config.aerie_host,
                port=self.config.aerie_port,
            )
        elif name == "run_scheduler":
            return await run_scheduler(
                plan_id=arguments["plan_id"],
                host=self.config.aerie_host,
                port=self.config.aerie_port,
            )
        elif name == "export_plan":
            return await export_plan(
                plan_id=arguments["plan_id"],
                output_dir=Path(arguments.get("output_dir", ".")),
                host=self.config.aerie_host,
                port=self.config.aerie_port,
            )

        # Viz tools
        elif name == "generate_viz":
            return await generate_viz(
                run_id=arguments["run_id"],
                runs_dir=runs_dir,
            )
        elif name == "compare_runs":
            return await compare_runs(
                run_a_id=arguments["run_a_id"],
                run_b_id=arguments["run_b_id"],
                runs_dir=runs_dir,
            )

        else:
            raise ValueError(f"Unknown tool: {name}")

    async def run_stdio(self) -> None:
        """Run server with stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting MCP server for spacecraft simulator")
        await self.run_stdio()


async def main():
    """Main entry point for MCP server."""
    logging.basicConfig(level=logging.INFO)
    server = SimulatorMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
