# Hydra Architecture

This document describes the containerized architecture of Hydra, where the backend API and garak vulnerability scanner run as separate services.

---

## Overview

```
                    ┌─────────────────┐
                    │  Flutter App    │
                    │  (Desktop/Web)  │
                    └────────┬────────┘
                             │ HTTP + WebSocket
                             │ port 8888
                    ┌────────▼────────┐
                    │  Backend API    │◄────── PostgreSQL (structured data)
                    │  (FastAPI)      │◄────── Minio (report artifacts)
                    │  hydra-backend  │
                    └────────┬────────┘
                             │ HTTP + SSE
                             │ port 9090 (internal)
                    ┌────────▼────────┐
                    │  Garak Service  │──────► Minio (upload reports)
                    │  (FastAPI thin  │
                    │   wrapper)      │
                    │  hydra-garak    │
                    └────────┬────────┘
                             │ subprocess
                             │ stdout parsing
                    ┌────────▼────────┐
                    │  garak CLI      │
                    │  (Python module)│
                    └────────┬────────┘
                             │ HTTP (LLM API calls)
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         ┌─────────┐  ┌──────────┐  ┌───────────┐
         │ OpenAI  │  │ Ollama   │  │ Anthropic │  ...
         └─────────┘  └──────────┘  └───────────┘
```

## Containers

### Backend API (`hydra-backend`)

The FastAPI backend that serves the frontend. It is a lightweight HTTP client -- it does **not** run garak directly.

- **Port**: 8888
- **Dockerfile**: `backend/Dockerfile`
- **Responsibilities**:
  - Serve REST API for the frontend (scan management, history, settings)
  - WebSocket endpoint for real-time scan progress to the frontend
  - Consume SSE progress stream from the garak service
  - Read scan reports from Minio object store (local filesystem fallback)
  - Persist scan metadata in PostgreSQL (SQLite fallback for dev/tests)
  - Model discovery (Ollama API queries)
- **Does NOT contain**: garak, Rust, or any garak dependencies

### Garak Service (`hydra-garak`)

A thin FastAPI wrapper around the garak CLI. It runs garak as a subprocess and exposes its functionality over HTTP with SSE for progress streaming.

- **Port**: 9090 (internal, not exposed to host)
- **Dockerfile**: `backend/Dockerfile.garak`
- **Responsibilities**:
  - Run garak CLI scans as subprocesses
  - Parse garak stdout for progress (7 regex patterns)
  - Stream progress events to the backend via SSE
  - List plugins (probes, detectors, generators)
  - Write scan reports locally, then upload to Minio
  - Manage scan lifecycle (start, cancel, status)
- **Contains**: Python 3.11, Rust (for base2048), garak, thin FastAPI service

### Ollama (production only, `hydra-ollama`)

Optional container for running local LLM models in production.

- **Port**: 11434
- **Image**: `ollama/ollama:latest`
- **Dev**: Ollama runs on the host machine, containers reach it via `host.docker.internal:11434`
- **Prod**: Runs as a container in the same network

## Data Services

### PostgreSQL (`hydra-postgres`)

Stores structured scan metadata, config templates, and custom probe metadata. Replaces the previous pattern of parsing JSONL files for every query.

- **Image**: `postgres:16-alpine`
- **Port**: 5432 (internal; exposed to host in dev for `psql`/pgAdmin)
- **Volume**: `pg-data` (persistent named volume)
- **Tables**: `scans`, `config_templates`, `custom_probes`, `db_meta`
- **Fallback**: SQLite in-memory for tests, SQLite file for dev without Docker

### Minio (`hydra-minio`)

S3-compatible object store for report artifacts (JSONL, HTML, hitlog). Replaces the shared Docker volume between backend and garak containers.

- **Image**: `minio/minio:latest`
- **Ports**: 9000 (API, internal), 9001 (console, exposed to host)
- **Volume**: `minio-data` (persistent named volume)
- **Bucket**: `hydra-reports`
- **Key pattern**: `{scan_id}/garak.{scan_id}.report.jsonl`

### Data Flow

```
Garak CLI writes to local scratch → Garak Service renames files →
Garak Service uploads to Minio → Backend reads from Minio (cached, immutable)
```

