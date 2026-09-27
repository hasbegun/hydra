"""
Tests for cli/hydra_scan.py — CLI argument parsing and offline subcommands.

Covers T4.3-T4.6 and T4.14 from the test plan (commands that don't need a running backend).
Also covers success criteria S5, S6, S12, S13, S14, S15, S16, S19, S21.
"""
import contextlib
import os
import sys
import subprocess
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hydra_scan import (
    build_parser, cmd_validate, cmd_init, cmd_scan, cmd_compare, cmd_run,
    _dry_run, _save_reports, _sanitize_filename, _render_progress_line,
    _load_and_validate_plan, _print_summary, _resolve_auth_token,
    _inject_auth_headers, _clean_cookie, _extract_jwt_claims,
    _check_token_expiry, _load_checkpoint, _save_checkpoint,
    _clear_checkpoint, _merge_probe_results, _get_token_remaining,
    HydraClient,
)
from comparator import extract_counts


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _make_mock_client(
    scan_results=None,
    scan_id="test-id",
    preset_available=False,
):
    """Create a pre-configured MagicMock HydraClient for scan tests.

    Args:
        scan_results: Dict to return from scan_results(). If None, uses a
            default with 5 passed / 0 failed.
        scan_id: The scan_id returned by start_scan().
        preset_available: If False, get_preset raises SystemExit (preset
            not found). If True, returns an empty preset config.
    """
    client = MagicMock()
    client.start_scan.return_value = {"scan_id": scan_id}
    client.scan_results.return_value = scan_results or {
        "status": "completed",
        "results": {"passed": 5, "failed": 0},
        "summary": {"total_tests": 5, "pass_rate": 100.0},
    }
    client.scan_report_html.return_value = b"<html><body>report</body></html>"
    if not preset_available:
        client.get_preset.side_effect = SystemExit(1)
    else:
        client.get_preset.return_value = {"config": {}}
    return client


@contextlib.contextmanager
def _patched_scan(mock_client, final_status=None, saved_reports=None):
    """Context manager that patches HydraClient, progress monitor, and
    report saving so that ``cmd_run`` / ``cmd_scan`` can execute without a
    real backend.
    """
    with patch("hydra_scan.HydraClient", return_value=mock_client), \
         patch("hydra_scan._monitor_progress_ws",
               return_value=final_status or {"status": "completed"}), \
         patch("hydra_scan._save_reports",
               return_value=saved_reports or {"json": "/tmp/r.json"}):
        yield


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
        output = captured.out + captured.err
        assert "error" in output.lower()


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
# extract_counts unit tests
# ---------------------------------------------------------------------------

class TestExtractCounts:
    """Test extract_counts with various backend response formats."""

    def test_results_nested(self):
        result = {
            "results": {"passed": 8, "failed": 2},
            "summary": {"total_tests": 10, "pass_rate": 80.0},
        }
        p, f, t, r = extract_counts(result)
        assert (p, f, t) == (8, 2, 10)
        assert r == 80.0

    def test_top_level_fallback(self):
        result = {"passed": 5, "failed": 3}
        p, f, t, r = extract_counts(result)
        assert (p, f, t) == (5, 3, 8)
        assert abs(r - 62.5) < 0.1

    def test_empty_result(self):
        result = {}
        p, f, t, r = extract_counts(result)
        assert (p, f, t, r) == (0, 0, 0, 0.0)

    def test_none_values(self):
        result = {"results": None, "summary": None}
        p, f, t, r = extract_counts(result)
        assert (p, f, t, r) == (0, 0, 0, 0.0)

    def test_summary_pass_rate_used(self):
        result = {
            "results": {"passed": 9, "failed": 1},
            "summary": {"total_tests": 10, "pass_rate": 90.0},
        }
        _, _, _, r = extract_counts(result)
        assert r == 90.0  # Uses summary.pass_rate


# ---------------------------------------------------------------------------
# S12: Exit code policy
# ---------------------------------------------------------------------------

