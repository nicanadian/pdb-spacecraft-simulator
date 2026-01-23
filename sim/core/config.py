"""Configuration loading and management."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from sim.core.types import SimConfig, SpacecraftConfig, Fidelity


logger = logging.getLogger(__name__)


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Configuration dictionary
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        return yaml.safe_load(f)


def load_json_config(path: str | Path) -> dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        path: Path to JSON file

    Returns:
        Configuration dictionary
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        return json.load(f)


def load_config(path: str | Path) -> dict[str, Any]:
    """
    Load configuration from file (auto-detect format).

    Args:
        path: Path to config file

    Returns:
        Configuration dictionary
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return load_yaml_config(path)
    elif suffix == ".json":
        return load_json_config(path)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")


def create_sim_config(
    spacecraft_config: dict[str, Any] | SpacecraftConfig,
    fidelity: str | Fidelity = Fidelity.LOW,
    time_step_s: float = 60.0,
    output_dir: str = "runs",
    enable_cache: bool = True,
    random_seed: Optional[int] = 42,
) -> SimConfig:
    """
    Create a SimConfig from components.

    Args:
        spacecraft_config: Spacecraft configuration (dict or SpacecraftConfig)
        fidelity: Simulation fidelity level
        time_step_s: Time step in seconds
        output_dir: Output directory for run artifacts
        enable_cache: Whether to enable disk caching
        random_seed: Random seed for reproducibility

    Returns:
        SimConfig instance
    """
    if isinstance(spacecraft_config, dict):
        spacecraft_config = SpacecraftConfig(**spacecraft_config)

    if isinstance(fidelity, str):
        fidelity = Fidelity(fidelity.upper())

    return SimConfig(
        fidelity=fidelity,
        time_step_s=time_step_s,
        spacecraft=spacecraft_config,
        output_dir=output_dir,
        enable_cache=enable_cache,
        random_seed=random_seed,
    )


def generate_run_id(prefix: str = "") -> str:
    """
    Generate a unique run ID.

    Args:
        prefix: Optional prefix for the run ID

    Returns:
        Run ID string
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    random_suffix = hashlib.sha256(os.urandom(8)).hexdigest()[:6]

    if prefix:
        return f"{prefix}_{timestamp}_{random_suffix}"
    return f"{timestamp}_{random_suffix}"


def setup_run_directory(output_dir: str, run_id: str) -> Path:
    """
    Create and return the run output directory.

    Args:
        output_dir: Base output directory
        run_id: Run identifier

    Returns:
        Path to run directory
    """
    run_path = Path(output_dir) / run_id
    run_path.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (run_path / "viz").mkdir(exist_ok=True)

    logger.info(f"Created run directory: {run_path}")
    return run_path


def setup_logging(level: int = logging.INFO, log_file: Optional[Path] = None):
    """
    Configure logging for simulation.

    Args:
        level: Logging level
        log_file: Optional log file path
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
