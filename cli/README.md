# Hydra CLI

Command-line tool for running LLM vulnerability scans via the Hydra backend API.

Supports YAML scan plans, ad-hoc scans, result comparison, and automation-friendly output.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Ollama running on host (for local model scans)

### Setup

```bash
cd hydra/backend
cp .env.example .env              # Set passwords
ollama pull llama3.2              # Pull a model (for local scans)
make hydra-dev                    # Start Docker stack
```

### First Scan (ad-hoc)

```bash
# Run directly (Python 3.11+ with deps installed)
cd hydra/cli
pip install -r requirements.txt
python hydra_scan.py scan --model llama3.2 --preset fast

# Or via Docker
cd hydra/backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --entrypoint python cli hydra_scan.py scan --model llama3.2 --preset fast
```

### First Scan (plan-based)

```bash
# Generate a starter plan
python hydra_scan.py init --plan scan_plans/my-scan.yaml

# Edit it, then validate
python hydra_scan.py validate --plan scan_plans/my-scan.yaml

# Run it
python hydra_scan.py run --plan scan_plans/my-scan.yaml

# Dry run (show what would happen without scanning)
python hydra_scan.py run --plan scan_plans/my-scan.yaml --dry-run
```

## YAML Scan Plan Format

### Minimal Plan

```yaml
name: "quick-check"
targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
```

### Full Plan

```yaml
name: "weekly-security-audit"
description: "Weekly LLM security scan"
version: "1.0"

defaults:
  preset: default               # fast | default | full | owasp
  generations: 10
  seed: 42

targets:
  # Local Ollama model
  - name: "llama3.2"
    type: ollama
    model: llama3.2

  # REST/Website endpoint
  - name: "my-api"
    type: rest
    endpoint: "http://host.docker.internal:8080/v1/chat/completions"
    headers:
      Authorization: "Bearer ${API_KEY}"
    body_template: |
      {"model":"gpt-4","messages":[{"role":"user","content":"$INPUT"}],"stream":false}
    response_field: "$.choices[0].message.content"
    probes:
      - dan
      - encoding

output:
  directory: "./hydra_reports"
  filename_pattern: "{name}_{date}"

compare:
  enabled: true
  regression_threshold: 5.0

automation:
  exit_code_policy: threshold   # never | any_fail | threshold
  min_pass_rate: 85.0
  quiet: false
  json_stdout: false
```

### Target Types

| Type | Description | Required Fields |
|------|-------------|-----------------|
| `ollama` | Local Ollama model | `model` |
| `rest` | Any HTTP API accepting text prompts | `endpoint`, `body_template`, `response_field` |

### Environment Variables

Use `${VAR_NAME}` in YAML plans for secrets:

```yaml
headers:
  Authorization: "Bearer ${MY_TOKEN}"
```

Variables are resolved at runtime from the process environment. Unset variables cause a clear error before scanning starts.

## Commands

| Command | Description |
|---------|-------------|
| `run --plan <path>` | Run a YAML scan plan |
| `run --plan <path> --dry-run` | Show what would run |
| `scan --model <name>` | Ad-hoc Ollama scan |
| `scan --target-type rest ...` | Ad-hoc REST scan |
| `validate --plan <path>` | Validate plan syntax |
| `init --plan <path>` | Generate starter template |
| `compare --target <name> --dir <path>` | Compare recent results |
| `health` | Check backend health |
| `probes` | List available probes |
| `models` | List Ollama models |
| `history` | View past scans |
| `report <scan_id>` | Download past reports |
| `status <scan_id>` | Check running scan |
| `start-services` | Start Docker stack |
| `stop-services` | Stop Docker stack |

## Presets

| Preset | Probes | Use Case |
|--------|--------|----------|
| `fast` | dan, encoding | Quick smoke test (~2 min) |
| `default` | dan, encoding, promptinject, toxicity | Balanced daily check |
| `full` | All probes | Comprehensive audit |
| `owasp` | OWASP LLM Top 10 probes | Compliance check |

## Result Comparison

When `compare.enabled: true` in the plan, results are automatically compared with the most recent previous scan for the same target. Regressions above the threshold are flagged.

Manual comparison:
```bash
python hydra_scan.py compare --target llama3.2 --dir ./hydra_reports --threshold 5.0
```

## Automation

### Cron

```bash
# Weekly scan every Monday at 2 AM
0 2 * * 1 cd /opt/hydra/backend && docker compose run --rm cli run --plan /plans/weekly.yaml
```

### CI/CD

```yaml
# ci-gate.yaml
automation:
  exit_code_policy: threshold
  min_pass_rate: 90.0
  quiet: true
  json_stdout: true
```

Exit code 0 = pass, 1 = fail.

### JSON Output

With `json_stdout: true`, machine-readable output goes to stdout:

```json
{
  "plan": "ci-gate",
  "targets": [{"name": "api", "pass_rate": 92.5, "status": "completed"}],
  "overall_pass": true,
  "exit_code": 0
}
```

## Docker Usage

The CLI runs in its own container with `profiles: [cli]` so it does NOT start with normal `docker compose up`.

```bash
# Run a plan
docker compose run --rm cli run --plan /plans/my-scan.yaml --output-dir /reports

# Mount custom plans
docker compose run --rm \
  -v ./my_plans:/plans:ro \
  -v ./my_reports:/reports \
  cli run --plan /plans/scan.yaml --output-dir /reports
```

## Running Tests

```bash
# Inside Docker (recommended)
cd hydra/backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm \
  --entrypoint python cli -m pytest tests/ -v

# Backend REST field tests
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend \
  python -m pytest tests/test_rest_target.py -v
```

## Examples

See `scan_plans/examples/` for ready-to-use scan plans:

- `quick-ollama.yaml` — Minimal local model scan
- `weekly-audit.yaml` — Multi-model weekly audit with comparison
- `website-scan.yaml` — REST endpoint scan
- `ci-gate.yaml` — CI/CD pipeline gate
