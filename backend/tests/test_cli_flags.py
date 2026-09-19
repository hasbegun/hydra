"""
Tests for CLI flag support in ScanConfigRequest schema and ScanManager._build_command.

Covers M21 (--config_file), M22 (--report_threshold), M23 (--hit_rate),
and M24 (--collect_timing).
"""
import json
import sys
import os
import pytest

# Add backend root to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "garak_service"))

from models.schemas import ScanConfigRequest


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestConfigFileSchema:
    """M21: --config_file schema validation."""

    def test_default_is_none(self):
        config = ScanConfigRequest(target_type="ollama", target_name="llama3.2:3b")
        assert config.config_file is None

    def test_valid_path(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            config_file="/path/to/config.yaml",
        )
        assert config.config_file == "/path/to/config.yaml"

    def test_json_path(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            config_file="scan_config.json",
        )
        assert config.config_file == "scan_config.json"

    def test_serialization_roundtrip(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            config_file="/data/my_config.yaml",
        )
        data = config.model_dump()
        assert data["config_file"] == "/data/my_config.yaml"
        restored = ScanConfigRequest(**data)
        assert restored.config_file == "/data/my_config.yaml"

    def test_none_omitted_in_json(self):
        config = ScanConfigRequest(target_type="ollama", target_name="llama3.2:3b")
        data = config.model_dump(exclude_none=True)
        assert "config_file" not in data


class TestHitRateSchema:
    """M23: --hit_rate schema validation."""

    def test_default_is_none(self):
        config = ScanConfigRequest(target_type="ollama", target_name="llama3.2:3b")
        assert config.hit_rate is None

    def test_valid_value(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            hit_rate=0.5,
        )
        assert config.hit_rate == 0.5

    def test_zero_is_valid(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            hit_rate=0.0,
        )
        assert config.hit_rate == 0.0

    def test_one_is_valid(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            hit_rate=1.0,
        )
        assert config.hit_rate == 1.0

    def test_negative_rejected(self):
        with pytest.raises(Exception):
            ScanConfigRequest(
                target_type="ollama",
                target_name="llama3.2:3b",
                hit_rate=-0.1,
            )

    def test_above_one_rejected(self):
        with pytest.raises(Exception):
            ScanConfigRequest(
                target_type="ollama",
                target_name="llama3.2:3b",
                hit_rate=1.1,
            )

    def test_serialization_roundtrip(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            hit_rate=0.3,
        )
        data = config.model_dump()
        assert data["hit_rate"] == 0.3
        restored = ScanConfigRequest(**data)
        assert restored.hit_rate == 0.3

    def test_none_omitted_in_json(self):
        config = ScanConfigRequest(target_type="ollama", target_name="llama3.2:3b")
        data = config.model_dump(exclude_none=True)
        assert "hit_rate" not in data


class TestReportThresholdSchema:
    """M22: --report_threshold schema validation."""

    def test_default_is_none(self):
        config = ScanConfigRequest(target_type="ollama", target_name="llama3.2:3b")
        assert config.report_threshold is None

    def test_valid_value(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            report_threshold=0.75,
        )
        assert config.report_threshold == 0.75

    def test_zero_is_valid(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            report_threshold=0.0,
        )
        assert config.report_threshold == 0.0

    def test_one_is_valid(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            report_threshold=1.0,
        )
        assert config.report_threshold == 1.0

    def test_negative_rejected(self):
        with pytest.raises(Exception):
            ScanConfigRequest(
                target_type="ollama",
                target_name="llama3.2:3b",
                report_threshold=-0.1,
            )

    def test_above_one_rejected(self):
        with pytest.raises(Exception):
            ScanConfigRequest(
                target_type="ollama",
                target_name="llama3.2:3b",
                report_threshold=1.1,
            )

    def test_serialization_roundtrip(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            report_threshold=0.42,
        )
        data = config.model_dump()
        assert data["report_threshold"] == 0.42
        restored = ScanConfigRequest(**data)
        assert restored.report_threshold == 0.42

    def test_none_omitted_in_json(self):
        config = ScanConfigRequest(target_type="ollama", target_name="llama3.2:3b")
        data = config.model_dump(exclude_none=True)
        assert "report_threshold" not in data


class TestCollectTimingSchema:
    """M24: --collect_timing schema validation."""

    def test_default_is_false(self):
        config = ScanConfigRequest(target_type="ollama", target_name="llama3.2:3b")
        assert config.collect_timing is False

    def test_set_true(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            collect_timing=True,
        )
        assert config.collect_timing is True

    def test_set_false_explicitly(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            collect_timing=False,
        )
        assert config.collect_timing is False

    def test_serialization_roundtrip(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            collect_timing=True,
        )
        data = config.model_dump()
        assert data["collect_timing"] is True
        restored = ScanConfigRequest(**data)
        assert restored.collect_timing is True


# ---------------------------------------------------------------------------
# CLI command building tests
# ---------------------------------------------------------------------------

class TestBuildCommandConfigFile:
    """M21: --config in CLI command builder."""

    def _build(self, config_overrides: dict) -> list[str]:
        from scan_manager import ScanManager
        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "ollama", "target_name": "llama3.2:3b"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_not_present_when_none(self):
        cmd = self._build({})
        assert "--config" not in cmd

    def test_present_when_set(self):
        cmd = self._build({"config_file": "/path/to/config.yaml"})
        idx = cmd.index("--config")
        assert cmd[idx + 1] == "/path/to/config.yaml"

    def test_empty_string_not_present(self):
        cmd = self._build({"config_file": ""})
        assert "--config" not in cmd

    def test_json_file_path(self):
        cmd = self._build({"config_file": "scan.json"})
        idx = cmd.index("--config")
        assert cmd[idx + 1] == "scan.json"


