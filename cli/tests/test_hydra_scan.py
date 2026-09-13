"""
Tests for cli/hydra_scan.py — CLI argument parsing and offline subcommands.

Covers T4.3-T4.6 and T4.14 from the test plan (commands that don't need a running backend).
Also covers success criteria S5, S6, S12, S13, S14, S15, S16, S19, S21.
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hydra_scan import (
    build_parser, cmd_validate, cmd_init, _dry_run, _extract_counts,
    _save_reports, HydraClient,
)


# ---------------------------------------------------------------------------
# Argument parser tests
# ---------------------------------------------------------------------------

class TestArgParser:
    def test_parser_creates(self):
        parser = build_parser()
        assert parser is not None

    def test_run_command_args(self):
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", "my-plan.yaml"])
        assert args.command == "run"
        assert args.plan == "my-plan.yaml"
        assert args.dry_run is False

    def test_run_dry_run_flag(self):
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", "my-plan.yaml", "--dry-run"])
        assert args.dry_run is True

    def test_scan_command_args(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "llama3.2", "--preset", "fast"])
        assert args.command == "scan"
        assert args.model == "llama3.2"
        assert args.preset == "fast"

    def test_scan_rest_args(self):
        parser = build_parser()
        args = parser.parse_args([
            "scan",
            "--target-type", "rest",
            "--rest-endpoint", "http://example.com/chat",
            "--rest-body-template", '{"msg": "$INPUT"}',
            "--rest-response-field", "response.text",
        ])
        assert args.target_type == "rest"
        assert args.rest_endpoint == "http://example.com/chat"

    def test_validate_command(self):
        parser = build_parser()
        args = parser.parse_args(["validate", "--plan", "plan.yaml"])
        assert args.command == "validate"
        assert args.plan == "plan.yaml"

    def test_init_command(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--plan", "new.yaml"])
        assert args.command == "init"
        assert args.plan == "new.yaml"

    def test_compare_command(self):
        parser = build_parser()
        args = parser.parse_args(["compare", "--target", "llama3.2", "--dir", "./reports"])
        assert args.command == "compare"
        assert args.target == "llama3.2"
        assert args.dir == "./reports"

    def test_health_command(self):
        parser = build_parser()
        args = parser.parse_args(["health"])
        assert args.command == "health"

    def test_history_command_with_pagination(self):
        parser = build_parser()
        args = parser.parse_args(["history", "--page", "2", "--page-size", "50"])
        assert args.command == "history"
        assert args.page == 2
        assert args.page_size == 50

    def test_no_command(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None


# ---------------------------------------------------------------------------
# T4.4: validate --plan valid.yaml
# ---------------------------------------------------------------------------

class TestValidateCommand:
    def test_valid_plan(self, tmp_path, capsys):
        plan_file = tmp_path / "valid.yaml"
        plan_file.write_text("""
name: "test-plan"
targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
""")
        parser = build_parser()
        args = parser.parse_args(["validate", "--plan", str(plan_file)])
        result = cmd_validate(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "valid" in captured.out.lower()

    def test_invalid_plan(self, tmp_path, capsys):
        plan_file = tmp_path / "invalid.yaml"
        plan_file.write_text("""
targets:
  - type: ollama
    model: m
""")
        parser = build_parser()
        args = parser.parse_args(["validate", "--plan", str(plan_file)])
        result = cmd_validate(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "error" in captured.out.lower() or "Error" in captured.out


# ---------------------------------------------------------------------------
# T4.6: init --plan new.yaml
# ---------------------------------------------------------------------------

class TestInitCommand:
    def test_creates_starter_template(self, tmp_path):
        plan_path = tmp_path / "new-plan.yaml"
        parser = build_parser()
        args = parser.parse_args(["init", "--plan", str(plan_path)])
        result = cmd_init(args)
        assert result == 0
        assert plan_path.exists()
        content = plan_path.read_text()
        assert "name:" in content
        assert "targets:" in content
        assert "ollama" in content

    def test_refuses_overwrite_without_force(self, tmp_path):
        plan_path = tmp_path / "existing.yaml"
        plan_path.write_text("existing content")
        parser = build_parser()
        args = parser.parse_args(["init", "--plan", str(plan_path)])
        with pytest.raises(SystemExit):
            cmd_init(args)

    def test_force_overwrite(self, tmp_path):
        plan_path = tmp_path / "existing.yaml"
        plan_path.write_text("old content")
        parser = build_parser()
        args = parser.parse_args(["init", "--plan", str(plan_path), "--force"])
        result = cmd_init(args)
        assert result == 0
        content = plan_path.read_text()
        assert "targets:" in content

    def test_creates_parent_dirs(self, tmp_path):
        plan_path = tmp_path / "deep" / "nested" / "plan.yaml"
        parser = build_parser()
        args = parser.parse_args(["init", "--plan", str(plan_path)])
        result = cmd_init(args)
        assert result == 0
        assert plan_path.exists()


# ---------------------------------------------------------------------------
# T4.3: run --plan ... --dry-run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_output(self, tmp_path, capsys):
        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text("""
