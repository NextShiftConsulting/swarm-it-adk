"""
Sidecar Lifecycle Management - Copilot SDK Pattern
Automatic sidecar process start/stop with health checking.
"""

import subprocess
import time
import requests
from typing import Optional, List
import platform


class SidecarManager:
    """
    Manages swarm-it sidecar process lifecycle.

    Inspired by GitHub Copilot SDK's automatic CLI management.

    Usage:
        >>> with SidecarManager(mode="docker") as sidecar:
        ...     client = SwarmIt(base_url="http://localhost:8080")
        ...     cert = client.certify("test prompt")
        # Sidecar automatically stopped
    """

    def __init__(
        self,
        mode: str = "docker",
        port: int = 8080,
        image: str = "swarmit/sidecar:latest",
        container_name: str = "swarm-it-sidecar",
        binary_path: str = "swarm-it-sidecar",
    ):
        """
        Initialize sidecar manager.

        Args:
            mode: "docker", "binary", or "external"
            port: Port to run sidecar on (default: 8080)
            image: Docker image name (for docker mode)
            container_name: Docker container name (for docker mode)
            binary_path: Path to sidecar binary (for binary mode)
        """
        self.mode = mode
        self.port = port
        self.image = image
        self.container_name = container_name
        self.binary_path = binary_path

        self.process: Optional[subprocess.Popen] = None
        self.container_id: Optional[str] = None

    def start(self, timeout: int = 30, check_interval: float = 0.5):
        """
        Start sidecar process.

        Args:
            timeout: Maximum seconds to wait for health check
            check_interval: Seconds between health check attempts

        Raises:
            RuntimeError: If sidecar fails to start
            TimeoutError: If health check times out
        """
        if self.mode == "docker":
            self._start_docker()
        elif self.mode == "binary":
            self._start_binary()
        elif self.mode == "external":
            pass  # User manages sidecar
        else:
            raise ValueError(
                f"Unsupported mode: {self.mode}. "
                f"Use 'docker', 'binary', or 'external'"
            )

        # Wait for health check (unless external mode)
        if self.mode != "external":
            self._wait_for_ready(timeout, check_interval)

    def _start_docker(self):
        """Start sidecar via docker run."""
        # Check if container already exists
        check_cmd = ["docker", "ps", "-a", "-q", "-f", f"name={self.container_name}"]
        result = subprocess.run(check_cmd, capture_output=True, text=True)

        if result.stdout.strip():
            # Container exists, try to start it
            start_cmd = ["docker", "start", self.container_name]
            result = subprocess.run(start_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[SidecarManager] Started existing container: {self.container_name}")
                return

            # If start failed, remove and recreate
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True)

        # Create and start new container
        cmd = [
            "docker", "run", "-d",
            "-p", f"{self.port}:8080",
            "--name", self.container_name,
            self.image
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to start docker container:\n{result.stderr}"
            )

        self.container_id = result.stdout.strip()
        print(f"[SidecarManager] Started docker container: {self.container_id[:12]}")

    def _start_binary(self):
        """Start sidecar as subprocess."""
        cmd = [self.binary_path, "--port", str(self.port)]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print(f"[SidecarManager] Started binary: {self.binary_path} (PID: {self.process.pid})")

    def _wait_for_ready(self, timeout: int, check_interval: float):
        """
        Poll health endpoint until ready.

        Args:
            timeout: Maximum seconds to wait
            check_interval: Seconds between checks

        Raises:
            TimeoutError: If sidecar doesn't become ready within timeout
        """
        start = time.time()
        url = f"http://localhost:{self.port}/health"

        while time.time() - start < timeout:
            try:
                response = requests.get(url, timeout=1.0)
                if response.status_code == 200:
                    elapsed = time.time() - start
                    print(f"[SidecarManager] Sidecar ready in {elapsed:.1f}s")
                    return
            except requests.ConnectionError:
                pass
            except requests.Timeout:
                pass

            time.sleep(check_interval)

        raise TimeoutError(
            f"Sidecar failed to start within {timeout}s. "
            f"Check logs: docker logs {self.container_name}"
        )

    def stop(self):
        """Stop sidecar process."""
        if self.container_id:
            print(f"[SidecarManager] Stopping docker container: {self.container_name}")
            subprocess.run(["docker", "stop", self.container_name], capture_output=True)
            subprocess.run(["docker", "rm", self.container_name], capture_output=True)
            self.container_id = None

        elif self.process:
            print(f"[SidecarManager] Stopping binary process (PID: {self.process.pid})")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    def is_running(self) -> bool:
        """
        Check if sidecar is running.

        Returns:
            True if sidecar is running
        """
        try:
            response = requests.get(
                f"http://localhost:{self.port}/health",
                timeout=1.0
            )
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False

    def restart(self, timeout: int = 30):
        """
        Restart sidecar.

        Args:
            timeout: Maximum seconds to wait for health check
        """
        self.stop()
        time.sleep(1)
        self.start(timeout=timeout)

    def get_logs(self, tail: int = 100) -> str:
        """
        Get sidecar logs.

        Args:
            tail: Number of lines to return

        Returns:
            Log output as string
        """
        if self.container_id or self.container_name:
            cmd = ["docker", "logs", "--tail", str(tail), self.container_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout + result.stderr

        elif self.process:
            # For binary mode, would need to capture logs during startup
            return "[Binary mode: logs not captured]"

        return "[Sidecar not running]"

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()

    def __repr__(self):
        status = "running" if self.is_running() else "stopped"
        return f"<SidecarManager mode={self.mode} port={self.port} status={status}>"


# Convenience function
def with_sidecar(
    mode: str = "docker",
    port: int = 8080,
    **kwargs
):
    """
    Convenience decorator for automatic sidecar management.

    Usage:
        @with_sidecar(mode="docker", port=8080)
        def test_certification():
            client = SwarmIt(base_url="http://localhost:8080")
            cert = client.certify("test")
            assert cert.allowed
    """
    def decorator(func):
        def wrapper(*args, **func_kwargs):
            with SidecarManager(mode=mode, port=port, **kwargs):
                return func(*args, **func_kwargs)
        return wrapper
    return decorator
