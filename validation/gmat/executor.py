"""GMAT CLI execution wrapper."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class GMATExecutionResult:
    """Result of GMAT script execution."""

    success: bool
    return_code: int
    stdout: str
    stderr: str
    output_files: list[Path]
    execution_time_s: float
    working_dir: Optional[Path] = None  # Isolated run directory for debugging


class GMATExecutor:
    """
    Executor for GMAT scripts.

    Wraps GMAT command-line interface for batch execution.
    """

    # Default GMAT executable locations
    DEFAULT_PATHS = [
        # macOS R2025a (Apple Silicon)
        "/Applications/GMAT R2025a/bin/GMAT-R2025a_Beta.app/Contents/MacOS/GmatConsole",
        "/Applications/GMAT R2025a/bin/GmatConsole",
        # macOS older versions
        "/Applications/GMAT/R2022a/bin/GMAT",
        "/usr/local/bin/GMAT",
        "/opt/GMAT/bin/GMAT",
        # Linux
        "/opt/GMAT/R2022a/bin/GMAT",
        # Windows
        "C:\\GMAT\\R2022a\\bin\\GMAT.exe",
        "C:\\Program Files\\GMAT\\R2025a\\bin\\GMAT.exe",
    ]

    def __init__(
        self,
        gmat_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize GMAT executor.

        Args:
            gmat_path: Path to GMAT executable. If None, searches default locations.
            output_dir: Directory for GMAT output files.
        """
        self.gmat_path = self._find_gmat(gmat_path)
        self.output_dir = Path(output_dir) if output_dir else Path("validation/gmat/output")

    def _find_gmat(self, gmat_path: Optional[Path]) -> Optional[Path]:
        """Find GMAT executable."""
        if gmat_path:
            path = Path(gmat_path)
            if path.exists():
                return path
            raise FileNotFoundError(f"GMAT not found at: {gmat_path}")

        # Check environment variable
        env_path = os.environ.get("GMAT_ROOT")
        if env_path:
            # Try macOS R2025a app bundle path first
            macos_paths = [
                Path(env_path) / "bin" / "GMAT-R2025a_Beta.app" / "Contents" / "MacOS" / "GmatConsole",
                Path(env_path) / "bin" / "GmatConsole",
                Path(env_path) / "bin" / "GMAT",
            ]
            for path in macos_paths:
                if path.exists():
                    return path

        # Search default locations
        for default_path in self.DEFAULT_PATHS:
            path = Path(default_path)
            if path.exists():
                return path

        # Check if in PATH
        gmat_in_path = shutil.which("GMAT")
        if gmat_in_path:
            return Path(gmat_in_path)

        return None

    def is_available(self) -> bool:
        """Check if GMAT is available for execution."""
        return self.gmat_path is not None and self.gmat_path.exists()

    @staticmethod
    def check_installation() -> dict:
        """
        Check GMAT installation status.

        Returns:
            Dict with installation details including 'available', 'path', 'version'
        """
        return check_gmat_installation()

    def execute_script(
        self,
        script_path: Path,
        timeout_s: int = 3600,
        isolated: bool = True,
    ) -> GMATExecutionResult:
        """
        Execute a GMAT script.

        Args:
            script_path: Path to GMAT script file
            timeout_s: Execution timeout in seconds
            isolated: If True, run in isolated temp directory (preserves artifacts)

        Returns:
            GMATExecutionResult with execution details
        """
        import time

        script_path = Path(script_path)
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        if not self.is_available():
            return GMATExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="GMAT executable not found. Install GMAT or set GMAT_ROOT environment variable.",
                output_files=[],
                execution_time_s=0.0,
                working_dir=None,
            )

        # Create working directory
        if isolated:
            # Create isolated run directory under validation/gmat/runs/
            runs_dir = Path(__file__).parent / "runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
            working_dir = runs_dir / run_id
            working_dir.mkdir(parents=True, exist_ok=True)

            # Copy script to working directory
            isolated_script = working_dir / script_path.name
            shutil.copy2(script_path, isolated_script)
            execution_script = isolated_script
        else:
            working_dir = script_path.parent
            execution_script = script_path

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build command - GMAT requires absolute paths as it ignores cwd
        cmd = [
            str(self.gmat_path),
            "--run",
            str(execution_script.resolve()),  # Must be absolute path
            "--minimize",  # Run without GUI
        ]

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(working_dir),
            )

            execution_time = time.time() - start_time

            # Find output files in working directory
            output_files = self._find_output_files_in_dir(working_dir)

            return GMATExecutionResult(
                success=result.returncode == 0,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                output_files=output_files,
                execution_time_s=execution_time,
                working_dir=working_dir,
            )

        except subprocess.TimeoutExpired:
            return GMATExecutionResult(
                success=False,
                return_code=-2,
                stdout="",
                stderr=f"GMAT execution timed out after {timeout_s} seconds",
                output_files=[],
                execution_time_s=timeout_s,
                working_dir=working_dir,
            )

        except Exception as e:
            return GMATExecutionResult(
                success=False,
                return_code=-3,
                stdout="",
                stderr=str(e),
                output_files=[],
                execution_time_s=time.time() - start_time,
                working_dir=working_dir,
            )

    def _find_output_files_in_dir(self, directory: Path) -> list[Path]:
        """Find output files in a specific directory."""
        output_files = []
        directory = Path(directory)

        if directory.exists():
            for ext in [".txt", ".csv", ".report", ".eph", ".dat"]:
                output_files.extend(directory.glob(f"*{ext}"))
                # Also check subdirectories
                output_files.extend(directory.glob(f"**/*{ext}"))

        return sorted(set(output_files))

    def _find_output_files(self, script_path: Path) -> list[Path]:
        """Find output files generated by a script."""
        output_files = []

        # Check output directory
        if self.output_dir.exists():
            output_files.extend(self._find_output_files_in_dir(self.output_dir))

        # Check script directory
        script_dir = script_path.parent
        if script_dir.exists():
            output_files.extend(self._find_output_files_in_dir(script_dir))

        return sorted(set(output_files))

    def execute_all_scripts(
        self,
        script_dir: Optional[Path] = None,
        timeout_per_script_s: int = 3600,
    ) -> dict[str, GMATExecutionResult]:
        """
        Execute all GMAT scripts in a directory.

        Args:
            script_dir: Directory containing .script files
            timeout_per_script_s: Timeout per script

        Returns:
            Dict mapping script name to execution result
        """
        if script_dir is None:
            script_dir = Path(__file__).parent / "scripts"

        script_dir = Path(script_dir)
        results = {}

        for script_path in sorted(script_dir.glob("*.script")):
            print(f"Executing: {script_path.name}")
            result = self.execute_script(script_path, timeout_per_script_s)
            results[script_path.stem] = result

            if result.success:
                print(f"  Success in {result.execution_time_s:.1f}s")
            else:
                print(f"  Failed: {result.stderr[:100]}")

        return results


def check_gmat_installation() -> dict:
    """
    Check GMAT installation status.

    Returns:
        Dict with installation details
    """
    executor = GMATExecutor()

    info = {
        "available": executor.is_available(),
        "path": str(executor.gmat_path) if executor.gmat_path else None,
        "env_var": os.environ.get("GMAT_ROOT"),
    }

    if executor.is_available():
        # Try to get version
        try:
            result = subprocess.run(
                [str(executor.gmat_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            info["version"] = result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            info["version"] = "unknown"

    return info


if __name__ == "__main__":
    info = check_gmat_installation()
    print("GMAT Installation Check:")
    print(f"  Available: {info['available']}")
    print(f"  Path: {info['path']}")
    print(f"  GMAT_ROOT: {info['env_var']}")
    if info.get("version"):
        print(f"  Version: {info['version']}")