class TestBuildCommandHitRate:
    """M23: --hit_rate in CLI command builder."""

    def _build(self, config_overrides: dict) -> list[str]:
        from scan_manager import ScanManager
        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "ollama", "target_name": "llama3.2:3b"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_not_present_when_none(self):
        cmd = self._build({})
        assert "--hit_rate" not in cmd

    def test_present_when_set(self):
        cmd = self._build({"hit_rate": 0.5})
        idx = cmd.index("--hit_rate")
        assert cmd[idx + 1] == "0.5"

    def test_zero_value(self):
        cmd = self._build({"hit_rate": 0.0})
        idx = cmd.index("--hit_rate")
        assert cmd[idx + 1] == "0.0"

    def test_one_value(self):
        cmd = self._build({"hit_rate": 1.0})
        idx = cmd.index("--hit_rate")
        assert cmd[idx + 1] == "1.0"


class TestBuildCommandReportThreshold:
    """M22: --report_threshold in CLI command builder."""

    def _build(self, config_overrides: dict) -> list[str]:
        """Helper: build command from a config dict via ScanManager._build_command."""
        from scan_manager import ScanManager
        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "ollama", "target_name": "llama3.2:3b"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_not_present_when_none(self):
        cmd = self._build({})
        assert "--report_threshold" not in cmd

    def test_present_when_set(self):
        cmd = self._build({"report_threshold": 0.75})
        idx = cmd.index("--report_threshold")
        assert cmd[idx + 1] == "0.75"

    def test_zero_value(self):
        cmd = self._build({"report_threshold": 0.0})
        # 0.0 is falsy in Python but `is not None` check should still include it
        idx = cmd.index("--report_threshold")
        assert cmd[idx + 1] == "0.0"

    def test_one_value(self):
        cmd = self._build({"report_threshold": 1.0})
        idx = cmd.index("--report_threshold")
        assert cmd[idx + 1] == "1.0"


class TestBuildCommandCollectTiming:
    """M24: --collect_timing in CLI command builder."""

    def _build(self, config_overrides: dict) -> list[str]:
        from scan_manager import ScanManager
        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "ollama", "target_name": "llama3.2:3b"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_not_present_when_false(self):
        cmd = self._build({})
        assert "--collect_timing" not in cmd

    def test_not_present_when_explicitly_false(self):
        cmd = self._build({"collect_timing": False})
        assert "--collect_timing" not in cmd

    def test_present_when_true(self):
        cmd = self._build({"collect_timing": True})
        assert "--collect_timing" in cmd

    def test_is_standalone_flag(self):
        """--collect_timing should be a standalone flag, not followed by a value."""
        cmd = self._build({"collect_timing": True})
        idx = cmd.index("--collect_timing")
        # Next element (if any) should be a different flag or end of list
        if idx + 1 < len(cmd):
            assert cmd[idx + 1].startswith("--") or cmd[idx + 1].startswith("-")


# ---------------------------------------------------------------------------
# Combined / integration-style tests
# ---------------------------------------------------------------------------

class TestBuildCommandCombined:
    """Test all M21-M24 flags together with other existing flags."""

    def _build(self, config_overrides: dict) -> list[str]:
        from scan_manager import ScanManager
        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "ollama", "target_name": "llama3.2:3b"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_all_four_flags_present(self):
        cmd = self._build({
            "config_file": "/path/to/config.yaml",
            "report_threshold": 0.5,
            "hit_rate": 0.3,
            "collect_timing": True,
        })
        assert "--config" in cmd
        assert "--report_threshold" in cmd
        assert "--hit_rate" in cmd
        assert "--collect_timing" in cmd
        idx = cmd.index("--config")
        assert cmd[idx + 1] == "/path/to/config.yaml"
        idx = cmd.index("--report_threshold")
        assert cmd[idx + 1] == "0.5"
        idx = cmd.index("--hit_rate")
        assert cmd[idx + 1] == "0.3"

    def test_all_flags_with_existing_flags(self):
        cmd = self._build({
            "config_file": "scan.yaml",
            "report_threshold": 0.8,
            "hit_rate": 0.5,
            "collect_timing": True,
            "timeout_per_probe": 120,
            "continue_on_error": True,
            "extended_detectors": True,
        })
        assert "--config" in cmd
        assert "--report_threshold" in cmd
        assert "--hit_rate" in cmd
        assert "--collect_timing" in cmd
        assert "--timeout_per_probe" in cmd
        # continue_on_error is a Hydra plan-level setting, NOT a garak flag
        assert "--continue_on_error" not in cmd
        assert "--extended_detectors" in cmd

    def test_parallel_flags_not_passed_to_garak(self):
        """parallel_attempts and parallel_requests must NOT be forwarded
        to garak — they cause 'daemonic processes are not allowed to have
        children' when the garak service runs inside uvicorn."""
        cmd = self._build({
            "parallel_attempts": 16,
            "parallel_requests": 10,
        })
        assert "--parallel_attempts" not in cmd
        assert "--parallel_requests" not in cmd

    def test_schema_to_command_roundtrip(self):
        """Validate schema -> dict -> command pipeline."""
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2:3b",
            config_file="/data/config.yaml",
            report_threshold=0.65,
            hit_rate=0.4,
            collect_timing=True,
            generations=3,
        )
        cmd = self._build(config.model_dump())
        assert "--config" in cmd
        assert "--report_threshold" in cmd
        assert "--hit_rate" in cmd
        assert "--collect_timing" in cmd
        idx = cmd.index("--config")
        assert cmd[idx + 1] == "/data/config.yaml"
        idx = cmd.index("--report_threshold")
        assert cmd[idx + 1] == "0.65"
        idx = cmd.index("--hit_rate")
        assert cmd[idx + 1] == "0.4"
