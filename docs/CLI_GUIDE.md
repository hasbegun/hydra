# Hydra CLI Testing Guide

This guide lists all CLI commands for testing the Hydra containerized services. Use these commands to verify everything works correctly after deployment.

## Prerequisites

Start the services first:

```bash
# Development mode (hot reload)
cd backend
make hydra-dev

# Or production mode (with Ollama container)
make hydra-prod
```

---

## 1. Health Checks

### Backend Health (port 8888)

```bash
curl -s http://localhost:8888/health | python -m json.tool
```

Expected:
```json
{
    "status": "healthy"
}
```

### Backend System Health

```bash
curl -s http://localhost:8888/api/v1/system/health | python -m json.tool
```

Expected:
```json
{
    "status": "healthy",
    "garak_available": true,
    "message": "OK"
}
```

If garak service is down:
```json
{
    "status": "degraded",
    "garak_available": false,
    "message": "Garak not installed or not accessible"
}
```

### Garak Service Health (internal, via docker exec)

```bash
docker compose exec garak python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:9090/health').read().decode())"
```

Or from within the backend container:
```bash
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://garak:9090/health').read().decode())"
```

Expected:
```json
{"status": "healthy", "garak_installed": true}
```

### Makefile shortcuts

```bash
make health          # Backend health
make hydra-garak-health    # Garak service health (via backend container)
```

---

## 2. Version & System Info

### Backend Version

```bash
curl -s http://localhost:8888/version | python -m json.tool
```

Expected:
```json
{
    "backend_version": "1.0.0",
    "api_version": "v1",
    "python_version": "3.11.x",
    "garak_version": "0.9.x.y.dev0"
}
```

### System Info (includes garak version + available generators)

```bash
curl -s http://localhost:8888/api/v1/system/info | python -m json.tool
```

Expected:
```json
{
    "garak_version": "0.9.x.y.dev0",
    "python_version": "3.11.x",
    "backend_version": "1.0.0",
    "garak_installed": true,
    "available_generators": ["openai", "huggingface", "ollama", "..."]
}
```

### Root Endpoint

```bash
curl -s http://localhost:8888/ | python -m json.tool
```

Expected:
```json
{
    "name": "Hydra Backend API",
    "version": "1.0.0",
    "status": "running",
    "docs": "/api/docs"
}
```

---

## 3. Plugin Discovery

### List Probes

```bash
curl -s http://localhost:8888/api/v1/plugins/probes | python -m json.tool
```

Expected:
```json
{
    "plugins": [
        {"name": "dan.Dan_11_0", "full_name": "probes.dan.Dan_11_0", "description": "...", "active": true},
        "..."
    ],
    "total_count": 150
}
```

### List Detectors

```bash
curl -s http://localhost:8888/api/v1/plugins/detectors | python -m json.tool
```

### List Generators

```bash
curl -s http://localhost:8888/api/v1/plugins/generators | python -m json.tool
```

### List Buffs

```bash
curl -s http://localhost:8888/api/v1/plugins/buffs | python -m json.tool
```

### Refresh Plugin Cache

```bash
curl -s -X POST http://localhost:8888/api/v1/plugins/cache/refresh | python -m json.tool
```

Expected:
```json
{
    "message": "Plugin cache invalidated",
    "ttl_seconds": 300
}
```

---

## 4. Model Discovery

### List Models for a Generator Type

```bash
# OpenAI models
curl -s http://localhost:8888/api/v1/generators/openai/models | python -m json.tool

# Ollama models (fetched dynamically from Ollama)
curl -s http://localhost:8888/api/v1/generators/ollama/models | python -m json.tool

# Anthropic models
curl -s http://localhost:8888/api/v1/generators/anthropic/models | python -m json.tool
```

Available generator types: `openai`, `huggingface`, `anthropic`, `cohere`, `replicate`, `ollama`, `litellm`, `nim`, `groq`, `mistral`, `azure`, `bedrock`

### All Models

