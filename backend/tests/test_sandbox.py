"""
Tests for Phase 1 Week 3: Sandbox Execution.

All Docker interactions are mocked — these tests verify that the
SandboxManager passes the correct parameters to the Docker SDK.

Covers:
- Container creation with correct image and security settings
- Non-root user enforcement (UID 1000)
- Read-only rootfs flag
- Memory limit enforcement
- CPU limit enforcement
- PID limit enforcement
- Network isolation (mode=none)
- Timeout handling and container kill
- Custom probe mounted read-only
- Report extraction via get_archive
- Container cleanup on normal exit
- Container cleanup on failure (exception in context manager)
- Container naming convention
- Sandbox config from settings
- Sandbox config defaults
- tmpfs mounts for /tmp and /data/garak_reports
- Double-create raises RuntimeError
- Destroy idempotent (no container)
- Logs retrieval
"""
import io
import os
import sys
import tarfile
import tempfile
from unittest.mock import patch, MagicMock, PropertyMock, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.sandbox import SandboxManager, SandboxConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client with a mock container."""
    client = MagicMock()
    container = MagicMock()
    container.id = "abc123"
    container.name = "hydra-sandbox-test-scan"
    container.status = "created"
    container.attrs = {
        "Id": "abc123",
        "State": {"Status": "created"},
        "HostConfig": {"ReadonlyRootfs": True},
    }
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = b"scan output here"
    client.containers.create.return_value = container
    return client, container


@pytest.fixture
def sandbox(mock_docker_client):
    """Create a SandboxManager with mocked Docker client."""
    client, container = mock_docker_client
    return SandboxManager(
        scan_id="test-scan",
        garak_command=["--model_type", "rest", "--probes", "dan"],
        sandbox_config=SandboxConfig(
            image="hydra-sandbox:test",
            memory_limit="2g",
            cpu_count=2,
            pids_limit=256,
            timeout_seconds=3600,
            grace_seconds=30,
            tmpfs_size="512m",
            network_mode="none",
            reports_host_dir="/tmp/test-reports",
        ),
        docker_client=client,
    )


# ---------------------------------------------------------------------------
# Container creation
# ---------------------------------------------------------------------------

class TestSandboxCreatesContainer:
    """Container is created with the correct image and config."""

    def test_creates_container_with_correct_image(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["image"] == "hydra-sandbox:test"

    def test_container_name_includes_scan_id(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["name"] == "hydra-sandbox-test-scan"

    def test_passes_garak_command(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["command"] == ["--model_type", "rest", "--probes", "dan"]

    def test_sets_detach_true(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["detach"] is True

    def test_sets_labels(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        labels = create_call.kwargs["labels"]
        assert labels["hydra.scan_id"] == "test-scan"
        assert labels["hydra.role"] == "sandbox"


class TestSandboxRunsAsNonroot:
    """Container user is set to UID 1000 (non-root)."""

    def test_user_is_1000(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["user"] == "1000:1000"


class TestSandboxReadOnlyRootfs:
    """Read-only rootfs is enabled."""

    def test_read_only_flag(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["read_only"] is True


class TestSandboxMemoryLimit:
    """Memory limit is enforced at 2GB."""

    def test_memory_limit_set(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["mem_limit"] == "2g"

    def test_custom_memory_limit(self, mock_docker_client):
        client, container = mock_docker_client
        mgr = SandboxManager(
            scan_id="s1",
            garak_command=["--probes", "dan"],
            sandbox_config=SandboxConfig(memory_limit="4g"),
            docker_client=client,
        )
        mgr.create()
        assert client.containers.create.call_args.kwargs["mem_limit"] == "4g"


class TestSandboxCPULimit:
    """CPU limit is enforced."""

    def test_cpu_count_converted_to_nanocpus(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        # 2 CPUs = 2 * 1e9 nanocpus
        assert create_call.kwargs["nano_cpus"] == 2_000_000_000


class TestSandboxPIDLimit:
    """PID limit is enforced at 256."""

    def test_pids_limit_set(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["pids_limit"] == 256


class TestSandboxNetworkRestricted:
    """Network is isolated by default (mode=none)."""

    def test_network_mode_none(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["network_mode"] == "none"

    def test_custom_network_for_external_target(self, mock_docker_client):
        """When scanning an external target, network mode can be overridden."""
        client, container = mock_docker_client
        mgr = SandboxManager(
            scan_id="s1",
            garak_command=["--probes", "dan"],
            sandbox_config=SandboxConfig(network_mode="bridge"),
            docker_client=client,
        )
        mgr.create()
        assert client.containers.create.call_args.kwargs["network_mode"] == "bridge"


class TestSandboxTmpfs:
    """tmpfs mounts for /tmp and /data/garak_reports."""

    def test_tmpfs_mounts(self, sandbox, mock_docker_client):
        client, _ = mock_docker_client
        sandbox.create()
        create_call = client.containers.create.call_args
        tmpfs = create_call.kwargs["tmpfs"]
        assert "/tmp" in tmpfs
        assert "/data/garak_reports" in tmpfs
        assert "512m" in tmpfs["/tmp"]


class TestSandboxTimeoutKillsContainer:
    """Container is killed after timeout."""

    def test_timeout_triggers_stop(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        # Simulate timeout by making wait() raise
        container.wait.side_effect = Exception("timeout")
        container.status = "running"

        sandbox.create()
        exit_code = sandbox.run()

        assert exit_code == -1
        # Container should be stopped with grace period
        container.stop.assert_called_once_with(timeout=30)

    def test_timeout_kills_if_stop_fails(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        container.wait.side_effect = Exception("timeout")
        container.stop.side_effect = Exception("stop failed")

        sandbox.create()
        exit_code = sandbox.run()

        assert exit_code == -1
        container.kill.assert_called_once()


class TestSandboxCustomProbeMountedReadonly:
    """Custom probe files are bind-mounted read-only."""

    def test_probe_mounted_readonly(self, mock_docker_client, tmp_path):
        client, container = mock_docker_client

        # Create a fake probe file
        probe_file = tmp_path / "my_probe.py"
        probe_file.write_text("class MyProbe: pass")

        mgr = SandboxManager(
            scan_id="s1",
            garak_command=["--probes", "custom"],
            sandbox_config=SandboxConfig(
                custom_probe_paths=[str(probe_file)],
            ),
            docker_client=client,
        )
        mgr.create()

        create_call = client.containers.create.call_args
        mounts = create_call.kwargs["mounts"]
        assert len(mounts) == 1
        mount = mounts[0]
        assert mount["ReadOnly"] is True
        assert "my_probe.py" in mount["Target"]

    def test_missing_probe_path_skipped(self, mock_docker_client):
        client, container = mock_docker_client
        mgr = SandboxManager(
            scan_id="s1",
            garak_command=["--probes", "custom"],
            sandbox_config=SandboxConfig(
                custom_probe_paths=["/nonexistent/probe.py"],
            ),
            docker_client=client,
        )
        mgr.create()
        create_call = client.containers.create.call_args
        assert create_call.kwargs["mounts"] == []


class TestSandboxReportsExtracted:
    """Reports are copied from container before destroy."""

    def test_reports_extracted(self, sandbox, mock_docker_client, tmp_path):
        client, container = mock_docker_client

        # Build a tar archive that simulates get_archive output
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            # Add a fake report file
            content = b'{"probe": "dan", "passed": true}'
            info = tarfile.TarInfo(name="garak_reports/report.jsonl")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

            # Add an HTML report
            html = b"<html>report</html>"
            info2 = tarfile.TarInfo(name="garak_reports/report.html")
            info2.size = len(html)
            tar.addfile(info2, io.BytesIO(html))

        tar_buffer.seek(0)
        container.get_archive.return_value = (iter([tar_buffer.read()]), {})

        sandbox.create()
        dest = str(tmp_path / "reports")
        extracted = sandbox.extract_reports(dest_dir=dest)

        assert len(extracted) == 2
        assert any("report.jsonl" in f for f in extracted)
        assert any("report.html" in f for f in extracted)

    def test_no_reports_dir_returns_empty(self, sandbox, mock_docker_client, tmp_path):
        client, container = mock_docker_client
        from docker.errors import NotFound
        container.get_archive.side_effect = NotFound("not found")

        sandbox.create()
        extracted = sandbox.extract_reports(dest_dir=str(tmp_path))
        assert extracted == []


class TestSandboxDestroyedAfterScan:
    """Container is removed after context manager exits."""

    def test_cleanup_on_normal_exit(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        container.status = "exited"

        with sandbox:
            pass  # create() called by __enter__

        container.remove.assert_called_once_with(force=True)

    def test_container_is_none_after_destroy(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        container.status = "exited"

        sandbox.create()
        sandbox.destroy()
        assert sandbox.container is None


class TestSandboxCleanupOnFailure:
    """Container is destroyed even when the scan raises an exception."""

    def test_cleanup_on_exception(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        container.status = "running"

        with pytest.raises(ValueError):
            with sandbox:
                raise ValueError("simulated crash")

        # Container should still be cleaned up
        container.stop.assert_called_once()
        container.remove.assert_called_once_with(force=True)

    def test_cleanup_on_run_failure(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        container.wait.return_value = {"StatusCode": 1}
        container.status = "exited"

        sandbox.create()
        exit_code = sandbox.run()

        assert exit_code == 1
        # Cleanup should work after failed run
        sandbox.destroy()
        container.remove.assert_called_once_with(force=True)


class TestSandboxDoubleCreate:
    """Creating a container twice raises RuntimeError."""

    def test_double_create_raises(self, sandbox, mock_docker_client):
        sandbox.create()
        with pytest.raises(RuntimeError, match="already exists"):
            sandbox.create()


class TestSandboxDestroyIdempotent:
    """Destroying when no container exists is a no-op."""

    def test_destroy_without_container(self, sandbox):
        sandbox.destroy()  # Should not raise


class TestSandboxImageNotFound:
    """Missing sandbox image gives a clear error."""

    def test_missing_image_raises(self, mock_docker_client):
        from docker.errors import ImageNotFound
        client, _ = mock_docker_client
        client.containers.create.side_effect = ImageNotFound("not found")

        mgr = SandboxManager(
            scan_id="s1",
            garak_command=["--probes", "dan"],
            docker_client=client,
        )
        with pytest.raises(RuntimeError, match="not found"):
            mgr.create()


class TestSandboxLogs:
    """Container logs are retrievable."""

    def test_get_logs(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        sandbox.create()
        logs = sandbox.get_logs()
        assert logs == "scan output here"

    def test_logs_without_container(self, sandbox):
        assert sandbox.get_logs() == ""


class TestSandboxConfig:
    """SandboxConfig construction."""

    def test_defaults(self):
        cfg = SandboxConfig()
        assert cfg.image == "hydra-sandbox:latest"
        assert cfg.memory_limit == "2g"
        assert cfg.cpu_count == 2
        assert cfg.pids_limit == 256
        assert cfg.timeout_seconds == 3600
        assert cfg.grace_seconds == 30
        assert cfg.network_mode == "none"

    def test_from_settings(self):
        with patch("services.sandbox.SandboxConfig.from_settings") as mock_fs:
            mock_fs.return_value = SandboxConfig(
                image="custom:v1", memory_limit="4g",
            )
            cfg = SandboxConfig.from_settings()
            assert cfg.image == "custom:v1"
            assert cfg.memory_limit == "4g"

    def test_custom_probe_paths_default_empty(self):
        cfg = SandboxConfig()
        assert cfg.custom_probe_paths == []

    def test_environment_default_empty(self):
        cfg = SandboxConfig()
        assert cfg.environment == {}


class TestSandboxContainerInfo:
    """Container inspection for debugging."""

    def test_get_container_info(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        sandbox.create()
        info = sandbox.get_container_info()
        assert info is not None
        assert info["Id"] == "abc123"

    def test_no_info_without_container(self, sandbox):
        assert sandbox.get_container_info() is None


class TestSandboxRunExitCodes:
    """Run returns the correct exit code."""

    def test_success_exit_code(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        container.wait.return_value = {"StatusCode": 0}

        sandbox.create()
        assert sandbox.run() == 0

    def test_failure_exit_code(self, sandbox, mock_docker_client):
        client, container = mock_docker_client
        container.wait.return_value = {"StatusCode": 137}

        sandbox.create()
        assert sandbox.run() == 137

    def test_run_without_create_raises(self, sandbox):
        with pytest.raises(RuntimeError, match="not created"):
            sandbox.run()