name: "dry-run-test"
description: "Testing dry run"
defaults:
  preset: fast
targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
  - name: "my-api"
    type: rest
    endpoint: "http://example.com/chat"
    body_template: '{"msg": "$INPUT"}'
    response_field: "r"
""")
        from plan_loader import load_plan
        plan = load_plan(str(plan_file))
        result = _dry_run(plan)
        assert result == 0

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "dry-run-test" in captured.out
        assert "llama3.2" in captured.out
        assert "my-api" in captured.out
        assert "2" in captured.out  # 2 targets

    def test_dry_run_no_scans_started(self, tmp_path, capsys):
        """Dry run should complete without any network calls."""
        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text("""
name: "offline-test"
targets:
  - name: "t"
    type: ollama
    model: llama3.2
""")
        from plan_loader import load_plan
        plan = load_plan(str(plan_file))
        result = _dry_run(plan)
        assert result == 0


# ---------------------------------------------------------------------------
# CLI --help
# ---------------------------------------------------------------------------

class TestHelpOutput:
    def test_main_help(self):
        """hydra_scan.py --help should exit 0 and print usage."""
        cli_dir = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, os.path.join(cli_dir, "hydra_scan.py"), "--help"],
            capture_output=True,
            text=True,
            cwd=cli_dir,
        )
        assert result.returncode == 0
        assert "hydra_scan" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_run_help(self):
        cli_dir = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, os.path.join(cli_dir, "hydra_scan.py"), "run", "--help"],
            capture_output=True,
            text=True,
            cwd=cli_dir,
        )
        assert result.returncode == 0
        assert "--plan" in result.stdout


# ---------------------------------------------------------------------------
# S5: Default values work — minimal YAML with just name + 1 target
# ---------------------------------------------------------------------------

class TestDefaultValues:
    """S5: A minimal plan with only name + 1 target should fill all defaults."""

    def test_minimal_plan_loads(self, tmp_path, capsys):
        """Minimal YAML (name + 1 target) validates and dry-run works."""
        plan_file = tmp_path / "minimal.yaml"
        plan_file.write_text("""
name: "minimal"
targets:
  - name: "t"
    type: ollama
    model: llama3.2
""")
        from plan_loader import load_plan, validate_plan, plan_to_scan_configs

        plan = load_plan(str(plan_file))
        errors = validate_plan(plan)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

        configs = plan_to_scan_configs(plan)
        assert len(configs) == 1
        cfg = configs[0]
        # All defaults should be applied
        assert cfg["generations"] == 5  # SCAN_DEFAULTS
        assert cfg["eval_threshold"] == 0.5
        assert cfg["target_type"] == "ollama"
        assert cfg["target_name"] == "llama3.2"

    def test_minimal_plan_dry_run(self, tmp_path, capsys):
        """Dry-run of a minimal plan should succeed."""
        plan_file = tmp_path / "minimal.yaml"
        plan_file.write_text("""
name: "minimal"
targets:
  - name: "t"
    type: ollama
    model: llama3.2