class TestExitCodePolicy:
    """S12: Exit code respects automation.exit_code_policy."""

    def test_cmd_scan_returns_1_on_failures(self):
        """cmd_scan should return exit code 1 when probe failures are detected."""
        client = _make_mock_client(scan_results={
            "status": "completed",
            "results": {"passed": 0, "failed": 2},
            "summary": {"total_tests": 2, "pass_rate": 0.0},
        })
        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "test-model", "--probes", "dan.Dan_11_0"])

        with _patched_scan(client):
            result = cmd_scan(args)
        assert result == 1

    def test_cmd_scan_returns_0_on_all_pass(self):
        """cmd_scan should return 0 when all tests pass."""
        client = _make_mock_client()
        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "test-model"])

        with _patched_scan(client):
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
        client = _make_mock_client(scan_results={
            "status": "completed",
            "results": {"passed": 0, "failed": 10},
            "summary": {"total_tests": 10, "pass_rate": 0.0},
        })
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
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
        client = _make_mock_client(scan_results={
            "status": "completed",
            "results": {"passed": 3, "failed": 7},
            "summary": {"total_tests": 10, "pass_rate": 30.0},
        })
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
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
        client = _make_mock_client(scan_results={
            "status": "completed",
            "results": {"passed": 9, "failed": 1},
            "summary": {"total_tests": 10, "pass_rate": 90.0},
        })
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
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
        client = _make_mock_client()
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
            cmd_run(args)

        out = capsys.readouterr().out
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
        client = _make_mock_client(scan_results={
            "status": "completed",
            "results": {"passed": 3, "failed": 2},
            "summary": {"total_tests": 5, "pass_rate": 60.0},
        })
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
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
        client = _make_mock_client()

        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "m"])

        with _patched_scan(client, final_status={
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


# ---------------------------------------------------------------------------
# Filename sanitization (security)
# ---------------------------------------------------------------------------

class TestFilenameSanitization:
    """Prevent path traversal and special characters in report filenames."""

    def test_path_traversal_slashes(self):
        assert "/" not in _sanitize_filename("../../etc/passwd")
        assert "\\" not in _sanitize_filename("..\\..\\windows\\system32")

    def test_normal_names_unchanged(self):
        assert _sanitize_filename("llama3.2") == "llama3.2"
        assert _sanitize_filename("qwen2.5-1.5b") == "qwen2.5-1.5b"
        assert _sanitize_filename("my-model") == "my-model"

    def test_colon_in_model_name(self):
        """Ollama model names like 'qwen2.5:1.5b' contain colons."""
        result = _sanitize_filename("qwen2.5:1.5b")
        assert ":" not in result
        assert len(result) > 0

    def test_empty_string(self):
        assert _sanitize_filename("") == "unnamed"

    def test_null_bytes(self):
        assert "\0" not in _sanitize_filename("model\0name")

    def test_special_characters(self):
        result = _sanitize_filename('model<>:"|?*name')
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_save_reports_uses_sanitized_name(self, tmp_path):
        """_save_reports uses sanitized filename, not raw target_name."""
        mock_client = MagicMock()
        mock_client.scan_results.return_value = {"scan_id": "abc", "status": "ok"}

        output_cfg = {
            "directory": str(tmp_path),
            "formats": ["json"],
            "filename_pattern": "{name}_{date}",
        }
        # Malicious target name with path traversal
        paths = _save_reports(mock_client, "scan-123", "../../etc/passwd", output_cfg)

        # File should be saved INSIDE tmp_path, not outside
        json_path = Path(paths["json"])
        assert json_path.parent == tmp_path
        assert "/" not in json_path.name
        assert ".." not in json_path.name


# ---------------------------------------------------------------------------
# _render_progress_line (refactored progress bar)
# ---------------------------------------------------------------------------

class TestRenderProgressLine:
    """Verify the extracted progress bar rendering helper."""

    def test_basic_rendering(self, capsys):
        _render_progress_line({"progress": 50.0, "passed": 3, "failed": 1})
        out = capsys.readouterr().out
        assert "50.0%" in out
        assert "Pass: 3" in out
        assert "Fail: 1" in out

    def test_with_probe_name(self, capsys):
        _render_progress_line({
            "progress": 75.0,
            "current_probe": "dan.Dan_11_0",
            "passed": 10,
            "failed": 2,
        })
        out = capsys.readouterr().out
        assert "75.0%" in out
        assert "dan.Dan_11_0" in out

    def test_zero_progress(self, capsys):
        _render_progress_line({"progress": 0})
        out = capsys.readouterr().out
        assert "0.0%" in out
        # Bar should be all dashes at 0%
        assert "--------------------" in out

    def test_full_progress(self, capsys):
        _render_progress_line({"progress": 100})
        out = capsys.readouterr().out
        assert "100.0%" in out
        # Bar should be all hashes at 100%
        assert "####################" in out

    def test_empty_data(self, capsys):
        """Should not crash on empty data dict."""
        _render_progress_line({})
        out = capsys.readouterr().out
        assert "0.0%" in out


# ---------------------------------------------------------------------------
# _load_and_validate_plan (refactored plan loading)
# ---------------------------------------------------------------------------

class TestLoadAndValidatePlan:
    """Verify the extracted plan loading and validation helper."""

    def test_valid_plan(self, tmp_path):
        plan_file = tmp_path / "good.yaml"
        plan_file.write_text("""
name: test
targets:
  - name: t
    type: ollama
    model: m
""")
        plan = _load_and_validate_plan(str(plan_file))
        assert plan is not None
        assert plan["name"] == "test"

    def test_invalid_plan_returns_none(self, tmp_path):
        plan_file = tmp_path / "bad.yaml"
        plan_file.write_text("""
targets:
  - type: ollama
""")
        plan = _load_and_validate_plan(str(plan_file))
        assert plan is None

    def test_nonexistent_file(self):
        with pytest.raises(SystemExit):
            _load_and_validate_plan("/no/such/file.yaml")

    def test_empty_yaml(self, tmp_path):
        plan_file = tmp_path / "empty.yaml"
        plan_file.write_text("")
        with pytest.raises(SystemExit):
            _load_and_validate_plan(str(plan_file))


# ---------------------------------------------------------------------------
# _print_summary output formatting
# ---------------------------------------------------------------------------

class TestPrintSummary:
    """Tests for _print_summary output formatting."""

    def test_basic_output(self, capsys):
        result = {
            "status": "completed",
            "results": {"passed": 8, "failed": 2},
            "summary": {"total_tests": 10, "pass_rate": 80.0},
        }
        _print_summary(result, "my-model", {"json": "/tmp/r.json"})
        out = capsys.readouterr().out
        assert "SCAN COMPLETE: my-model" in out
        assert "Total:      10 tests" in out
        assert "Passed:     8" in out
        assert "Failed:     2" in out
        assert "Pass Rate:  80.0%" in out
        assert "/tmp/r.json" in out

    def test_no_reports(self, capsys):
        result = {"status": "completed", "results": {"passed": 0, "failed": 0}}
        _print_summary(result, "target", {})
        out = capsys.readouterr().out
        assert "SCAN COMPLETE" in out
        assert "JSON:" not in out
        assert "HTML:" not in out

    def test_html_report_shown(self, capsys):
        result = {"status": "completed"}
        _print_summary(result, "t", {"html": "/tmp/r.html"})
        out = capsys.readouterr().out
        assert "/tmp/r.html" in out


# ---------------------------------------------------------------------------
# _save_reports pattern KeyError fallback
# ---------------------------------------------------------------------------

class TestSaveReportsPatternFallback:
    """Verify _save_reports handles invalid filename_pattern gracefully."""

    def test_bad_pattern_fallback(self, tmp_path):
        mock_client = type("C", (), {
            "scan_results": lambda self, sid: {"status": "completed"},
            "scan_report_html": lambda self, sid: b"<html></html>",
        })()
        output_cfg = {
            "directory": str(tmp_path),
            "formats": ["json"],
            "filename_pattern": "{name}_{unknown_field}",
        }
        paths = _save_reports(mock_client, "scan-1", "test-target", output_cfg)
        assert "json" in paths
        json_path = Path(paths["json"])
        assert json_path.exists()
        assert "test-target" in json_path.stem


# ---------------------------------------------------------------------------
# Interim report saving
# ---------------------------------------------------------------------------

class TestInterimReports:
    """Verify interim reports are saved during scan progress."""

    def test_save_interim_report_creates_file(self, tmp_path):
        from hydra_scan import _save_interim_report

        mock_client = MagicMock()
        mock_client.scan_results.return_value = {"partial": True}

        output_cfg = {"directory": str(tmp_path)}
        status = {"status": "running", "progress": 42.0, "passed": 3, "failed": 1}

        path = _save_interim_report(mock_client, "scan-1", "my-target", output_cfg, status)
        assert path is not None
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert data["status"] == "running"
        assert data["progress"] == 42.0
        assert data["passed"] == 3
        assert data["failed"] == 1
        assert data["target"] == "my-target"
        assert "updated_at" in data

    def test_interim_overwrites_previous(self, tmp_path):
        from hydra_scan import _save_interim_report

        mock_client = MagicMock()
        mock_client.scan_results.return_value = {}

        output_cfg = {"directory": str(tmp_path)}

        _save_interim_report(mock_client, "s1", "tgt", output_cfg,
                             {"progress": 10, "passed": 0, "failed": 0})
        _save_interim_report(mock_client, "s1", "tgt", output_cfg,
                             {"progress": 50, "passed": 5, "failed": 2})

        from hydra_scan import _interim_report_path
        data = json.loads(_interim_report_path("tgt", output_cfg).read_text())
        assert data["progress"] == 50
        assert data["passed"] == 5

    def test_cleanup_interim_report(self, tmp_path):
        from hydra_scan import _save_interim_report, _cleanup_interim_report, _interim_report_path

        mock_client = MagicMock()
        mock_client.scan_results.return_value = {}
        output_cfg = {"directory": str(tmp_path)}

        _save_interim_report(mock_client, "s1", "tgt", output_cfg,
                             {"progress": 100, "passed": 10, "failed": 0})
        assert _interim_report_path("tgt", output_cfg).exists()

        _cleanup_interim_report("tgt", output_cfg)
        assert not _interim_report_path("tgt", output_cfg).exists()

    def test_interim_survives_results_api_failure(self, tmp_path):
        from hydra_scan import _save_interim_report

        mock_client = MagicMock()
        mock_client.scan_results.side_effect = Exception("API down")

        output_cfg = {"directory": str(tmp_path)}
        status = {"status": "running", "progress": 25, "passed": 1, "failed": 0}

        path = _save_interim_report(mock_client, "s1", "tgt", output_cfg, status)
        assert path is not None
        data = json.loads(Path(path).read_text())
        # Falls back to status data when results API fails
        assert data["progress"] == 25


# ---------------------------------------------------------------------------
# cmd_scan preset override logic
# ---------------------------------------------------------------------------

class TestCmdScanPresetOverride:
    """Verify that preset values fill in when user doesn't explicitly set params."""

    def test_no_explicit_generations_uses_default(self):
        """When --generations is not passed, config should use default of 5."""
        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "test-model"])
        # args.generations should be None (not 5) so preset can override
        assert args.generations is None
        assert args.eval_threshold is None

    def test_explicit_generations_preserved(self):
        """When --generations is passed, it should be set."""
        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "test-model", "--generations", "10"])
        assert args.generations == 10


