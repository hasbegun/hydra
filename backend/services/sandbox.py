"""
Sandbox execution manager for garak scans.

Creates ephemeral Docker containers with security hardening:
  - Non-root user (UID 1000)
  - Read-only rootfs
  - Memory, CPU, and PID limits
  - Network isolation (configurable)
  - Hard timeout with grace period
  - tmpfs for /tmp and /data/reports
  - Custom probe injection via read-only bind mount
  - Report extraction via ``docker cp`` before destroy

Usage as a context manager (guarantees cleanup)::

    with SandboxManager(scan_id="abc", config={...}) as sandbox:
        exit_code = sandbox.run()
        reports = sandbox.extract_reports()
"""
import io
import logging
import os
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker
from docker.errors import ContainerError, ImageNotFound, NotFound, APIError
from docker.types import Mount

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Configuration for a sandbox container.

    All fields have sensible defaults from ``config.py`` settings.
    Callers can override per-scan (e.g., longer timeout for full preset).
    """
    image: str = "hydra-sandbox:latest"
    memory_limit: str = "2g"
    cpu_count: int = 2
    pids_limit: int = 256
    timeout_seconds: int = 3600
    grace_seconds: int = 30
    tmpfs_size: str = "512m"
    network_mode: str = "none"
    reports_host_dir: str = "/data/garak_reports"
    custom_probe_paths: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_settings(cls) -> "SandboxConfig":
        """Build config from the application settings."""
        try:
            from config import settings
            return cls(
                image=settings.sandbox_image,
                memory_limit=settings.sandbox_memory_limit,
                cpu_count=settings.sandbox_cpu_count,
                pids_limit=settings.sandbox_pids_limit,
                timeout_seconds=settings.sandbox_timeout_seconds,
                grace_seconds=settings.sandbox_grace_seconds,
                tmpfs_size=settings.sandbox_tmpfs_size,
                network_mode=settings.sandbox_network_mode,
                reports_host_dir=settings.sandbox_reports_dir,
            )
        except Exception:
            return cls()


class SandboxManager:
    """Manages the lifecycle of an ephemeral garak sandbox container.

    Use as a context manager to guarantee cleanup even on failure::

        with SandboxManager(scan_id, garak_command, sandbox_config) as mgr:
            exit_code = mgr.run()
            reports = mgr.extract_reports()
    """

    def __init__(
        self,
        scan_id: str,
        garak_command: List[str],
        sandbox_config: Optional[SandboxConfig] = None,
        docker_client: Optional[docker.DockerClient] = None,
    ):
        """
        Args:
            scan_id: Unique scan identifier (used for container naming).
            garak_command: The garak CLI arguments to run inside the sandbox.
                           Example: ["--model_type", "rest", "--probes", "dan"].
            sandbox_config: Container configuration. Defaults from settings.
            docker_client: Optional Docker client (injectable for testing).
        """
        self.scan_id = scan_id
        self.garak_command = garak_command
        self.config = sandbox_config or SandboxConfig.from_settings()
        self._client = docker_client
        self._container = None
        self._container_name = f"hydra-sandbox-{scan_id}"

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    @property
    def container(self):
        """The Docker container object, or None if not created."""
        return self._container

    @property
    def container_id(self) -> Optional[str]:
        return self._container.id if self._container else None

    # --- Lifecycle ---

    def __enter__(self) -> "SandboxManager":
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.destroy()
        return False  # Do not suppress exceptions

    def create(self) -> None:
        """Create the sandbox container (does not start it)."""
        if self._container is not None:
            raise RuntimeError(f"Sandbox container already exists: {self._container_name}")

        mounts = self._build_mounts()
        tmpfs = {
            "/tmp": f"size={self.config.tmpfs_size},mode=1777",
            "/data/garak_reports": "size=256m,mode=0755,uid=1000,gid=1000",
        }

        try:
            self._container = self.client.containers.create(
                image=self.config.image,
                name=self._container_name,
                command=self.garak_command,
                user="1000:1000",
                read_only=True,
                mem_limit=self.config.memory_limit,
                nano_cpus=self.config.cpu_count * 1_000_000_000,
                pids_limit=self.config.pids_limit,
                network_mode=self.config.network_mode,
                tmpfs=tmpfs,
                mounts=mounts,
                environment=self.config.environment,
                labels={
                    "hydra.scan_id": self.scan_id,
                    "hydra.role": "sandbox",
                },
                detach=True,
            )
            logger.info(
                f"Sandbox container created: {self._container_name} "
                f"(image={self.config.image}, mem={self.config.memory_limit}, "
                f"cpu={self.config.cpu_count}, pids={self.config.pids_limit})"
            )
        except ImageNotFound:
            raise RuntimeError(
                f"Sandbox image '{self.config.image}' not found. "
                f"Build it with: docker build -f Dockerfile.sandbox -t {self.config.image} ."
            )

    def run(self) -> int:
        """Start the container and wait for it to finish (or timeout).

        Returns:
            Container exit code (0 = success).
        """
        if self._container is None:
            raise RuntimeError("Container not created. Call create() or use context manager.")

        self._container.start()
        logger.info(f"Sandbox started: {self._container_name}")

        deadline = time.monotonic() + self.config.timeout_seconds

        try:
            result = self._container.wait(
                timeout=self.config.timeout_seconds
            )
            exit_code = result.get("StatusCode", -1)
        except Exception:
            # Timeout or connection error — kill the container
            elapsed = time.monotonic() - (deadline - self.config.timeout_seconds)
            logger.warning(
                f"Sandbox {self._container_name} timed out after {elapsed:.0f}s, killing"
            )
            try:
                self._container.stop(timeout=self.config.grace_seconds)
            except Exception:
                self._container.kill()
            exit_code = -1

        self._container.reload()
        logger.info(
            f"Sandbox finished: {self._container_name} exit_code={exit_code}"
        )
        return exit_code

    def get_logs(self) -> str:
        """Get container stdout+stderr logs."""
        if self._container is None:
            return ""
        try:
            return self._container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Failed to get sandbox logs: {e}")
            return ""

    def extract_reports(self, dest_dir: Optional[str] = None) -> List[str]:
        """Copy report files from the container to the host.

        Args:
            dest_dir: Host directory for reports. Defaults to
                      ``{reports_host_dir}/{scan_id}/``.

        Returns:
            List of extracted file paths on the host.
        """
        if self._container is None:
            return []

        if dest_dir is None:
            dest_dir = os.path.join(self.config.reports_host_dir, self.scan_id)

        os.makedirs(dest_dir, exist_ok=True)
        extracted = []

        try:
            # docker cp from /data/garak_reports inside the container
            bits, stat = self._container.get_archive("/data/garak_reports")
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)

            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        # Strip the leading directory from the tar path
                        filename = os.path.basename(member.name)
                        if not filename:
                            continue
                        member.name = filename
                        tar.extract(member, path=dest_dir)
                        extracted.append(os.path.join(dest_dir, filename))

            logger.info(
                f"Extracted {len(extracted)} report files from {self._container_name} to {dest_dir}"
            )
        except NotFound:
            logger.warning(f"No reports directory in sandbox {self._container_name}")
        except Exception as e:
            logger.error(f"Failed to extract reports from {self._container_name}: {e}")

        return extracted

    def destroy(self) -> None:
        """Remove the sandbox container and all associated resources."""
        if self._container is None:
            return

        try:
            self._container.reload()
            if self._container.status in ("running", "paused"):
                logger.warning(
                    f"Sandbox {self._container_name} still {self._container.status}, "
                    f"stopping with {self.config.grace_seconds}s grace"
                )
                self._container.stop(timeout=self.config.grace_seconds)
        except NotFound:
            # Already removed
            self._container = None
            return
        except Exception as e:
            logger.warning(f"Error stopping sandbox {self._container_name}: {e}")
            try:
                self._container.kill()
            except Exception:
                pass

        try:
            self._container.remove(force=True)
            logger.info(f"Sandbox destroyed: {self._container_name}")
        except NotFound:
            pass
        except Exception as e:
            logger.error(f"Failed to remove sandbox {self._container_name}: {e}")
        finally:
            self._container = None

    # --- Introspection ---

    def get_container_info(self) -> Optional[Dict[str, Any]]:
        """Return container inspection data (for debugging/testing)."""
        if self._container is None:
            return None
        try:
            self._container.reload()
            return self._container.attrs
        except Exception:
            return None

    # --- Internal helpers ---

    def _build_mounts(self) -> List[Mount]:
        """Build Docker bind mounts for custom probes."""
        mounts = []
        for probe_path in self.config.custom_probe_paths:
            if not os.path.exists(probe_path):
                logger.warning(f"Custom probe path does not exist: {probe_path}")
                continue
            # Mount custom probes read-only into the container
            container_path = f"/home/garak/.garak/custom_probes/{os.path.basename(probe_path)}"
            mounts.append(Mount(
                target=container_path,
                source=os.path.abspath(probe_path),
                type="bind",
                read_only=True,
            ))
        return mounts