```bash
curl -s http://localhost:8888/api/v1/generators/models/all | python -m json.tool
```

### Recommended Models

```bash
curl -s http://localhost:8888/api/v1/generators/models/recommended | python -m json.tool
```

### Ollama Status

```bash
curl -s http://localhost:8888/api/v1/generators/ollama/status | python -m json.tool
```

Expected:
```json
{
    "connected": true,
    "host": "http://host.docker.internal:11434"
}
```

### Refresh Ollama Models

```bash
curl -s -X POST http://localhost:8888/api/v1/generators/ollama/refresh | python -m json.tool
```

### Validate an API Key

```bash
curl -s -X POST http://localhost:8888/api/v1/generators/validate-api-key \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-..."}' | python -m json.tool
```

Expected:
```json
{
    "valid": true,
    "provider": "openai",
    "message": "OpenAI API key is valid",
    "details": null
}
```

---

## 5. Configuration Presets

### List Presets

```bash
curl -s http://localhost:8888/api/v1/config/presets | python -m json.tool
```

Expected:
```json
[
    {"name": "fast", "description": "Quick scan with parallel execution", "config": {"generations": 5, "...": "..."}},
    {"name": "default", "description": "Balanced scan with common probes", "config": {"...": "..."}},
    {"name": "full", "description": "Comprehensive scan with all probes", "config": {"...": "..."}},
    {"name": "owasp", "description": "OWASP LLM Top 10 focused scan", "config": {"...": "..."}}
]
```

### Get a Specific Preset

```bash
curl -s http://localhost:8888/api/v1/config/presets/fast | python -m json.tool
```

### Validate Config

```bash
curl -s -X POST http://localhost:8888/api/v1/config/validate \
  -H "Content-Type: application/json" \
  -d '{"target_type": "openai", "target_name": "gpt-3.5-turbo"}' | python -m json.tool
```

Expected:
```json
{
    "valid": true,
    "message": "Configuration is valid"
}
```

---

## 6. Scan Lifecycle

### Start a Scan

```bash
curl -s -X POST http://localhost:8888/api/v1/scan/start \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "ollama",
    "target_name": "llama3.2",
    "probes": ["dan.Dan_11_0"],
    "generations": 5
  }' | python -m json.tool
```

Expected:
```json
{
    "scan_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "status": "pending",
    "message": "Scan initiated successfully",
    "created_at": "2025-01-01T00:00:00.000000"
}
```

**Note**: Replace `ollama` / `llama3.2` with your actual generator and model. For OpenAI, use `"target_type": "openai", "target_name": "gpt-3.5-turbo"` and make sure the `OPENAI_API_KEY` is set in `.env`.

### Check Scan Status

```bash
curl -s http://localhost:8888/api/v1/scan/{scan_id}/status | python -m json.tool
```

Expected (while running):
```json
{
    "scan_id": "...",
    "status": "running",
    "progress": 0.25,
    "current_probe": "dan.Dan_11_0",
    "completed_probes": 1,
    "total_probes": 4,
    "passed": 10,
    "failed": 2,
    "error_message": null
}
```

### Cancel a Running Scan

```bash
curl -s -X DELETE http://localhost:8888/api/v1/scan/{scan_id}/cancel | python -m json.tool
```

Expected:
```json
{
    "message": "Scan xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx cancelled successfully"
}
```

### Delete a Scan (and its reports)

```bash
curl -s -X DELETE http://localhost:8888/api/v1/scan/{scan_id} | python -m json.tool
```

Expected:
```json
{
    "message": "Scan xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx deleted successfully"
}
```

### WebSocket Progress (via wscat)

```bash
# Install wscat if needed: npm install -g wscat
wscat -c ws://localhost:8888/api/v1/scan/{scan_id}/progress
```

Expected (JSON messages every ~1 second):
```json
{
    "scan_id": "...",
    "status": "running",
    "progress": 0.5,
    "current_probe": "dan.Dan_11_0",
    "completed_probes": 2,
    "total_probes": 4,
    "passed": 15,
    "failed": 3,
    "timestamp": "2025-01-01T00:01:00.000000"
}
```