# ---------------------------------------------------------------------------
# cmd_compare — finding and comparing result files
# ---------------------------------------------------------------------------

class TestCmdCompare:
    """Tests for the compare subcommand."""

    def test_compare_two_files(self, tmp_path, capsys):
        """Compare should read two JSON files and print a comparison table."""
        import time as time_mod

        r1 = {"results": {"passed": 8, "failed": 2}, "summary": {"pass_rate": 80.0}}
        r2 = {"results": {"passed": 9, "failed": 1}, "summary": {"pass_rate": 90.0}}

        f1 = tmp_path / "model_2026-01-01.json"
        f1.write_text(json.dumps(r1))
        time_mod.sleep(0.05)  # ensure different mtime
        f2 = tmp_path / "model_2026-01-02.json"
        f2.write_text(json.dumps(r2))

        parser = build_parser()
        args = parser.parse_args([
            "compare", "--target", "model", "--dir", str(tmp_path),
        ])
        result = cmd_compare(args)
        captured = capsys.readouterr()
        assert "COMPARISON" in captured.out
        assert result == 0  # no regression (90% -> 80% is improvement when newer is f2)

    def test_compare_insufficient_files(self, tmp_path):
        """Should exit with error if fewer than 2 result files exist."""
        f1 = tmp_path / "model_2026-01-01.json"
        f1.write_text("{}")

        parser = build_parser()
        args = parser.parse_args([
            "compare", "--target", "model", "--dir", str(tmp_path),
        ])
        with pytest.raises(SystemExit):
            cmd_compare(args)

    def test_compare_nonexistent_dir(self):
        """Should exit with error for a nonexistent directory."""
        parser = build_parser()
        args = parser.parse_args([
            "compare", "--target", "x", "--dir", "/no/such/dir",
        ])
        with pytest.raises(SystemExit):
            cmd_compare(args)

    def test_compare_detects_regression(self, tmp_path, capsys):
        """Should return 1 when regression exceeds threshold."""
        import time as time_mod

        r_old = {"results": {"passed": 9, "failed": 1}, "summary": {"pass_rate": 90.0}}
        r_new = {"results": {"passed": 5, "failed": 5}, "summary": {"pass_rate": 50.0}}

        f1 = tmp_path / "model_2026-01-01.json"
        f1.write_text(json.dumps(r_old))
        time_mod.sleep(0.05)
        f2 = tmp_path / "model_2026-01-02.json"
        f2.write_text(json.dumps(r_new))

        parser = build_parser()
        args = parser.parse_args([
            "compare", "--target", "model", "--dir", str(tmp_path),
            "--threshold", "5.0",
        ])
        result = cmd_compare(args)
        assert result == 1  # regression: 90% -> 50% exceeds 5% threshold


