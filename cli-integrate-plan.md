---
agent: devin-local
session: polarized-plane
created: 2026-09-12T18:41:49Z
---
# Hydra CLI Scan Tool

Add a Dockerized Python CLI tool with YAML-based scan plans, automated scheduling, result comparison, and support for scanning both local LLMs and website/REST endpoints via the existing backend API.

## Implementation Progress

### Implementation Steps

| Step | Description | Status | Commit |
|------|-------------|--------|--------|
| 1 | Add REST fields to `schemas.py` | DONE | `31969f5` |
| 2 | Pass REST flags in `scan_manager.py` | DONE | `31969f5` |
| 3 | Create `plan_loader.py` | DONE | `31969f5` |
| 4 | Create `comparator.py` | DONE | `31969f5` |
| 5 | Create `hydra_scan.py` | DONE | `31969f5` |
| 6 | Create `requirements.txt` | DONE | `31969f5` |
| 7 | Create example scan plans | DONE | `31969f5` |
| 8 | Create `Dockerfile.cli` | DONE | `31969f5` |
| 9 | Add CLI service to `docker-compose.yml` | DONE | `31969f5` |
| 10 | Create CLI `README.md` | DONE | `31969f5` |

### Test Results

| Group | Tests | Status | Details |
|-------|-------|--------|---------|
| T1: Backend REST fields | 26 tests | PASS | `test_rest_target.py` — schema, command builder |
| T2: Plan Loader | 29 tests | PASS | `test_plan_loader.py` — load, validate, merge, env vars |
| T3: Comparator | 20 tests | PASS | `test_comparator.py` — find, compare, threshold, print |
| T4: CLI (offline) | 21 tests | PASS | `test_hydra_scan.py` — argparse, validate, init, dry-run, help |
| T4: CLI (Docker integration) | 7 verified | PASS | --help, health, dry-run, validate, init, env vars, probes |
| T4: CLI (E2E with Ollama) | 4 verified | PASS | T4.1 plan scan, T4.7 ad-hoc scan, T4.9 comparison, T5.3 Docker scan |
| T5: Docker CLI | 3 verified | PASS | T5.1 --help, T5.2 health, T5.4 not in default compose |
| T6: Regression | verified | PASS | 253 backend tests pass (1 pre-existing failure unrelated) |
| **Total** | **96 automated + 14 manual** | **ALL PASS** | 0 regressions |

### Phase 3 Bug Fixes (found during E2E testing)

