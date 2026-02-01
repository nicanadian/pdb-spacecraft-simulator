"""Tests for MCP server."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch


# Import local MCP server module
from sim_mcp.server import SimulatorMCPServer, MCPConfig, MCP_AVAILABLE


# Skip all tests that require the MCP SDK
pytestmark = pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP SDK not installed")


class TestMCPConfig:
    """Test MCPConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MCPConfig()

        assert config.runs_dir == "runs"
        assert config.aerie_host == "localhost"
        assert config.aerie_port == 9000
        assert config.enable_aerie is True
        assert config.enable_viz is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MCPConfig(
            runs_dir="/custom/runs",
            aerie_host="aerie.example.com",
            aerie_port=8080,
            enable_aerie=False,
            enable_viz=False,
        )

        assert config.runs_dir == "/custom/runs"
        assert config.aerie_host == "aerie.example.com"
        assert config.enable_aerie is False


class TestSimulatorMCPServer:
    """Test SimulatorMCPServer class."""

    def test_server_initialization(self):
        """Test server initializes correctly."""
        server = SimulatorMCPServer()

        assert server.config is not None
        assert server.server is not None

    def test_server_with_custom_config(self):
        """Test server with custom config."""
        config = MCPConfig(runs_dir="/tmp/runs")
        server = SimulatorMCPServer(config)

        assert server.config.runs_dir == "/tmp/runs"


class TestToolListing:
    """Test tool listing functionality."""

    def test_list_tools_includes_simulation_tools(self):
        """Test that simulation tools are listed."""
        server = SimulatorMCPServer()

        # Get the list_tools handler
        tools = asyncio.run(server.list_tools())

        tool_names = [t.name for t in tools]

        assert "run_simulation" in tool_names
        assert "get_run_status" in tool_names
        assert "get_run_results" in tool_names
        assert "list_runs" in tool_names

    def test_list_tools_includes_aerie_tools(self):
        """Test that Aerie tools are listed when enabled."""
        config = MCPConfig(enable_aerie=True)
        server = SimulatorMCPServer(config)

        tools = asyncio.run(server.list_tools())
        tool_names = [t.name for t in tools]

        assert "aerie_status" in tool_names
        assert "create_plan" in tool_names
        assert "run_scheduler" in tool_names
        assert "export_plan" in tool_names

    def test_list_tools_excludes_aerie_when_disabled(self):
        """Test that Aerie tools are excluded when disabled."""
        config = MCPConfig(enable_aerie=False)
        server = SimulatorMCPServer(config)

        tools = asyncio.run(server.list_tools())
        tool_names = [t.name for t in tools]

        assert "aerie_status" not in tool_names
        assert "create_plan" not in tool_names

    def test_list_tools_includes_viz_tools(self):
        """Test that viz tools are listed when enabled."""
        config = MCPConfig(enable_viz=True)
        server = SimulatorMCPServer(config)

        tools = asyncio.run(server.list_tools())
        tool_names = [t.name for t in tools]

        assert "generate_viz" in tool_names
        assert "compare_runs" in tool_names

    def test_list_tools_excludes_viz_when_disabled(self):
        """Test that viz tools are excluded when disabled."""
        config = MCPConfig(enable_viz=False)
        server = SimulatorMCPServer(config)

        tools = asyncio.run(server.list_tools())
        tool_names = [t.name for t in tools]

        assert "generate_viz" not in tool_names
        assert "compare_runs" not in tool_names


class TestToolDispatch:
    """Test tool call dispatching."""

    def test_dispatch_unknown_tool(self):
        """Test dispatching unknown tool raises error."""
        server = SimulatorMCPServer()

        with pytest.raises(ValueError, match="Unknown tool"):
            asyncio.run(server._dispatch_tool("unknown_tool", {}))

    def test_dispatch_list_runs(self, tmp_path):
        """Test dispatching list_runs tool."""
        config = MCPConfig(runs_dir=str(tmp_path))
        server = SimulatorMCPServer(config)

        result = asyncio.run(server._dispatch_tool("list_runs", {"limit": 5}))

        assert "runs" in result
        assert "total" in result

    def test_dispatch_get_run_status_not_found(self, tmp_path):
        """Test dispatching get_run_status for non-existent run."""
        config = MCPConfig(runs_dir=str(tmp_path))
        server = SimulatorMCPServer(config)

        result = asyncio.run(server._dispatch_tool("get_run_status", {"run_id": "nonexistent"}))

        assert result["found"] is False


class TestToolInputSchemas:
    """Test tool input schemas."""

    def test_run_simulation_schema(self):
        """Test run_simulation tool has correct schema."""
        server = SimulatorMCPServer()

        tools = asyncio.run(server.list_tools())
        run_sim = next(t for t in tools if t.name == "run_simulation")

        schema = run_sim.inputSchema

        assert schema["type"] == "object"
        assert "plan_path" in schema["properties"]
        assert "fidelity" in schema["properties"]
        assert "plan_path" in schema["required"]

    def test_compare_runs_schema(self):
        """Test compare_runs tool has correct schema."""
        config = MCPConfig(enable_viz=True)
        server = SimulatorMCPServer(config)

        tools = asyncio.run(server.list_tools())
        compare = next(t for t in tools if t.name == "compare_runs")

        schema = compare.inputSchema

        assert "run_a_id" in schema["properties"]
        assert "run_b_id" in schema["properties"]
        assert "run_a_id" in schema["required"]
        assert "run_b_id" in schema["required"]


class TestGracefulShutdown:
    """Test graceful shutdown handling."""

    def test_server_can_be_created_and_destroyed(self):
        """Test that server can be created and garbage collected."""
        server = SimulatorMCPServer()
        del server
        # If we get here without error, the test passes