# ---------------------------------------------------------------------------
# S2/S18: Full cmd_run and cmd_scan flow tests (mocked backend)
# ---------------------------------------------------------------------------

class TestCmdRunFullFlow:
    """Test the full cmd_run flow: load plan, start scan, monitor, save, summarise."""

    def test_plan_scan_saves_reports_and_prints_summary(self, tmp_path, capsys):
        """S2: Full plan scan produces reports and summary output."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text("""
name: "flow-test"
targets:
  - name: "test-model"
    type: ollama
    model: test-model
output:
  directory: "{out_dir}"
  formats: [json]
""".format(out_dir=str(tmp_path / "reports")))

        scan_result = {
            "status": "completed",
            "results": {"passed": 7, "failed": 3},
            "summary": {"total_tests": 10, "pass_rate": 70.0},
        }
        client = _make_mock_client(scan_results=scan_result)

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        # Use real _save_reports (not mocked) to verify file creation
        with patch("hydra_scan.HydraClient", return_value=client), \
             patch("hydra_scan._monitor_progress_ws",
                   return_value={"status": "completed"}):
            result = cmd_run(args)

        # Exit code: any_fail policy (default), 3 failures -> exit 1
        assert result == 1

        # Summary printed
        out = capsys.readouterr().out
        assert "SCAN COMPLETE: test-model" in out
        assert "Passed:     7" in out
        assert "Failed:     3" in out
        assert "Pass Rate:  70.0%" in out

        # Report file created
        reports_dir = tmp_path / "reports"
        json_files = list(reports_dir.glob("*.json"))
        assert len(json_files) == 1
        with open(json_files[0]) as f:
            saved = json.load(f)
        assert saved["status"] == "completed"

    def test_plan_scan_with_comparison(self, tmp_path, capsys):
        """S11: Plan scan with comparison enabled detects changes."""
        from hydra_scan import cmd_run
        import time as time_mod

        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        # Create a "previous" result file
        prev_result = {
            "results": {"passed": 9, "failed": 1},
            "summary": {"pass_rate": 90.0},
        }
        prev_file = reports_dir / "test-model_2026-01-01.json"
        prev_file.write_text(json.dumps(prev_result))
        time_mod.sleep(0.05)  # ensure different mtime

        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text("""
name: "compare-test"
targets:
  - name: "test-model"
    type: ollama
    model: test-model
output:
  directory: "{out_dir}"
  formats: [json]
compare:
  enabled: true
  regression_threshold: 5.0
automation:
  exit_code_policy: never
