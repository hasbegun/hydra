# Hydra CLI Test Guide

This document describes how to run, write, and maintain tests for the Hydra CLI scanning tool and its backend integration.

---

## Table of Contents

1. [Overview](#overview)
2. [Running Tests](#running-tests)
3. [Test Architecture](#test-architecture)
4. [CLI Test Suites](#cli-test-suites)
5. [Backend Test Suites](#backend-test-suites)
6. [Writing New Tests](#writing-new-tests)
7. [Test Helpers](#test-helpers)
8. [End-to-End Testing](#end-to-end-testing)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The project has two test groups:

| Group | Location | Tests | Framework | Runs in |
|-------|----------|-------|-----------|---------|
| **CLI** | `cli/tests/` | 146 | pytest | CLI Docker container |
| **Backend** | `backend/tests/` | 255 | pytest | Backend Docker container |

All tests run inside Docker to ensure consistent environments. The Docker stack must be running before executing tests.

**Current test totals:** 254 backend + 146 CLI = **400 pass**, 1 pre-existing failure (unrelated to CLI).

---

## Running Tests

### Prerequisites

Start the Docker stack:

```bash
cd hydra/backend
make hydra-dev
```

### CLI tests

```bash
# Run all CLI tests
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli -m pytest tests/ -v

# Run a single test file
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli -m pytest tests/test_hydra_scan.py -v

# Run a single test class
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli -m pytest tests/test_hydra_scan.py::TestExitCodePolicy -v

# Run a single test
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli -m pytest tests/test_hydra_scan.py::TestExitCodePolicy::test_cmd_scan_returns_1_on_failures -v
```

### Backend tests

```bash
# Run CLI-related backend tests only
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  exec backend python -m pytest tests/test_rest_target.py -v

# Run all backend tests
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  exec backend python -m pytest tests/test_cli_flags.py tests/test_rest_target.py \
  tests/test_report_cache.py tests/test_workflow_analyzer.py tests/test_logging_config.py \
  tests/test_scan_statistics.py tests/test_config_templates.py tests/test_concurrent_scans.py \
  --tb=short -q
```

### Quick regression check

Run both groups and check totals:

```bash
# CLI tests (expect 146 passed)
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli -m pytest tests/ -q

# Backend tests (expect 254 passed, 1 failed pre-existing)
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  exec backend python -m pytest tests/test_cli_flags.py tests/test_rest_target.py \
  tests/test_report_cache.py tests/test_workflow_analyzer.py tests/test_logging_config.py \
  tests/test_scan_statistics.py tests/test_config_templates.py tests/test_concurrent_scans.py \
  --tb=short -q
```

---

## Test Architecture

```
cli/
  tests/
    __init__.py
    test_hydra_scan.py     # 81 tests — CLI tool, commands, helpers
    test_comparator.py     # 30 tests — result comparison engine
    test_plan_loader.py    # 35 tests — YAML plan loading and validation
backend/
  tests/
    test_rest_target.py    # 27 tests — REST target config and command builder
    test_cli_flags.py      # 44 tests — garak CLI flag generation
    test_report_cache.py   # 41 tests — report caching and retrieval
    ...                    # Other backend test files
```

### Test categories

Tests are organized by what they verify, not by what they import:

| Category | Purpose | Requires backend? |
|----------|---------|-------------------|
| **Unit** | Single function or class in isolation | No |
| **Integration (mocked)** | Full command flow with mocked HTTP client | No |
| **Integration (Docker)** | Commands run against real Docker services | Yes |
| **E2E** | Full scan with real models (Ollama) | Yes + Ollama |

All CLI tests in `cli/tests/` are unit or mocked-integration tests. They do **not** require a running backend.

---

## CLI Test Suites

### `test_hydra_scan.py` (81 tests)

The main CLI test file, organized into test classes by feature:

#### Argument parsing (11 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestArgParser` | 11 | All subcommands parse correctly, required args enforced, optional args have correct defaults |

#### Offline commands (10 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestValidateCommand` | 2 | Valid plan accepted, invalid plan rejected with errors to stderr |
| `TestInitCommand` | 4 | Starter template created, overwrite refused without `--force`, parent dirs created |
| `TestDryRun` | 2 | Dry-run output lists targets/probes/config, no scans started |
| `TestHelpOutput` | 2 | `--help` and `run --help` include expected keywords |

#### Default values and overrides (6 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestDefaultValues` | 2 | Minimal plan loads with all defaults filled; dry-run succeeds |
| `TestPerTargetOverride` | 4 | Target-level generations, probes, preset override global defaults |

#### Result extraction (5 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestExtractCounts` | 5 | Parses nested `results.passed`, top-level fallback, empty results, null values, summary pass_rate |

#### Exit code policies (5 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestExitCodePolicy` | 5 | `cmd_scan` returns 1 on failures, 0 on all pass; `cmd_run` respects `never`, `threshold` (both directions) |

#### Quiet mode and JSON output (2 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestQuietAndJsonStdout` | 2 | `quiet: true` suppresses banners; `json_stdout: true` outputs parseable JSON with plan name, targets, exit code |

#### Error handling (5 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestErrorHandling` | 5 | Connection refused message (no traceback), nonexistent plan, bad model, invalid JSON headers, failed scan status |

#### Report saving (2 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestSaveReports` | 2 | Output directory created, JSON content matches scan results |

#### Multi-target (1 test)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestMultiTargetDryRun` | 1 | 3-target plan renders all targets in dry run output |

#### Filename sanitization (7 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestFilenameSanitization` | 7 | Path traversal (`../`), normal names unchanged, colon in model name, empty string, null bytes, special characters, end-to-end with malicious names |

#### Progress bar rendering (5 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestRenderProgressLine` | 5 | Basic bar, probe name display, zero progress, full progress, empty data |

#### Plan loading helper (4 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestLoadAndValidatePlan` | 4 | Valid plan returns dict, invalid returns None, nonexistent exits, empty YAML exits |

#### Summary and pattern fallback (4 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestPrintSummary` | 3 | Basic output formatting, no-reports case, HTML path shown |
| `TestSaveReportsPatternFallback` | 1 | Invalid `{placeholder}` in filename_pattern falls back gracefully |

#### Preset override (2 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestCmdScanPresetOverride` | 2 | `--generations` argparse default is `None` (not 5); explicit value preserved |

#### Compare command (4 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestCmdCompare` | 4 | Two-file comparison, insufficient files error, nonexistent dir error, regression detection |

#### Full flow integration tests (8 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestCmdRunFullFlow` | 4 | Plan scan saves reports + prints summary, comparison during scan, failed target continues to next, JSON stdout with multiple targets |
| `TestCmdScanFullFlow` | 4 | Ad-hoc scan full flow, REST target config forwarding, preset fills generations, explicit `--generations` overrides preset |

---

### `test_comparator.py` (30 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestFindPreviousResult` | 3 | Finds most recent file, excludes current file, matches target name only |
| `TestNoPreviousResult` | 3 | Empty dir, nonexistent dir, only current file |
| `TestCompareImproved` | 2 | Overall improvement detected, per-probe improvement |
| `TestCompareRegression` | 2 | Overall regression detected, per-probe regression flagged |
| `TestThresholdCheck` | 4 | Below threshold OK, above threshold triggers, improvement never triggers, per-probe regression |
| `TestPrintComparison` | 2 | Output contains key info, regression output formatted correctly |
| `TestDataClasses` | 4 | `ProbeComparison` delta/label/regression, `ComparisonResult.regressions` filtering |
| `TestExtractCounts` | 7 | Nested results, top-level fallback, empty, null, summary pass_rate precedence, direct pass_rate, results preferred over top-level |
| `TestExtractDateFromFilename` | 3 | Standard date format, date in middle of name, no-date mtime fallback |

---

### `test_plan_loader.py` (35 tests)

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestMinimalPlanLoads` | 2 | Minimal YAML loads, all section defaults filled in |
| `TestFullPlanLoads` | 1 | Full plan with all fields loads correctly |
| `TestEnvVarSubstitution` | 3 | `${VAR}` resolved from env, unset var raises ValueError, multiple vars in one string |
| `TestDefaultMerging` | 2 | Target inherits defaults, target keeps own values |
| `TestTargetOverride` | 1 | Target preset overrides default preset |
| `TestInvalidYamlRejected` | 4 | Missing name, missing targets, empty targets, target missing name |
| `TestUnknownTargetType` | 2 | `grpc` rejected, arbitrary string rejected |
| `TestRestMissingFields` | 3 | REST without endpoint, without body_template, without response_field |
| `TestPlanToScanConfigs` | 3 | Ollama target config, REST target config, multi-target config list |
| `TestEdgeCases` | 8 | File not found, empty file, invalid YAML, no env vars, invalid preset, invalid generations, invalid exit_code_policy, invalid output format |
| `TestGeneratorOptions` | 3 | REST generator_options pass-through, Ollama generator_options, no generator_options |
| `TestBodyTemplateStrip` | 3 | Trailing newline stripped, multiline YAML stripped, no-trailing-whitespace unchanged |

---

## Backend Test Suites

### `test_rest_target.py` (27 tests)

Tests the backend's `scan_manager._build_command()` for REST target configuration:

| Area | What it verifies |
|------|------------------|
| REST generator_options | `--generator_options` JSON contains `uri`, `headers`, `req_template`, `response_json_field` |
| Ollama host injection | `OLLAMA_HOST` env var injected into generator_options for ollama targets |
| User options precedence | User-provided `generator_options` take precedence over auto-mapped REST fields |
| Command structure | All flags present in correct order (`--model_type`, `--probes`, `--generations`, etc.) |

### Other backend test files

| File | Tests | Area |
|------|-------|------|
| `test_cli_flags.py` | 44 | Garak CLI flag generation for all target types |
| `test_report_cache.py` | 41 | Report caching, retrieval, and probe filtering |
| `test_workflow_analyzer.py` | 42 | Scan workflow analysis and state tracking |
| `test_config_templates.py` | 45 | Scan configuration template management |
| `test_logging_config.py` | 20 | Logging configuration and output |
| `test_scan_statistics.py` | 18 | Scan statistics aggregation |
| `test_concurrent_scans.py` | 18 | Concurrent scan handling and limits |

---

## Writing New Tests

### File placement

- CLI-side logic (commands, plan loading, comparison) goes in `cli/tests/`.
- Backend-side logic (API, scan_manager, garak wrapper) goes in `backend/tests/`.

### Using the test helpers

Two shared helpers in `test_hydra_scan.py` reduce boilerplate for tests that exercise `cmd_run` or `cmd_scan`:

#### `_make_mock_client()`

Creates a pre-configured `MagicMock` of `HydraClient`:

```python
# Default: 5 passed, 0 failed, preset not available
client = _make_mock_client()

# Custom scan results
client = _make_mock_client(scan_results={
    "status": "completed",
    "results": {"passed": 3, "failed": 7},
    "summary": {"total_tests": 10, "pass_rate": 30.0},
})

# With preset available
client = _make_mock_client(preset_available=True)
client.get_preset.return_value = {"config": {"generations": 20}}
```

Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scan_results` | `dict` | 5 pass / 0 fail | Return value of `client.scan_results()` |
| `scan_id` | `str` | `"test-id"` | The scan_id returned by `start_scan()` |
| `preset_available` | `bool` | `False` | If False, `get_preset()` raises SystemExit |

#### `_patched_scan()`

Context manager that patches `HydraClient`, the progress monitor, and report saving:

```python
client = _make_mock_client(scan_results={...})

with _patched_scan(client):
    result = cmd_run(args)
assert result == 0
```

Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_client` | `MagicMock` | (required) | The mock client to inject |
| `final_status` | `dict` | `{"status": "completed"}` | Return value of progress monitor |
| `saved_reports` | `dict` | `{"json": "/tmp/r.json"}` | Return value of `_save_reports` |

### Test patterns

#### Testing a plan-based command

```python
def test_my_feature(self, tmp_path, capsys):
    from hydra_scan import cmd_run

    plan_file = tmp_path / "test.yaml"
    plan_file.write_text("""
name: "test"
targets:
  - name: "t"
    type: ollama
    model: m
automation:
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
        result = cmd_run(args)

    assert result == 0
    out = capsys.readouterr().out
    assert "SCAN COMPLETE" in out
```

#### Testing a pure function

```python
def test_sanitize_path_traversal(self):
    assert _sanitize_filename("../../etc/passwd") == "etc_passwd"

def test_extract_counts_empty(self):
    p, f, t, r = extract_counts({})
    assert (p, f, t, r) == (0, 0, 0, 0.0)
```

#### Testing error handling

```python
def test_nonexistent_plan(self):
    """Should exit with SystemExit on missing file."""
    with pytest.raises(SystemExit):
        _load_and_validate_plan("/no/such/file.yaml")
```

#### Testing with real file I/O

```python
def test_reports_saved(self, tmp_path):
    """Use tmp_path for file tests — pytest cleans it up automatically."""
    client = _make_mock_client()

    output_cfg = {
        "directory": str(tmp_path),
        "formats": ["json"],
    }
    paths = _save_reports(client, "scan-1", "target", output_cfg)

    assert Path(paths["json"]).exists()
    with open(paths["json"]) as f:
        data = json.load(f)
    assert data["status"] == "completed"
```

### Naming conventions

- Test files: `test_<module>.py`
- Test classes: `Test<Feature>` (e.g. `TestExitCodePolicy`)
- Test methods: `test_<specific_scenario>` (e.g. `test_cmd_scan_returns_1_on_failures`)

---

## End-to-End Testing

E2E tests require a running Docker stack and Ollama with at least one model pulled.

### Setup

```bash
cd hydra/backend
make hydra-dev
ollama pull qwen2.5:1.5b    # Small model for fast E2E tests
```

### Running E2E tests manually

These are not in the automated test suite (they require live services and take minutes):

```bash
# Health check
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli hydra_scan.py health

# Ad-hoc scan
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli hydra_scan.py scan \
  --model qwen2.5:1.5b --probes dan.Dan_11_0 --generations 1

# Plan-based scan
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli hydra_scan.py run \
  --plan scan_plans/examples/e2e-test.yaml

# Validate
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli hydra_scan.py validate \
  --plan scan_plans/examples/quick-ollama.yaml

# Dry run
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli hydra_scan.py run \
  --plan scan_plans/examples/weekly-audit.yaml --dry-run
```

### E2E test matrix

These tests were verified manually during development:

| ID | Test | Model | Status |
|----|------|-------|--------|
| T4.1 | Plan-based scan | qwen2.5:1.5b | Verified |
| T4.2 | Multi-target plan | qwen2.5:1.5b + phi3:mini | Verified |
| T4.7 | Ad-hoc scan | qwen2.5:1.5b | Verified |
| T4.8 | REST endpoint scan | Ollama OpenAI-compatible API | Verified |
| T4.9 | Result comparison | Real garak digest data | Verified |
| T5.3 | Full Docker CLI flow | qwen2.5:1.5b | Verified |

---

## Troubleshooting

### "Container ... Creating" takes too long

The CLI container image may need rebuilding after code changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build cli
```

In dev mode, source is mounted so rebuilds are only needed for dependency changes.

### Import errors in tests

CLI tests insert `cli/` into `sys.path`. If you see import errors, verify the test file has:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```

### Pre-existing failure: `test_probe_attempts_filter`

`tests/test_report_cache.py::TestCachedResultsCorrectness::test_probe_attempts_filter` has 1 known pre-existing failure unrelated to CLI work. It should not be counted as a regression.

### Tests pass locally but fail in Docker

The CLI container uses Python 3.11-slim. Check for:

- Python version-specific syntax (e.g. `X | Y` union types require 3.10+)
- Missing dependencies (only `requirements.txt` + pytest are installed)
- File path differences (container uses `/app`, not the host path)
