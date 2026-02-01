"""Validation report generation."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .comparator import ValidationResult


class ValidationReportGenerator:
    """Generator for validation reports in various formats."""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize report generator.

        Args:
            output_dir: Directory for output reports
        """
        if output_dir is None:
            output_dir = Path("validation/output")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json_report(
        self,
        results: List[ValidationResult],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate JSON validation report.

        Args:
            results: List of validation results
            filename: Output filename (default: validation_report_<timestamp>.json)

        Returns:
            Path to generated report
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"validation_report_{timestamp}.json"

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self._generate_summary(results),
            "results": [r.to_dict() for r in results],
        }

        output_path = self.output_dir / filename
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return output_path

    def generate_markdown_report(
        self,
        results: List[ValidationResult],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate Markdown validation report.

        Args:
            results: List of validation results
            filename: Output filename

        Returns:
            Path to generated report
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"validation_report_{timestamp}.md"

        summary = self._generate_summary(results)

        lines = [
            "# GMAT Validation Report",
            "",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## Summary",
            "",
            f"- **Total Scenarios**: {summary['total_scenarios']}",
            f"- **Passed**: {summary['passed']} ({summary['pass_rate']:.1%})",
            f"- **Failed**: {summary['failed']}",
            "",
            "## Results by Scenario",
            "",
        ]

        for result in results:
            status = "PASS" if result.passed else "FAIL"
            status_icon = "✅" if result.passed else "❌"

            lines.extend([
                f"### {result.scenario_id}",
                "",
                f"**Status**: {status_icon} {status}",
                f"**Type**: {result.scenario_type}",
                "",
            ])

            if result.metrics:
                lines.append("**Metrics**:")
                lines.append("")
                lines.append("| Metric | Value | Status |")
                lines.append("|--------|-------|--------|")

                for key, value in result.metrics.items():
                    if isinstance(value, bool):
                        metric_status = "✅" if value else "❌"
                        lines.append(f"| {key} | {value} | {metric_status} |")
                    elif isinstance(value, float):
                        lines.append(f"| {key} | {value:.4f} | |")
                    elif isinstance(value, (int, str)):
                        lines.append(f"| {key} | {value} | |")

                lines.append("")

            if result.details:
                lines.append("**Details**:")
                lines.append("")
                for key, value in result.details.items():
                    lines.append(f"- {key}: {value}")
                lines.append("")

        output_path = self.output_dir / filename
        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        return output_path

    def generate_console_report(self, results: List[ValidationResult]) -> str:
        """
        Generate console-friendly validation report.

        Args:
            results: List of validation results

        Returns:
            Formatted string for console output
        """
        summary = self._generate_summary(results)

        lines = [
            "",
            "=" * 60,
            "GMAT VALIDATION REPORT",
            "=" * 60,
            "",
            f"Total Scenarios: {summary['total_scenarios']}",
            f"Passed: {summary['passed']} ({summary['pass_rate']:.1%})",
            f"Failed: {summary['failed']}",
            "",
            "-" * 60,
        ]

        for result in results:
            status = "PASS" if result.passed else "FAIL"
            lines.extend([
                "",
                f"Scenario: {result.scenario_id}",
                f"Type: {result.scenario_type}",
                f"Status: [{status}]",
            ])

            # Key metrics
            if result.metrics:
                if "position_rms_km" in result.metrics:
                    lines.append(f"  Position RMS: {result.metrics['position_rms_km']:.3f} km")
                if "velocity_rms_m_s" in result.metrics:
                    lines.append(f"  Velocity RMS: {result.metrics['velocity_rms_m_s']:.3f} m/s")
                if "altitude_rms_km" in result.metrics:
                    lines.append(f"  Altitude RMS: {result.metrics['altitude_rms_km']:.3f} km")

        lines.extend([
            "",
            "-" * 60,
            f"Overall: {'ALL PASSED' if summary['all_passed'] else 'SOME FAILED'}",
            "=" * 60,
            "",
        ])

        return "\n".join(lines)

    def _generate_summary(self, results: List[ValidationResult]) -> Dict:
        """Generate summary statistics from results."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        return {
            "total_scenarios": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "all_passed": failed == 0,
        }


def generate_validation_report(
    results: List[ValidationResult],
    output_dir: Optional[Path] = None,
    formats: Optional[List[str]] = None,
) -> Dict[str, Path]:
    """
    Generate validation reports in multiple formats.

    Args:
        results: List of validation results
        output_dir: Output directory
        formats: List of formats ("json", "markdown", "console")

    Returns:
        Dict mapping format to output path
    """
    if formats is None:
        formats = ["json", "markdown"]

    generator = ValidationReportGenerator(output_dir)
    outputs = {}

    if "json" in formats:
        outputs["json"] = generator.generate_json_report(results)

    if "markdown" in formats:
        outputs["markdown"] = generator.generate_markdown_report(results)

    if "console" in formats:
        report = generator.generate_console_report(results)
        print(report)
        outputs["console"] = None

    return outputs