""".format(out_dir=str(reports_dir)))

        scan_result = {
            "status": "completed",
            "results": {"passed": 5, "failed": 5},
            "summary": {"pass_rate": 50.0},
        }
        client = _make_mock_client(scan_results=scan_result)

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with patch("hydra_scan.HydraClient", return_value=client), \
             patch("hydra_scan._monitor_progress_ws",
                   return_value={"status": "completed"}):
            result = cmd_run(args)

        assert result == 0  # exit_code_policy: never

        out = capsys.readouterr().out
        # Should show comparison output
        assert "COMPARISON" in out or "No previous result" in out

    def test_plan_scan_failed_target_continues(self, tmp_path, capsys):
        """cmd_run continues to next target when one fails."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "multi.yaml"
        plan_file.write_text("""
name: "multi-test"
targets:
  - name: "fail-target"
    type: ollama
    model: fail-model
  - name: "pass-target"
    type: ollama
    model: pass-model
automation:
  exit_code_policy: never
""")
        client = _make_mock_client()

        call_count = [0]
        def mock_monitor(client_arg, scan_id, quiet=False, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"status": "failed", "error_message": "Model not found"}
            return {"status": "completed"}

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with patch("hydra_scan.HydraClient", return_value=client), \
             patch("hydra_scan._monitor_progress_ws", side_effect=mock_monitor), \
             patch("hydra_scan._save_reports", return_value={"json": "/tmp/r.json"}):
            result = cmd_run(args)

        # Both targets attempted
        assert call_count[0] == 2
        # Failed target logged to stderr
        captured = capsys.readouterr()
        assert "Scan failed" in captured.err

    def test_json_stdout_multi_target(self, tmp_path, capsys):
        """S13: JSON stdout with multiple targets includes all results."""
        from hydra_scan import cmd_run

        plan_file = tmp_path / "multi_json.yaml"
        plan_file.write_text("""
name: "multi-json"
targets:
  - name: "target-a"
    type: ollama
    model: model-a
  - name: "target-b"
    type: ollama
    model: model-b
automation:
  quiet: true
  json_stdout: true
  exit_code_policy: never
""")
        client = _make_mock_client(scan_results={
            "status": "completed",
            "results": {"passed": 4, "failed": 1},
            "summary": {"total_tests": 5, "pass_rate": 80.0},
        })

        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
            cmd_run(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["plan"] == "multi-json"
        assert len(data["targets"]) == 2
        assert data["targets"][0]["name"] == "target-a"
        assert data["targets"][1]["name"] == "target-b"
        assert all(t["passed"] == 4 for t in data["targets"])


class TestCmdScanFullFlow:
    """Test the full cmd_scan flow: start, monitor, save, summarise."""

    def test_ad_hoc_scan_full_flow(self, tmp_path, capsys):
        """S18: Ad-hoc scan produces summary and saves reports."""
        scan_result = {
            "status": "completed",
            "results": {"passed": 10, "failed": 0},
            "summary": {"total_tests": 10, "pass_rate": 100.0},
        }
        client = _make_mock_client(scan_results=scan_result)

        parser = build_parser()
        args = parser.parse_args([
            "scan", "--model", "llama3.2",
            "--probes", "dan.Dan_11_0",
            "--generations", "3",
            "--output-dir", str(tmp_path),
        ])

        with patch("hydra_scan.HydraClient", return_value=client), \
             patch("hydra_scan._monitor_progress_ws",
                   return_value={"status": "completed"}):
            result = cmd_scan(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "Scan started:" in out
        assert "SCAN COMPLETE: llama3.2" in out
        assert "Passed:     10" in out

        # Report saved
        json_files = list(Path(tmp_path).glob("*.json"))
        assert len(json_files) >= 1

        # Verify client was called with correct config
        call_args = client.start_scan.call_args[0][0]
        assert call_args["target_name"] == "llama3.2"
        assert call_args["probes"] == ["dan.Dan_11_0"]
        assert call_args["generations"] == 3

    def test_ad_hoc_scan_with_rest_target(self, capsys):
        """S3/S18: Ad-hoc REST scan passes correct config to backend."""
        client = _make_mock_client()

        parser = build_parser()
        args = parser.parse_args([
            "scan",
            "--target-type", "rest",
            "--rest-endpoint", "http://localhost:8080/v1/chat/completions",
            "--rest-body-template", '{"prompt":"$INPUT"}',
            "--rest-response-field", "$.choices[0].text",
            "--rest-headers", '{"Authorization":"Bearer tok"}',
        ])

        with _patched_scan(client):
            result = cmd_scan(args)

        assert result == 0
        call_args = client.start_scan.call_args[0][0]
        assert call_args["target_type"] == "rest"
        assert call_args["rest_endpoint"] == "http://localhost:8080/v1/chat/completions"
        assert call_args["rest_body_template"] == '{"prompt":"$INPUT"}'
        assert call_args["rest_response_json_field"] == "$.choices[0].text"
        assert call_args["rest_headers"] == {"Authorization": "Bearer tok"}

    def test_ad_hoc_scan_preset_fills_generations(self, capsys):
        """Preset value for generations should apply when not explicitly set."""
        client = _make_mock_client(preset_available=True)
        client.get_preset.return_value = {
            "config": {"generations": 20, "probes": ["dan"]}
        }

        parser = build_parser()
        args = parser.parse_args(["scan", "--model", "m", "--preset", "fast"])

        with _patched_scan(client):
            cmd_scan(args)

        call_args = client.start_scan.call_args[0][0]
        # Preset generations (20) should be used since --generations was not passed
        assert call_args["generations"] == 20
        assert call_args["probes"] == ["dan"]

    def test_ad_hoc_scan_explicit_generations_wins(self, capsys):
        """Explicit --generations overrides preset value."""
        client = _make_mock_client(preset_available=True)
        client.get_preset.return_value = {
            "config": {"generations": 20}
        }

        parser = build_parser()
        args = parser.parse_args([
            "scan", "--model", "m", "--preset", "fast", "--generations", "3",
        ])

        with _patched_scan(client):
            cmd_scan(args)

        call_args = client.start_scan.call_args[0][0]
        assert call_args["generations"] == 3  # explicit wins over preset


# ===================================================================
# Auth token resolution
# ===================================================================

class TestResolveAuthToken:
    """Test _resolve_auth_token with env vars and refresh commands."""

    def test_none_type_returns_none(self):
        result = _resolve_auth_token({"type": "none"})
        assert result is None

    def test_empty_config_returns_none(self):
        result = _resolve_auth_token({})
        assert result is None

    def test_token_from_env_var(self, monkeypatch):
        monkeypatch.setenv("TEST_TOKEN", "my-secret-token")
        result = _resolve_auth_token({"type": "okta", "token_env": "TEST_TOKEN"})
        assert result == "my-secret-token"

    def test_missing_env_var_exits(self, monkeypatch):
        monkeypatch.delenv("MISSING_TOKEN", raising=False)
        with pytest.raises(SystemExit):
            _resolve_auth_token({"type": "okta", "token_env": "MISSING_TOKEN"})

    def test_refresh_command_success(self):
        auth_cfg = {
            "type": "okta",
            "token_env": "FALLBACK",
            "refresh_command": "echo fresh-token-123",
        }
        result = _resolve_auth_token(auth_cfg)
        assert result == "fresh-token-123"

    def test_refresh_command_failure_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("FALLBACK_TOKEN", "env-token")
        auth_cfg = {
            "type": "okta",
            "token_env": "FALLBACK_TOKEN",
            "refresh_command": "exit 1",
        }
        result = _resolve_auth_token(auth_cfg)
        assert result == "env-token"

    def test_bearer_type_works_same_as_okta(self, monkeypatch):
        monkeypatch.setenv("BEARER_TOK", "bearer-val")
        result = _resolve_auth_token({"type": "bearer", "token_env": "BEARER_TOK"})
        assert result == "bearer-val"

    def test_strips_bearer_prefix_from_env_var(self, monkeypatch):
        monkeypatch.setenv("TOK", "Bearer eyJabc123")
        result = _resolve_auth_token({"type": "okta", "token_env": "TOK"})
        assert result == "eyJabc123"

    def test_strips_bearer_prefix_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("TOK", "bearer   eyJxyz")
        result = _resolve_auth_token({"type": "okta", "token_env": "TOK"})
        assert result == "eyJxyz"

    def test_strips_bearer_prefix_from_refresh_command(self):
        auth_cfg = {
            "type": "okta",
            "token_env": "FALLBACK",
            "refresh_command": "echo 'Bearer fresh-token'",
        }
        result = _resolve_auth_token(auth_cfg)
        assert result == "fresh-token"

    def test_no_strip_when_no_bearer_prefix(self, monkeypatch):
        monkeypatch.setenv("TOK", "eyJplaintoken")
        result = _resolve_auth_token({"type": "okta", "token_env": "TOK"})
        assert result == "eyJplaintoken"

    def test_no_token_env_and_no_refresh_exits(self):
        with pytest.raises(SystemExit):
            _resolve_auth_token({"type": "okta"})

    def _make_jwt_token(self, claims):
        """Build a minimal JWT with the given payload claims."""
        import base64
        payload = json.dumps(claims)
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        return f"eyJ.{b64}.sig"

    def test_expired_token_exits(self, monkeypatch):
        expired = self._make_jwt_token({"exp": int(time.time()) - 60})
        monkeypatch.setenv("TOK", expired)
        with pytest.raises(SystemExit):
            _resolve_auth_token({"type": "okta", "token_env": "TOK"})

    def test_nearly_expired_token_exits(self, monkeypatch):
        almost = self._make_jwt_token({"exp": int(time.time()) + 120})  # 2 min left
        monkeypatch.setenv("TOK", almost)
        with pytest.raises(SystemExit):
            _resolve_auth_token({"type": "okta", "token_env": "TOK"})

    def test_valid_token_passes(self, monkeypatch):
        valid = self._make_jwt_token({"exp": int(time.time()) + 3600})  # 1 hr
        monkeypatch.setenv("TOK", valid)
        result = _resolve_auth_token({"type": "okta", "token_env": "TOK"})
        assert result == valid


class TestInjectAuthHeaders:
    """Test _inject_auth_headers header injection."""

    def test_injects_bearer_authorization(self):
        config = {"rest_headers": {"Content-Type": "application/json"}}
        _inject_auth_headers(config, {"type": "okta"}, "my-token")
        assert config["rest_headers"]["Authorization"] == "Bearer my-token"
        assert config["rest_headers"]["Content-Type"] == "application/json"

    def test_creates_headers_if_missing(self):
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        assert config["rest_headers"]["Authorization"] == "Bearer tok"

    def test_custom_header_name(self):
        config = {}
        auth_cfg = {"type": "okta", "token_header": "X-Auth-Token", "token_prefix": ""}
        _inject_auth_headers(config, auth_cfg, "raw-token")
        assert config["rest_headers"]["X-Auth-Token"] == "raw-token"
        assert "Authorization" not in config["rest_headers"]

    def test_custom_prefix(self):
        config = {}
        auth_cfg = {"type": "okta", "token_prefix": "Token "}
        _inject_auth_headers(config, auth_cfg, "abc")
        assert config["rest_headers"]["Authorization"] == "Token abc"

    def test_injects_content_type_when_missing(self):
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        assert config["rest_headers"]["Content-Type"] == "application/json"

    def test_preserves_existing_content_type(self):
        config = {"rest_headers": {"Content-Type": "text/plain"}}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        assert config["rest_headers"]["Content-Type"] == "text/plain"

    def test_injects_default_user_agent(self):
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        assert "User-Agent" in config["rest_headers"]
        assert "Chrome" in config["rest_headers"]["User-Agent"]

    def test_preserves_existing_user_agent(self):
        config = {"rest_headers": {"User-Agent": "custom-agent/1.0"}}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        assert config["rest_headers"]["User-Agent"] == "custom-agent/1.0"

    def test_injects_cookie_from_env(self, monkeypatch):
        monkeypatch.setenv("AUTH_COOKIE", "ARRAffinity=abc123")
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        cookie = config["rest_headers"]["Cookie"]
        assert "ARRAffinity=abc123" in cookie
        assert "ARRAffinitySameSite=abc123" in cookie

    def test_no_cookie_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("AUTH_COOKIE", raising=False)
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        assert "Cookie" not in config["rest_headers"]

    def test_preserves_existing_cookie_header(self, monkeypatch):
        monkeypatch.setenv("AUTH_COOKIE", "ARRAffinity=from-env")
        config = {"rest_headers": {"Cookie": "existing=cookie"}}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        assert config["rest_headers"]["Cookie"] == "existing=cookie"

    def test_custom_cookie_env(self, monkeypatch):
        monkeypatch.setenv("MY_COOKIE", "session=xyz")
        config = {}
        auth_cfg = {"type": "okta", "cookie_env": "MY_COOKIE"}
        _inject_auth_headers(config, auth_cfg, "tok")
        assert config["rest_headers"]["Cookie"] == "session=xyz"

    def test_strips_set_cookie_metadata(self, monkeypatch):
        """Full Set-Cookie header pasted into env should be cleaned."""
        raw = "ARRAffinity=abc123;Path=/;HttpOnly;Secure;Domain=example.com"
        monkeypatch.setenv("AUTH_COOKIE", raw)
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, "tok")
        cookie = config["rest_headers"]["Cookie"]
        assert "ARRAffinity=abc123" in cookie
        assert "ARRAffinitySameSite=abc123" in cookie


class TestCleanCookie:
    """Test _clean_cookie strips Set-Cookie attributes."""

    def test_strips_all_attributes(self):
        raw = "ARRAffinity=abc;Path=/;HttpOnly;Secure;Domain=x.com;SameSite=None"
        result = _clean_cookie(raw)
        assert "ARRAffinity=abc" in result
        assert "ARRAffinitySameSite=abc" in result

    def test_keeps_plain_cookie(self):
        assert _clean_cookie("session=xyz") == "session=xyz"

    def test_no_duplicate_samesite(self):
        """Don't add SameSite variant if already present."""
        raw = "ARRAffinity=abc; ARRAffinitySameSite=abc"
        assert _clean_cookie(raw) == "ARRAffinity=abc; ARRAffinitySameSite=abc"

    def test_keeps_multiple_cookies(self):
        raw = "a=1; b=2; Path=/; HttpOnly"
        assert _clean_cookie(raw) == "a=1; b=2"

    def test_handles_empty(self):
        assert _clean_cookie("") == ""

    def test_real_azure_cookie(self):
        raw = ("ARRAffinity=205712c70cb93f8bb4599b8f873840c10ff4de7a685d6b1bab"
               "7843d8593b8063;Path=/;HttpOnly;Secure;Domain=isioaiffwwebuat07"
               ".azurewebsites.net")
        result = _clean_cookie(raw)
        assert "ARRAffinity=205712c" in result
        assert "ARRAffinitySameSite=205712c" in result
        assert "Path" not in result
        assert "HttpOnly" not in result
        assert "Domain" not in result


class TestExtractJwtClaims:
    """Test JWT claim extraction for X-User-* headers."""

    def test_extracts_sub_and_uid(self):
        # Build a minimal JWT: header.payload.signature
        import base64
        payload = json.dumps({"sub": "user@corp.com", "uid": "abc123"})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"eyJ.{b64}.sig"
        claims = _extract_jwt_claims(token)
        assert claims["sub"] == "user@corp.com"
        assert claims["uid"] == "abc123"

    def test_returns_empty_on_invalid(self):
        assert _extract_jwt_claims("not-a-jwt") == {}
        assert _extract_jwt_claims("") == {}


class TestXUserHeaderInjection:
    """Test that X-User-* headers are auto-injected via Okta userinfo."""

    def _make_token(self, claims):
        import base64
        payload = json.dumps(claims)
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        return f"eyJ.{b64}.sig"

    @patch("hydra_scan._fetch_okta_userinfo")
    def test_injects_from_userinfo(self, mock_fetch):
        mock_fetch.return_value = {
            "sub": "00u123", "name": "Inho Choi",
            "email": "Inho.Choi@intusurg.com",
            "preferred_username": "IChoi2@corp.intusurg.com",
            "given_name": "Inho", "family_name": "Choi",
        }
        token = self._make_token({"sub": "IChoi2@corp.intusurg.com", "uid": "00u123", "iss": "https://example.okta.com"})
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, token)
        assert config["rest_headers"]["X-User-Email"] == "Inho.Choi@intusurg.com"
        assert config["rest_headers"]["X-User-Name"] == "Inho Choi"
        assert config["rest_headers"]["X-User-Username"] == "IChoi2"
        assert config["rest_headers"]["X-User-Id"] == "00u123"
        assert config["rest_headers"]["X-User-Given-Name"] == "Inho"
        assert config["rest_headers"]["X-User-Family-Name"] == "Choi"
        assert "All-Claims" in config["rest_headers"]

    @patch("hydra_scan._fetch_okta_userinfo", return_value={})
    def test_fallback_to_jwt_claims(self, mock_fetch):
        token = self._make_token({"sub": "user@corp.com", "uid": "uid123", "iss": "https://x"})
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, token)
        assert config["rest_headers"]["X-User-Email"] == "user@corp.com"
        assert config["rest_headers"]["X-User-Username"] == "user"
        assert config["rest_headers"]["X-User-Id"] == "uid123"

    @patch("hydra_scan._fetch_okta_userinfo")
    def test_preserves_existing_x_user(self, mock_fetch):
        mock_fetch.return_value = {"email": "auto@corp.com", "sub": "x"}
        token = self._make_token({"sub": "x", "iss": "https://x"})
        config = {"rest_headers": {"X-User-Email": "manual@corp.com"}}
        _inject_auth_headers(config, {"type": "okta"}, token)
        assert config["rest_headers"]["X-User-Email"] == "manual@corp.com"

    @patch("hydra_scan._fetch_okta_userinfo", return_value={})
    def test_no_x_user_without_sub(self, mock_fetch):
        token = self._make_token({"iss": "test"})
        config = {}
        _inject_auth_headers(config, {"type": "okta"}, token)
        assert "X-User-Email" not in config["rest_headers"]