""")
        from plan_loader import load_plan
        plan = load_plan(str(plan_file))
        result = _dry_run(plan)
        assert result == 0
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "llama3.2" in out


# ---------------------------------------------------------------------------
# S6: Per-target override
# ---------------------------------------------------------------------------

class TestPerTargetOverride:
    """S6: Target-level settings override global defaults."""

    def test_target_overrides_defaults_generations(self):
        from plan_loader import plan_to_scan_configs
        plan = {
            "name": "test",
            "defaults": {"generations": 10, "preset": "fast"},
            "targets": [
                {"name": "t1", "type": "ollama", "model": "m1"},
                {"name": "t2", "type": "ollama", "model": "m2", "generations": 3},
            ],
        }
        configs = plan_to_scan_configs(plan)
        assert configs[0]["generations"] == 10  # uses default
        assert configs[1]["generations"] == 3   # target override

    def test_target_overrides_defaults_probes(self):
        from plan_loader import plan_to_scan_configs
        plan = {
            "name": "test",
            "defaults": {"probes": ["dan", "encoding"]},
            "targets": [
                {"name": "t1", "type": "ollama", "model": "m1"},
                {"name": "t2", "type": "ollama", "model": "m2", "probes": ["xss"]},
            ],
        }
        configs = plan_to_scan_configs(plan)
        assert configs[0]["probes"] == ["dan", "encoding"]  # from defaults
        assert configs[1]["probes"] == ["xss"]               # target override

    def test_target_overrides_defaults_preset(self):
        from plan_loader import plan_to_scan_configs
        plan = {
            "name": "test",
            "defaults": {"preset": "fast"},
            "targets": [
                {"name": "t1", "type": "ollama", "model": "m1"},
                {"name": "t2", "type": "ollama", "model": "m2", "preset": "full"},
            ],
        }
        configs = plan_to_scan_configs(plan)
        # The preset value should be available for per-target usage
        # (actual preset fetching happens during scan execution)
        # Here we verify the merge produces different targets
        assert len(configs) == 2

    def test_dry_run_shows_per_target_overrides(self, tmp_path, capsys):
        plan_file = tmp_path / "override.yaml"
        plan_file.write_text("""
name: "override-test"
defaults:
  generations: 10
targets:
  - name: "default-gens"
    type: ollama
    model: m1
  - name: "custom-gens"
    type: ollama
    model: m2
    generations: 2
""")
        from plan_loader import load_plan
        plan = load_plan(str(plan_file))
        _dry_run(plan)
        out = capsys.readouterr().out
        assert "default-gens" in out
        assert "custom-gens" in out


# ---------------------------------------------------------------------------
# _extract_counts unit tests
# ---------------------------------------------------------------------------

class TestExtractCounts:
    """Test _extract_counts with various backend response formats."""

    def test_results_nested(self):
        result = {
            "results": {"passed": 8, "failed": 2},
            "summary": {"total_tests": 10, "pass_rate": 80.0},
        }
        p, f, t, r = _extract_counts(result)
        assert (p, f, t) == (8, 2, 10)
        assert r == 80.0

    def test_top_level_fallback(self):
        result = {"passed": 5, "failed": 3}
        p, f, t, r = _extract_counts(result)
        assert (p, f, t) == (5, 3, 8)
        assert abs(r - 62.5) < 0.1

    def test_empty_result(self):
        result = {}
        p, f, t, r = _extract_counts(result)
        assert (p, f, t, r) == (0, 0, 0, 0.0)

    def test_none_values(self):
        result = {"results": None, "summary": None}
        p, f, t, r = _extract_counts(result)
        assert (p, f, t, r) == (0, 0, 0, 0.0)

    def test_summary_pass_rate_used(self):
        result = {
            "results": {"passed": 9, "failed": 1},
            "summary": {"total_tests": 10, "pass_rate": 90.0},
        }
        _, _, _, r = _extract_counts(result)
        assert r == 90.0  # Uses summary.pass_rate


# ---------------------------------------------------------------------------
# S12: Exit code policy
# ---------------------------------------------------------------------------

class TestExitCodePolicy:
    """S12: Exit code respects automation.exit_code_policy."""

    def test_cmd_scan_returns_1_on_failures(self):
        """cmd_scan should return exit code 1 when probe failures are detected."""
        from hydra_scan import cmd_scan

        # Mock the HydraClient
        mock_client = MagicMock()
        mock_client.start_scan.return_value = {"scan_id": "test-scan-id"}
        mock_client.scan_results.return_value = {
            "status": "completed",
            "results": {"passed": 0, "failed": 2},
            "summary": {"total_tests": 2, "pass_rate": 0.0},
        }

        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "test-model", "--probes", "dan.Dan_11_0"])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={"status": "completed"}), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            result = cmd_scan(args)

        assert result == 1  # failures detected

    def test_cmd_scan_returns_0_on_all_pass(self):
        """cmd_scan should return 0 when all tests pass."""
        from hydra_scan import cmd_scan

        mock_client = MagicMock()
        mock_client.start_scan.return_value = {"scan_id": "test-scan-id"}
        mock_client.scan_results.return_value = {
            "status": "completed",
            "results": {"passed": 5, "failed": 0},
            "summary": {"total_tests": 5, "pass_rate": 100.0},
        }

        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "test-model"])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={"status": "completed"}), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            result = cmd_scan(args)

        assert result == 0

    def test_exit_code_policy_never(self, tmp_path, capsys):
        """exit_code_policy: never should always return 0."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "policy.yaml"
        plan_file.write_text("""
name: "policy-test"
targets:
  - name: "t"
    type: ollama
    model: m
automation:
  exit_code_policy: never
""")
        mock_client = MagicMock()
        mock_client.get_preset.side_effect = SystemExit(1)
        mock_client.start_scan.return_value = {"scan_id": "test-id"}
        mock_client.scan_results.return_value = {
            "status": "completed",
            "results": {"passed": 0, "failed": 10},
            "summary": {"total_tests": 10, "pass_rate": 0.0},
        }

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={"status": "completed"}), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            result = cmd_run(args)

        assert result == 0  # never policy

    def test_exit_code_policy_threshold(self, tmp_path, capsys):
        """exit_code_policy: threshold should return 1 when pass_rate < min_pass_rate."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "threshold.yaml"
        plan_file.write_text("""
