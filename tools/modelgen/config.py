"""Load and process mappings.yml configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(mappings_path: Path) -> dict[str, Any]:
    """Load mappings.yml and resolve glob patterns.

    Args:
        mappings_path: Path to mappings.yml.

    Returns:
        Parsed configuration dict.
    """
    if not mappings_path.exists():
        return _default_config()

    with open(mappings_path) as f:
        data = yaml.safe_load(f)

    return data or _default_config()


def _default_config() -> dict[str, Any]:
    """Return default configuration for this codebase."""
    return {
        "scan_paths": ["sim", "cli", "sim_mcp"],
        "exclude_paths": ["__pycache__", ".pyc", "node_modules", ".git"],
        "project_prefixes": ["sim", "cli", "sim_mcp", "tools"],
        "groups": {
            "engine": {
                "name": "Engine",
                "color": "#ef4444",
                "description": "Core simulation engine",
                "module_patterns": ["sim.engine", "sim.cache"],
            },
            "core_types": {
                "name": "Core Types",
                "color": "#a855f7",
                "description": "Core data structures and configuration",
                "module_patterns": ["sim.core"],
            },
            "models": {
                "name": "Physical Models",
                "color": "#06b6d4",
                "description": "Physical simulation models",
                "module_patterns": ["sim.models"],
            },
            "activities": {
                "name": "Activity Handlers",
                "color": "#22c55e",
                "description": "Activity handler implementations",
                "module_patterns": ["sim.activities"],
            },
            "io": {
                "name": "I/O",
                "color": "#f59e0b",
                "description": "Input/output and external integrations",
                "module_patterns": ["sim.io"],
            },
            "viz": {
                "name": "Visualization",
                "color": "#ec4899",
                "description": "Visualization and output formatting",
                "module_patterns": ["sim.viz"],
            },
            "cli": {
                "name": "CLI",
                "color": "#6366f1",
                "description": "Command-line interface",
                "module_patterns": ["cli"],
            },
            "mcp": {
                "name": "MCP",
                "color": "#8b5cf6",
                "description": "MCP server integration",
                "module_patterns": ["sim_mcp"],
            },
            "infrastructure": {
                "name": "Infrastructure",
                "color": "#64748b",
                "description": "Infrastructure and utilities",
                "module_patterns": ["tools", "scripts"],
            },
        },
    }
