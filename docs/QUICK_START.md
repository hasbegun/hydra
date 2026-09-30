# Hydra — Quick Start Guide

Step-by-step instructions to set up the entire Hydra platform from scratch, including the backend services, desktop GUI, CLI, and web API documentation.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone & Configure](#2-clone--configure)
3. [Start the Backend Stack](#3-start-the-backend-stack)
4. [Verify the Backend](#4-verify-the-backend)
5. [Launch the Desktop GUI](#5-launch-the-desktop-gui)
6. [Use the CLI](#6-use-the-cli)
7. [Use the REST API](#7-use-the-rest-api)
8. [Run Your First Scan (GUI)](#8-run-your-first-scan-gui)
9. [Run Your First Scan (CLI)](#9-run-your-first-scan-cli)
10. [Run Your First Scan (API)](#10-run-your-first-scan-api)
11. [Enable Multi-Tenancy](#11-enable-multi-tenancy)
12. [Connect Prism (Encrypted Storage)](#12-connect-prism)
13. [Connect Panopticon (Observability)](#13-connect-panopticon)
14. [Production Deployment](#14-production-deployment)
15. [What's Next](#15-whats-next)

---

## 1. Prerequisites

Install these before starting:

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| **Docker** | 24+ | Runs all backend services | [docker.com](https://docs.docker.com/get-docker/) |
| **Docker Compose** | v2+ | Orchestrates multi-container stack | Included with Docker Desktop |
| **Flutter** | 3.9+ | Builds the desktop GUI | [flutter.dev](https://docs.flutter.dev/get-started/install) |
| **Python** | 3.11+ | Runs the CLI (optional, if not using Docker) | [python.org](https://www.python.org/downloads/) |
| **Git** | 2.x | Clone the repository | Pre-installed on most systems |

**Optional but recommended:**

| Tool | Purpose |
|------|---------|
| **Ollama** | Run local LLM models (no API key needed) |
| **OpenAI API key** | Scan OpenAI models (GPT-4o, etc.) |

---

## 2. Clone & Configure

### 2.1 Clone the repository

```bash
git clone <your-repo-url> aegis
cd aegis/hydra
```

### 2.2 Create the environment file

```bash
cd backend
cp .env.example .env
```

### 2.3 Edit `.env` — set required passwords

Open `backend/.env` and set **at minimum** these values:

```env
# ── Required (docker-compose won't start without these) ──────────────
POSTGRES_PASSWORD=your-strong-postgres-password
MINIO_ROOT_PASSWORD=your-strong-minio-password

# ── LLM Provider (set at least one) ──────────────────────────────────
# Option A: OpenAI
OPENAI_API_KEY=sk-...

# Option B: Local Ollama (no key needed, just install Ollama)
# OLLAMA_HOST=http://host.docker.internal:11434

# Option C: Anthropic
# ANTHROPIC_API_KEY=sk-ant-...
```

### 2.4 (Optional) Pull a local model with Ollama

If using Ollama instead of a cloud API:

```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2
ollama pull phi3:mini     # smaller, faster for testing
```

---

## 3. Start the Backend Stack

### 3.1 Development mode (recommended for first-time setup)

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This starts 4 containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `hydra-backend` | **8888** | FastAPI API server (hot-reload in dev) |
| `hydra-garak` | 9090 (internal) | Garak vulnerability scanner |
| `hydra-postgres` | 5432 (internal) | PostgreSQL database |
| `hydra-minio` | **9001** | Minio console (object storage) |

### 3.2 Wait for healthy state

Watch the logs until you see:

```
hydra-backend  | INFO: Uvicorn running on http://0.0.0.0:8888
hydra-garak    | INFO: Uvicorn running on http://0.0.0.0:9090
```

### 3.3 Background mode

To run in the background:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose logs -f    # follow logs
```

### 3.4 Using Make shortcuts

```bash
make hydra-dev            # start dev stack
make hydra-dev-logs       # follow logs
make hydra-dev-down       # stop everything
make hydra-dev-restart    # restart
```

---

## 4. Verify the Backend

### 4.1 Health check

```bash
curl -s http://localhost:8888/health | python3 -m json.tool
```

Expected output:

```json
{
    "status": "running",
    "database": "connected",
    "garak_service": "connected"
}
```

### 4.2 API documentation (Swagger UI)

Open in your browser:

- **Swagger UI:** [http://localhost:8888/docs](http://localhost:8888/docs)
- **ReDoc:** [http://localhost:8888/redoc](http://localhost:8888/redoc)

These show every available endpoint with request/response schemas and a "Try it out" button.

### 4.3 Minio console

Open [http://localhost:9001](http://localhost:9001) and log in with:

- **Username:** `hydra` (or your `MINIO_ROOT_USER`)
- **Password:** the `MINIO_ROOT_PASSWORD` from `.env`

You'll see the `hydra-reports` bucket where scan reports are stored.

---

## 5. Launch the Desktop GUI

The Flutter desktop app provides a graphical interface for scanning, viewing results, and managing scan history.

### 5.1 Install Flutter dependencies

```bash
cd frontend
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs
```

### 5.2 Run the app

```bash
# macOS
flutter run -d macos

# Linux
flutter run -d linux

# Windows
flutter run -d windows

# Web browser
flutter run -d chrome
```

### 5.3 Configure the backend URL

The GUI connects to `http://localhost:8888` by default. To change it:

1. Open the app
2. Go to **Settings** (gear icon or `Cmd/Ctrl + ,`)
3. Update the **Backend URL**

Or edit `frontend/lib/config/constants.dart`:

```dart
static const String apiBaseUrl = 'http://your-server:8888/api/v1';
```

### 5.4 GUI walkthrough

| Screen | What It Does |
|--------|-------------|
| **Home** | Dashboard with quick-scan cards, recent scans, and navigation |
| **New Scan** | Select LLM provider → pick model → choose probes → configure → start |
| **Scan Progress** | Real-time WebSocket progress: current probe, pass/fail counter, ETA |
| **Results** | Interactive report: pass rate, DEFCON rating, per-probe breakdown, heatmap |
| **History** | Browse all past scans, filter, sort, compare two scans side-by-side |
| **Settings** | API keys, backend URL, theme (dark/light), language |
| **Probe Browser** | Search/filter all 200+ probes by category, OWASP mapping |
| **Workflow** | Visual probe dependency graph |

**Keyboard shortcuts:**

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + N` | New scan |
| `Cmd/Ctrl + H` | Scan history |
| `Cmd/Ctrl + ,` | Settings |
| `Cmd/Ctrl + Enter` | Start scan |
| `Cmd/Ctrl + F` | Search |
| `Escape` | Go back |

---

## 6. Use the CLI

The CLI is for scripting, automation, and CI/CD integration.

### 6.1 Install locally (Python)

```bash
cd cli
pip install -r requirements.txt
```

### 6.2 Or run via Docker

```bash
cd backend

# Ad-hoc scan via Docker
docker compose run --rm cli scan --model llama3.2 --preset fast

# Run a YAML plan via Docker
docker compose run --rm cli run --plan /plans/quick-ollama.yaml
```

### 6.3 Key CLI commands

```bash
# Check backend health
python hydra_scan.py health

# List available probes
python hydra_scan.py probes

# List Ollama models
python hydra_scan.py models

# Ad-hoc scan (Ollama)
python hydra_scan.py scan --model llama3.2 --preset fast

# Ad-hoc scan (REST endpoint)
python hydra_scan.py scan \
  --target-type rest \
  --endpoint "https://api.openai.com/v1/chat/completions" \
  --body-template '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"$INPUT"}]}' \
  --response-field '$.choices[0].message.content' \
  --preset owasp

# Generate a scan plan template
python hydra_scan.py init --plan my-scan.yaml

# Validate a plan
python hydra_scan.py validate --plan my-scan.yaml

# Run a plan
python hydra_scan.py run --plan my-scan.yaml

# Dry run (no scanning, just shows what would happen)
python hydra_scan.py run --plan my-scan.yaml --dry-run

# View scan history
python hydra_scan.py history

# Download a report
python hydra_scan.py report <scan_id>

# Compare recent scans for a target
python hydra_scan.py compare --target llama3.2 --dir ./hydra_reports
```

---

## 7. Use the REST API

Every capability is accessible via REST API. The Swagger UI at `http://localhost:8888/docs` is the best interactive reference.

### 7.1 Quick examples

```bash
# Set base URL
export HYDRA="http://localhost:8888"

# Health check
curl -s "$HYDRA/health" | python3 -m json.tool

# List available probes
curl -s "$HYDRA/api/v1/system/probes" | python3 -m json.tool

# Start a scan
curl -s -X POST "$HYDRA/api/v1/scan/start" \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "openai",
    "model_name": "gpt-4o-mini",
    "probes": ["dan.Dan_11_0"]
  }' | python3 -m json.tool

# Check scan status
curl -s "$HYDRA/api/v1/scan/<scan_id>/status" | python3 -m json.tool

# Get vulnerability report
curl -s "$HYDRA/api/v1/scan/<scan_id>/report/vulnerability" | python3 -m json.tool

# Download PDF
curl -s "$HYDRA/api/v1/scan/<scan_id>/report/pdf" -o report.pdf
```

---

## 8. Run Your First Scan (GUI)

1. **Launch the GUI** (`flutter run -d macos`)
2. Click **New Scan** on the home screen
3. **Select provider:** Choose "OpenAI" or "Ollama"
4. **Select model:** Pick `gpt-4o-mini` (OpenAI) or `llama3.2` (Ollama)
5. **Enter API key** if prompted (OpenAI). Ollama needs no key.
6. Click **Next** to select probes
7. Choose **Fast Scan** preset (or hand-pick probes)
8. Click **Start Scan** (`Cmd/Ctrl + Enter`)
9. **Watch progress** — real-time probe results stream in via WebSocket
10. **View results** — pass rate, severity breakdown, per-probe details
11. **Export** — download HTML report or PDF

---

## 9. Run Your First Scan (CLI)

### Option A: Ad-hoc scan (Ollama)

```bash
cd cli
python hydra_scan.py scan --model llama3.2 --preset fast
```

### Option B: Ad-hoc scan (OpenAI)

```bash
export OPENAI_API_KEY=sk-...
cd cli
python hydra_scan.py scan --model gpt-4o-mini --preset fast
```

### Option C: YAML plan

```bash
cd cli

# Generate a template
python hydra_scan.py init --plan my-first-scan.yaml

# Edit it (or use as-is for Ollama llama3.2)

# Run it
python hydra_scan.py run --plan my-first-scan.yaml
```

---

## 10. Run Your First Scan (API)

```bash
# 1. Start scan
SCAN_ID=$(curl -s -X POST "http://localhost:8888/api/v1/scan/start" \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "ollama",
    "model_name": "llama3.2",
    "probes": ["dan.Dan_11_0", "encoding.InjectBase64"]
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['scan_id'])")

echo "Started scan: $SCAN_ID"

# 2. Wait for completion (poll every 10 seconds)
while true; do
  STATUS=$(curl -s "http://localhost:8888/api/v1/scan/$SCAN_ID/status" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))")
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 10
done

# 3. Get vulnerability report
curl -s "http://localhost:8888/api/v1/scan/$SCAN_ID/report/vulnerability" \
  | python3 -m json.tool

# 4. Download PDF
curl -s "http://localhost:8888/api/v1/scan/$SCAN_ID/report/pdf" -o scan-report.pdf
echo "Report saved to scan-report.pdf"
```

---

## 11. Enable Multi-Tenancy

By default, Hydra runs in **single-tenant mode** (no authentication required). To enable multi-tenant isolation with JWT authentication:

### 11.1 Set tenant mode

Add to `backend/.env`:

```env
TENANT_MODE=multi
```

### 11.2 Restart the backend

```bash
docker compose restart backend
```

### 11.3 Create a JWT token

In production, tokens come from Anima (the identity service). For testing:

```bash
TOKEN=$(python3 -c "
import base64, json
header = base64.urlsafe_b64encode(json.dumps({'alg':'none'}).encode()).rstrip(b'=').decode()
payload = base64.urlsafe_b64encode(json.dumps({
    'tenant_id': 'my-company',
    'sub': 'admin-user',
    'roles': ['SYSTEM_ADMIN']
}).encode()).rstrip(b'=').decode()
print(f'{header}.{payload}.test-signature')
")

echo "Token: $TOKEN"
```

### 11.4 Use the token

```bash
# All API calls now require Authorization header
curl -s "http://localhost:8888/api/v1/scan/history" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 11.5 What changes in multi-tenant mode

| Aspect | Single-tenant | Multi-tenant |
|--------|:------------:|:------------:|
| JWT required | No | Yes (every request) |
| Data isolation | All data shared | Filtered by `tenant_id` from JWT |
| Admin endpoints | Open | Requires `SYSTEM_ADMIN` role |
| Target credentials | Per-instance | Per-tenant in Prism |
| Portfolio dashboard | N/A | Cross-tenant view for admins |

---

## 12. Connect Prism (Encrypted Storage)

Prism provides encrypted report and credential storage using Shamir secret sharing.

### 12.1 Deploy Prism

See the [Prism documentation](../../prism/) for deployment instructions. Prism requires at least 3 Minio nodes for its Shamir (3,5) threshold scheme.

### 12.2 Configure Hydra to use Prism

Add to `backend/.env`:

```env
PRISM_ENABLED=true
PRISM_URL=http://prism:8080          # or your Prism deployment URL
PRISM_API_KEY=your-prism-api-key     # from Prism admin
PRISM_CACHE_TTL=300                  # Redis cache TTL (seconds)
PRISM_FALLBACK_TO_MINIO=true         # fall back to local Minio if Prism is down
```

### 12.3 What changes with Prism enabled

- **Reports** are encrypted and stored via Prism (Shamir secret shares across nodes)
- **Target credentials** are stored in Prism (never in Postgres)
- **Read path:** Redis cache → Prism → Minio fallback (3-tier)
- **Health endpoint** reports Prism status
- **Audit trail:** All access logged in OCSF format

---

## 13. Connect Panopticon (Observability)

Panopticon provides real-time observability for scan lifecycle events.

### 13.1 Configure Hydra

Add to `backend/.env`:

```env
PANOPTICON_ENABLED=true
PANOPTICON_URL=http://panopticon:8080
PANOPTICON_API_KEY=your-panopticon-key
PANOPTICON_TIMEOUT=5.0               # seconds (fire-and-forget)
PANOPTICON_BATCH_SIZE=50             # events per batch
```

### 13.2 What gets traced

| Event | When | Data |
|-------|------|------|
| `scan_started` | Scan begins | scan_id, tenant_id, probe count |
| `probe_running` | Each probe starts | probe name, parent scan_id |
| `probe_completed` | Each probe finishes | pass/fail, duration |
| `scan_completed` | Scan finishes | risk score, finding counts |
| `scan_failed` | Scan errors | error message |
| `security_flag` | Critical/high findings | finding severity, count |

Panopticon is **fire-and-forget** — if it's down, scans are unaffected.

---

## 14. Production Deployment

### 14.1 Architecture

```
Load Balancer (HTTPS)
       │
       ▼
┌──────────────┐     ┌───────────┐     ┌───────────┐
│  API (x2+)   │────▶│  Redis    │────▶│  Worker   │
│  FastAPI     │     │  (broker) │     │  (x N)    │
│  :8888       │     └───────────┘     └─────┬─────┘
└──────────────┘                             │
       │                               ┌─────▼─────┐
       ▼                               │  Sandbox   │
┌──────────────┐                       │  (Docker)  │
│  PostgreSQL  │                       └───────────┘
│  (metadata)  │
└──────────────┘     ┌───────────┐
                     │  Prism    │
                     │  (SMPC)   │
                     └───────────┘
```

### 14.2 Production docker-compose

```bash
cd backend

# Build all images
docker compose build

# Start in production mode
docker compose up -d

# Scale workers
docker compose up -d --scale worker=4
```

### 14.3 Production `.env`

```env
# ── Required ──────────────────────────────────────────────────────────
POSTGRES_PASSWORD=<generated-32-char-password>
MINIO_ROOT_PASSWORD=<generated-32-char-password>

# ── Security ──────────────────────────────────────────────────────────
TENANT_MODE=multi
CORS_ORIGINS=https://your-domain.com
LOG_LEVEL=INFO
LOG_FORMAT=json

# ── Prism ─────────────────────────────────────────────────────────────
PRISM_ENABLED=true
PRISM_URL=http://prism:8080
PRISM_API_KEY=<your-prism-api-key>

# ── Sandbox ───────────────────────────────────────────────────────────
SANDBOX_ENABLED=true
SANDBOX_MEMORY_LIMIT=2g
SANDBOX_CPU_COUNT=2
SANDBOX_TIMEOUT_SECONDS=3600
SANDBOX_NETWORK_MODE=none

# ── LLM Keys (passed to garak workers) ───────────────────────────────
OPENAI_API_KEY=sk-...
```

### 14.4 Build the sandbox image

```bash
cd backend
docker build -f Dockerfile.sandbox -t hydra-sandbox:latest .
```

### 14.5 Reverse proxy (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name hydra.your-domain.com;

    ssl_certificate     /etc/ssl/certs/hydra.pem;
    ssl_certificate_key /etc/ssl/private/hydra.key;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (for real-time scan progress)
    location /api/v1/scan/ws/ {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 15. What's Next

### If you're a startup (Scenario 1 — CI/CD Red-Teaming)

1. Register your chat endpoint as a target: `POST /api/v1/targets`
2. Run an OWASP scan and fix critical findings
3. Add the CI/CD gate to your deployment pipeline
4. Set up weekly campaign scheduling + Slack alerts
5. See: [User Guide — Scenario 1](SERVICE_USER_GUIDE.md#4-scenario-1--startup)

### If you're an enterprise (Scenario 2 — Compliance)

1. Register all your models as targets (Azure, Ollama, vLLM, OpenAI)
2. Create a compliance campaign covering all models
3. Generate SOC 2 + ISO 27001 evidence packages
4. Schedule quarterly audits + credential rotation
5. See: [User Guide — Scenario 2](SERVICE_USER_GUIDE.md#5-scenario-2--enterprise)

### If you're a consultancy (Scenario 3 — Multi-Client)

1. Enable multi-tenancy (`TENANT_MODE=multi`)
2. Create client tenants via Anima
3. Register client targets + set up branding
4. Generate branded PDF deliverables
5. Monitor all clients via the portfolio dashboard
6. See: [User Guide — Scenario 3](SERVICE_USER_GUIDE.md#6-scenario-3--consultancy)

### Reference documentation

| Document | Description |
|----------|-------------|
| [User Guide](SERVICE_USER_GUIDE.md) | Scenario-driven usage guide with all 3 use cases |
| [Developer Guide](SERVICE_DEVELOPER_GUIDE.md) | Architecture, extending, testing, and deployment |
| [CLI README](../cli/README.md) | CLI commands, YAML plan format, presets |
| [Swagger UI](http://localhost:8888/docs) | Interactive API explorer (backend must be running) |
| [Final V&V Report](../final-vnv.md) | Verification of all service plan phases |

---

## Appendix: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    HYDRA QUICK REFERENCE                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  START:   cd backend && make hydra-dev                      │
│  STOP:    make hydra-dev-down                               │
│  LOGS:    make hydra-dev-logs                               │
│  HEALTH:  curl http://localhost:8888/health                 │
│  DOCS:    http://localhost:8888/docs (Swagger)              │
│  MINIO:   http://localhost:9001                             │
│                                                             │
│  GUI:     cd frontend && flutter run -d macos               │
│  CLI:     cd cli && python hydra_scan.py scan --model ...   │
│                                                             │
│  SCAN PRESETS:                                              │
│    fast    — dan + encoding           (~2 min)              │
│    default — common vulns             (~5 min)              │
│    owasp   — OWASP LLM Top 10        (~10 min)             │
│    full    — all probes               (~30 min)             │
│                                                             │
│  KEY ENDPOINTS:                                             │
│    POST /api/v1/scan/start          Start a scan            │
│    GET  /api/v1/scan/{id}/status    Check status            │
│    GET  /api/v1/scan/{id}/report/vulnerability  JSON report │
│    GET  /api/v1/scan/{id}/report/pdf            PDF report  │
│    POST /api/v1/scan/gate           CI/CD gate              │
│    POST /api/v1/targets             Register target         │
│    POST /api/v1/campaigns           Create campaign         │
│    GET  /api/v1/admin/portfolio     All-tenant dashboard    │
│                                                             │
│  TESTS:                                                     │
│    Backend:  pytest tests/ (771 tests)                      │
│    CLI:      pytest tests/ (210 tests)                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