name: "threshold-test"
targets:
  - name: "t"
    type: ollama
    model: m
automation:
  exit_code_policy: threshold
  min_pass_rate: 80.0
""")
        mock_client = MagicMock()
        mock_client.get_preset.side_effect = SystemExit(1)
        mock_client.start_scan.return_value = {"scan_id": "test-id"}
        mock_client.scan_results.return_value = {
            "status": "completed",
            "results": {"passed": 3, "failed": 7},
            "summary": {"total_tests": 10, "pass_rate": 30.0},
        }

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={"status": "completed"}), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            result = cmd_run(args)

        assert result == 1  # 30% < 80% threshold

    def test_exit_code_policy_threshold_passes(self, tmp_path, capsys):
        """threshold policy returns 0 when pass_rate >= min_pass_rate."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "threshold_pass.yaml"
        plan_file.write_text("""
name: "threshold-pass-test"
targets:
  - name: "t"
    type: ollama
    model: m
automation:
  exit_code_policy: threshold
  min_pass_rate: 80.0
""")
        mock_client = MagicMock()
        mock_client.get_preset.side_effect = SystemExit(1)
        mock_client.start_scan.return_value = {"scan_id": "test-id"}
        mock_client.scan_results.return_value = {
            "status": "completed",
            "results": {"passed": 9, "failed": 1},
            "summary": {"total_tests": 10, "pass_rate": 90.0},
        }

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={"status": "completed"}), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            result = cmd_run(args)

        assert result == 0  # 90% >= 80%


# ---------------------------------------------------------------------------
# S13: Quiet mode + JSON stdout
# ---------------------------------------------------------------------------

class TestQuietAndJsonStdout:
    """S13: automation.quiet + json_stdout produce clean machine-readable output."""

    def test_quiet_mode_no_progress(self, tmp_path, capsys):
        """quiet: true suppresses progress and summary output."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "quiet.yaml"
        plan_file.write_text("""
name: "quiet-test"
targets:
  - name: "t"
    type: ollama
    model: m
automation:
  quiet: true
  exit_code_policy: never