---

## 7. Scan History & Results

### Scan History (paginated)

```bash
curl -s "http://localhost:8888/api/v1/scan/history?page=1&page_size=10" | python -m json.tool
```

Expected:
```json
{
    "scans": [
        {
            "scan_id": "...",
            "status": "completed",
            "target_type": "ollama",
            "target_name": "llama3.2",
            "started_at": "...",
            "completed_at": "...",
            "passed": 40,
            "failed": 5,
            "total_tests": 45,
            "progress": 1.0,
            "html_report_path": "/data/garak_reports/...",
            "jsonl_report_path": "/data/garak_reports/..."
        }
    ],
    "pagination": {
        "page": 1,
        "page_size": 10,
        "total_items": 3,
        "total_pages": 1,
        "has_next": false,
        "has_previous": false
    },
    "total_count": 3
}
```

### Query Parameters for History

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | 1 | Page number |
| `page_size` | 20 | Items per page (max 100) |
| `sort_by` | `started_at` | Sort field: `started_at`, `completed_at`, `status`, `target_name`, `pass_rate` |
| `sort_order` | `desc` | Sort order: `asc` or `desc` |
| `status` | (none) | Filter: `completed`, `running`, `failed`, `cancelled` |
| `search` | (none) | Search by target name or scan ID |

Example with filters:
```bash
curl -s "http://localhost:8888/api/v1/scan/history?status=completed&sort_by=pass_rate&sort_order=asc" | python -m json.tool
```

### Get Scan Results (detailed probe breakdown)

```bash
curl -s http://localhost:8888/api/v1/scan/{scan_id}/results | python -m json.tool
```

### Get HTML Report

```bash
curl -s http://localhost:8888/api/v1/scan/{scan_id}/report/html -o report.html
```

### Get Detailed HTML Report (inline)

```bash
curl -s http://localhost:8888/api/v1/scan/{scan_id}/report/detailed
```

---

## 8. Docker Compose Commands

### Start / Stop

| Command | Description |
|---------|-------------|
| `make hydra-dev` | Start dev mode (hot reload, local Ollama) |
| `make hydra-dev-down` | Stop dev mode |
| `make hydra-dev-logs` | Follow dev mode logs |
| `make hydra-dev-restart` | Restart dev services |
| `make hydra-up` | Start default mode (detached) |
| `make hydra-up-build` | Build and start |
| `make hydra-down` | Stop services |
| `make hydra-down-v` | Stop and remove volumes |
| `make hydra-prod` | Start prod mode (backend + garak + ollama) |
| `make hydra-prod-down` | Stop prod mode |
| `make hydra-prod-logs` | Follow prod mode logs |

### Debugging

| Command | Description |
|---------|-------------|
| `make hydra-logs` | Follow all service logs |
| `make hydra-ps` | List running services |
| `make hydra-config` | Validate and view compose config |
| `make hydra-garak-shell` | Shell into garak container |
| `make hydra-garak-logs` | Follow garak service logs |
| `make hydra-garak-health` | Check garak service health |
| `make docker-status` | Show container status |

### Direct Docker Compose

```bash
# Dev mode
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f
docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# Prod mode
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

---

## 9. Garak Service Internal API (port 9090)

These endpoints run inside the Docker network. Access them via `docker compose exec`:

### Health

```bash
docker compose exec garak curl -s http://localhost:9090/health | python -m json.tool
```

### Version

```bash
docker compose exec garak curl -s http://localhost:9090/version | python -m json.tool
```

Expected:
```json
{"version": "0.9.x.y.dev0"}
```

### List Plugins

```bash
docker compose exec garak curl -s http://localhost:9090/plugins/probes | python -m json.tool
docker compose exec garak curl -s http://localhost:9090/plugins/detectors | python -m json.tool
docker compose exec garak curl -s http://localhost:9090/plugins/generators | python -m json.tool
docker compose exec garak curl -s http://localhost:9090/plugins/buffs | python -m json.tool
```

### Start a Scan (directly on garak service)

```bash
docker compose exec garak curl -s -X POST http://localhost:9090/scans \
  -H "Content-Type: application/json" \
  -d '{"scan_id": "test-001", "config": {"target_type": "ollama", "target_name": "llama3.2", "probes": ["dan.Dan_11_0"], "generations": 5}}' | python -m json.tool
