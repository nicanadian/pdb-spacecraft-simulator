"""MCP (Model Context Protocol) server for spacecraft simulator.

This package provides an MCP server that exposes simulation, Aerie integration,
and visualization tools for use by AI assistants.
"""

from sim_mcp.server import SimulatorMCPServer, MCPConfig, MCP_AVAILABLE

__all__ = ["SimulatorMCPServer"]
