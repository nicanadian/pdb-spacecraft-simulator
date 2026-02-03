"""Service management fixtures for ETE tests.

Manages Docker containers for Aerie and development servers for the viewer.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class ServiceConfig:
    """Configuration for service endpoints."""

    aerie_graphql_url: str = "http://localhost:8080/v1/graphql"
    aerie_ui_url: str = "http://localhost"
    viewer_url: str = "http://localhost:3004"  # Vite may use different ports
    mcp_server_url: str = "http://localhost:8765"
    aerie_admin_secret: str = "hasura_admin_secret"  # Default from deployment .env


class AerieServiceManager:
    """Manages Aerie Docker stack lifecycle."""

    # Default compose file location
    COMPOSE_FILE = Path(".aerie-upstream/deployment/docker-compose.yml")

    def __init__(
        self,
        compose_file: Optional[Path] = None,
        project_name: str = "aerie-ete",
    ):
        """
        Initialize Aerie service manager.

        Args:
            compose_file: Path to docker-compose file
            project_name: Docker Compose project name (for isolation)
        """
        self.compose_file = compose_file or self.COMPOSE_FILE
        self.project_name = project_name
        self._started = False

    def start(self, timeout: float = 120.0) -> None:
        """
        Start Aerie services and wait for health.

        Args:
            timeout: Maximum time to wait for services to be healthy

        Raises:
            RuntimeError: If services fail to start or become healthy
        """
        if not self.compose_file.exists():
            raise FileNotFoundError(
                f"Docker Compose file not found: {self.compose_file}"
            )

        # Start services
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                "-p",
                self.project_name,
                "up",
                "-d",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to start Aerie: {result.stderr}")

        # Wait for health
        self._wait_for_health(timeout)
        self._started = True

    def stop(self) -> None:
        """Stop Aerie services."""
        if not self._started:
            return

        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                "-p",
                self.project_name,
                "down",
            ],
            capture_output=True,
        )
        self._started = False

    def _wait_for_health(self, timeout: float) -> None:
        """Wait for Aerie GraphQL endpoint to respond."""
        graphql_url = os.environ.get(
            "AERIE_GRAPHQL_URL", "http://localhost:8080/v1/graphql"
        )
        admin_secret = os.environ.get(
            "HASURA_GRAPHQL_ADMIN_SECRET", "hasura_admin_secret"
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.post(
                    graphql_url,
                    json={"query": "{ __typename }"},
                    headers={"x-hasura-admin-secret": admin_secret},
                    timeout=5,
                )
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass

            time.sleep(2)

        raise RuntimeError(f"Aerie did not become healthy within {timeout}s")

    @staticmethod
    def is_running() -> bool:
        """Check if Aerie is currently running and healthy."""
        graphql_url = os.environ.get(
            "AERIE_GRAPHQL_URL", "http://localhost:8080/v1/graphql"
        )
        admin_secret = os.environ.get(
            "HASURA_GRAPHQL_ADMIN_SECRET", "hasura_admin_secret"
        )

        try:
            response = requests.post(
                graphql_url,
                json={"query": "{ __typename }"},
                headers={"x-hasura-admin-secret": admin_secret},
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False


class ViewerServerManager:
    """Manages Vite dev server for the viewer application."""

    def __init__(
        self,
        viewer_dir: str = "viewer",
        port: int = 3002,
    ):
        """
        Initialize viewer server manager.

        Args:
            viewer_dir: Path to viewer directory
            port: Port to run dev server on
        """
        self.viewer_dir = Path(viewer_dir)
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self._started = False

    def start(self, timeout: float = 30.0) -> None:
        """
        Start Vite dev server and wait for ready.

        Args:
            timeout: Maximum time to wait for server to start

        Raises:
            RuntimeError: If server fails to start
        """
        if not self.viewer_dir.exists():
            raise FileNotFoundError(f"Viewer directory not found: {self.viewer_dir}")

        # Check if port is already in use
        if self._is_port_in_use():
            # Assume another dev server is running
            self._started = True
            return

        # Start dev server
        env = os.environ.copy()
        env["PORT"] = str(self.port)

        self.process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(self.port)],
            cwd=self.viewer_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )

        # Wait for ready
        self._wait_for_ready(timeout)
        self._started = True

    def stop(self) -> None:
        """Stop the dev server."""
        if self.process:
            if os.name != "nt":
                # Kill process group on Unix
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            else:
                self.process.terminate()

            self.process.wait(timeout=10)
            self.process = None

        self._started = False

    def _wait_for_ready(self, timeout: float) -> None:
        """Wait for dev server to respond."""
        url = f"http://localhost:{self.port}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass

            # Check if process died
            if self.process and self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(
                    f"Viewer dev server exited unexpectedly:\n"
                    f"stdout: {stdout.decode()}\n"
                    f"stderr: {stderr.decode()}"
                )

            time.sleep(1)

        raise RuntimeError(f"Viewer did not start within {timeout}s")

    def _is_port_in_use(self) -> bool:
        """Check if the port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", self.port)) == 0

    @property
    def url(self) -> str:
        """Get the viewer URL."""
        return f"http://localhost:{self.port}"

    @staticmethod
    def is_running(port: int = 3002) -> bool:
        """Check if viewer is currently running."""
        try:
            response = requests.get(f"http://localhost:{port}", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False


class MCPClientManager:
    """Manages MCP server client for tool invocations."""

    def __init__(self, server_url: str = "http://localhost:8765"):
        """
        Initialize MCP client manager.

        Args:
            server_url: MCP server URL
        """
        self.server_url = server_url
        self.process: Optional[subprocess.Popen] = None
        self._started = False

    def start(self, timeout: float = 30.0) -> None:
        """
        Start MCP server if not already running.

        Args:
            timeout: Maximum time to wait for server to start
        """
        if self.is_running():
            self._started = True
            return

        # Start MCP server
        self.process = subprocess.Popen(
            ["mcp-server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )

        # Wait for ready
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_running():
                self._started = True
                return
            time.sleep(1)

        raise RuntimeError(f"MCP server did not start within {timeout}s")

    def stop(self) -> None:
        """Stop the MCP server."""
        if self.process:
            if os.name != "nt":
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            else:
                self.process.terminate()

            self.process.wait(timeout=10)
            self.process = None

        self._started = False

    def is_running(self) -> bool:
        """Check if MCP server is running."""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def invoke_tool(self, tool_name: str, **kwargs) -> dict:
        """
        Invoke an MCP tool.

        Args:
            tool_name: Name of the tool to invoke
            **kwargs: Tool arguments

        Returns:
            Tool result

        Raises:
            RuntimeError: If tool invocation fails
        """
        response = requests.post(
            f"{self.server_url}/tools/{tool_name}",
            json=kwargs,
            timeout=300,  # Long timeout for simulation tools
        )

        if response.status_code != 200:
            raise RuntimeError(f"Tool invocation failed: {response.text}")

        return response.json()
