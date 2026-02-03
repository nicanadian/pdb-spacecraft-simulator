"""Configurable tolerance settings for GMAT validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class GMATToleranceConfig:
    """
    Configurable tolerances with scenario-specific overrides.

    Tolerances define the acceptable error bounds between simulator output
    and GMAT reference data for validation tests.
    """

    # Global defaults
    position_rms_km: float = 5.0
    velocity_rms_m_s: float = 5.0
    position_max_km: float = 20.0
    velocity_max_m_s: float = 20.0
    altitude_rms_km: float = 2.0
    sma_error_km: float = 200.0  # Relaxed for development

    # Scenario-specific overrides
    # Format: {scenario_id: {field: value}}
    scenario_overrides: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def get_tolerance(
        self,
        field_name: str,
        scenario_id: Optional[str] = None,
    ) -> float:
        """
        Get tolerance value with optional scenario override.

        Args:
            field_name: Tolerance field name (e.g., "position_rms_km")
            scenario_id: Optional scenario ID for scenario-specific tolerance

        Returns:
            Tolerance value

        Raises:
            AttributeError: If field_name is not a valid tolerance field
        """
        # Check scenario override first
        if scenario_id and scenario_id in self.scenario_overrides:
            if field_name in self.scenario_overrides[scenario_id]:
                return self.scenario_overrides[scenario_id][field_name]

        # Fall back to global default
        if hasattr(self, field_name):
            return getattr(self, field_name)

        raise AttributeError(f"Unknown tolerance field: {field_name}")

    def get_tolerances_for_scenario(
        self,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Get all tolerances for a scenario.

        Args:
            scenario_id: Scenario ID (uses global defaults if None)

        Returns:
            Dict of tolerance field names to values
        """
        tolerances = {
            "position_rms_km": self.position_rms_km,
            "velocity_rms_m_s": self.velocity_rms_m_s,
            "position_max_km": self.position_max_km,
            "velocity_max_m_s": self.velocity_max_m_s,
            "altitude_rms_km": self.altitude_rms_km,
            "sma_error_km": self.sma_error_km,
        }

        # Apply scenario overrides
        if scenario_id and scenario_id in self.scenario_overrides:
            tolerances.update(self.scenario_overrides[scenario_id])

        return tolerances

    @classmethod
    def from_dict(cls, data: Dict) -> "GMATToleranceConfig":
        """
        Create from dictionary.

        Args:
            data: Dict with tolerance configuration

        Returns:
            GMATToleranceConfig instance
        """
        global_tolerances = data.get("global", {})
        scenario_overrides = data.get("scenarios", {})

        return cls(
            position_rms_km=global_tolerances.get("position_rms_km", 5.0),
            velocity_rms_m_s=global_tolerances.get("velocity_rms_m_s", 5.0),
            position_max_km=global_tolerances.get("position_max_km", 20.0),
            velocity_max_m_s=global_tolerances.get("velocity_max_m_s", 20.0),
            altitude_rms_km=global_tolerances.get("altitude_rms_km", 2.0),
            sma_error_km=global_tolerances.get("sma_error_km", 200.0),
            scenario_overrides=scenario_overrides,
        )

    @classmethod
    def from_yaml(cls, path: Path) -> "GMATToleranceConfig":
        """
        Load tolerance configuration from YAML file.

        Expected YAML structure:
        ```yaml
        tolerances:
          global:
            position_rms_km: 5.0
            velocity_rms_m_s: 5.0
          scenarios:
            pure_propagation:
              position_rms_km: 1.0
        ```

        Args:
            path: Path to YAML config file

        Returns:
            GMATToleranceConfig instance
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            config = yaml.safe_load(f)

        tolerances_section = config.get("tolerances", {})
        return cls.from_dict(tolerances_section)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "global": {
                "position_rms_km": self.position_rms_km,
                "velocity_rms_m_s": self.velocity_rms_m_s,
                "position_max_km": self.position_max_km,
                "velocity_max_m_s": self.velocity_max_m_s,
                "altitude_rms_km": self.altitude_rms_km,
                "sma_error_km": self.sma_error_km,
            },
            "scenarios": self.scenario_overrides,
        }


def load_default_tolerance_config() -> GMATToleranceConfig:
    """
    Load default tolerance configuration from validation config.

    Searches for config file at:
        validation/config/validation_config.yaml

    Returns:
        GMATToleranceConfig with defaults or from config file
    """
    config_path = Path(__file__).parent.parent / "config" / "validation_config.yaml"

    if config_path.exists():
        return GMATToleranceConfig.from_yaml(config_path)

    # Return defaults if no config file
    return GMATToleranceConfig()
