"""MCP tools for spacecraft simulator.

This package contains tool implementations for:
- Simulation execution and results
- Aerie integration
- Visualization generation
"""

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

__all__ = [
    "run_simulation",
    "get_run_status",
    "get_run_results",
    "list_runs",
    "aerie_status",
    "create_plan",
    "run_scheduler",
    "export_plan",
    "generate_viz",
    "compare_runs",
]
