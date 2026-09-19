# Nexus Scan Troubleshooting Report

This document chronicles every issue encountered while integrating the Nexus (Okta-protected) chat application as a scan target in Hydra, including root causes, debugging reasoning, and the fixes applied.

---

## Architecture Overview

```
hydra/backend/
  ├── services/garak_service/scan_manager.py   # Builds & runs garak CLI commands
  ├── services/garak_wrapper.py                # Wraps garak, manages scan lifecycle
  ├── api/routes/scan.py                       # REST API for scan start/status/results
  └── docker-compose.yml                       # uvicorn → garak service → garak CLI

hydra/cli/
  ├── hydra_scan.py            # CLI tool: runs plans, monitors progress, saves reports
  ├── plan_loader.py           # Validates & loads YAML scan plans
  └── scan_plans/nexus-test.yaml  # Nexus scan configuration
```

**Execution chain:**
```
User → make scan-nexus
       → docker compose run cli hydra_scan.py run --plan nexus-test.yaml
         → CLI calls backend API POST /api/v1/scan/start
           → Backend's scan_manager builds garak CLI command
             → asyncio.create_subprocess_exec("python", "-m", "garak", ...)
               → garak runs probes against the Nexus REST API
```

---

## Issue 1: `daemonic processes are not allowed to have children`

**Commit:** `a74f279` — Fix: daemonic processes error when garak uses multiprocessing

### Symptom
```
File "/usr/local/lib/python3.11/site-packages/garak/probes/base.py", line 346, in _execute_all
    for result in attempt_pool.imap_unordered(
AssertionError: daemonic processes are not allowed to have children
```

### Investigation

The error occurs in Python's `multiprocessing.Pool` when a **daemon process** tries to spawn child processes. I traced the full execution chain to find where the daemon flag was being set:

1. **Uvicorn reload mode**: The garak service's `docker-compose.yml` starts uvicorn with `LOG_LEVEL=DEBUG`, which translates to `reload=True` in the uvicorn startup command.

2. **Uvicorn's reload supervisor** uses `multiprocessing.get_context("spawn")` to create a `spawn.Process` for the actual app worker. This worker process (PID 409081 in the container) is where the FastAPI app runs.

3. **scan_manager** uses `asyncio.create_subprocess_exec` to start garak. This does a real OS-level `fork + exec`, creating a completely new Python process. I verified via `docker exec` that this subprocess has `daemon=False` — so the subprocess itself is fine.

4. **The real trigger**: The `fast` preset (fetched from the backend) included `parallel_attempts: 16` and `parallel_requests: 10`. The scan_manager was passing these as `--parallel_attempts 16 --parallel_requests 10` to garak's CLI.

5. **Inside garak**, `probes/base.py` line 346 checks:
   ```python
   if self.parallel_attempts and self.parallel_attempts > 1 and self.parallelisable_attempts:
       attempt_pool = multiprocessing.Pool(self.parallel_attempts)
   ```
   With `parallel_attempts=16`, garak creates a `multiprocessing.Pool(16)`.

6. **The conflict**: garak's `detectors/base.py` line 109 calls `torch.multiprocessing.set_start_method("spawn", force=True)` during import. This changes the **global** multiprocessing start method from `fork` to `spawn`. When garak then creates a Pool using `spawn`, each worker inherits process context from the parent. Although the garak subprocess itself isn't daemonic, the combination of the spawn context and the uvicorn environment triggers the assertion.

### Why it only happens in the service container

Running garak directly on the host (e.g., `python -m garak ...`) works fine because:
- No uvicorn parent process setting multiprocessing context
- No `set_start_method("spawn", force=True)` interference
- Default `fork` start method, fresh MainProcess with `daemon=False`

### Fix

**Strip `--parallel_attempts` and `--parallel_requests`** from the garak command in `scan_manager.py`. These flags trigger multiprocessing.Pool inside garak, which is unsafe when garak is invoked from the service container. Sequential execution is adequate for REST targets where the bottleneck is network latency, not CPU.

```python
# scan_manager.py — after building the command
STRIP_FLAGS = ("--parallel_requests", "--parallel_attempts")
```

### Files changed
- `backend/services/garak_service/scan_manager.py` — Strip parallel flags
- `backend/tests/test_cli_flags.py` — Assert flags are NOT in garak command

---

## Issue 2: `unrecognized arguments: --continue_on_error`

**Commit:** `382e954` — Fix: remove --continue_on_error from garak command

