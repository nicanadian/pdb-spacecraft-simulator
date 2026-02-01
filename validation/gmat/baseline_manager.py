"""Manager for GMAT baseline storage and retrieval."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .baseline import GMATBaseline, GMATBaselineMetadata, GMATEphemerisRecord, datetime_to_jd
from .generator import ScenarioConfig


class GMATBaselineManager:
    """
    Manager for GMAT validation baselines.

    Handles storage, retrieval, and versioning of baseline data.

    Directory structure:
        validation/baselines/gmat/
        ├── manifest.json                    # Index of all baselines
        ├── pure_propagation_12h/
        │   └── baseline_v1.json            # GMATBaseline serialized
        ├── orbit_lowering_24h/
        │   └── baseline_v1.json
        └── ground_access_24h/
            └── baseline_v1.json
    """

    MANIFEST_FILE = "manifest.json"

    def __init__(self, baselines_dir: Optional[Path] = None):
        """
        Initialize baseline manager.

        Args:
            baselines_dir: Directory for baseline storage.
                Defaults to validation/baselines/gmat.
        """
        if baselines_dir is None:
            baselines_dir = Path(__file__).parent.parent / "baselines" / "gmat"

        self.baselines_dir = Path(baselines_dir)

    def _ensure_dir(self) -> None:
        """Ensure baselines directory exists."""
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def _manifest_path(self) -> Path:
        """Get path to manifest file."""
        return self.baselines_dir / self.MANIFEST_FILE

    def _load_manifest(self) -> Dict:
        """Load manifest file or return empty dict."""
        manifest_path = self._manifest_path()
        if manifest_path.exists():
            with open(manifest_path, "r") as f:
                return json.load(f)
        return {"baselines": {}}

    def _save_manifest(self, manifest: Dict) -> None:
        """Save manifest file."""
        self._ensure_dir()
        with open(self._manifest_path(), "w") as f:
            json.dump(manifest, f, indent=2)

    def compute_scenario_hash(self, config: ScenarioConfig) -> str:
        """
        Compute deterministic hash for a scenario configuration.

        The hash is based on key parameters that affect simulation output.

        Args:
            config: Scenario configuration

        Returns:
            SHA256 hash string (first 16 characters)
        """
        # Extract key fields that affect simulation
        hash_data = {
            "sma_km": config.sma_km,
            "ecc": config.ecc,
            "inc_deg": config.inc_deg,
            "raan_deg": config.raan_deg,
            "aop_deg": config.aop_deg,
            "ta_deg": config.ta_deg,
            "epoch": config.epoch.isoformat(),
            "duration_hours": config.duration_hours,
            "dry_mass_kg": config.dry_mass_kg,
            "drag_area_m2": config.drag_area_m2,
            "has_ep_thruster": config.has_ep_thruster,
            "include_drag": config.include_drag,
            "high_fidelity": config.high_fidelity,
        }

        if config.has_ep_thruster:
            hash_data.update({
                "thrust_mN": config.thrust_mN,
                "isp_s": config.isp_s,
                "thrusts_per_orbit": config.thrusts_per_orbit,
                "thrust_arc_deg": config.thrust_arc_deg,
            })

        # Create deterministic JSON string
        json_str = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def store_baseline(
        self,
        scenario_id: str,
        baseline: GMATBaseline,
        version: Optional[str] = None,
    ) -> Path:
        """
        Store a baseline for a scenario.

        Args:
            scenario_id: Scenario identifier
            baseline: Baseline data to store
            version: Version string (default: auto-increment)

        Returns:
            Path to stored baseline file
        """
        self._ensure_dir()

        # Create scenario directory
        scenario_dir = self.baselines_dir / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # Determine version
        if version is None:
            existing = list(scenario_dir.glob("baseline_v*.json"))
            if existing:
                versions = [int(p.stem.split("_v")[1]) for p in existing]
                version = f"v{max(versions) + 1}"
            else:
                version = "v1"

        # Save baseline
        baseline_path = scenario_dir / f"baseline_{version}.json"
        baseline.to_json(baseline_path)

        # Update manifest
        manifest = self._load_manifest()
        if scenario_id not in manifest["baselines"]:
            manifest["baselines"][scenario_id] = {}

        manifest["baselines"][scenario_id][version] = {
            "path": str(baseline_path.relative_to(self.baselines_dir)),
            "scenario_hash": baseline.metadata.scenario_hash,
            "gmat_version": baseline.metadata.gmat_version,
            "created_at": baseline.metadata.execution_timestamp,
            "num_points": baseline.num_points,
            "start_epoch": baseline.start_epoch,
            "end_epoch": baseline.end_epoch,
        }

        # Update latest pointer
        manifest["baselines"][scenario_id]["latest"] = version

        self._save_manifest(manifest)

        return baseline_path

    def load_baseline(
        self,
        scenario_id: str,
        version: str = "latest",
    ) -> GMATBaseline:
        """
        Load a baseline for a scenario.

        Args:
            scenario_id: Scenario identifier
            version: Version to load ("latest", "v1", "v2", etc.)

        Returns:
            Loaded GMATBaseline

        Raises:
            FileNotFoundError: If baseline not found
        """
        manifest = self._load_manifest()

        if scenario_id not in manifest["baselines"]:
            raise FileNotFoundError(f"No baselines found for scenario: {scenario_id}")

        scenario_data = manifest["baselines"][scenario_id]

        # Resolve version
        if version == "latest":
            version = scenario_data.get("latest")
            if version is None:
                raise FileNotFoundError(f"No latest version for scenario: {scenario_id}")

        if version not in scenario_data:
            raise FileNotFoundError(
                f"Version {version} not found for scenario: {scenario_id}"
            )

        baseline_path = self.baselines_dir / scenario_data[version]["path"]
        return GMATBaseline.from_json(baseline_path)

    def list_baselines(self) -> List[Dict[str, str]]:
        """
        List all available baselines with metadata.

        Returns:
            List of dicts with scenario_id, version, created_at, etc.
        """
        manifest = self._load_manifest()
        result = []

        for scenario_id, scenario_data in manifest.get("baselines", {}).items():
            for version, version_data in scenario_data.items():
                if version == "latest":
                    continue

                result.append({
                    "scenario_id": scenario_id,
                    "version": version,
                    "is_latest": version == scenario_data.get("latest"),
                    "scenario_hash": version_data.get("scenario_hash"),
                    "gmat_version": version_data.get("gmat_version"),
                    "created_at": version_data.get("created_at"),
                    "num_points": version_data.get("num_points"),
                    "start_epoch": version_data.get("start_epoch"),
                    "end_epoch": version_data.get("end_epoch"),
                })

        return result

    def has_baseline(self, scenario_id: str, version: str = "latest") -> bool:
        """
        Check if a baseline exists.

        Args:
            scenario_id: Scenario identifier
            version: Version to check

        Returns:
            True if baseline exists
        """
        try:
            self.load_baseline(scenario_id, version)
            return True
        except FileNotFoundError:
            return False

    def delete_baseline(self, scenario_id: str, version: str) -> bool:
        """
        Delete a specific baseline version.

        Args:
            scenario_id: Scenario identifier
            version: Version to delete (cannot be "latest")

        Returns:
            True if deleted, False if not found
        """
        if version == "latest":
            raise ValueError("Cannot delete 'latest' pointer directly. Delete a specific version.")

        manifest = self._load_manifest()

        if scenario_id not in manifest["baselines"]:
            return False

        if version not in manifest["baselines"][scenario_id]:
            return False

        # Get path and delete file
        version_data = manifest["baselines"][scenario_id][version]
        baseline_path = self.baselines_dir / version_data["path"]
        if baseline_path.exists():
            baseline_path.unlink()

        # Remove from manifest
        del manifest["baselines"][scenario_id][version]

        # Update latest if needed
        if manifest["baselines"][scenario_id].get("latest") == version:
            # Find next latest
            versions = [k for k in manifest["baselines"][scenario_id].keys() if k != "latest"]
            if versions:
                manifest["baselines"][scenario_id]["latest"] = sorted(versions)[-1]
            else:
                del manifest["baselines"][scenario_id]

        self._save_manifest(manifest)
        return True


def create_baseline_from_ephemeris(
    scenario_id: str,
    scenario_config: ScenarioConfig,
    ephemeris_df,  # pandas DataFrame
    gmat_version: Optional[str] = None,
) -> GMATBaseline:
    """
    Create a GMATBaseline from parsed ephemeris DataFrame.

    Args:
        scenario_id: Scenario identifier
        scenario_config: Configuration used to generate the data
        ephemeris_df: DataFrame with time, x_km, y_km, z_km, vx_km_s, vy_km_s, vz_km_s
        gmat_version: GMAT version string

    Returns:
        GMATBaseline ready for storage
    """
    manager = GMATBaselineManager()

    # Create ephemeris records
    records = []
    for _, row in ephemeris_df.iterrows():
        epoch_dt = row["time"].to_pydatetime()
        if epoch_dt.tzinfo is None:
            from datetime import timezone
            epoch_dt = epoch_dt.replace(tzinfo=timezone.utc)

        records.append(GMATEphemerisRecord(
            epoch_utc=epoch_dt.isoformat(),
            epoch_jd=datetime_to_jd(epoch_dt),
            x_km=float(row["x_km"]),
            y_km=float(row["y_km"]),
            z_km=float(row["z_km"]),
            vx_km_s=float(row["vx_km_s"]),
            vy_km_s=float(row["vy_km_s"]),
            vz_km_s=float(row["vz_km_s"]),
        ))

    # Create metadata
    metadata = GMATBaselineMetadata(
        scenario_id=scenario_id,
        scenario_hash=manager.compute_scenario_hash(scenario_config),
        gmat_version=gmat_version,
        execution_timestamp=datetime.now().isoformat(),
    )

    return GMATBaseline(
        metadata=metadata,
        ephemeris=records,
    )