class TestCheckpointResume:
    """Test checkpoint save/load/clear for resume support."""

    def test_save_and_load(self, tmp_path):
        output_cfg = {"directory": str(tmp_path)}
        checkpoint = {"completed": ["probe.A", "probe.B"], "results": [{"probe": "probe.A", "passed": 5}]}
        _save_checkpoint("test-target", output_cfg, checkpoint)
        loaded = _load_checkpoint("test-target", output_cfg)
        assert loaded["completed"] == ["probe.A", "probe.B"]
        assert len(loaded["results"]) == 1

    def test_load_missing(self, tmp_path):
        output_cfg = {"directory": str(tmp_path)}
        loaded = _load_checkpoint("nonexistent", output_cfg)
        assert loaded == {"completed": [], "results": []}

    def test_clear(self, tmp_path):
        output_cfg = {"directory": str(tmp_path)}
        _save_checkpoint("test", output_cfg, {"completed": ["a"], "results": []})
        _clear_checkpoint("test", output_cfg)
        loaded = _load_checkpoint("test", output_cfg)
        assert loaded == {"completed": [], "results": []}

    def test_merge_results(self):
        results = [
            {"probe": "a", "passed": 5, "failed": 1},
            {"probe": "b", "passed": 10, "failed": 0},
        ]
        merged = _merge_probe_results(results)
        assert merged["passed"] == 15
        assert merged["failed"] == 1
        assert merged["total_tests"] == 16
        assert merged["pass_rate"] == 93.8

    def test_get_token_remaining(self):
        import base64
        claims = {"exp": int(time.time()) + 600}
        payload = json.dumps(claims)
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"eyJ.{b64}.sig"
        remaining = _get_token_remaining(token)
        assert 595 <= remaining <= 605

    def test_get_token_remaining_no_exp(self):
        assert _get_token_remaining("not-a-jwt") is None


