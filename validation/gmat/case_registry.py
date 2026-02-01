"""GMAT regression test case registry and schemas.

Defines:
- CaseDefinition: Test case metadata and configuration
- TruthCheckpoint: Numeric checkpoint for regression validation
- CaseTruth: Complete truth file for a case
- CaseResult: Execution result with artifacts
- CASE_REGISTRY: Registry of all R1-R12 and N1-N6 cases
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class CaseStatus(str, Enum):
    """Case implementation status."""

    READY = "READY"  # Adapted from existing GMAT sample
    READY_WITH_MODS = "READY_WITH_MODS"  # Sample with modifications
    NEW_REFERENCE = "NEW_REFERENCE"  # New ops-grade scenario


class CaseTier(str, Enum):
    """Test tier for CI/nightly organization."""

    A = "A"  # CI fast checks
    B = "B"  # Nightly ops checks


class PropulsionType(str, Enum):
    """Propulsion modeling type."""

    NONE = "none"
    CHEMICAL_FB = "chemical_fb"  # Chemical finite burn
    EP = "ep"  # Electric propulsion
    THF = "thf"  # Thrust history file


class OrbitRegime(str, Enum):
    """Orbital regime."""

    LEO = "LEO"
    VLEO = "VLEO"
    SSO = "SSO"
    GEO = "GEO"


@dataclass
class CaseDefinition:
    """Definition of a GMAT regression test case."""

    case_id: str  # R01, R02, ..., N01, N02
    name: str  # Human-readable name
    category: str  # finite_burn, targeting, ep_modeling, etc.
    orbit_regime: OrbitRegime
    propulsion: PropulsionType
    status: CaseStatus
    tier: CaseTier
    complexity: int  # 1-5
    reg_suitability: int  # 1-5 (regression suitability score)
    force_models: List[str]  # gravity, drag, srp, third_bodies
    has_targeting: bool
    duration_hours: float
    expected_runtime_s: float  # Budget for CI
    source_script: Optional[str] = None  # Path to GMAT sample (for READY cases)
    description: str = ""
    template_name: Optional[str] = None  # Template file to use

    @classmethod
    def from_dict(cls, data: Dict) -> CaseDefinition:
        """Create from dictionary."""
        return cls(
            case_id=data["case_id"],
            name=data["name"],
            category=data["category"],
            orbit_regime=OrbitRegime(data["orbit_regime"]),
            propulsion=PropulsionType(data["propulsion"]),
            status=CaseStatus(data["status"]),
            tier=CaseTier(data["tier"]),
            complexity=data["complexity"],
            reg_suitability=data["reg_suitability"],
            force_models=data["force_models"],
            has_targeting=data["has_targeting"],
            duration_hours=data["duration_hours"],
            expected_runtime_s=data["expected_runtime_s"],
            source_script=data.get("source_script"),
            description=data.get("description", ""),
            template_name=data.get("template_name"),
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d["orbit_regime"] = self.orbit_regime.value
        d["propulsion"] = self.propulsion.value
        d["status"] = self.status.value
        d["tier"] = self.tier.value
        return d


@dataclass
class TruthCheckpoint:
    """Numeric checkpoint for regression validation.

    Captures orbital state at a specific epoch for comparison.
    """

    epoch_utc: str  # ISO8601 format
    sma_km: float  # Semi-major axis
    ecc: float  # Eccentricity
    inc_deg: float  # Inclination
    raan_deg: float  # Right ascension of ascending node
    aop_deg: float  # Argument of perigee
    ta_deg: float  # True anomaly
    mass_kg: float  # Total spacecraft mass
    altitude_km: Optional[float] = None  # Altitude (for convenience)
    x_km: Optional[float] = None  # ECI position components
    y_km: Optional[float] = None
    z_km: Optional[float] = None
    vx_km_s: Optional[float] = None  # ECI velocity components
    vy_km_s: Optional[float] = None
    vz_km_s: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict) -> TruthCheckpoint:
        """Create from dictionary."""
        return cls(
            epoch_utc=data["epoch_utc"],
            sma_km=data["sma_km"],
            ecc=data["ecc"],
            inc_deg=data["inc_deg"],
            raan_deg=data["raan_deg"],
            aop_deg=data["aop_deg"],
            ta_deg=data["ta_deg"],
            mass_kg=data["mass_kg"],
            altitude_km=data.get("altitude_km"),
            x_km=data.get("x_km"),
            y_km=data.get("y_km"),
            z_km=data.get("z_km"),
            vx_km_s=data.get("vx_km_s"),
            vy_km_s=data.get("vy_km_s"),
            vz_km_s=data.get("vz_km_s"),
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class CaseTruth:
    """Complete truth file for a GMAT regression case.

    Contains initial state, final state checkpoints, key events,
    and derived metrics for regression validation.
    """

    case_id: str
    schema_version: str = "1.0"
    gmat_version: Optional[str] = None
    generated_at: Optional[str] = None
    initial: Optional[TruthCheckpoint] = None
    final: Optional[TruthCheckpoint] = None
    checkpoints: List[TruthCheckpoint] = field(default_factory=list)
    events: Dict[str, str] = field(default_factory=dict)  # burn_1_start_utc, etc.
    derived: Dict[str, float] = field(default_factory=dict)  # sma_drift_km_per_day, etc.
    solver_iterations: Optional[int] = None
    propagation_steps: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict) -> CaseTruth:
        """Create from dictionary."""
        initial = None
        if data.get("initial"):
            initial = TruthCheckpoint.from_dict(data["initial"])

        final = None
        if data.get("final"):
            final = TruthCheckpoint.from_dict(data["final"])

        checkpoints = []
        for cp in data.get("checkpoints", []):
            checkpoints.append(TruthCheckpoint.from_dict(cp))

        return cls(
            case_id=data["case_id"],
            schema_version=data.get("schema_version", "1.0"),
            gmat_version=data.get("gmat_version"),
            generated_at=data.get("generated_at"),
            initial=initial,
            final=final,
            checkpoints=checkpoints,
            events=data.get("events", {}),
            derived=data.get("derived", {}),
            solver_iterations=data.get("solver_iterations"),
            propagation_steps=data.get("propagation_steps"),
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = {
            "case_id": self.case_id,
            "schema_version": self.schema_version,
        }
        if self.gmat_version:
            d["gmat_version"] = self.gmat_version
        if self.generated_at:
            d["generated_at"] = self.generated_at
        if self.initial:
            d["initial"] = self.initial.to_dict()
        if self.final:
            d["final"] = self.final.to_dict()
        if self.checkpoints:
            d["checkpoints"] = [cp.to_dict() for cp in self.checkpoints]
        if self.events:
            d["events"] = self.events
        if self.derived:
            d["derived"] = self.derived
        if self.solver_iterations is not None:
            d["solver_iterations"] = self.solver_iterations
        if self.propagation_steps is not None:
            d["propagation_steps"] = self.propagation_steps
        return d

    @classmethod
    def from_json(cls, path: Path) -> CaseTruth:
        """Load from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_json(self, path: Path, indent: int = 2) -> None:
        """Save to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=indent)


@dataclass
class CaseResult:
    """Result of executing a GMAT regression case."""

    case_id: str
    success: bool
    execution_time_s: float
    return_code: int
    stdout: str
    stderr: str
    output_files: List[Path] = field(default_factory=list)
    ephemeris_path: Optional[Path] = None
    keplerian_path: Optional[Path] = None
    mass_path: Optional[Path] = None
    truth_path: Optional[Path] = None
    error_message: Optional[str] = None
    working_dir: Optional[Path] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "case_id": self.case_id,
            "success": self.success,
            "execution_time_s": self.execution_time_s,
            "return_code": self.return_code,
            "output_files": [str(p) for p in self.output_files],
            "ephemeris_path": str(self.ephemeris_path) if self.ephemeris_path else None,
            "keplerian_path": str(self.keplerian_path) if self.keplerian_path else None,
            "mass_path": str(self.mass_path) if self.mass_path else None,
            "truth_path": str(self.truth_path) if self.truth_path else None,
            "error_message": self.error_message,
            "working_dir": str(self.working_dir) if self.working_dir else None,
        }


# =============================================================================
# Case Registry - All R1-R12 (Tier A) and N1-N6 (Tier B) cases
# =============================================================================

TIER_A_CASES = [
    CaseDefinition(
        case_id="R01",
        name="Finite Burn",
        category="finite_burn",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.CHEMICAL_FB,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=2,
        reg_suitability=5,
        force_models=["gravity"],
        has_targeting=False,
        duration_hours=0.5,
        expected_runtime_s=30.0,
        source_script="Ex_FiniteBurn.script",
        template_name="R01_finite_burn.tpl",
        description="Basic finite burn maneuver with chemical thruster",
    ),
    CaseDefinition(
        case_id="R02",
        name="Target Finite Burn",
        category="targeting",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.CHEMICAL_FB,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=3,
        reg_suitability=4,
        force_models=["gravity"],
        has_targeting=True,
        duration_hours=1.0,
        expected_runtime_s=60.0,
        source_script="Ex_TargetFiniteBurn.script",
        template_name="R02_target_finite_burn.tpl",
        description="Targeted finite burn using differential corrector",
    ),
    CaseDefinition(
        case_id="R03",
        name="Tutorial Target Finite Burn",
        category="targeting",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.CHEMICAL_FB,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=3,
        reg_suitability=4,
        force_models=["gravity"],
        has_targeting=True,
        duration_hours=1.0,
        expected_runtime_s=60.0,
        source_script="Tut_Target_Finite_Burn.script",
        template_name="R03_tut_target_finite_burn.tpl",
        description="Tutorial version of targeted finite burn",
    ),
    CaseDefinition(
        case_id="R04",
        name="Electric Propulsion Modeling",
        category="ep_modeling",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.EP,
        status=CaseStatus.READY_WITH_MODS,
        tier=CaseTier.A,
        complexity=4,
        reg_suitability=5,
        force_models=["gravity", "drag"],
        has_targeting=False,
        duration_hours=12.0,
        expected_runtime_s=120.0,
        source_script="Tut_ElectricPropulsionModelling.script",
        template_name="R04_electric_propulsion.tpl",
        description="EP modeling converted to LEO with drag",
    ),
    CaseDefinition(
        case_id="R05",
        name="Force Models",
        category="force_models",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.NONE,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=2,
        reg_suitability=5,
        force_models=["gravity", "drag", "srp"],
        has_targeting=False,
        duration_hours=24.0,
        expected_runtime_s=90.0,
        source_script="Ex_ForceModels.script",
        template_name="R05_force_models.tpl",
        description="Force model comparison (gravity, drag, SRP)",
    ),
    CaseDefinition(
        case_id="R06",
        name="Integrators",
        category="integrators",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.NONE,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=2,
        reg_suitability=4,
        force_models=["gravity"],
        has_targeting=False,
        duration_hours=1.0,
        expected_runtime_s=45.0,
        source_script="Ex_Integrators.script",
        template_name="R06_integrators.tpl",
        description="Integrator comparison with step count capture",
    ),
    CaseDefinition(
        case_id="R07",
        name="Attitude VNB",
        category="attitude",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.CHEMICAL_FB,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=3,
        reg_suitability=4,
        force_models=["gravity"],
        has_targeting=False,
        duration_hours=0.5,
        expected_runtime_s=30.0,
        source_script="Ex_Attitude_VNB.script",
        template_name="R07_attitude_vnb.tpl",
        description="VNB attitude-aligned thrust direction validation",
    ),
    CaseDefinition(
        case_id="R08",
        name="THF Propagation",
        category="thf_propagation",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.THF,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=3,
        reg_suitability=5,
        force_models=["gravity"],
        has_targeting=False,
        duration_hours=2.0,
        expected_runtime_s=60.0,
        source_script="Ex_R2020a_Propagate_ThrustHistoryFile.script",
        template_name="R08_thf_propagation.tpl",
        description="Thrust history file propagation with mass/state reports",
    ),
    CaseDefinition(
        case_id="R09",
        name="Eclipse Location",
        category="eclipse",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.NONE,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=2,
        reg_suitability=4,
        force_models=["gravity"],
        has_targeting=False,
        duration_hours=6.0,
        expected_runtime_s=45.0,
        source_script="Ex_R2015a_EclipseLocation.script",
        template_name="R09_eclipse_location.tpl",
        description="Eclipse boundary detection and timing",
    ),
    CaseDefinition(
        case_id="R10",
        name="Constellation Script",
        category="constellation",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.NONE,
        status=CaseStatus.READY_WITH_MODS,
        tier=CaseTier.A,
        complexity=3,
        reg_suitability=3,
        force_models=["gravity"],
        has_targeting=False,
        duration_hours=2.0,
        expected_runtime_s=90.0,
        source_script="Ex_ConstellationScript.script",
        template_name="R10_constellation.tpl",
        description="Simplified constellation (2 SC) with reports",
    ),
    CaseDefinition(
        case_id="R11",
        name="LEO Station Keeping",
        category="station_keeping",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.CHEMICAL_FB,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=4,
        reg_suitability=5,
        force_models=["gravity", "drag"],
        has_targeting=True,
        duration_hours=168.0,  # 7 days
        expected_runtime_s=180.0,
        source_script="Ex_LEOStationKeeping.script",
        template_name="R11_leo_station_keeping.tpl",
        description="LEO station keeping with SK maneuver capture",
    ),
    CaseDefinition(
        case_id="R12",
        name="Tutorial LEO Station Keeping",
        category="station_keeping",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.CHEMICAL_FB,
        status=CaseStatus.READY,
        tier=CaseTier.A,
        complexity=4,
        reg_suitability=5,
        force_models=["gravity", "drag"],
        has_targeting=True,
        duration_hours=72.0,  # 3 days
        expected_runtime_s=120.0,
        source_script="Tut_LEOStationKeeping.script",
        template_name="R12_tut_leo_station_keeping.tpl",
        description="Tutorial LEO station keeping (simplified)",
    ),
]

TIER_B_CASES = [
    CaseDefinition(
        case_id="N01",
        name="LEO EP Drag Makeup",
        category="ep_ops",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.EP,
        status=CaseStatus.NEW_REFERENCE,
        tier=CaseTier.B,
        complexity=4,
        reg_suitability=5,
        force_models=["gravity", "drag"],
        has_targeting=False,
        duration_hours=240.0,  # 10 days
        expected_runtime_s=120.0,
        template_name="N01_leo_ep_drag_makeup.tpl",
        description="Maintain mean SMA under drag using EP finite burns at apogee",
    ),
    CaseDefinition(
        case_id="N02",
        name="VLEO Continuous Drag Compensation",
        category="ep_ops",
        orbit_regime=OrbitRegime.VLEO,
        propulsion=PropulsionType.EP,
        status=CaseStatus.NEW_REFERENCE,
        tier=CaseTier.B,
        complexity=5,
        reg_suitability=4,
        force_models=["gravity", "drag"],
        has_targeting=False,
        duration_hours=72.0,  # 3 days
        expected_runtime_s=180.0,
        template_name="N02_vleo_continuous_drag.tpl",
        description="Continuous thrust balancing drag at 300 km VLEO",
    ),
    CaseDefinition(
        case_id="N03",
        name="VLEO Duty-Cycle Drag Makeup",
        category="ep_ops",
        orbit_regime=OrbitRegime.VLEO,
        propulsion=PropulsionType.EP,
        status=CaseStatus.NEW_REFERENCE,
        tier=CaseTier.B,
        complexity=5,
        reg_suitability=5,
        force_models=["gravity", "drag"],
        has_targeting=False,
        duration_hours=120.0,  # 5 days
        expected_runtime_s=150.0,
        template_name="N03_vleo_duty_cycle.tpl",
        description="EP thrust only in sunlight arcs (eclipse gating)",
    ),
    CaseDefinition(
        case_id="N04",
        name="SSO LTAN/RAAN Maintenance",
        category="raan_control",
        orbit_regime=OrbitRegime.SSO,
        propulsion=PropulsionType.EP,
        status=CaseStatus.NEW_REFERENCE,
        tier=CaseTier.B,
        complexity=5,
        reg_suitability=4,
        force_models=["gravity", "drag", "srp"],
        has_targeting=True,
        duration_hours=720.0,  # 30 days
        expected_runtime_s=300.0,
        template_name="N04_sso_ltan_raan.tpl",
        description="LTAN/RAAN control via out-of-plane EP thrust",
    ),
    CaseDefinition(
        case_id="N05",
        name="Constellation Phasing",
        category="phasing",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.EP,
        status=CaseStatus.NEW_REFERENCE,
        tier=CaseTier.B,
        complexity=4,
        reg_suitability=4,
        force_models=["gravity", "drag"],
        has_targeting=True,
        duration_hours=168.0,  # 7 days
        expected_runtime_s=180.0,
        template_name="N05_constellation_phasing.tpl",
        description="Two-spacecraft along-track phasing with differential EP",
    ),
    CaseDefinition(
        case_id="N06",
        name="SK Finite Burn Conversion",
        category="station_keeping",
        orbit_regime=OrbitRegime.LEO,
        propulsion=PropulsionType.CHEMICAL_FB,
        status=CaseStatus.NEW_REFERENCE,
        tier=CaseTier.B,
        complexity=4,
        reg_suitability=5,
        force_models=["gravity", "drag"],
        has_targeting=True,
        duration_hours=168.0,  # 7 days
        expected_runtime_s=180.0,
        template_name="N06_sk_finite_burn.tpl",
        description="Convert impulsive SK to finite burn (same corridor as R11)",
    ),
]

# Combined registry
CASE_REGISTRY: Dict[str, CaseDefinition] = {
    case.case_id: case for case in TIER_A_CASES + TIER_B_CASES
}


def get_case(case_id: str) -> CaseDefinition:
    """Get case definition by ID."""
    if case_id not in CASE_REGISTRY:
        raise KeyError(f"Unknown case ID: {case_id}")
    return CASE_REGISTRY[case_id]


def get_tier_cases(tier: CaseTier) -> List[CaseDefinition]:
    """Get all cases for a tier."""
    return [case for case in CASE_REGISTRY.values() if case.tier == tier]


def get_cases_by_category(category: str) -> List[CaseDefinition]:
    """Get all cases in a category."""
    return [case for case in CASE_REGISTRY.values() if case.category == category]


def get_cases_by_propulsion(propulsion: PropulsionType) -> List[CaseDefinition]:
    """Get all cases using a propulsion type."""
    return [case for case in CASE_REGISTRY.values() if case.propulsion == propulsion]


def list_case_ids(tier: Optional[CaseTier] = None) -> List[str]:
    """List all case IDs, optionally filtered by tier."""
    if tier is None:
        return list(CASE_REGISTRY.keys())
    return [case.case_id for case in get_tier_cases(tier)]


def get_all_cases() -> List[CaseDefinition]:
    """Get all case definitions."""
    return list(CASE_REGISTRY.values())