### Symptom
```
python -m garak: error: unrecognized arguments: --continue_on_error
```
Process exited with code 2.

### Root cause

`continue_on_error` is a **Hydra plan-level** setting that tells the CLI to continue to the next target when one fails. It is NOT a garak CLI flag. The scan_manager was blindly including it in the garak command because it appeared in the scan config dictionary.

I verified which flags garak actually accepts by running:
```bash
docker exec hydra-garak python -m garak --help
```
Confirmed: garak accepts `--verbose`, `--eval_threshold`, `--generations`, `--seed` — but NOT `--continue_on_error`.

### Fix

Added `continue_on_error` to the exclusion list in `scan_manager.py` alongside `parallel_requests` and `parallel_attempts`.

### Files changed
- `backend/services/garak_service/scan_manager.py`
- `backend/tests/test_cli_flags.py`
- `backend/tests/test_rest_target.py`

---

## Issue 3: Scan completes with 0 tests (wrong API endpoint)

**Commit:** `eccb8c1` — Fix nexus-test.yaml: correct API endpoint and body format

### Symptom
```
Total: 0 tests, Passed: 0, Failed: 0, Pass Rate: 0.0%
```
Garak log showed:
```
POST /api/chat HTTP/1.1" 200 None
ERROR: Expecting value: line 1 column 1 (char 0)
```

### Investigation

The endpoint returned HTTP 200 but an **empty body**. This seemed like the body format was wrong. But the actual problem was deeper.

I started by fetching the app's runtime configuration:
```bash
curl https://isioaiffwwebuat06.azurewebsites.net/app-config.js
```
Response:
```javascript
window.__APP_CONFIG__ = {
  "NEXUS_API_BASE_URL": "https://isioaiffwwebuat07.azurewebsites.net/api/Nexus"
};
```

**Key discovery:** The Nexus architecture has two separate Azure Web Apps:
- `isioaiffwwebuat06` — **Frontend SPA** (React). Serves HTML for all routes including `/api/chat`. This is why we got a 200 with empty JSON — garak was hitting the SPA, which returned the HTML shell.
- `isioaiffwwebuat07` — **Backend API** (ASP.NET with Swagger at `/swagger`).

I then discovered the Swagger spec:
```bash
curl https://isioaiffwwebuat07.azurewebsites.net/swagger/v1/swagger.json
```

This revealed the complete API surface — over 100 endpoints. The chat endpoint is:
- `POST /api/Nexus/PromptOrchestrator` (streaming, used by the UI)
- `POST /api/Nexus/PromptOrchestratorEval` (non-streaming, better for scanning)

The request schema (`PromptOrchestratorRequest`) requires:
```json
{
  "prompt": "string",       // the user message
  "conversationId": 0,      // 0 = new conversation
  "username": "string",     // REQUIRED by server validation
  "clientTimeZone": "string", // REQUIRED by server validation
  "conversationMode": false,
  "responseMode": "text",
  "isWidgetOrigin": false
}
```

I confirmed by sending a test request to `PromptOrchestratorEval` — got a proper validation error (400) instead of HTML, proving it was the correct endpoint.

### Fix

Updated `nexus-test.yaml`:
- **Endpoint**: Changed from `isioaiffwwebuat06/api/chat` to `isioaiffwwebuat07/api/Nexus/PromptOrchestratorEval`
- **body_template**: Changed from `{"message": "$INPUT"}` to the full `PromptOrchestratorRequest` schema with required fields
- **response_field**: Kept as `$.response` (to be confirmed with live test)

### Files changed
- `cli/scan_plans/nexus-test.yaml`

---

## Issue 4: 415 Unsupported Media Type

**Commit:** `f87393d` — Fix 415 Unsupported Media Type and Bearer prefix handling

### Symptom
```
ConnectionError: REST URI client error: 415 - Unsupported Media Type,
uri: https://isioaiffwwebuat07.azurewebsites.net/api/Nexus/PromptOrchestratorEval
```

### Root cause

The ASP.NET backend requires `Content-Type: application/json`. Garak's `RestGenerator._call_model` sends the request body via Python's `requests.post(data=request_data)` — using the `data=` parameter instead of `json=`.

When you use `json=`, the `requests` library automatically sets `Content-Type: application/json`. But with `data=`, it defaults to `application/x-www-form-urlencoded`. The ASP.NET endpoint rejects this with 415.

The relevant garak code (in `generators/rest.py`):
```python
data_kw = "params" if self.http_function == requests.get else "data"
req_kArgs = {
    data_kw: request_data,       # ← uses data=, NOT json=
    "headers": request_headers,  # ← no auto Content-Type
}
```