```

Expected:
```json
{"scan_id": "test-001", "status": "running", "message": "Scan started"}
```

### Stream Progress (SSE)

```bash
docker compose exec garak curl -s -N http://localhost:9090/scans/test-001/progress
```

Expected (SSE stream):
```
event: progress
data: {"event_type": "progress", "progress": 0.5, "completed_probes": 1, "total_probes": 2}

event: result
data: {"event_type": "result", "probe": "dan.Dan_11_0", "passed": 5, "failed": 0}
```

### Check Scan Status

```bash
docker compose exec garak curl -s http://localhost:9090/scans/test-001/status | python -m json.tool
```

### Cancel a Scan

```bash
docker compose exec garak curl -s -X DELETE http://localhost:9090/scans/test-001 | python -m json.tool
```

### List Active Scans

```bash
docker compose exec garak curl -s http://localhost:9090/scans | python -m json.tool
```

### List Report Files

```bash
docker compose exec garak curl -s http://localhost:9090/reports | python -m json.tool
```

---

## 10. Quick Verification Checklist

Run these commands in sequence to verify the full stack is working:

```bash
# 1. Start services
cd backend
make hydra-dev

# 2. Wait for services to be ready
sleep 10

# 3. Check backend health
curl -s http://localhost:8888/health | python -m json.tool

# 4. Check garak connectivity
curl -s http://localhost:8888/api/v1/system/health | python -m json.tool

# 5. Get version info
curl -s http://localhost:8888/version | python -m json.tool

# 6. List probes (verifies garak plugin discovery works)
curl -s http://localhost:8888/api/v1/plugins/probes | python -m json.tool | head -20

# 7. Check Ollama status
curl -s http://localhost:8888/api/v1/generators/ollama/status | python -m json.tool

# 8. Start a test scan (replace with your model)
curl -s -X POST http://localhost:8888/api/v1/scan/start \
  -H "Content-Type: application/json" \
  -d '{"target_type": "ollama", "target_name": "llama3.2", "probes": ["dan.Dan_11_0"], "generations": 2}' | python -m json.tool

# 9. Check scan status (use scan_id from step 8)
curl -s http://localhost:8888/api/v1/scan/{scan_id}/status | python -m json.tool

# 10. View scan history
curl -s http://localhost:8888/api/v1/scan/history | python -m json.tool
```

---

## 11. Troubleshooting

### "Garak is not installed or not accessible"

The backend cannot reach the garak service. Check:

```bash
# Are both containers running?
make hydra-ps

# Check garak container logs
make hydra-garak-logs

# Test garak health from inside the network
make hydra-garak-health
```

### Scan starts but no progress

Check garak service logs for subprocess errors:

```bash
make hydra-garak-logs
```

Common causes:
- Missing API keys in `.env` (for OpenAI, Anthropic, etc.)
- Ollama not running on host (for Ollama generator)
- Invalid model name

### Cannot connect to Ollama

In dev mode, Ollama runs on the host. Containers reach it via `host.docker.internal`:

```bash
# Verify Ollama is running on host
curl -s http://localhost:11434/api/tags | python -m json.tool

# Check from inside the container
docker compose exec backend curl -s http://host.docker.internal:11434/api/tags | python -m json.tool
```

### Container won't start

```bash
# Check build errors
docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache

# Check startup logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs
```

### API Docs

Interactive API documentation is available at:
- Swagger UI: http://localhost:8888/api/docs
- ReDoc: http://localhost:8888/api/redoc
