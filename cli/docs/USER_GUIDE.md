# Hydra CLI User Guide

A command-line tool for running LLM vulnerability scans using [NVIDIA garak](https://github.com/NVIDIA/garak) via the Hydra backend API. Scans can be driven by YAML plan files or ad-hoc command-line flags.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Commands Reference](#commands-reference)
5. [YAML Scan Plans](#yaml-scan-plans)
6. [Target Types](#target-types)
7. [Presets](#presets)
8. [Environment Variables](#environment-variables)
9. [Result Comparison](#result-comparison)
10. [Automation and CI/CD](#automation-and-cicd)
11. [Docker Usage](#docker-usage)
12. [Report Formats](#report-formats)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Ollama** running on the host machine (for local model scans)
- **Python 3.11+** (only if running outside Docker)

## Installation

### Docker (recommended)

No separate install needed. The CLI runs in its own container.

```bash
cd hydra/backend
cp .env.example .env        # Set database and MinIO passwords
make hydra-dev               # Start the Docker stack
```

### Standalone Python

```bash
cd hydra/cli
pip install -r requirements.txt
```

Dependencies: `requests`, `websocket-client`, `PyYAML`.

---

## Quick Start

### 1. Check that services are healthy

```bash
# Docker
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli hydra_scan.py health

# Standalone
python hydra_scan.py health
```

Expected output:

```
Backend:  healthy
Garak:    installed
Version:  0.17
```

### 2. Run an ad-hoc scan

```bash
python hydra_scan.py scan --model llama3.2 --preset fast
```

This scans `llama3.2` with the `fast` preset (probes: `dan`, `encoding`), saves JSON and HTML reports to `./hydra_reports/`, and prints a summary.

### 3. Run a plan-based scan

```bash
# Generate a starter plan
python hydra_scan.py init --plan scan_plans/my-scan.yaml

# Edit the plan, then validate it
python hydra_scan.py validate --plan scan_plans/my-scan.yaml

# Preview what will happen (no scan started)
python hydra_scan.py run --plan scan_plans/my-scan.yaml --dry-run

# Run the scan
python hydra_scan.py run --plan scan_plans/my-scan.yaml
```

---

## Commands Reference

### `run` -- Execute a YAML scan plan

```bash
python hydra_scan.py run --plan <path.yaml> [--dry-run] [--output-dir <dir>]
```

| Flag | Description |
|------|-------------|
| `--plan` | Path to the YAML scan plan (required) |
| `--dry-run` | Show what would run without starting any scans |
| `--output-dir` | Override the output directory from the plan |

Scans each target in the plan sequentially, saves reports, and optionally compares results against previous runs. Exit code is determined by the plan's `exit_code_policy`.

### `scan` -- Ad-hoc single-target scan

```bash
python hydra_scan.py scan --model <name> [options]
```

| Flag | Description |
|------|-------------|
| `--model` | Ollama model name (e.g. `llama3.2`) |
| `--target-type` | `ollama` (default) or `rest` |
| `--preset` | Probe preset: `fast`, `default`, `full`, `owasp` |
| `--probes` | Comma-separated probe names (overrides preset) |
| `--generations` | Generations per probe (default: 5, or from preset) |
| `--eval-threshold` | Evaluation threshold 0.0-1.0 (default: 0.5) |
| `--output-dir` | Directory for report files |
| `--rest-endpoint` | REST API URL (when `--target-type rest`) |
| `--rest-body-template` | JSON body with `$INPUT` placeholder |
| `--rest-response-field` | JSONPath to extract response text |
| `--rest-headers` | JSON string of HTTP headers |

Exit code: `0` if all tests pass, `1` if any test fails.

### `validate` -- Validate a plan file

```bash
python hydra_scan.py validate --plan <path.yaml>
```

Checks YAML syntax, required fields, target types, preset names, and parameter ranges. Prints specific error messages for each issue found.

### `init` -- Generate a starter plan

```bash
python hydra_scan.py init --plan <path.yaml> [--force]
```

Creates a commented template with example Ollama and REST targets. Use `--force` to overwrite an existing file. Parent directories are created automatically.

### `compare` -- Compare recent results

```bash
python hydra_scan.py compare --target <name> --dir <path> [--threshold <pct>]
```

Finds the two most recent JSON result files for `<name>` in `<dir>`, computes overall and per-probe pass rate deltas, and prints a comparison table. Exit code `1` if any regression exceeds the threshold.

### `health` -- Check backend health

```bash
python hydra_scan.py health
```

### `probes` -- List available probes

```bash
python hydra_scan.py probes
```

### `models` -- List Ollama models

```bash
python hydra_scan.py models
```

### `history` -- View past scans

```bash
python hydra_scan.py history [--page N] [--page-size N]
```

### `report` -- Download reports for a past scan

```bash
python hydra_scan.py report <scan_id> [--output-dir <dir>]
```

### `status` -- Check a running scan

```bash
python hydra_scan.py status <scan_id>
```

### `start-services` / `stop-services` -- Manage Docker stack

```bash
python hydra_scan.py start-services [--compose-dir <path>]
python hydra_scan.py stop-services  [--compose-dir <path>]
```

### Global flag

| Flag | Description |
|------|-------------|
| `--backend-url` | Override the backend API URL (default: `http://localhost:8888`, or `$HYDRA_BACKEND_URL`) |

---

## YAML Scan Plans

A scan plan is a YAML file that defines one or more targets to scan, along with output, comparison, and automation settings.

### Minimal plan

```yaml
name: "quick-check"
targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
```

All other fields use sensible defaults: 5 generations, all probes, JSON+HTML output to `./hydra_reports/`, `any_fail` exit code policy.

### Full plan structure

```yaml
name: "weekly-security-audit"          # Required
description: "Weekly LLM security scan" # Optional
version: "1.0"                          # Optional

# --- Global defaults (inherited by all targets) ---
defaults:
  preset: default         # fast | default | full | owasp
  generations: 10         # 1-500
  eval_threshold: 0.5     # 0.0-1.0
  seed: 42                # Reproducibility
  # probes:               # Override all-probes default
  #   - dan
  #   - encoding

# --- Targets (one or more) ---
targets:
  # Ollama target
  - name: "llama3.2"
    type: ollama
    model: llama3.2
    # Any field from defaults can be overridden per-target:
    # preset: full
    # generations: 20
    # probes: [dan, encoding]

  # REST/API target
  - name: "my-api"
    type: rest
    endpoint: "http://host.docker.internal:8080/v1/chat/completions"
    headers:
      Authorization: "Bearer ${API_KEY}"
      Content-Type: "application/json"
    body_template: |
      {"model":"gpt-4","messages":[{"role":"user","content":"$INPUT"}],"stream":false}
    response_field: "$.choices[0].message.content"
    generator_options:       # Advanced garak RestGenerator options
      rest:
        request_timeout: 120

# --- Output ---
output:
  directory: "./hydra_reports"
  formats: [json, html]                     # json, html, summary
  filename_pattern: "{name}_{date}"         # Placeholders: {name}, {date}, {time}
  timestamp_format: "%Y-%m-%d"

# --- Comparison ---
compare:
  enabled: true
  baseline_dir: "./hydra_reports"           # Where to find previous results
  regression_threshold: 5.0                 # Percentage-point tolerance
  fail_on_regression: false                 # Set exit code 1 on regression

# --- Automation ---
automation:
  exit_code_policy: threshold               # never | any_fail | threshold
  min_pass_rate: 85.0                       # Used with threshold policy
  quiet: false                              # Suppress progress and summary
  json_stdout: false                        # Machine-readable JSON to stdout
```

### Per-target overrides

Any scan parameter set at the target level overrides the same field from `defaults`:

```yaml
defaults:
  preset: fast
  generations: 5

targets:
  - name: "quick-model"
    type: ollama
    model: llama3.2
    # Inherits preset: fast, generations: 5

  - name: "thorough-model"
    type: ollama
    model: mistral
    preset: full           # Overrides fast -> full
    generations: 20        # Overrides 5 -> 20
```

### Filename pattern placeholders

| Placeholder | Expands to |
|-------------|------------|
| `{name}` | Sanitized target name |
| `{date}` | Formatted date (per `timestamp_format`) |
| `{time}` | Time as `HHMMSS` |

---

## Target Types

### Ollama

Scans a local Ollama model. Ollama must be running on the host.

```yaml
- name: "llama3.2"
  type: ollama
  model: llama3.2         # Required: Ollama model name
```

List available models:

```bash
python hydra_scan.py models
```

### REST

Scans any HTTP endpoint that accepts text prompts and returns text responses.

```yaml
- name: "my-api"
  type: rest
  endpoint: "https://api.example.com/v1/chat/completions"   # Required
  body_template: |                                           # Required
    {"model":"gpt-4","messages":[{"role":"user","content":"$INPUT"}],"stream":false}
  response_field: "$.choices[0].message.content"             # Required (JSONPath)
  headers:                                                   # Optional
    Authorization: "Bearer ${API_KEY}"
    Content-Type: "application/json"
  generator_options:                                         # Optional
    rest:
      request_timeout: 120
      max_tokens: 256
```

Key details:

- **`$INPUT`** in `body_template` is replaced with the probe text by garak.
- **`response_field`** must be a JSONPath expression starting with `$` (e.g. `$.choices[0].message.content`) or a simple top-level key.
- **`body_template`** trailing whitespace is automatically stripped (YAML block scalars add a trailing newline).
- **`generator_options`** are passed directly to garak's `RestGenerator`. Use this for settings like `request_timeout`, `max_tokens`, etc.

### Inside Docker

When the CLI runs in Docker, `localhost` refers to the container itself. To reach services on the host machine, use `host.docker.internal`:

```yaml
endpoint: "http://host.docker.internal:11434/v1/chat/completions"
```

---

## Presets

Presets configure which probes garak runs. Set in `defaults.preset` or per-target.

| Preset | Probes | Typical Duration | Use Case |
|--------|--------|-----------------|----------|
| `fast` | `dan`, `encoding` | ~2 min | Quick smoke test |
| `default` | `dan`, `encoding`, `promptinject`, `toxicity` | ~10 min | Balanced daily check |
| `full` | All available probes | ~30+ min | Comprehensive audit |
| `owasp` | OWASP LLM Top 10 probes | ~15 min | Compliance check |

When a preset is set and `--probes` is not explicitly provided, the preset's probe list is used. Explicit `--probes` always overrides the preset.

---

## Environment Variables

### In YAML plans

Use `${VAR_NAME}` anywhere in a plan file to reference environment variables:

```yaml
headers:
  Authorization: "Bearer ${API_TOKEN}"
endpoint: "${LLM_ENDPOINT}"
```

Variables are resolved at plan load time. If any referenced variable is not set, the CLI exits with a clear error before any scan starts:

```
Error: Unset environment variable(s): API_TOKEN. Set them before running the scan plan.
```

### CLI configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_BACKEND_URL` | Backend API URL | `http://localhost:8888` |
| `CLI_PLANS_DIR` | Docker volume: host plans directory | `./cli_plans` |
| `CLI_REPORTS_DIR` | Docker volume: host reports directory | `./cli_reports` |

---

## Result Comparison

### Automatic (in plans)

Enable comparison in the scan plan to automatically compare results after each scan:

```yaml
compare:
  enabled: true
  baseline_dir: "./hydra_reports"     # Where previous results are stored
  regression_threshold: 5.0           # Ignore deltas smaller than this
  fail_on_regression: false           # Set to true to fail the run on regression
```

After each target completes, the CLI looks for the most recent previous JSON result file for the same target name in `baseline_dir` and prints a comparison table showing overall and per-probe pass rate changes.

### Manual

```bash
python hydra_scan.py compare --target llama3.2 --dir ./hydra_reports --threshold 5.0
```

Finds the two most recent JSON files matching `llama3.2` in the directory, computes deltas, and prints a table:

```
============================================================
  COMPARISON: llama3.2 (2026-01-20 vs 2026-01-13)
============================================================
  Overall Pass Rate:  85.0%  ->  90.0%  (+5.0%)  [IMPROVED]
------------------------------------------------------------
  PROBE CHANGES
------------------------------------------------------------
  dan.Dan_11_0                0.0% -> 50.0%  (+50.0%)  [IMPROVED]
  encoding.InjectBase64       100.0% -> 100.0%  (+0.0%)  [UNCHANGED]
------------------------------------------------------------
  No regressions detected.
============================================================
```

Exit code: `0` if no regressions exceed the threshold, `1` otherwise.

---

## Automation and CI/CD

### Exit code policies

The `automation.exit_code_policy` controls when the CLI exits with code 1 (failure):

| Policy | Behavior |
|--------|----------|
| `never` | Always exit 0, regardless of results |
| `any_fail` (default) | Exit 1 if any probe test fails |
| `threshold` | Exit 1 if overall pass rate is below `min_pass_rate` |

### CI/CD pipeline example

**Scan plan (`ci-gate.yaml`):**

```yaml
name: "ci-gate"
description: "Fast gate scan for CI pipeline"

defaults:
  preset: fast
  continue_on_error: true

targets:
  - name: "staging-api"
    type: rest
    endpoint: "${CI_LLM_ENDPOINT}"
    headers:
      Authorization: "Bearer ${CI_LLM_TOKEN}"
    body_template: '{"model":"${CI_MODEL}","messages":[{"role":"user","content":"$INPUT"}]}'
    response_field: "$.choices[0].message.content"

automation:
  exit_code_policy: threshold
  min_pass_rate: 90.0
  quiet: true
  json_stdout: true
```

**GitHub Actions step:**

```yaml
- name: LLM Security Gate
  run: |
    docker compose run --rm cli run --plan /plans/ci-gate.yaml
  env:
    CI_LLM_ENDPOINT: ${{ secrets.LLM_ENDPOINT }}
    CI_LLM_TOKEN: ${{ secrets.LLM_TOKEN }}
    CI_MODEL: gpt-4
```

### Cron scheduling

```bash
# Weekly scan every Monday at 2 AM
0 2 * * 1 cd /opt/hydra/backend && docker compose run --rm cli run --plan /plans/weekly.yaml
```

With `quiet: true`, only errors are printed. With `json_stdout: true`, machine-readable JSON goes to stdout for downstream parsing.

### JSON output format

When `automation.json_stdout: true`, the CLI outputs a single JSON object to stdout:

```json
{
  "plan": "ci-gate",
  "timestamp": "2026-01-20T02:00:00.123456",
  "targets": [
    {
      "name": "staging-api",
      "type": "rest",
      "status": "completed",
      "total_tests": 10,
      "passed": 9,
      "failed": 1,
      "pass_rate": 90.0,
      "reports": {
        "json": "/reports/staging-api_2026-01-20.json",
        "html": "/reports/staging-api_2026-01-20.html"
      }
    }
  ],
  "overall_pass": true,
  "exit_code": 0
}
```

---

## Docker Usage

The CLI runs in its own container with `profiles: [cli]`, so it does **not** start with normal `docker compose up`.

### Run a plan

```bash
cd hydra/backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm --entrypoint python cli hydra_scan.py run --plan /plans/my-scan.yaml
```

### Mount custom plans and reports

```bash
docker compose run --rm \
  -v /path/to/my_plans:/plans:ro \
  -v /path/to/my_reports:/reports \
  --entrypoint python cli hydra_scan.py run --plan /plans/scan.yaml --output-dir /reports
```

### Development mode

In dev mode (`docker-compose.dev.yml`), the CLI source is mounted at `/app` so code changes take effect immediately without rebuilding.

### Default volume paths

| Container path | Host default | Purpose |
|----------------|-------------|---------|
| `/plans` | `$CLI_PLANS_DIR` or `./cli_plans` | Scan plan YAML files (read-only) |
| `/reports` | `$CLI_REPORTS_DIR` or `./cli_reports` | Saved JSON/HTML reports |

---

## Report Formats

### JSON

Contains the full scan result from the backend: status, pass/fail counts, per-probe breakdown, and the garak digest. Used for comparison, automation, and archival.

```bash
cat hydra_reports/llama3.2_2026-01-20.json | python -m json.tool
```

### HTML

The garak-generated HTML visualization. Open in a browser to see detailed probe results with charts and tables.

### Summary

A text summary printed to the terminal after each scan:

```
============================================================
  SCAN COMPLETE: llama3.2
============================================================
  Status:     completed
  Total:      10 tests
  Passed:     8
  Failed:     2
  Pass Rate:  80.0%
  JSON:       ./hydra_reports/llama3.2_2026-01-20.json
  HTML:       ./hydra_reports/llama3.2_2026-01-20.html
============================================================
```

---

## Troubleshooting

### "Cannot connect to backend"

The Docker stack is not running or the backend URL is wrong.

```bash
# Start the stack
make hydra-dev

# Or specify a custom URL
python hydra_scan.py --backend-url http://my-server:8888 health
```

### "Unset environment variable(s)"

A `${VAR}` placeholder in the plan references a variable that is not set in the current shell.

```bash
export API_KEY="sk-..."
python hydra_scan.py run --plan my-plan.yaml
```

### Scan completes with 0 tests

Common causes:

- **REST target**: The `response_field` is not a valid JSONPath. It must start with `$` (e.g. `$.choices[0].message.content`), not use bracket notation without the prefix.
- **REST target**: The `body_template` has invalid JSON. Check for unescaped quotes or missing commas.
- **Model not found**: Verify the model is installed with `ollama list` and the name matches exactly.

### REST scan timeout

The garak `RestGenerator` has a default 20-second request timeout. For large models or slow endpoints, increase it with `generator_options`:

```yaml
generator_options:
  rest:
    request_timeout: 120
```

### Reports not saved to expected location

In Docker, paths are relative to the container filesystem. Use `/reports` (the mounted volume) or an absolute path:

```yaml
output:
  directory: "/reports"
```

### Progress bar not showing

Progress display requires the `websocket-client` library. It falls back to REST polling automatically, but `quiet: true` suppresses all progress output.

---

## Example Plans

Ready-to-use plans are in `cli/scan_plans/examples/`:

| File | Description |
|------|-------------|
| `quick-ollama.yaml` | Minimal single-model scan with `fast` preset |
| `weekly-audit.yaml` | Multi-model weekly audit with comparison and threshold gate |
| `website-scan.yaml` | REST endpoint scan with OpenAI-compatible API |
| `rest-test.yaml` | REST E2E test targeting Ollama's OpenAI-compatible endpoint |
| `ci-gate.yaml` | CI/CD pipeline gate with quiet + JSON output |
| `multi-target-test.yaml` | Multi-target scan for E2E testing |
| `e2e-test.yaml` | End-to-end test plan for verification |