The garak container has its own scratch volume (`garak-scratch`) for temporary CLI output. After scan completion, the garak service uploads the renamed report files to Minio. The backend reads from Minio as the primary source, with local filesystem as fallback for backward compatibility.

## Communication

### Frontend to Backend

Standard HTTP REST + WebSocket, unchanged from before:

- **REST**: `http://localhost:8888/api/v1/*` -- scan management, plugins, history
- **WebSocket**: `ws://localhost:8888/api/v1/scan/{id}/progress` -- real-time updates

### Backend to Garak Service

HTTP REST + SSE (Server-Sent Events):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/version` | GET | Garak version |
| `/plugins/{type}` | GET | List probes/detectors/generators/buffs |
| `/scans` | POST | Start a new scan |
| `/scans/{id}/progress` | GET | SSE stream of progress events |
| `/scans/{id}/status` | GET | Current status snapshot |
| `/scans/{id}` | DELETE | Cancel a running scan |

### Progress Streaming Chain

```
garak CLI stdout  -->  Garak Service (parse + SSE)  -->  Backend (SSE client)  -->  Frontend (WebSocket)
```

1. Garak CLI writes progress to stdout (stderr merged into stdout)
2. Garak service reads stdout line-by-line, parses with regex, emits SSE events
3. Backend consumes SSE stream (with retry logic: 3 attempts, exponential backoff), updates in-memory `active_scans` dict
4. Backend's WebSocket handler polls `active_scans` every 1s, sends full status (including `error_message`) to frontend
5. Flutter WebSocket client parses status, forwards to UI, and disconnects cleanly on terminal status

### Ollama Host Injection

The garak `OllamaGenerator` defaults its host to `127.0.0.1:11434` (localhost inside the container), which won't reach the host machine. To fix this, the scan manager automatically injects the `OLLAMA_HOST` environment variable into `--generator_options` when the target type is Ollama:

```
--generator_options {"ollama": {"host": "http://host.docker.internal:11434"}}
```

This overrides the generator's default and routes requests to the host's Ollama instance.

### API Keys

API keys (OpenAI, Anthropic, etc.) are configured on the **garak container**, since garak is the one making LLM API calls. Keys are passed via docker-compose environment variables from the host `.env` file.

## Docker Compose Configurations

### Default (`docker-compose.yml`)

Four services (backend + garak + PostgreSQL + Minio). Ollama on host.

```bash
docker compose up -d --build
```

### Development (`docker-compose.dev.yml`)

Overlay that adds:
- Hot reload for both backend and garak service (source code mounted)
- Debug logging
- `host.docker.internal` for Ollama on host
- Bind mount for reports (easier to inspect)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
# or simply:
make hydra-dev
```

### Production (`docker-compose.prod.yml`)

