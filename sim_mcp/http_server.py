"""HTTP server wrapper for MCP tools.

Provides an HTTP interface to the MCP tools for testing and integration.
This complements the stdio-based MCP server for Claude Code integration.

Usage:
    python -m sim_mcp.http_server  # Start on port 8765
    python -m sim_mcp.http_server --port 9000  # Custom port
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

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


class MCPHTTPServer:
    """
    HTTP server exposing MCP tools as REST endpoints.

    Endpoints:
        GET  /health          - Health check
        GET  /tools           - List available tools
        POST /tools/<name>    - Invoke a tool
        POST /tools/simulate  - Run simulation (alias)
    """

    def __init__(self, runs_dir: str = "runs", port: int = 8765):
        if not AIOHTTP_AVAILABLE:
            raise ImportError(
                "aiohttp not installed. Install with: pip install aiohttp"
            )

        self.runs_dir = Path(runs_dir)
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up HTTP routes."""
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/tools", self.list_tools_handler)
        self.app.router.add_post("/tools/{tool_name}", self.invoke_tool_handler)
        # Alias for backwards compatibility
        self.app.router.add_post("/tools/simulate", self.simulate_handler)

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "service": "mcp-http-server",
            "version": "1.0.0",
        })

    async def list_tools_handler(self, request: web.Request) -> web.Response:
        """List available tools."""
        tools = [
            {
                "name": "run_simulation",
                "description": "Run a spacecraft simulation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "plan_path": {"type": "string"},
                        "fidelity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
                    },
                    "required": ["plan_path"],
                },
            },
            {
                "name": "simulate",
                "description": "Run simulation (inline plan)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "plan": {"type": "object"},
                        "initial_state": {"type": "object"},
                        "fidelity": {"type": "string"},
                        "output_dir": {"type": "string"},
                    },
                    "required": ["plan", "initial_state"],
                },
            },
            {
                "name": "get_run_status",
                "description": "Get simulation run status",
                "inputSchema": {
                    "type": "object",
                    "properties": {"run_id": {"type": "string"}},
                    "required": ["run_id"],
                },
            },
            {
                "name": "get_run_results",
                "description": "Get simulation results",
                "inputSchema": {
                    "type": "object",
                    "properties": {"run_id": {"type": "string"}},
                    "required": ["run_id"],
                },
            },
            {
                "name": "list_runs",
                "description": "List simulation runs",
                "inputSchema": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                },
            },
            {
                "name": "aerie_status",
                "description": "Check Aerie service health",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "generate_viz",
                "description": "Generate visualization",
                "inputSchema": {
                    "type": "object",
                    "properties": {"run_id": {"type": "string"}},
                    "required": ["run_id"],
                },
            },
        ]
        return web.json_response({"tools": tools})

    async def simulate_handler(self, request: web.Request) -> web.Response:
        """Handle inline simulation request."""
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "Invalid JSON in request body"},
                status=400,
            )

        try:
            result = await self._run_inline_simulation(data)
            return web.json_response(result)
        except Exception as e:
            logger.exception("Simulation failed")
            return web.json_response(
                {"error": str(e), "detail": "Simulation execution failed"},
                status=500,
            )

    async def _run_inline_simulation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run simulation with inline plan data."""
        from datetime import datetime
        from sim.engine import simulate
        from sim.core.types import Fidelity, PlanInput, Activity, InitialState, SimConfig, SpacecraftConfig

        plan_data = data.get("plan", {})
        initial_data = data.get("initial_state", {})
        fidelity_str = data.get("fidelity", "LOW")
        output_dir = data.get("output_dir", f"runs/mcp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        # Parse plan
        activities = []
        for act_data in plan_data.get("activities", []):
            activities.append(Activity(
                activity_id=act_data.get("activity_id", "act_001"),
                activity_type=act_data.get("activity_type", "idle"),
                start_time=datetime.fromisoformat(act_data["start_time"].replace("Z", "+00:00")),
                end_time=datetime.fromisoformat(act_data["end_time"].replace("Z", "+00:00")),
                parameters=act_data.get("parameters", {}),
            ))

        # Add a fallback idle activity if plan has no activities
        # (required for PlanInput.start_time property to work)
        if not activities:
            from datetime import timedelta
            start_str = plan_data.get("start_time", initial_data.get("epoch", datetime.utcnow().isoformat()))
            end_str = plan_data.get("end_time")
            start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if end_str:
                end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            else:
                end_time = start_time + timedelta(hours=2)
            activities.append(Activity(
                activity_id="idle_001",
                activity_type="idle",
                start_time=start_time,
                end_time=end_time,
                parameters={},
            ))

        plan = PlanInput(
            spacecraft_id=plan_data.get("spacecraft_id", "MCP_SC"),
            plan_id=plan_data.get("plan_id", "mcp_plan"),
            activities=activities,
        )

        # Parse initial state
        epoch_str = initial_data.get("epoch", plan_data.get("start_time", datetime.utcnow().isoformat()))
        epoch = datetime.fromisoformat(epoch_str.replace("Z", "+00:00"))

        initial_state = InitialState(
            epoch=epoch,
            position_eci=initial_data.get("position_eci", [6778.137, 0.0, 0.0]),
            velocity_eci=initial_data.get("velocity_eci", [0.0, 7.6686, 0.0]),
            mass_kg=initial_data.get("mass_kg", 500.0),
        )

        fidelity = Fidelity[fidelity_str.upper()]

        # Create spacecraft config
        spacecraft_id = plan_data.get("spacecraft_id", "MCP_SC")
        spacecraft_config = SpacecraftConfig(
            spacecraft_id=spacecraft_id,
            dry_mass_kg=initial_data.get("mass_kg", 500.0) - initial_data.get("propellant_kg", 50.0),
            initial_propellant_kg=initial_data.get("propellant_kg", 50.0),
        )

        config = SimConfig(
            fidelity=fidelity,
            output_dir=output_dir,
            time_step_s=60.0,
            spacecraft=spacecraft_config,
        )

        # Run simulation
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=fidelity,
            config=config,
        )

        # Calculate duration from initial to final state
        duration_s = 0.0
        if result.final_state:
            duration_s = (result.final_state.epoch - initial_state.epoch).total_seconds()

        return {
            "success": True,
            "plan_id": plan.plan_id,
            "output_dir": output_dir,
            "summary": {
                "duration_s": duration_s,
                "event_count": len(result.events) if result.events else 0,
            },
            "final_state": {
                "epoch": result.final_state.epoch.isoformat() if result.final_state else None,
                "position_eci": list(result.final_state.position_eci) if result.final_state else None,
                "velocity_eci": list(result.final_state.velocity_eci) if result.final_state else None,
                "mass_kg": result.final_state.mass_kg if result.final_state else None,
            },
        }

    async def invoke_tool_handler(self, request: web.Request) -> web.Response:
        """Invoke a specific tool."""
        tool_name = request.match_info["tool_name"]

        try:
            data = await request.json()
        except json.JSONDecodeError:
            data = {}

        try:
            result = await self._dispatch_tool(tool_name, data)
            return web.json_response(result)
        except ValueError as e:
            return web.json_response(
                {"error": str(e)},
                status=404,
            )
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed")
            return web.json_response(
                {"error": str(e), "tool": tool_name},
                status=500,
            )

    async def _dispatch_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatch tool call to handler."""
        if name == "simulate":
            return await self._run_inline_simulation(arguments)
        elif name == "run_simulation":
            return await run_simulation(
                plan_path=Path(arguments["plan_path"]),
                fidelity=arguments.get("fidelity", "LOW"),
                config_overrides=arguments.get("config_overrides"),
                runs_dir=self.runs_dir,
            )
        elif name == "get_run_status":
            return await get_run_status(
                run_id=arguments["run_id"],
                runs_dir=self.runs_dir,
            )
        elif name == "get_run_results":
            return await get_run_results(
                run_id=arguments["run_id"],
                runs_dir=self.runs_dir,
            )
        elif name == "list_runs":
            return await list_runs(
                runs_dir=self.runs_dir,
                limit=arguments.get("limit", 10),
            )
        elif name == "aerie_status":
            return await aerie_status()
        elif name == "generate_viz":
            return await generate_viz(
                run_id=arguments["run_id"],
                runs_dir=self.runs_dir,
            )
        elif name == "compare_runs":
            return await compare_runs(
                run_a_id=arguments["run_a_id"],
                run_b_id=arguments["run_b_id"],
                runs_dir=self.runs_dir,
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

    def run(self) -> None:
        """Run the HTTP server."""
        logger.info(f"Starting MCP HTTP server on port {self.port}")
        web.run_app(self.app, port=self.port, print=lambda _: None)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP HTTP Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--runs-dir", default="runs", help="Directory for simulation runs")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    server = MCPHTTPServer(runs_dir=args.runs_dir, port=args.port)
    server.run()


if __name__ == "__main__":
    main()