- `hydra_scan.py`: `_print_summary` now correctly extracts pass/fail from `result.results.passed/failed` (was looking at `summary.passed` which doesn't exist)
- `hydra_scan.py`: Added `_extract_counts()` helper to centralize pass/fail/total/pass_rate extraction from the backend's JSON structure
- `comparator.py`: `_extract_pass_rate` now checks `result.results.passed/failed` in addition to `summary` and top-level fields
- `comparator.py`: `_extract_probe_rates` now handles both the flat test format (`digest.probe.{passed, failed}`) and the real garak nested format (`digest.group.probe._summary.probe_counts.detection_counts.{passed, fails}`)

### Remaining

| ID | Test | Blocker |
|----|------|---------|
| T4.2 | Multi-target plan end-to-end | Needs plan with multiple available models |
| T4.8 | REST plan scan end-to-end | Needs live REST endpoint |
| T6.3 | Frontend GUI regression | Needs Flutter app |

---

## Architecture Overview

### System Components

Hydra is composed of 6 services. Five run inside Docker on a shared `hydra-network`. The sixth (Ollama) runs on the host machine.

```
┌─── HOST MACHINE ─────────────────────────────────────────────────────────┐
│                                                                         │
│  Ollama  (port 11434)                                                   │
│  ├── Serves local LLM models (llama3.2, mistral, etc.)                  │
│  └── Accessed by Docker via host.docker.internal:11434                   │
│                                                                         │
│  ┌─── DOCKER  (hydra-network) ────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  CLI Container  (hydra-cli)              [NEW - this plan]  │  │  │
│  │  │  ├── Python + requests + websocket-client + PyYAML          │  │  │
│  │  │  ├── Reads YAML scan plans from mounted ./scan_plans/       │  │  │
│  │  │  ├── Talks to Backend via http://backend:8888               │  │  │
│  │  │  ├── Saves reports to mounted ./cli_reports/                │  │  │
│  │  │  └── profiles: [cli] — only runs when explicitly invoked    │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │           │ HTTP REST + WebSocket                                  │  │
│  │           ▼                                                        │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Backend API  (hydra-backend)                   port 8888   │  │  │
│  │  │  ├── FastAPI application (main.py)                          │  │  │
│  │  │  ├── Routes: /api/v1/scan/*, /api/v1/plugins/*, etc.       │  │  │
│  │  │  ├── GarakWrapper: HTTP/SSE client → garak service          │  │  │
│  │  │  ├── Reads/caches JSONL reports from Minio + local FS      │  │  │
│  │  │  ├── WebSocket endpoint: /api/v1/scan/{id}/progress         │  │  │
│  │  │  └── Stores scan metadata in PostgreSQL                     │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │           │ HTTP + SSE (internal)                                  │  │
│  │           ▼                                                        │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Garak Service  (hydra-garak)                   port 9090   │  │  │
│  │  │  ├── Thin FastAPI wrapper (app.py)                          │  │  │
│  │  │  ├── ScanManager: builds garak CLI commands from config     │  │  │
│  │  │  ├── Runs garak as subprocess, parses stdout for progress   │  │  │
│  │  │  ├── Streams progress events via SSE to backend             │  │  │
│  │  │  ├── Uploads reports (JSONL + HTML) to Minio on completion  │  │  │
│  │  │  └── Has garak installed from NVIDIA/garak GitHub main      │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │           │ subprocess                    │ S3 API                 │  │
│  │           ▼                               ▼                        │  │
│  │  ┌────────────────────┐    ┌────────────────────────────────────┐  │  │
│  │  │  garak CLI         │    │  Minio  (hydra-minio)   port 9001 │  │  │
│  │  │  └── Sends attack  │    │  ├── S3-compatible object store   │  │  │
│  │  │      prompts to    │    │  ├── Bucket: hydra-reports        │  │  │
│  │  │      the target    │    │  ├── Stores: JSONL + HTML reports │  │  │
│  │  │      (Ollama or    │    │  └── Console at :9001             │  │  │
│  │  │       REST URL)    │    └────────────────────────────────────┘  │  │
│  │  └────────────────────┘                                            │  │
│  │                             ┌────────────────────────────────────┐  │  │
│  │                             │  PostgreSQL  (hydra-postgres)      │  │  │
│  │                             │  ├── Database: hydra               │  │  │
│  │                             │  ├── Stores: scan metadata, config │  │  │
│  │                             │  ├── Tables: scans, db_meta        │  │  │
│  │                             │  └── Used by: Backend only         │  │  │
│  │                             └────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─── OPTIONAL: Flutter Frontend ──────────────────────────────────────┐│
│  │  ├── Desktop app (macOS/Linux/Windows)                              ││
│  │  ├── Talks to Backend API at http://localhost:8888                   ││
│  │  └── NOT needed for CLI scanning                                    ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Complete Scan Lifecycle

#### Phase 1: Scan Initiation

```
User runs:  hydra_scan.py run --plan weekly-ollama.yaml

Step 1: CLI reads YAML scan plan file from disk
  Parses targets, probes, params, output settings

Step 2: For each target in the plan, CLI fetches preset config (if used)
  CLI ──GET /api/v1/config/presets/fast──▶ Backend
  CLI ◀── { "config": { "generations": 5, "probes": ["dan","encoding"], ... } }

Step 3: CLI merges plan + preset into ScanConfigRequest and starts scan
  CLI ──POST /api/v1/scan/start──▶ Backend
  CLI ◀── { "scan_id": "a1b2c3d4-...", "status": "pending" }
```

#### Phase 2: Backend → Garak Service Handoff

```
Step 4: Backend's GarakWrapper forwards config to Garak Service
  Backend ──POST http://garak:9090/scans──▶ Garak Service

Step 5: Backend saves initial scan state to PostgreSQL

Step 6: Backend starts background task consuming SSE progress stream
  Backend ──GET http://garak:9090/scans/{id}/progress──▶ Garak Service
```

#### Phase 3: Garak Runs the Scan

```
Step 7: ScanManager._build_command() constructs the garak CLI command
  For Ollama:
    python -m garak --target_type ollama --target_name llama3.2 \
      --probes dan,encoding --generations 5 \
      --generator_options '{"ollama":{"host":"http://host.docker.internal:11434"}}'

  For REST:
    python -m garak --target_type rest --target_name "My Chatbot" \
      --rest_endpoint http://site.com/api/chat \
      --rest_headers '{"Authorization":"Bearer tk"}' \
      --rest_body_template '{"msg":"$INPUT"}' \
      --rest_response_json_field "choices[0].message.content" \
      --probes dan,encoding --generations 5

Step 8: ScanManager runs garak as async subprocess, parses stdout

Step 9: Progress events streamed via SSE to Backend
  Backend updates in-memory active_scans + PostgreSQL
```

#### Phase 4: Real-Time Progress to CLI

```
Step 10: CLI connects WebSocket for progress
  CLI ──WS ws://localhost:8888/api/v1/scan/{id}/progress──▶ Backend

Step 11: CLI renders progress in terminal
  [50.0%] Probe: dan.Dan_11_0 (1/2) | Pass: 8 | Fail: 2 | Elapsed: 1m23s | ETA: 1m15s

  (Falls back to REST polling GET /api/v1/scan/{id}/status every 3s if WS drops)
```

#### Phase 5: Completion & Reports

```
Step 12: garak writes JSONL + HTML reports to /data/garak_reports/
Step 13: ScanManager renames files with scan_id, uploads to Minio
Step 14: Final SSE "complete" event → Backend saves to PostgreSQL

Step 15: CLI downloads reports
  CLI ──GET /api/v1/scan/{id}/results──▶ Backend (JSON)
  CLI ──GET /api/v1/scan/{id}/report/html──▶ Backend (HTML)
  CLI writes files to output directory

Step 16: CLI prints terminal summary table
Step 17: If multi-target plan, CLI proceeds to next target (back to Step 3)
Step 18: After all targets, CLI generates comparison summary (if enabled)
```

### Key Files by Service

| Service | Key Files | Role |
|---------|-----------|------|
| **Backend** | `main.py` | FastAPI app entry, mounts all route modules |
| | `api/routes/scan.py` | `/api/v1/scan/*` - start, status, results, history, WebSocket |
| | `api/routes/config.py` | `/api/v1/config/presets/*` - presets + user template CRUD |
| | `api/routes/plugins.py` | `/api/v1/plugins/probes` - list probes |
| | `api/routes/models.py` | `/api/v1/generators/*` - model discovery |
| | `services/garak_wrapper.py` | HTTP/SSE client to garak service, report caching |
| | `services/object_store.py` | Minio/local FS abstraction |
| | `services/config_template_store.py` | DB-backed config template CRUD (already exists) |
| | `models/schemas.py` | `ScanConfigRequest`, `ScanStatus`, etc. |
| | `database/session.py` | SQLAlchemy (PostgreSQL / SQLite fallback) |
| **Garak Service** | `services/garak_service/scan_manager.py` | Builds garak CLI commands, runs subprocess, streams SSE |
| | `services/garak_service/progress_parser.py` | Parses garak stdout → structured events |
| | `services/garak_service/report_uploader.py` | Uploads reports to Minio |
| **Docker** | `docker-compose.yml` | All services + volumes + network |

### Port Map

| Port | Service | Exposed To |
|------|---------|------------|
| 8888 | Backend API | Host + Docker network |
| 9090 | Garak Service | Docker network only |
| 5432 | PostgreSQL | Docker network only |
| 9000/9001 | Minio | Docker network (9001 exposed to host) |
| 11434 | Ollama | Host (Docker via `host.docker.internal`) |

---

## YAML Scan Plan Format

A scan plan is a YAML file that defines **what to scan**, **how to scan it**, and **where to save results**. Users write it once and reuse it for every run.

### Complete Reference

```yaml
# =============================================================================
# Hydra Scan Plan
# =============================================================================
# Save as: scan_plans/my-scan.yaml
# Run as:  python cli/hydra_scan.py run --plan scan_plans/my-scan.yaml
# =============================================================================

# Plan metadata
name: "weekly-security-audit"         # Required. Used in report filenames and history.
description: "Weekly LLM security scan for all production endpoints"  # Optional.
version: "1.0"                        # Optional. Track plan changes over time.

# ─── Global defaults ────────────────────────────────────────────────────
# These apply to ALL targets unless overridden per-target.
defaults:
  preset: fast                        # fast | default | full | owasp | (omit for custom)
  probes:                             # Override preset probes (ignored if preset sets them)
    - dan
    - encoding
    - promptinject
  exclude_probes: "toxicity"          # Comma-separated probes to skip
  generations: 5                      # Prompts per probe (1-500, default: 5)
  eval_threshold: 0.5                 # Pass/fail threshold (0.0-1.0, default: 0.5)
  parallel_attempts: 4                # Parallel probe attempts (default: 4)
  parallel_requests: 10               # Parallel HTTP requests (default: unset)
  timeout_per_probe: 300              # Seconds before a probe times out (default: unset)
  continue_on_error: true             # Keep going if a probe fails (default: false)
  seed: 42                            # Reproducible results (default: random)
  verbose: 0                          # 0=quiet, 1=-v, 2=-vv, 3=-vvv

# ─── Targets ────────────────────────────────────────────────────────────
# Each target is scanned sequentially. Each produces its own report.
targets:

  # --- Target Type 1: Ollama (local LLM) ---
  - name: "llama3.2-local"            # Required. Label for this target.
    type: ollama                      # ollama | rest
    model: llama3.2                   # Ollama model name
    # Per-target overrides (optional — falls back to defaults above):
    # preset: default
    # probes: [dan, encoding, promptinject, malwaregen]
    # generations: 10

  - name: "mistral-local"
    type: ollama
    model: mistral
    preset: owasp                     # Override: use OWASP preset for this target

  # --- Target Type 2: REST / Website (any HTTP LLM endpoint) ---
  - name: "openwebui-prod"
    type: rest
    endpoint: "http://host.docker.internal:3030/api/v1/chat/completions"
    headers:                          # HTTP headers (optional)
      Authorization: "Bearer sk-mytoken123"
    body_template: |                  # JSON body — $INPUT is replaced with attack prompt
      {
        "model": "mistral:latest",
        "messages": [{"role": "user", "content": "$INPUT"}],
        "stream": false
      }
    response_field: "choices[0].message.content"   # JSON path to extract LLM response
    # Per-target overrides:
    probes:
      - dan
      - promptinject
      - encoding
    generations: 10

  - name: "customer-support-bot"
    type: rest
    endpoint: "https://api.myapp.com/chat"
    headers:
      X-API-Key: "abc123"
    body_template: '{"message": "$INPUT"}'
    response_field: "response.text"
    preset: full                      # Full scan for production bot

# ─── Output settings ───────────────────────────────────────────────────
output:
  directory: "./hydra_reports"        # Where to save reports (default: ./hydra_reports)
  formats:                            # Which report formats to save
    - json                            # Structured results (always saved)
    - html                            # Garak's visual report (always saved)
    - summary                         # Terminal summary text saved to file (optional)
  filename_pattern: "{name}_{date}"   # Pattern for filenames (default: "{name}_{date}")
                                      # Variables: {name}, {date}, {time}, {plan}, {preset}
  timestamp_format: "%Y-%m-%d"        # Date format in filenames (default: %Y-%m-%d)
  # Enables easy comparison: weekly runs produce:
  #   hydra_reports/llama3.2-local_2026-01-06.json
  #   hydra_reports/llama3.2-local_2026-01-13.json
  #   hydra_reports/llama3.2-local_2026-01-20.json

# ─── Comparison settings ───────────────────────────────────────────────
compare:
  enabled: true                       # Auto-compare with previous run (default: false)
  baseline_dir: "./hydra_reports"     # Where to find previous results
  fail_on_regression: false           # Exit code 1 if pass rate drops (default: false)
  regression_threshold: 5.0           # Alert if pass rate drops by more than N% (default: 5.0)

# ─── Automation settings ───────────────────────────────────────────────
automation:
  exit_code_policy: "any_fail"        # When to exit non-zero:
                                      #   "never"     - always exit 0
                                      #   "any_fail"  - exit 1 if any probe fails (default)
                                      #   "threshold" - exit 1 if pass rate < min_pass_rate
  min_pass_rate: 80.0                 # Used with exit_code_policy: threshold (default: 80.0)
  quiet: false                        # Suppress progress output, only print summary (for cron)
  json_stdout: false                  # Print JSON summary to stdout (for piping to other tools)
```

### Defaults Reference

When a field is omitted from the YAML, these defaults apply:

| Field | Default | Source |
|-------|---------|--------|
| `defaults.preset` | (none - uses all probes) | -- |
| `defaults.probes` | `["all"]` | `ScanConfigRequest.probes` |
| `defaults.generations` | `5` | `ScanConfigRequest.generations` |
| `defaults.eval_threshold` | `0.5` | `ScanConfigRequest.eval_threshold` |
| `defaults.parallel_attempts` | (unset) | -- |
| `defaults.parallel_requests` | (unset) | -- |
| `defaults.timeout_per_probe` | (unset - no timeout) | -- |
| `defaults.continue_on_error` | `false` | `ScanConfigRequest.continue_on_error` |
| `defaults.seed` | (random) | -- |
| `defaults.verbose` | `0` | `ScanConfigRequest.verbose` |
| `output.directory` | `./hydra_reports` | -- |
| `output.formats` | `[json, html]` | -- |
| `output.filename_pattern` | `{name}_{date}` | -- |
| `output.timestamp_format` | `%Y-%m-%d` | -- |
| `compare.enabled` | `false` | -- |
| `compare.regression_threshold` | `5.0` | -- |
| `automation.exit_code_policy` | `any_fail` | -- |
| `automation.min_pass_rate` | `80.0` | -- |
| `automation.quiet` | `false` | -- |
| `automation.json_stdout` | `false` | -- |

### Minimal Scan Plan (smallest possible)

```yaml
name: "quick-check"
targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
```

This uses all defaults: all probes, 5 generations, 0.5 threshold, JSON + HTML output to `./hydra_reports/`.

---

## Target Reference

### What Can Be Scanned

| Target Type | `type:` value | What It Is | Requirements |
|-------------|---------------|------------|--------------|
| **Ollama** | `ollama` | A local LLM model served by Ollama | Ollama running on host with model pulled |
| **REST/Website** | `rest` | Any HTTP API that accepts text prompts and returns text responses | Network-reachable URL, request/response format known |

### Target Type: `ollama`

Scans an LLM running on the local Ollama instance. Garak sends attack prompts directly to the Ollama API.

```yaml
targets:
  - name: "llama3.2-local"
    type: ollama
    model: llama3.2          # Must match `ollama list` output
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Label for reports and history |
| `type` | Yes | Must be `ollama` |
| `model` | Yes | Ollama model name (e.g., `llama3.2`, `mistral`, `phi3`, `gemma2`) |

**How it maps to garak:** `--target_type ollama --target_name llama3.2`
**Network path:** garak container → `host.docker.internal:11434` → Ollama on host

### Target Type: `rest`

Scans any website or service that exposes an HTTP API accepting a text prompt and returning a text response. This covers:

| Targetable Service | Example `endpoint` |
|--------------------|-------------------|
| **OpenWebUI** | `http://server:3030/api/v1/chat/completions` |
| **Any OpenAI-compatible API** (vLLM, LiteLLM, TGI, Ollama OpenAI mode) | `http://server:8080/v1/chat/completions` |
| **Custom chatbot REST API** | `https://api.myapp.com/chat` |
| **LLM gateway/proxy** | `https://gateway.corp.com/llm/query` |
| **Azure OpenAI** | `https://myinstance.openai.azure.com/openai/deployments/gpt-4/chat/completions` |

**NOT targetable:**
- Static web pages (no LLM endpoint)
- Non-HTTP protocols (gRPC, WebSocket-only)
- APIs that don't return text (image generators, embeddings-only)

```yaml
targets:
  - name: "prod-chatbot"
    type: rest
    endpoint: "https://api.myapp.com/v1/chat/completions"
    headers:
      Authorization: "Bearer sk-abc123"
      Content-Type: "application/json"
    body_template: |
      {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "$INPUT"}],
        "stream": false
      }
    response_field: "choices[0].message.content"
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Label for reports and history |
| `type` | Yes | Must be `rest` |
| `endpoint` | Yes | Full URL of the HTTP API |
| `headers` | No | HTTP headers (auth tokens, content type, etc.) |
| `body_template` | Yes | JSON request body. `$INPUT` is replaced with each attack prompt. |
| `response_field` | Yes | JSON path to extract the LLM's text response from the API response |

**How it maps to garak:** `--target_type rest --target_name "prod-chatbot" --rest_endpoint URL --rest_headers JSON --rest_body_template TPL --rest_response_json_field PATH`

**Network note:** For services on the host machine, use `http://host.docker.internal:<port>` when running CLI in Docker.

---

## Probe Reference

Garak probes are the attack tests. Each probe sends crafted prompts to the target and evaluates the responses.

### Probe Categories

| Probe Family | Category | Severity | What It Tests | OWASP LLM |
|-------------|----------|----------|---------------|-----------|
| `dan` | DAN Jailbreak | Critical | "Do Anything Now" prompts that bypass all safety | LLM01 |
| `promptinject` | Prompt Injection | Critical | Attacker input overriding system instructions | LLM01 |
| `latentinjection` | Latent Prompt Injection | Critical | Hidden instructions in data the model processes | LLM01 |
| `malwaregen` | Malware Generation | Critical | Generating functional exploit/malware code | LLM02 |
| `encoding` | Encoding Attacks | High | Encoded payloads (Base64, ROT13, Braille, Morse) | LLM01 |
| `leakreplay` | Data Leakage | High | Extracting memorized training data / PII | LLM06 |
| `packagehallucination` | Package Hallucination | High | Recommending non-existent packages (supply chain) | LLM09 |
| `goodside` | Prompt Injection | High | Riley Goodside's prompt injection techniques | LLM01 |
| `grandma` | Social Engineering | High | Emotional manipulation jailbreaks | LLM01 |
| `smuggling` | Prompt Smuggling | High | Obfuscated harmful instructions | LLM01 |
| `suffix` | Adversarial Suffix | High | Machine-generated jailbreak suffixes (GCG) | LLM01 |
| `tap` | Automated Red-Team | High | Tree-of-Attacks with Pruning | LLM01 |
| `lmrc` | Risk Cards | High | Toxicity, bias, misinformation | LLM02/09 |
| `donotanswer` | Refusal Bypass | High | Circumventing safety refusals | LLM01 |
| `dra` | Direct Refusal Attack | High | Challenging model refusal behavior | LLM01 |
| `doctor` | Role-Play Jailbreak | High | Medical professional role-play bypass | LLM01 |
| `exploitation` | Exploitation | High | Various exploitation techniques | LLM01 |
| `web_injection` | Web Injection | High | XSS, HTML injection via model output | LLM02 |
| `ansiescape` | ANSI Injection | High | Terminal escape sequence attacks | LLM02 |
| `visual_jailbreak` | Visual Jailbreak | High | Image-embedded jailbreaks (multimodal) | LLM01 |
| `realtoxicityprompts` | Toxicity | High | Toxic language generation | LLM02 |
| `continuation` | Text Continuation | Medium | Completing partial harmful prompts | LLM01 |
| `divergence` | Model Divergence | Medium | Pushing model into unpredictable states | LLM01 |
| `phrasing` | Phrasing Attacks | Medium | Bypassing filters via rephrasing | LLM01 |
| `snowball` | Snowball Attack | Medium | Escalating via false premises | LLM09 |
| `fitd` | Foot-in-the-Door | Medium | Gradual escalation from benign to harmful | LLM01 |
| `glitch` | Glitch Tokens | Medium | Unusual tokens causing unpredictable output | LLM01 |
| `misleading` | Misinformation | Medium | Plausible but false information | LLM09 |
| `topic` | Restricted Topics | Medium | Content on restricted subjects | LLM02 |
| `fileformats` | File Format | Medium | Instructions in structured data | LLM01 |
| `badchars` | Bad Characters | Medium | Special char / null byte injection | LLM01 |
| `apikey` | API Key Leakage | Medium | Generating or completing API keys | LLM06 |
| `av_spam_scanning` | AV/Spam Evasion | Medium | AV/spam filter evasion content | LLM02 |
| `sata` | Automated Analysis | Medium | Automated weakness probing at scale | LLM01 |
| `atkgen` | Auto Attack Gen | High | Automated adversarial prompt generation | LLM01 |

### Presets (Built-in Probe Sets)

| Preset | Probes | Generations | Parallelism | Use Case |
|--------|--------|-------------|-------------|----------|
| `fast` | `dan`, `encoding` | 5 | 10 req / 16 attempts | Quick smoke test (~2 min) |
| `default` | `dan`, `encoding`, `promptinject`, `toxicity` | 10 | 4 attempts | Balanced daily check (~5 min) |
| `full` | ALL probes | 20 | 8 attempts | Comprehensive audit (~30+ min) |
| `owasp` | Probes tagged `owasp:llm*` | 10 | 4 attempts | OWASP Top 10 compliance (~10 min) |

### How Probes Are Selected (Precedence)

```
1. Target-level `probes:` in YAML        (highest priority)
2. Global `defaults.probes:` in YAML
3. Preset's probe list (from backend)
4. All probes (ScanConfigRequest default)  (lowest priority)
```

---

## Example Scan Plans

### 1. Minimal: Quick local model check

```yaml
name: "quick-check"
targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
    preset: fast
```

### 2. Weekly security audit with multiple local models

```yaml
name: "weekly-ollama-audit"
description: "Weekly scan of all local Ollama models"
version: "1.0"

defaults:
  preset: default
  seed: 42

targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2

  - name: "mistral"
    type: ollama
    model: mistral

  - name: "phi3"
    type: ollama
    model: phi3

output:
  directory: "./hydra_reports/weekly"
  filename_pattern: "{name}_{date}"

compare:
  enabled: true
  baseline_dir: "./hydra_reports/weekly"
  regression_threshold: 5.0

automation:
  exit_code_policy: threshold
  min_pass_rate: 85.0
  quiet: true
  json_stdout: true
```

### 3. Production website scan

```yaml
name: "prod-endpoint-audit"
description: "Monthly security audit of production LLM endpoints"

defaults:
  preset: owasp
  generations: 15
  continue_on_error: true

targets:
  - name: "openwebui-prod"
    type: rest
    endpoint: "http://host.docker.internal:3030/api/v1/chat/completions"
    headers:
      Authorization: "Bearer ${OPENWEBUI_TOKEN}"
    body_template: |
      {
        "model": "mistral:latest",
        "messages": [{"role": "user", "content": "$INPUT"}],
        "stream": false
      }
    response_field: "choices[0].message.content"

  - name: "support-bot"
    type: rest
    endpoint: "https://api.myapp.com/chat"
    headers:
      X-API-Key: "${SUPPORT_BOT_KEY}"
    body_template: '{"message": "$INPUT"}'
    response_field: "response.text"
    preset: full

output:
  directory: "./hydra_reports/monthly"
  filename_pattern: "{plan}_{name}_{date}"

compare:
  enabled: true
  fail_on_regression: true
  regression_threshold: 3.0

automation:
  exit_code_policy: threshold
  min_pass_rate: 90.0
```

### 4. CI/CD pipeline scan

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
    response_field: "choices[0].message.content"

automation:
  exit_code_policy: threshold
  min_pass_rate: 90.0
  quiet: true
  json_stdout: true
```

---

## Result Comparison

### How It Works

When `compare.enabled: true`, after each scan the CLI:
1. Scans `compare.baseline_dir` for previous JSON results matching the same target name
2. Finds the most recent previous result by filename timestamp
3. Compares pass rates (overall and per-probe)
4. Prints a comparison table and optionally fails if regression exceeds threshold

### Comparison Output

```
============================================================
  COMPARISON: llama3.2 (2026-01-13 vs 2026-01-06)
============================================================
  Overall Pass Rate:  88.9%  →  91.2%  (+2.3%)  [IMPROVED]
------------------------------------------------------------
  PROBE CHANGES
------------------------------------------------------------
  dan.Dan_11_0           80.0% → 85.0%  (+5.0%)  [IMPROVED]
  encoding.InjectBase64  91.4% → 88.6%  (-2.8%)  [OK]
  promptinject.Hijack    95.0% → 100%   (+5.0%)  [IMPROVED]
------------------------------------------------------------
  No regressions detected.
============================================================
```

### Comparison with Regression Alert

```
============================================================
  COMPARISON: support-bot (2026-02-01 vs 2026-01-01)
============================================================
  Overall Pass Rate:  92.0%  →  84.5%  (-7.5%)  [!! REGRESSION]
------------------------------------------------------------
  PROBE CHANGES
------------------------------------------------------------
  dan.Dan_11_0           90.0% → 72.0%  (-18.0%)  [!! REGRESSION]
  encoding.InjectBase64  95.0% → 93.0%  (-2.0%)   [OK]
  promptinject.Hijack    91.0% → 88.5%  (-2.5%)   [OK]
------------------------------------------------------------
  REGRESSION DETECTED: dan.Dan_11_0 dropped 18.0% (threshold: 3.0%)
  Exit code: 1
============================================================
```

### JSON Stdout for Automation

When `automation.json_stdout: true`, a machine-readable summary goes to stdout:

```json
{
  "plan": "weekly-ollama-audit",
  "timestamp": "2026-01-13T14:30:00Z",
  "targets": [
    {
      "name": "llama3.2",
      "type": "ollama",
      "model": "llama3.2",
      "status": "completed",
      "total_tests": 45,
      "passed": 40,
      "failed": 5,
      "pass_rate": 88.9,
      "duration_seconds": 125,
      "comparison": {
        "previous_date": "2026-01-06",
        "previous_pass_rate": 86.7,
        "delta": 2.2,
        "regressions": []
      },
      "reports": {
        "json": "./hydra_reports/weekly/llama3.2_2026-01-13.json",
        "html": "./hydra_reports/weekly/llama3.2_2026-01-13.html"
      }
    }
  ],
  "overall_pass": true,
  "exit_code": 0
}
```

---

## Automation

### Cron Scheduling

The CLI is designed to be cron-friendly. With `automation.quiet: true` and `json_stdout: true`, it produces minimal output suitable for log aggregation.

```bash
# Weekly scan every Monday at 2 AM
0 2 * * 1 cd /opt/hydra/backend && docker compose run --rm cli run --plan /plans/weekly-ollama.yaml --output-dir /reports >> /var/log/hydra-scan.log 2>&1

# Monthly full audit on the 1st at 3 AM
0 3 1 * * cd /opt/hydra/backend && docker compose run --rm cli run --plan /plans/monthly-full.yaml --output-dir /reports >> /var/log/hydra-audit.log 2>&1

# CI gate (runs on every deployment)
docker compose run --rm cli run --plan scan_plans/ci-gate.yaml --output-dir /reports
# Exit code 0 = pass, 1 = fail → CI pipeline stops on failure
```

### Environment Variable Substitution

YAML plans support `${ENV_VAR}` syntax for secrets so credentials never live in YAML files:

```yaml
targets:
  - name: "prod-api"
    type: rest
    endpoint: "${LLM_ENDPOINT}"
    headers:
      Authorization: "Bearer ${LLM_API_KEY}"
```

The CLI resolves these from the process environment at runtime. Unset variables cause a clear error before the scan starts.

### Exit Code Policy

| Policy | Exit Code | Use Case |
|--------|-----------|----------|
| `never` | Always 0 | Informational scans, dashboards |
| `any_fail` | 1 if any probe has failures | Strict CI gates |
| `threshold` | 1 if overall pass rate < `min_pass_rate` | Practical CI gates with tolerance |

### Docker Compose Integration

```bash
# Run a scan plan in Docker (reports saved to host)
docker compose run --rm cli run --plan /plans/weekly.yaml --output-dir /reports

# Mount custom plans directory
docker compose run --rm \
  -v ./my_scan_plans:/plans:ro \
  -v ./my_reports:/reports \
  cli run --plan /plans/my-scan.yaml --output-dir /reports
```

---

## CLI Command Reference

```bash
# ─── Plan-based scanning (primary workflow) ─────────────────────────────
hydra_scan.py run --plan <path.yaml>              # Run a full scan plan
hydra_scan.py run --plan <path.yaml> --dry-run    # Validate plan, show what would run
hydra_scan.py validate --plan <path.yaml>         # Validate YAML syntax + target reachability
hydra_scan.py init --plan <path.yaml>             # Generate a starter scan plan template

# ─── Ad-hoc scanning (quick one-off) ────────────────────────────────────
hydra_scan.py scan --model llama3.2 --preset fast
hydra_scan.py scan --target-type rest --rest-endpoint URL --rest-body-template TPL ...

# ─── Comparison ─────────────────────────────────────────────────────────
hydra_scan.py compare --target llama3.2 --dir ./hydra_reports/weekly
  # Compares the two most recent results for the given target

# ─── Utility ────────────────────────────────────────────────────────────
hydra_scan.py health                              # Check backend + garak + Ollama
hydra_scan.py probes                              # List all available probes
hydra_scan.py models                              # List Ollama models
hydra_scan.py history                             # View past scans
hydra_scan.py report <scan_id>                    # Download past reports
hydra_scan.py status <scan_id>                    # Check running scan
hydra_scan.py start-services                      # Start Docker stack
hydra_scan.py stop-services                       # Stop Docker stack
```

---

## How to Run (After Implementation)

### One-Time Setup

```bash
cd hydra/backend
cp .env.example .env              # Set POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD
ollama pull llama3.2              # Pull model for local scans
make hydra-dev                    # Build and start Docker stack (~60-90s)
```

### Create a Scan Plan

```bash
# Generate a starter template
python cli/hydra_scan.py init --plan scan_plans/my-scan.yaml
# Edit the generated file to configure targets, probes, output settings
```

### Run a Scan Plan

```bash
# Validate first (dry run)
python cli/hydra_scan.py run --plan scan_plans/my-scan.yaml --dry-run

# Run it
python cli/hydra_scan.py run --plan scan_plans/my-scan.yaml

# Or via Docker (no Python needed on host)
docker compose run --rm cli run --plan /plans/my-scan.yaml --output-dir /reports
```

### Set Up Weekly Automation

```bash
# Add to crontab
crontab -e
# Add:  0 2 * * 1 cd /opt/hydra/backend && docker compose run --rm cli run --plan /plans/weekly.yaml --output-dir /reports >> /var/log/hydra.log 2>&1
```

### Compare Results Over Time

```bash
# Auto-compare (built into scan plan)
# Set compare.enabled: true in YAML — comparison runs automatically after each scan

# Manual compare
python cli/hydra_scan.py compare --target llama3.2 --dir ./hydra_reports/weekly
```

---

## Scope

### In-Scope

| Item | Description |
|------|-------------|
| YAML scan plan format | Declarative YAML files defining targets, probes, params, output |
| Plan-based scanning | `run --plan` command executes full multi-target plans |
| Ad-hoc scanning | `scan --model` / `scan --target-type rest` for quick one-offs |
| Multi-target plans | Scan multiple Ollama models and REST endpoints in one plan |
| Ollama targeting | Local Ollama models |
| REST/website targeting | Any HTTP endpoint with LLM chat interface |
| Preset support | fast / default / full / owasp presets |
| Custom probe selection | Per-target and global-default probe overrides |
| Env var substitution | `${VAR}` in YAML for secrets |
| Default values | Sensible defaults for all optional fields |
| Result comparison | Compare current vs previous results, detect regressions |
| Automation support | Cron-friendly quiet mode, JSON stdout, configurable exit codes |
| Dockerized CLI | Container with profiles: [cli], volume mounts for plans + reports |
| Host-native CLI | Also runnable with `python` directly |
| Real-time progress | WebSocket with REST polling fallback |
| Report download | HTML + JSON saved to configurable directory |
| Plan validation | `--dry-run` and `validate` commands |
| Plan generation | `init --plan` creates starter template |
| Backend REST fields | Small changes to pass REST flags to garak CLI |
| Documentation | README with full YAML reference and examples |

### Out-of-Scope

| Item | Rationale |
|------|-----------|
| Cloud LLM providers (OpenAI, Anthropic) as first-class `type:` | Can be targeted via `type: rest` with their API URLs |
| Custom probe authoring | Complex; better suited for GUI |
| PDF reports | Heavy dependency; HTML covers the need |
| Interactive TUI | Keep simple; plain terminal output |
| Windows support | Not tested; Linux/macOS primary |
| Static website scanning | Garak needs LLM chat interface |
| gRPC / WebSocket targets | Garak only supports HTTP REST |

---

## Implementation Plan (Step by Step)

### Step 1: Backend — Add REST fields to ScanConfigRequest [DONE]

**File:** `backend/models/schemas.py`
**Changes:** Added `REST = "rest"` to `GeneratorType` enum. Added 4 optional fields to `ScanConfigRequest` (rest_endpoint, rest_headers, rest_body_template, rest_response_json_field).
**Lines changed:** 19

### Step 2: Backend — Pass REST flags in garak command builder [DONE]

**File:** `backend/services/garak_service/scan_manager.py`
**Changes:** Added 4 conditionals in `_build_command()` to pass `--rest_*` flags when present.
**Lines changed:** 13

### Step 3: CLI — Create scan plan parser (`plan_loader.py`) [DONE]

**File:** `cli/plan_loader.py` (NEW, 342 lines)
**Content:**
- `load_plan(path) -> dict` — reads YAML, validates schema, resolves env vars
- `validate_plan(plan) -> list[str]` — returns validation errors
- `resolve_env_vars(value) -> str` — substitutes `${VAR}` from os.environ
- `merge_defaults(target, defaults) -> dict` — merges per-target overrides with global defaults
- `plan_to_scan_configs(plan) -> list[ScanConfig]` — converts plan targets into API request payloads

### Step 4: CLI — Create result comparator (`comparator.py`) [DONE]

**File:** `cli/comparator.py` (NEW, 326 lines)
**Content:**
- `find_previous_result(target_name, baseline_dir) -> Path|None` — finds most recent matching JSON
- `compare_results(current, previous) -> ComparisonResult` — computes deltas per-probe and overall
- `print_comparison(result)` — formatted terminal output
- `check_regression(result, threshold) -> bool` — returns True if regression exceeds threshold

### Step 5: CLI — Create main CLI script (`hydra_scan.py`) [DONE]

**File:** `cli/hydra_scan.py` (NEW, 976 lines)
**Content:**
- Argparse setup with subcommands: `run`, `scan`, `validate`, `init`, `compare`, `health`, `probes`, `models`, `history`, `report`, `status`, `start-services`, `stop-services`
- `HydraClient` class — API client wrapper
- `cmd_run(args)` — load plan, iterate targets, start scans, monitor, save reports, compare
- `cmd_scan(args)` — ad-hoc single-target scan
- `cmd_validate(args)` — validate YAML plan
- `cmd_init(args)` — generate starter template
- `cmd_compare(args)` — manual result comparison
- All other commands (health, probes, models, etc.)

### Step 6: CLI — Create requirements.txt [DONE]

**File:** `cli/requirements.txt` (NEW)
```
requests>=2.28.0,<3.0
websocket-client>=1.5.0,<2.0
PyYAML>=6.0,<7.0
```

### Step 7: CLI — Create example scan plans [DONE]

**Files (NEW):**
- `cli/scan_plans/examples/quick-ollama.yaml` — minimal Ollama scan
- `cli/scan_plans/examples/weekly-audit.yaml` — multi-model weekly scan with comparison
- `cli/scan_plans/examples/website-scan.yaml` — REST endpoint scan
- `cli/scan_plans/examples/ci-gate.yaml` — CI pipeline gate scan

### Step 8: Docker — Create CLI Dockerfile [DONE]

**File:** `backend/Dockerfile.cli` (NEW, 28 lines)

### Step 9: Docker — Add CLI service to docker-compose [DONE]

**File:** `backend/docker-compose.yml` — Added `cli` service with `profiles: [cli]`, volume mounts for plans + reports.
**File:** `backend/docker-compose.dev.yml` — Added dev overrides (depends_on, volume mounts).
**Lines changed:** 32

### Step 10: Documentation — Create CLI README [DONE]

**File:** `cli/README.md` (NEW, 236 lines)
**Content:** Full YAML reference, all command examples, setup guide, automation/cron guide, testing instructions.

---

## Test Plan

### T1: Backend REST Field Tests (after Steps 1-2)

| ID | Test | Pass Condition |
|----|------|----------------|
| T1.1 | Schema accepts REST fields | `ScanConfigRequest(target_type="rest", target_name="test", rest_endpoint="http://x", ...)` validates |
| T1.2 | REST fields are optional | `ScanConfigRequest(target_type="ollama", target_name="llama3.2")` validates, REST fields are None |
| T1.3 | `_build_command` includes REST flags | Command list contains all `--rest_*` flags with correct values |
| T1.4 | `_build_command` omits REST flags when absent | No `--rest_*` flags for Ollama config |
| T1.5 | Existing tests pass | `make test-local` passes |

### T2: Plan Loader Tests (after Step 3)

| ID | Test | Pass Condition |
|----|------|----------------|
| T2.1 | Minimal plan loads | `load_plan("quick-check.yaml")` returns valid dict with defaults filled |
| T2.2 | Full plan loads | All fields parsed correctly including nested targets, output, compare, automation |
| T2.3 | Env var substitution | `${MY_VAR}` replaced with env value; unset var raises clear error |
| T2.4 | Default merging | Target without `probes:` inherits from `defaults.probes:` |
| T2.5 | Target override | Target with `preset: owasp` overrides `defaults.preset: fast` |
| T2.6 | Invalid YAML rejected | Missing `name:` or `targets:` returns validation errors |
| T2.7 | Unknown target type | `type: grpc` returns validation error |
| T2.8 | REST missing fields | REST target without `endpoint:` returns validation error |

### T3: Comparator Tests (after Step 4)

| ID | Test | Pass Condition |
|----|------|----------------|
| T3.1 | Find previous result | Finds most recent JSON matching target name in baseline dir |
| T3.2 | No previous result | Returns None gracefully |
| T3.3 | Compare improved | Correctly identifies pass rate increase |
| T3.4 | Compare regression | Correctly identifies pass rate decrease, flags per-probe regressions |
| T3.5 | Threshold check | `regression_threshold: 5.0` triggers only when delta > 5% |

### T4: CLI End-to-End Tests (after Steps 5-6, requires running stack)

| ID | Test | Pass Condition |
|----|------|----------------|
| T4.1 | `run --plan quick-ollama.yaml` | Scan completes, JSON + HTML saved, summary printed |
| T4.2 | `run --plan weekly-audit.yaml` (multi-target) | All targets scanned sequentially, separate reports per target |
| T4.3 | `run --plan ... --dry-run` | Prints what would run, no scan started |
| T4.4 | `validate --plan valid.yaml` | Prints "Plan is valid" |
| T4.5 | `validate --plan invalid.yaml` | Prints validation errors |
| T4.6 | `init --plan new.yaml` | Generates valid starter template |
| T4.7 | `scan --model llama3.2 --preset fast` (ad-hoc) | Scan completes, reports saved |
| T4.8 | REST plan scan | REST target completes, reports saved |
| T4.9 | Comparison output | Second run with `compare.enabled: true` shows delta table |
| T4.10 | `compare --target llama3.2 --dir ./reports` | Manual comparison works |
| T4.11 | Quiet + JSON stdout | `automation.quiet: true` suppresses progress, JSON printed to stdout |
| T4.12 | Exit code threshold | Pass rate < `min_pass_rate` → exit code 1 |
| T4.13 | Env var substitution | `${TEST_VAR}` in YAML resolved from env |
| T4.14 | Invalid model error | Human-readable error, exit code 1 |

### T5: Docker CLI Tests (after Steps 8-9)

| ID | Test | Pass Condition |
|----|------|----------------|
| T5.1 | `docker compose run --rm cli --help` | Prints usage |
| T5.2 | `docker compose run --rm cli health` | Backend healthy via hydra-network |
| T5.3 | `docker compose run --rm cli run --plan /plans/quick.yaml` | Scan completes, reports in mounted volume |
| T5.4 | CLI not in default compose | `docker compose up -d && docker compose ps` — no `hydra-cli` |

### T6: Regression Tests

| ID | Test | Pass Condition |
|----|------|----------------|
| T6.1 | `make test-local` | All existing backend tests pass |
| T6.2 | Backend health | `curl http://localhost:8888/health` → healthy |
| T6.3 | Frontend GUI scan | Start Flutter app, run GUI scan — works normally |

---

## Success Matrix

| # | Criterion | How to Verify | Pass Condition |
|---|-----------|---------------|----------------|
| S1 | **YAML plan loads** | `run --plan quick-ollama.yaml --dry-run` | Plan parsed, targets listed, no errors |
| S2 | **Ollama scan via plan** | `run --plan quick-ollama.yaml` | Scan completes, reports saved |
| S3 | **REST scan via plan** | `run --plan website-scan.yaml` | REST target scanned, reports saved |
| S4 | **Multi-target plan** | `run --plan weekly-audit.yaml` (3 targets) | All 3 scanned sequentially, 3 report sets |
| S5 | **Default values work** | Minimal YAML (name + 1 target) | All defaults applied, scan completes |
| S6 | **Per-target override** | Target with different preset than default | Target uses its own preset |
| S7 | **Env var substitution** | `${MY_TOKEN}` in headers | Resolved from env, scan authenticates |
| S8 | **Progress display** | Watch terminal during plan scan | Updates every 1-3s per target |
| S9 | **JSON report correct** | Inspect saved JSON | Has scan_id, status, pass/fail, probe breakdown |
| S10 | **HTML report renders** | Open in browser | Shows garak visualization |
| S11 | **Comparison works** | Second run with `compare.enabled: true` | Delta table printed, regression detected/reported |
| S12 | **Exit code policy** | `exit_code_policy: threshold`, pass rate < min | Exit code 1 |
| S13 | **Quiet + JSON stdout** | `automation.quiet: true, json_stdout: true` | No progress, JSON on stdout |
| S14 | **Dry run** | `run --plan X --dry-run` | Shows targets/probes, no scan started |
| S15 | **Plan validation** | `validate --plan invalid.yaml` | Clear error messages |
| S16 | **Plan generation** | `init --plan new.yaml` | Valid starter template created |
| S17 | **Docker CLI** | `docker compose run --rm cli run --plan ...` | Works, reports on host volume |
| S18 | **Ad-hoc scan** | `scan --model llama3.2 --preset fast` | Works without YAML |
| S19 | **Error handling** | Bad model / unreachable endpoint | Human-readable error, exit 1 |
| S20 | **No regression** | `make test-local` + GUI scan | All pass, frontend unaffected |
| S21 | **Cron-friendly** | Run from crontab | Completes unattended, log output clean |

---

## Files Created / Modified

### New Files (14) [ALL CREATED]

| File | Description | Lines |
|------|-------------|-------|
| `cli/hydra_scan.py` | Main CLI tool | 976 |
| `cli/plan_loader.py` | YAML plan parser, validator, env var resolver | 342 |
| `cli/comparator.py` | Result comparison engine | 326 |
| `cli/requirements.txt` | `requests`, `websocket-client`, `PyYAML` | 3 |
| `cli/README.md` | Full documentation | 236 |
| `cli/scan_plans/examples/quick-ollama.yaml` | Minimal example | 9 |
| `cli/scan_plans/examples/weekly-audit.yaml` | Multi-model weekly example | 38 |
| `cli/scan_plans/examples/website-scan.yaml` | REST endpoint example | 36 |
| `cli/scan_plans/examples/ci-gate.yaml` | CI pipeline example | 27 |
| `backend/Dockerfile.cli` | CLI Docker image | 28 |
| `backend/tests/test_rest_target.py` | Backend REST field tests | 417 |
| `cli/tests/test_plan_loader.py` | Plan loader tests | 499 |
| `cli/tests/test_comparator.py` | Comparator tests | 330 |
| `cli/tests/test_hydra_scan.py` | CLI tool tests | 251 |

### Modified Files (5) [ALL DONE]

| File | What Changed | Lines Added |
|------|-------------|-------------|
| `backend/models/schemas.py` | `REST` enum + 4 optional REST fields | +19 |
| `backend/services/garak_service/scan_manager.py` | 4 conditionals for `--rest_*` flags | +13 |
| `backend/docker-compose.yml` | `cli` service with plans + reports volumes | +21 |
| `backend/docker-compose.dev.yml` | Dev mode CLI overrides | +11 |
| `backend/Makefile` | `test-rest`, `test-cli-tool`, `test-all` targets | +24 |

**Total: 22 files changed, 4730 insertions, 5 deletions.**

---

## Risks & Considerations

1. **Docker build time**: First `make hydra-dev` takes 5-10 min. Subsequent starts are fast.
2. **Ollama on host**: Docker reaches via `host.docker.internal:11434`. Must be running.
3. **REST target network**: From Docker, use `host.docker.internal` for host services.
4. **Scan duration**: Fast scans ~2 min, full scans ~30+ min. CLI shows progress.
5. **REST headers stored in DB**: Auth tokens are in PostgreSQL scan config.
6. **Env var security**: `${VAR}` resolved at runtime; YAML files should not contain raw secrets.
7. **Comparison accuracy**: Relies on consistent `filename_pattern` + `timestamp_format`. Changing these between runs breaks comparison.
8. **Sequential multi-target**: Targets are scanned one at a time (backend enforces concurrent scan limit).

---

## Future Work

| Item | Description | Priority |
|------|-------------|----------|
| **Parallel multi-target** | Scan multiple targets concurrently (needs backend limit increase) | High |
| **Cloud provider shortcuts** | `type: openai`, `type: anthropic` with built-in body templates | High |
| **Notification hooks** | `notify:` section in YAML for Slack/email/webhook on completion | Medium |
| **Rich terminal UI** | `--rich` flag for colored tables and progress bars | Medium |
| **Report dashboard** | Static HTML dashboard aggregating comparison data over time | Medium |
| **Plan inheritance** | `extends: base-plan.yaml` for shared defaults across plans | Medium |
| **Probe tag filtering** | `probe_tags: owasp:llm01` in YAML targets | Medium |
| **PDF report** | `pdf` in `output.formats` | Low |
| **Windows support** | Test Docker Desktop + WSL2 | Low |