### Fix

Modified `_inject_auth_headers` in `hydra_scan.py` to also inject `Content-Type: application/json` alongside the auth token. Uses `setdefault()` so it doesn't override if the user already set a custom Content-Type.

```python
scan_config["rest_headers"].setdefault("Content-Type", "application/json")
```

Also applied the same fix to the `--auth-token` CLI flag path.

### Files changed
- `cli/hydra_scan.py` — Add Content-Type to auth header injection
- `cli/tests/test_hydra_scan.py` — 7 new tests

---

## Issue 5: Bearer prefix duplication

**Commit:** `f87393d` — (same commit as Issue 4)

### Symptom

When a user copies the full Authorization header from DevTools and pastes it:
```bash
export OKTA_TOKEN="Bearer eyJraWQ..."
```

The CLI would produce `Authorization: Bearer Bearer eyJraWQ...` (double Bearer prefix).

### Root cause

The `_inject_auth_headers` function always prepends `Bearer `:
```python
scan_config["rest_headers"][header_name] = f"{token_prefix}{token}"
```
If the token already contains "Bearer ", it gets doubled.

### Fix

Added Bearer prefix stripping in three places:
1. `_resolve_auth_token` — strips from env var value
2. `_resolve_auth_token` — strips from refresh command output
3. `cmd_scan` — strips from `--auth-token` CLI flag

```python
if token.lower().startswith("bearer "):
    token = token[7:].strip()
```

Case-insensitive matching and extra whitespace handling included.

---

## Issue 6: Terminal disconnect kills scan

**Commit:** `918e98c` — Add background scan targets (nohup)

### Symptom

Long-running scans (Nexus probes take 10-30+ minutes) get killed when the SSH session disconnects or the terminal is closed. Docker Compose `run` is a foreground process attached to the terminal's process group.

### Fix

Added `nohup`-based Makefile targets:

| Target | Purpose |
|--------|---------|
| `make scan-nexus-bg` | Run scan in background via nohup |
| `make scan-nexus-status` | Check if scan is running + show log tail |
| `make scan-nexus-stop` | Kill a running background scan |

Logs are timestamped (`nexus-scan-YYYYMMDD-HHMMSS.log`) so multiple runs don't overwrite each other.

### Files changed
- `backend/Makefile`

---

## Issue 7: No interim reports during long scans

**Commit:** (current) — Add incremental report saving

### Symptom

During a 30+ minute scan, there's no on-disk report until the scan finishes. If the process dies mid-scan, all results are lost.

### Fix

Added interim report saving every 30 seconds during scan progress monitoring:
- `_save_interim_report()` — Writes a JSON snapshot of current scan state
- `_cleanup_interim_report()` — Removes interim file after final report is saved
- Both REST polling and WebSocket monitoring paths save interim reports
- If the results API is unavailable, falls back to status data

Interim files are written to `{output_dir}/{target_name}_interim.json` and overwritten each cycle. On scan completion, the final report replaces it.

---

## Commit Summary

| # | Commit | Issue | Key Insight |
|---|--------|-------|-------------|
| 1 | `adecf75` | Okta auth support | New `auth` section for YAML plans, token injection |
| 2 | `e95fc95` | Makefile scan targets | One-command scanning with `make scan-nexus` |
| 3 | `382e954` | `--continue_on_error` rejected | Hydra plan-level flag, not a garak CLI flag |
| 4 | `a74f279` | Daemon process error | uvicorn reload + multiprocessing.Pool conflict |
| 5 | `eccb8c1` | 0 tests (wrong endpoint) | Frontend SPA (06) vs Backend API (07) |
| 6 | `f87393d` | 415 + Bearer duplication | garak uses `data=` not `json=`; prefix stripping |
| 7 | `918e98c` | Terminal disconnect | nohup + timestamped logs |
| 8 | (current) | No interim reports | Save JSON snapshots every 30s during scan |

---

## Test Coverage

All changes maintain backward compatibility. Test counts across the fix series:

| Stage | Backend | CLI | Total |
|-------|---------|-----|-------|
| Before Nexus work | 254 | 146 | 400 |
| After auth support | 254 | 171 | 425 |
| After daemon fix | 255 | 171 | 426 |
| After 415 + Bearer fix | 255 | 178 | 433 |
| After interim reports | 255 | 182 | 437 |

The single pre-existing test failure (`test_timeline.py` collection error) is unrelated to this work.