class TestAuthInDryRun:
    """Test that dry run shows auth info."""

    def test_dry_run_shows_auth_type(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret")
        plan_file = tmp_path / "auth-plan.yaml"
        plan_file.write_text("""
name: "auth-test"
auth:
  type: okta
  token_env: MY_TOKEN
targets:
  - name: "api"
    type: rest
    endpoint: "https://example.com/api/chat"
    body_template: '{"msg": "$INPUT"}'
    response_field: "$.reply"
""")
        from plan_loader import load_plan
        plan = load_plan(str(plan_file))
        _dry_run(plan)
        out = capsys.readouterr().out
        assert "okta" in out
        assert "MY_TOKEN" in out
        assert "SET" in out

    def test_dry_run_shows_token_not_set(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("UNSET_VAR", raising=False)
        plan_file = tmp_path / "auth-plan.yaml"
        # Write plan without env var references in non-auth sections
        plan_file.write_text("""
name: "auth-test"
auth:
  type: okta
  token_env: UNSET_VAR
targets:
  - name: "api"
    type: rest
    endpoint: "https://example.com/api/chat"
    body_template: '{"msg": "$INPUT"}'
    response_field: "$.reply"
""")
        from plan_loader import load_plan
        plan = load_plan(str(plan_file))
        _dry_run(plan)
        out = capsys.readouterr().out
        assert "NOT SET" in out


class TestAuthInCmdScan:
    """Test --auth-token flag for ad-hoc scans."""

    def test_auth_token_injected_into_headers(self):
        client = _make_mock_client()
        parser = build_parser()
        args = parser.parse_args([
            "scan", "--target-type", "rest",
            "--rest-endpoint", "https://example.com/api",
            "--rest-body-template", '{"msg": "$INPUT"}',
            "--rest-response-field", "$.reply",
            "--auth-token", "my-okta-token",
        ])

        with _patched_scan(client):
            cmd_scan(args)

        call_args = client.start_scan.call_args[0][0]
        assert call_args["rest_headers"]["Authorization"] == "Bearer my-okta-token"
        assert call_args["rest_headers"]["Content-Type"] == "application/json"

    def test_auth_token_strips_bearer_prefix(self):
        client = _make_mock_client()
        parser = build_parser()
        args = parser.parse_args([
            "scan", "--target-type", "rest",
            "--rest-endpoint", "https://example.com/api",
            "--rest-body-template", '{"msg": "$INPUT"}',
            "--rest-response-field", "$.reply",
            "--auth-token", "Bearer eyJsometoken",
        ])

        with _patched_scan(client):
            cmd_scan(args)

        call_args = client.start_scan.call_args[0][0]
        assert call_args["rest_headers"]["Authorization"] == "Bearer eyJsometoken"


class TestAuthInCmdRun:
    """Test auth injection in plan-based cmd_run."""

    def test_auth_token_injected_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCAN_TOKEN", "env-jwt-token")
        plan_file = tmp_path / "auth-plan.yaml"
        plan_file.write_text("""
name: "auth-flow"
auth:
  type: okta
  token_env: SCAN_TOKEN
targets:
  - name: "api"
    type: rest
    endpoint: "https://example.com/api"
    body_template: '{"msg": "$INPUT"}'
    response_field: "$.reply"
automation:
  exit_code_policy: never
""")
        client = _make_mock_client()
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
            result = cmd_run(args)

        assert result == 0
        call_args = client.start_scan.call_args[0][0]
        assert call_args["rest_headers"]["Authorization"] == "Bearer env-jwt-token"

    def test_auth_not_injected_for_ollama_targets(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCAN_TOKEN", "should-not-appear")
        plan_file = tmp_path / "auth-plan.yaml"
        plan_file.write_text("""
name: "ollama-with-auth"
auth:
  type: okta
  token_env: SCAN_TOKEN
targets:
  - name: "llm"
    type: ollama
    model: llama3.2
automation:
  exit_code_policy: never
""")
        client = _make_mock_client()
        parser = build_parser()
        args = parser.parse_args(["run", "--plan", str(plan_file)])

        with _patched_scan(client):
            cmd_run(args)

        call_args = client.start_scan.call_args[0][0]
        assert "rest_headers" not in call_args
