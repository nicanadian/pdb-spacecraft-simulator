"""Truth file generation from GMAT outputs.

Generates truth files (final state checkpoints, derived metrics) from
GMAT execution results for use in regression testing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..case_registry import (
    CaseDefinition,
    CaseResult,
    CaseTruth,
    TruthCheckpoint,
    get_case,
)
from ..parser import GMATOutputParser
from .run_case import CaseRunner, run_case


class TruthGenerator:
    """Generator for truth files from GMAT outputs."""

    def __init__(
        self,
        baselines_dir: Optional[Path] = None,
    ):
        """
        Initialize truth generator.

        Args:
            baselines_dir: Directory for storing truth files
        """
        base_dir = Path(__file__).parent.parent.parent
        self.baselines_dir = baselines_dir or base_dir / "baselines" / "gmat"
        self.parser = GMATOutputParser()

    def generate_truth(
        self,
        case_id: str,
        result: Optional[CaseResult] = None,
        version: str = "v1",
    ) -> CaseTruth:
        """
        Generate truth file for a case.

        If no result is provided, executes the case first.

        Args:
            case_id: Case identifier
            result: Existing CaseResult (will run case if None)
            version: Version string for the truth file

        Returns:
            CaseTruth containing checkpoints and derived metrics
        """
        case_def = get_case(case_id)

        # Run case if no result provided
        if result is None:
            runner = CaseRunner()
            result = runner.run_case(case_id, generate_truth=True)

        if not result.success:
            raise RuntimeError(
                f"Cannot generate truth for failed case {case_id}: "
                f"{result.error_message or result.stderr}"
            )

        # Parse outputs
        keplerian_df = None
        ephemeris_df = None
        mass_df = None

        if result.keplerian_path and result.keplerian_path.exists():
            keplerian_df = self.parser.parse_keplerian_report(result.keplerian_path)

        if result.ephemeris_path and result.ephemeris_path.exists():
            ephemeris_df = self.parser.parse_ephemeris_report(result.ephemeris_path)

        if result.mass_path and result.mass_path.exists():
            mass_df = self.parser.parse_propellant_report(result.mass_path)

        # Build truth object
        truth = CaseTruth(
            case_id=case_id,
            schema_version="1.0",
            gmat_version=self._detect_gmat_version(result),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Extract initial checkpoint
        if keplerian_df is not None and len(keplerian_df) > 0:
            truth.initial = self._extract_checkpoint(keplerian_df.iloc[0], ephemeris_df, 0)

        # Extract final checkpoint
        if keplerian_df is not None and len(keplerian_df) > 0:
            final_idx = len(keplerian_df) - 1
            truth.final = self._extract_checkpoint(
                keplerian_df.iloc[-1],
                ephemeris_df,
                final_idx if ephemeris_df is not None else None,
            )

        # Compute derived metrics
        truth.derived = self._compute_derived_metrics(
            case_def, keplerian_df, ephemeris_df, mass_df
        )

        # Extract events from stdout/reports
        truth.events = self._extract_events(case_def, result)

        return truth

    def _extract_checkpoint(
        self,
        kep_row: pd.Series,
        ephemeris_df: Optional[pd.DataFrame],
        eph_idx: Optional[int],
    ) -> TruthCheckpoint:
        """Extract a checkpoint from Keplerian and optionally ephemeris data."""
        checkpoint = TruthCheckpoint(
            epoch_utc=kep_row["time"].isoformat() if hasattr(kep_row["time"], "isoformat")
                      else str(kep_row["time"]),
            sma_km=float(kep_row["sma_km"]),
            ecc=float(kep_row["ecc"]),
            inc_deg=float(kep_row["inc_deg"]),
            raan_deg=float(kep_row["raan_deg"]),
            aop_deg=float(kep_row["aop_deg"]),
            ta_deg=float(kep_row["ta_deg"]),
            mass_kg=0.0,  # Will be filled from mass report if available
            altitude_km=float(kep_row.get("altitude_km", 0.0)),
        )

        # Add ECI state if ephemeris available
        if ephemeris_df is not None and eph_idx is not None and eph_idx < len(ephemeris_df):
            eph_row = ephemeris_df.iloc[eph_idx]
            checkpoint.x_km = float(eph_row["x_km"])
            checkpoint.y_km = float(eph_row["y_km"])
            checkpoint.z_km = float(eph_row["z_km"])
            checkpoint.vx_km_s = float(eph_row["vx_km_s"])
            checkpoint.vy_km_s = float(eph_row["vy_km_s"])
            checkpoint.vz_km_s = float(eph_row["vz_km_s"])

        return checkpoint

    def _compute_derived_metrics(
        self,
        case_def: CaseDefinition,
        keplerian_df: Optional[pd.DataFrame],
        ephemeris_df: Optional[pd.DataFrame],
        mass_df: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """Compute derived metrics based on case category."""
        derived = {}

        if keplerian_df is None or len(keplerian_df) < 2:
            return derived

        # SMA drift rate (km/day)
        if len(keplerian_df) > 1:
            dt_days = (
                keplerian_df["time"].iloc[-1] - keplerian_df["time"].iloc[0]
            ).total_seconds() / 86400.0
            if dt_days > 0:
                sma_change = keplerian_df["sma_km"].iloc[-1] - keplerian_df["sma_km"].iloc[0]
                derived["sma_drift_km_per_day"] = sma_change / dt_days

        # Altitude statistics
        if "altitude_km" in keplerian_df.columns:
            derived["altitude_mean_km"] = float(keplerian_df["altitude_km"].mean())
            derived["altitude_min_km"] = float(keplerian_df["altitude_km"].min())
            derived["altitude_max_km"] = float(keplerian_df["altitude_km"].max())

        # RAAN drift (deg/day) for SSO cases
        if case_def.orbit_regime.value == "SSO" and len(keplerian_df) > 1:
            dt_days = (
                keplerian_df["time"].iloc[-1] - keplerian_df["time"].iloc[0]
            ).total_seconds() / 86400.0
            if dt_days > 0:
                # Handle wraparound
                raan_change = keplerian_df["raan_deg"].iloc[-1] - keplerian_df["raan_deg"].iloc[0]
                if raan_change > 180:
                    raan_change -= 360
                elif raan_change < -180:
                    raan_change += 360
                derived["raan_drift_deg_per_day"] = raan_change / dt_days

        # Mass consumption for EP cases
        if mass_df is not None and len(mass_df) > 1:
            if "total_mass_kg" in mass_df.columns:
                mass_consumed = mass_df["total_mass_kg"].iloc[0] - mass_df["total_mass_kg"].iloc[-1]
                derived["mass_consumed_kg"] = float(mass_consumed)

                dt_hours = (
                    mass_df["time"].iloc[-1] - mass_df["time"].iloc[0]
                ).total_seconds() / 3600.0
                if dt_hours > 0:
                    derived["mass_rate_kg_per_hour"] = mass_consumed / dt_hours

        # Duty cycle for EP cases
        if case_def.category in ["ep_ops"] and mass_df is not None:
            # Estimate duty cycle from mass consumption rate
            # (actual implementation would parse thrust reports)
            pass

        return derived

    def _extract_events(
        self,
        case_def: CaseDefinition,
        result: CaseResult,
    ) -> Dict[str, str]:
        """Extract event timestamps from case outputs."""
        events = {}

        # Parse stdout for key events
        if result.stdout:
            # Look for burn start/end messages
            import re

            # Pattern for finite burn events
            burn_pattern = r"(Begin|End)FiniteBurn.*?(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2})"
            for match in re.finditer(burn_pattern, result.stdout, re.IGNORECASE):
                event_type = match.group(1).lower()
                timestamp = match.group(2)
                event_key = f"burn_{event_type}"
                if event_key not in events:
                    events[event_key] = timestamp

            # Pattern for eclipse events
            eclipse_pattern = r"(Umbra|Penumbra).*?(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2})"
            for match in re.finditer(eclipse_pattern, result.stdout, re.IGNORECASE):
                event_type = match.group(1).lower()
                timestamp = match.group(2)
                event_key = f"eclipse_{event_type}"
                if event_key not in events:
                    events[event_key] = timestamp

        return events

    def _detect_gmat_version(self, result: CaseResult) -> Optional[str]:
        """Detect GMAT version from execution output."""
        if result.stdout:
            import re
            # Look for version string in output
            version_pattern = r"GMAT\s+([R\d]+[a-z]?)"
            match = re.search(version_pattern, result.stdout)
            if match:
                return match.group(1)
        return None

    def save_truth(
        self,
        truth: CaseTruth,
        version: str = "v1",
    ) -> Path:
        """
        Save truth file to baselines directory.

        Args:
            truth: CaseTruth to save
            version: Version string

        Returns:
            Path to saved truth file
        """
        case_dir = self.baselines_dir / truth.case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        truth_path = case_dir / f"truth_{version}.json"
        truth.to_json(truth_path)

        return truth_path

    def load_truth(
        self,
        case_id: str,
        version: str = "v1",
    ) -> CaseTruth:
        """
        Load truth file from baselines directory.

        Args:
            case_id: Case identifier
            version: Version string

        Returns:
            CaseTruth loaded from file
        """
        truth_path = self.baselines_dir / case_id / f"truth_{version}.json"
        return CaseTruth.from_json(truth_path)


def generate_truth(
    case_id: str,
    version: str = "v1",
    save: bool = True,
) -> CaseTruth:
    """
    Generate truth file for a case.

    Convenience function that creates a TruthGenerator and generates truth.

    Args:
        case_id: Case identifier (e.g., "R01", "N01")
        version: Version string for the truth file
        save: Whether to save the truth file

    Returns:
        CaseTruth containing checkpoints and derived metrics
    """
    generator = TruthGenerator()
    truth = generator.generate_truth(case_id, version=version)

    if save:
        path = generator.save_truth(truth, version)
        print(f"Truth saved to: {path}")

    return truth


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate truth files from GMAT")
    parser.add_argument("--case", "-c", required=True, help="Case ID (e.g., R01)")
    parser.add_argument("--version", "-v", default="v1", help="Version string")
    parser.add_argument("--no-save", action="store_true", help="Don't save to disk")

    args = parser.parse_args()

    truth = generate_truth(args.case, args.version, save=not args.no_save)

    print(f"\nGenerated truth for {args.case}:")
    if truth.initial:
        print(f"  Initial SMA: {truth.initial.sma_km:.3f} km")
    if truth.final:
        print(f"  Final SMA: {truth.final.sma_km:.3f} km")
    if truth.derived:
        print("  Derived metrics:")
        for key, value in truth.derived.items():
            print(f"    {key}: {value:.6f}")