Overlay that adds Ollama as a container:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# or simply:
make hydra-prod
```

## Directory Structure

```
backend/
├── Dockerfile                          # Backend API (lightweight, no garak)
├── Dockerfile.garak                    # Garak service (garak + thin API)
├── docker-compose.yml                  # Default: backend + garak + postgres + minio
├── docker-compose.dev.yml              # Dev: hot reload, debug logging, exposed ports
├── docker-compose.prod.yml             # Prod: adds Ollama container
├── Makefile                            # Build & deploy commands
├── main.py                             # Backend entry point
├── config.py                           # Backend settings (DB, Minio, garak service URL)
├── api/routes/                         # REST endpoints
├── database/
│   ├── models.py                       # SQLAlchemy ORM (Scan, ConfigTemplate, etc.)
│   ├── session.py                      # Engine + session management (PG/SQLite)
│   └── migrations.py                   # Schema migrations + backfill from files
├── services/
│   ├── garak_wrapper.py                # HTTP/SSE client to garak service
│   ├── object_store.py                 # Storage abstraction (LocalStorage / MinioStorage)
│   ├── model_discovery.py              # Ollama model discovery
│   ├── workflow_analyzer.py            # Workflow analysis
│   └── garak_service/                  # Garak service (runs in its own container)
│       ├── app.py                      # FastAPI app with SSE endpoints
│       ├── scan_manager.py             # Subprocess lifecycle + Minio upload
│       ├── progress_parser.py          # garak stdout parsing (7 regex patterns)
│       ├── report_uploader.py          # Upload reports to Minio after scan
│       └── requirements.txt            # Service dependencies (incl. minio)
└── models/schemas.py                   # Pydantic models
```

## Error Handling

### Progress Parser

The garak service parses stdout line-by-line using 7 regex patterns for progress, probe counts, results, and report paths. Error detection matches specific Python exception types (`ConnectionError`, `ModuleNotFoundError`, `ImportError`, `RuntimeError`, `FileNotFoundError`, `TimeoutError`, etc.) rather than the generic "Traceback" header, ensuring the user sees the actual error message.

### Scan Failure Diagnostics

When the garak CLI exits with a non-zero code and no specific error pattern was matched, the scan manager includes the last 20 lines of CLI output in the error message. This makes debugging much easier -- the user sees the actual traceback in the UI.

### SSE Consumer Resilience

The backend's SSE consumer (in `garak_wrapper.py`) implements:
- **0.5s startup delay** to let the garak service register the scan
- **3 retries with exponential backoff** for connection failures
- **HTTP status code validation** before consuming the stream
- **Auto-completion** when the stream ends normally and the scan is still in a running state

### WebSocket Error Reporting

The backend WebSocket handler includes `error_message` in every poll message (not just the final one), so the Flutter UI can display the failure reason as soon as the scan fails.

## Key Design Decisions

1. **SSE for backend-to-garak communication**: Simpler than WebSocket for unidirectional streaming. Maps naturally to stdout line parsing. Works well with httpx streaming client.

2. **Minio for report artifacts**: Reports are uploaded to Minio after scan completion. No shared volume between containers. Garak writes locally to scratch, then uploads. Backend reads from Minio (immutable, cached forever).

3. **Thin API wrapper**: The garak service is intentionally minimal -- just wrapping CLI invocations. This keeps it reusable and avoids coupling to Hydra-specific logic.

4. **Scan ID generated by backend**: The backend creates the UUID and passes it to the garak service, keeping the backend as the authoritative source for scan tracking.

5. **Backend as the state authority**: The backend maintains the `active_scans` dict and serves the WebSocket to the frontend. The garak service is stateless from the backend's perspective -- if the backend restarts, it can reconnect to running scans.

6. **Ollama host injection via generator_options**: Rather than relying on the `OLLAMA_HOST` env var (which garak's OllamaGenerator ignores in favor of its hardcoded default), the scan manager explicitly injects the host into `--generator_options`. This ensures garak connects to the correct Ollama instance regardless of the generator's default configuration.

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make hydra-up` | Start backend + garak (default) |
| `make hydra-dev` | Start with hot reload |
| `make hydra-prod` | Start with Ollama container |
| `make hydra-down` | Stop all services |
| `make hydra-garak-shell` | Shell into garak container |
| `make hydra-garak-logs` | View garak service logs |
| `make hydra-garak-health` | Check garak service health |

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `GARAK_SERVICE_URL` | `http://localhost:9090` | URL of the garak service |
| `GARAK_REPORTS_DIR` | `/tmp/garak_reports` | Local fallback directory (Minio is primary) |
| `DATABASE_URL` | (SQLite fallback) | PostgreSQL connection string |
| `STORAGE_BACKEND` | `minio` | Object store backend (`minio` or `local`) |
| `MINIO_ENDPOINT` | `minio:9000` | Minio server endpoint |
| `MINIO_ACCESS_KEY` | `hydra` | Minio access key |
| `MINIO_SECRET_KEY` | (from `.env`) | Minio secret key |
| `MINIO_BUCKET` | `hydra-reports` | Minio bucket name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama URL (for model discovery) |

### Garak Service

| Variable | Default | Description |
|----------|---------|-------------|
| `GARAK_REPORTS_DIR` | `/data/garak_reports` | Local scratch dir for garak CLI output |
| `MINIO_ENDPOINT` | `minio:9000` | Minio server endpoint (for uploads) |
| `MINIO_ACCESS_KEY` | `hydra` | Minio access key |
| `MINIO_SECRET_KEY` | (from `.env`) | Minio secret key |
| `MINIO_BUCKET` | `hydra-reports` | Minio bucket name |
| `OLLAMA_HOST` | (from compose) | Ollama URL (passed to garak CLI) |
| `OPENAI_API_KEY` | (from .env) | OpenAI API key |
| `ANTHROPIC_API_KEY` | (from .env) | Anthropic API key |
| ... | | Other LLM provider keys |
