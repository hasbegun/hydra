"""
Tests for cli/hydra_scan.py — CLI argument parsing and offline subcommands.

Covers T4.3-T4.6 and T4.14 from the test plan (commands that don't need a running backend).
"""
import os
import sys
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hydra_scan import build_parser, cmd_validate, cmd_init, _dry_run


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
