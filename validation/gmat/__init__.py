"""GMAT integration for validation."""

from .generator import GMATScriptGenerator, ScenarioConfig
from .parser import GMATOutputParser
from .executor import GMATExecutor, GMATExecutionResult, check_gmat_installation
from .baseline import GMATBaseline, GMATBaselineMetadata, GMATEphemerisRecord
from .baseline_manager import GMATBaselineManager, create_baseline_from_ephemeris
from .tolerance_config import GMATToleranceConfig, load_default_tolerance_config
from .regression import GMATRegressionComparator, RegressionResult

__all__ = [
    # Script generation
    "GMATScriptGenerator",
    "ScenarioConfig",
    # Parsing
    "GMATOutputParser",
    # Execution
    "GMATExecutor",
    "GMATExecutionResult",
    "check_gmat_installation",
    # Baselines
    "GMATBaseline",
    "GMATBaselineMetadata",
    "GMATEphemerisRecord",
    "GMATBaselineManager",
    "create_baseline_from_ephemeris",
    # Tolerances
    "GMATToleranceConfig",
    "load_default_tolerance_config",
    # Regression
    "GMATRegressionComparator",
    "RegressionResult",
]