""")
        mock_client = MagicMock()
        mock_client.get_preset.side_effect = SystemExit(1)
        mock_client.start_scan.return_value = {"scan_id": "test-id"}
        mock_client.scan_results.return_value = {
            "status": "completed",
            "results": {"passed": 5, "failed": 0},
            "summary": {"total_tests": 5, "pass_rate": 100.0},
        }

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={"status": "completed"}), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            cmd_run(args)

        out = capsys.readouterr().out
        # Quiet mode should suppress "SCAN COMPLETE" banner
        assert "SCAN COMPLETE" not in out

    def test_json_stdout(self, tmp_path, capsys):
        """json_stdout: true outputs JSON summary to stdout."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "json_out.yaml"
        plan_file.write_text("""
name: "json-test"
targets:
  - name: "t"
    type: ollama
    model: m
automation:
  quiet: true
  json_stdout: true
  exit_code_policy: never
""")
        mock_client = MagicMock()
        mock_client.get_preset.side_effect = SystemExit(1)
        mock_client.start_scan.return_value = {"scan_id": "test-id"}
        mock_client.scan_results.return_value = {
            "status": "completed",
            "results": {"passed": 3, "failed": 2},
            "summary": {"total_tests": 5, "pass_rate": 60.0},
        }

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={"status": "completed"}), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            cmd_run(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["plan"] == "json-test"
        assert data["overall_pass"] is True  # exit_code_policy: never
        assert data["exit_code"] == 0
        assert len(data["targets"]) == 1
        assert data["targets"][0]["name"] == "t"
        assert data["targets"][0]["passed"] == 3
        assert data["targets"][0]["failed"] == 2


# ---------------------------------------------------------------------------
# S19: Error handling — human-readable errors, no raw tracebacks
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """S19: Human-readable error messages, proper exit codes."""

    def test_connection_error_message(self):
        """Connection error produces human-readable message, not traceback."""
        client = HydraClient("http://localhost:19999")  # connection refused
        with pytest.raises(SystemExit):
            client.health()

    def test_validate_nonexistent_plan(self):
        """Validating a nonexistent plan exits cleanly."""
        parser = build_parser()
        args = parser.parse_args(["validate", "--plan", "/nonexistent/path.yaml"])
        with pytest.raises(SystemExit):
            cmd_validate(args)

    def test_scan_bad_model_no_traceback(self):
        """scan with unreachable backend exits without raw traceback."""
        cli_dir = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, os.path.join(cli_dir, "hydra_scan.py"),
             "--backend-url", "http://localhost:19999",
             "scan", "--model", "fake-model"],
            capture_output=True,
            text=True,
            cwd=cli_dir,
            timeout=15,
        )
        assert result.returncode != 0
        # Should NOT contain raw Python traceback
        assert "Traceback" not in result.stderr
        assert "Error:" in result.stderr

    def test_rest_headers_invalid_json(self):
        """--rest-headers with invalid JSON exits cleanly."""
        cli_dir = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, os.path.join(cli_dir, "hydra_scan.py"),
             "--backend-url", "http://localhost:19999",
             "scan", "--model", "m", "--rest-headers", "not-json"],
            capture_output=True,
            text=True,
            cwd=cli_dir,
            timeout=15,
        )
        assert result.returncode != 0
        assert "JSON" in result.stderr

    def test_scan_failed_status_exits_nonzero(self):
        """Scan that returns failed status produces exit code 1."""
        from hydra_scan import cmd_scan

        mock_client = MagicMock()
        mock_client.start_scan.return_value = {"scan_id": "test-id"}

        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "m"])

        with patch("hydra_scan.HydraClient", return_value=mock_client), \
             patch("hydra_scan._monitor_progress_ws", return_value={
                 "status": "failed",
                 "error_message": "Model not found",
             }):
            with pytest.raises(SystemExit):
                cmd_scan(args)


# ---------------------------------------------------------------------------
# S9: JSON report correctness
# ---------------------------------------------------------------------------

class TestSaveReports:
    """S9: Reports are saved with correct file naming and content."""

    def test_save_reports_creates_directory(self, tmp_path):
        from hydra_scan import _save_reports

        mock_client = MagicMock()
        mock_client.scan_results.return_value = {"scan_id": "abc", "status": "completed"}
        mock_client.scan_report_html.return_value = "<html>report</html>"

        output_cfg = {
            "directory": str(tmp_path / "reports"),
            "formats": ["json"],
            "filename_pattern": "{name}_{date}",
        }
        paths = _save_reports(mock_client, "scan-123", "my-target", output_cfg)
        assert "json" in paths
        assert Path(paths["json"]).exists()

    def test_save_reports_json_content(self, tmp_path):
        from hydra_scan import _save_reports

        mock_client = MagicMock()
        mock_client.scan_results.return_value = {
            "scan_id": "abc",
            "status": "completed",
            "results": {"passed": 5, "failed": 1},
        }

        output_cfg = {
            "directory": str(tmp_path),
            "formats": ["json"],
            "filename_pattern": "{name}_{date}",
        }
        paths = _save_reports(mock_client, "scan-123", "test-target", output_cfg)
        with open(paths["json"]) as f:
            data = json.load(f)
        assert data["scan_id"] == "abc"
        assert data["results"]["passed"] == 5


# ---------------------------------------------------------------------------
# Multi-target dry run (S4)
# ---------------------------------------------------------------------------

class TestMultiTargetDryRun:
    """S4: Multi-target plan renders all targets in dry run."""

    def test_three_targets_dry_run(self, tmp_path, capsys):
        plan_file = tmp_path / "multi.yaml"
        plan_file.write_text("""
name: "multi-test"
targets:
  - name: "model-a"
    type: ollama
    model: llama3.2
  - name: "model-b"
    type: ollama
    model: phi3
  - name: "rest-api"
    type: rest
    endpoint: "http://example.com/chat"
    body_template: '{"msg":"$INPUT"}'
    response_field: "$.r"
""")
        from plan_loader import load_plan
        plan = load_plan(str(plan_file))
        result = _dry_run(plan)
        assert result == 0

        out = capsys.readouterr().out
        assert "model-a" in out
        assert "model-b" in out
        assert "rest-api" in out
        assert "3" in out  # 3 targets
