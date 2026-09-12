# H1: Database Backend for Persistence

**Status:** Implemented
**Difficulty:** Hard (1-3 days)
**Created:** 2026-02-12
**Completed:** 2026-02-12

---

## Why This Matters

### Current State: Everything Is Files

Hydra stores all data as flat files on a shared Docker volume:

| Data | Format | Location |
|------|--------|----------|
| Scan reports | JSONL | `garak.{id}.report.jsonl` |
| Scan metadata | Embedded in JSONL first entry | Same file |
| Config templates | Individual JSON files | `config_templates/{slug}.json` |
| Custom probes | `.py` files + `metadata.json` | `~/.garak/custom_probes/` |
| Scan history | Reconstructed by globbing + parsing all JSONLs | N/A |
| Workflow graphs | In-memory only | Lost on restart |
| Active scans | In-memory dict | Lost on restart |

### The 5 Core Problems This Solves

**1. Scan History Is O(n) Per Request**
To list 100 scans, the backend globs all `garak.*.report.jsonl` files, opens each one, parses the first JSON entry, extracts metadata, then sorts/filters in memory. As scans accumulate, history gets slower. A DB query is O(1) with an index.

**2. No Query Capability**
"Show me all failed scans against llama3 from last week" requires loading every scan into memory, then filtering. SQL: `WHERE status='failed' AND target='llama3' AND date > '...'`.

**3. Statistics Are Expensive**
`get_scan_statistics()` iterates every report file, parses every JSONL line, counts probe failures across all of them. With a DB, this is an aggregate query.

**4. No Atomic Operations**
Config template save = write JSON file + hope no concurrent write. Custom probe create = write .py file + update metadata.json separately (can get out of sync). DB provides ACID transactions.

**5. Data Lost on Restart**
Active scan tracking, workflow graphs, and scan status are in-memory. Container restart = gone. A DB persists this state.

### What This Does NOT Replace

- **JSONL report files stay.** They're garak's native output format, used for raw data access and the upcoming per-probe drill-down (H16). The DB indexes metadata *about* them, not replaces them.
- **Custom probe `.py` files stay.** They're executable Python code. The DB replaces only the `metadata.json` index.

---

## Architecture Decision: SQL vs NoSQL vs SQLite

### Why SQL at All? (SQL vs NoSQL)

Hydra data is **relational and structured** — scans have a fixed schema (target, status, timestamps, counts), config templates have a fixed schema, probes have a fixed schema. The primary access patterns are:

| Access Pattern | Best Fit |
|---------------|----------|
| "List scans filtered by status + target + date range" | SQL (WHERE + INDEX) |
| "Aggregate pass rates across all scans" | SQL (GROUP BY + AVG) |
| "Get top 10 failing probe categories" | SQL (GROUP BY + ORDER BY + LIMIT) |
| "CRUD config templates by name" | Either |
| "Store flexible per-probe metadata" | NoSQL (schema-less) |

**NoSQL options considered:**

| Option | Pros | Cons for Hydra |
|--------|------|----------------|
| **MongoDB** | Flexible schema, JSON-native | New container + credentials. Overkill — Hydra data is well-structured, not schema-evolving. Aggregation pipelines are harder to write/maintain than SQL. |
| **Redis** | Fast key-value, great for caching | Not a primary data store. No complex queries. Already have in-memory caching. |
| **TinyDB** | Pure Python, JSON-based, zero config | No concurrent access support. No indexing beyond basic. Loads entire DB into memory. Fine for <1K records, breaks at scale. |
| **LiteDB / UnQLite** | Embedded NoSQL | Poor Python ecosystem. Niche libraries with uncertain maintenance. |

**NoSQL would make sense if:**
- Schema was evolving rapidly (it's not — scan metadata is stable)
- Data was deeply nested/document-oriented (JSONL reports are, but we keep those as files)
- We needed horizontal scaling (single-user desktop app)

**SQL wins because:**
- All 3 data types (scans, templates, probes) have rigid, well-known schemas
- The most important queries are filters + aggregations = SQL's core strength
- SQLAlchemy provides a mature ORM with migration tooling
- No additional infrastructure (SQLite is embedded)

### SQL Engine: SQLite → PostgreSQL

| Factor | SQLite | PostgreSQL |
|--------|--------|------------|
| Deployment | Zero config, single file | Separate container, credentials, networking |
| Docker complexity | None (file on shared volume) | New service in docker-compose + health checks |
| Separation of concerns | **Embedded in backend** — violates container isolation | **Own container** — clean separation |
| Concurrent reads | Excellent (WAL mode) | Excellent |
| Concurrent writes | Adequate (1 writer at a time) | Excellent (MVCC) |
| Backup | Copy one file | pg_dump / pg_basebackup |
| Data volume | < 100K scans easily | Millions+ |
| Full-text search | FTS5 extension (built-in) | Built-in tsvector |
| JSON queries | json_extract() (basic) | jsonb operators (powerful) |
| Python driver | Built into stdlib | Requires psycopg2 or asyncpg |

**H1 Phase 1 used SQLite** as a rapid prototype to validate the ORM models and migration logic. All code uses SQLAlchemy ORM — no raw SQL, no SQLite-specific features.

**PostgreSQL is the target** because:
- Clean separation of concerns — DB is its own container, backend is stateless
- Proper concurrent write support (MVCC) for when multi-user is added
- Richer JSON support (`jsonb` operators) for config/probe metadata
- Standard production database with mature tooling (pg_dump, replication, monitoring)
- Follows the same principle as Minio — each service is its own container

**Migration effort is minimal** because SQLAlchemy abstracts the dialect. The only changes:
- Connection string: `sqlite:///path` → `postgresql://user:pass@postgres:5432/hydra`
- Remove SQLite-specific pragmas (WAL mode, foreign_keys)
- Add `psycopg2-binary` to requirements.txt
- Add PostgreSQL container to docker-compose.yml

### Decision Summary

```
Files (current) → SQL (relational, structured) → PostgreSQL (own container)
                  ✗ NoSQL (data is structured,     ✗ SQLite (embedded in backend
                    queries are relational)            violates separation of concerns)
```

### Target Architecture: 4 Containers

```
┌──────────────────────────────────────────────────────────────────┐
│                        hydra-network                             │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │   Backend    │   │ Garak Service│   │    Ollama    │        │
│  │  (port 8888) │   │  (port 9090) │   │  (port 11434)│        │
│  │              │   │              │   │              │        │
│  │  Stateless   │   │  garak CLI   │   │  LLM engine  │        │
│  │  FastAPI app │   │  + upload    │   │              │        │
│  └──────┬───┬───┘   └──────┬───────┘   └──────────────┘        │
│         │   │              │                                     │
│    SQL  │   │ S3 API       │ S3 API                             │
│         │   │              │                                     │
│  ┌──────▼───┘    ┌────────▼─────┐                               │
│  │              │              │                               │
│  │ PostgreSQL  │    Minio     │                               │
│  │ (port 5432) │  (port 9000) │                               │
│  │             │              │                               │
│  │ Structured  │  Artifacts   │                               │
│  │ metadata    │  JSONL/HTML  │                               │
│  └─────────────┘  └─────────────┘                               │
│        ▲                 ▲                                       │
│   pg-data vol       minio-data vol                              │
└──────────────────────────────────────────────────────────────────┘
```

Each container has exactly one responsibility:
- **Backend**: API logic, WebSocket, scan orchestration (stateless)
- **Garak Service**: Run garak CLI, parse output, upload artifacts (stateless)
- **PostgreSQL**: Structured data (scans, templates, probes)
- **Minio**: Immutable artifacts (JSONL, HTML, hitlog reports)
- **Ollama**: LLM inference (external)

---

## Database Schema

```sql
-- Core scan tracking
CREATE TABLE scans (
    id TEXT PRIMARY KEY,              -- scan UUID
    target_type TEXT NOT NULL,         -- e.g., "ollama"
    target_name TEXT NOT NULL,         -- e.g., "llama3"
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/running/completed/failed/cancelled
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_probes INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    pass_rate REAL,
    error_message TEXT,
    report_path TEXT,                  -- path to JSONL file (relative)
    config_json TEXT,                  -- snapshot of ScanConfig used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_scans_target ON scans(target_type, target_name);
CREATE INDEX idx_scans_started ON scans(started_at DESC);

-- Config templates (replaces individual JSON files)
CREATE TABLE config_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    config_json TEXT NOT NULL,         -- ScanConfig as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom probe metadata (replaces metadata.json)
CREATE TABLE custom_probes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    tags TEXT,                         -- JSON array of tags
    file_path TEXT NOT NULL,           -- relative path to .py file
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Intentionally NOT in the DB:**
- Individual probe results / attempts (stay in JSONL — too large, already structured, parsed on demand for H16)
- Workflow graph data (rebuilt from JSONL on demand — not worth caching)

---

## Implementation Plan

### Phase 1: Database Foundation
**Files to create:**
- `backend/database/models.py` — SQLAlchemy ORM models (Scan, ConfigTemplate, CustomProbe)
- `backend/database/session.py` — Engine creation, session factory, DB init
- `backend/database/migrations.py` — Simple migration system (create tables if not exist + version tracking)

**Depends on:** Nothing
**Estimated effort:** 2-3 hours

### Phase 2: Scan Metadata Migration
**Files to modify:**
- `backend/services/garak_wrapper.py` — Write scan metadata to DB on create/update/complete; read from DB for history/stats

**What changes:**
- `start_scan()` → INSERT into scans table
- `update_scan_status()` → UPDATE scans table (new method, called from SSE handler)
- `get_all_scans()` → SELECT from scans table (replaces glob + parse all files)
- `get_scan_results()` → SELECT metadata from DB + parse JSONL for detailed results
- `get_scan_statistics()` → SQL aggregation (replaces iterating all files)
- `delete_scan()` → DELETE from DB + remove files

**Backward compatibility:** On first startup, scan the existing JSONL files and backfill the scans table. This is a one-time migration.

**Depends on:** Phase 1
**Estimated effort:** 3-4 hours

### Phase 3: Config Templates Migration
**Files to modify:**
- `backend/services/config_template_store.py` — Replace file I/O with DB queries

**What changes:**
- `list_templates()` → SELECT all
- `get_template()` → SELECT by name
- `save_template()` → INSERT
- `update_template()` → UPDATE
- `delete_template()` → DELETE

**Backward compatibility:** On first startup, import existing JSON template files into the DB.

**Depends on:** Phase 1
**Estimated effort:** 1-2 hours

### Phase 4: Custom Probes Metadata Migration
**Files to modify:**
- `backend/services/custom_probe_service.py` — Replace metadata.json with DB queries

**What changes:**
- `_read_metadata()` / `_write_metadata()` → DB queries
- CRUD operations use DB for metadata, file system for `.py` files only

**Backward compatibility:** On first startup, import existing metadata.json into the DB.

**Depends on:** Phase 1
**Estimated effort:** 1-2 hours

### Phase 5: Remove File Caching Layer
**Files to modify:**
- `backend/services/garak_wrapper.py` — Remove `_report_cache`, `_scan_info_cache` for metadata queries (keep `_results_cache` for JSONL parsing)

**Rationale:** The 3-tier caching was needed because file parsing was the bottleneck. With scan metadata in the DB, the cache layers for listing/history are no longer needed. Keep the JSONL entry cache since detailed results still read from files.

**Depends on:** Phase 2
**Estimated effort:** 1 hour

### Phase 6: Update Tests
**Files to modify/create:**
- `backend/tests/test_database.py` — Unit tests for DB models and session
- Update `backend/tests/test_scan_statistics.py` — Use DB-backed queries
- Update `backend/tests/test_config_templates.py` — Use DB-backed store

**Depends on:** Phases 2-4
**Estimated effort:** 2-3 hours

---

## Total Effort Estimate

| Phase | Effort |
|-------|--------|
| 1. DB Foundation | 2-3 hours |
| 2. Scan Metadata | 3-4 hours |
| 3. Config Templates | 1-2 hours |
| 4. Custom Probes | 1-2 hours |
| 5. Remove Cache | 1 hour |
| 6. Tests | 2-3 hours |
| **Total** | **10-15 hours** |

---

## Dependencies

**Python packages:**
- `sqlalchemy>=2.0` — ORM + query builder (already added)
- `psycopg2-binary>=2.9` — PostgreSQL driver (replaces built-in sqlite3)
- `minio>=7.0` — S3-compatible client for Minio

**Docker services to add:**
- `postgres:16-alpine` — PostgreSQL container (~80 MB image)
- `minio/minio:latest` — Minio S3 container (~200 MB image)

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Backfill is additive — never deletes JSONL files |
| PostgreSQL container goes down | Health checks + restart policy in docker-compose |
| Breaking existing API contracts | API responses don't change — only internal storage changes |
| Test disruption | Tests use in-memory SQLite for speed; PostgreSQL only in integration tests |

---

## What This Unlocks

Once H1 is done, these features become much easier:

- **H2 (Scheduled Scans):** Store cron schedules in the DB
- **H3 (Webhooks):** Store webhook URLs + event history in the DB
- **VH1 (API Auth):** Store users/tokens in the DB
- **VH2 (RBAC):** Store roles/permissions in the DB
- **VH3 (Audit Logging):** Store audit events in the DB
- **VH9 (Analytics Dashboard):** SQL aggregation instead of file iteration

H1 is the foundation that almost every "Hard" and "Very Hard" feature depends on.

---

## H1.1: Containerized Data Services (PostgreSQL + Minio)

**Status:** Implemented
**Completed:** 2026-02-14
**Prerequisite:** H1 (Database Backend) — completed (SQLite prototype)

### The Remaining Problems

H1 proved the ORM models and migration logic work, but two separation-of-concerns issues remain:

1. **SQLite is embedded in the backend container** — the DB file sits on a shared volume, the backend process owns it. If the backend restarts, DB connections drop. If we scale to multiple backend instances, SQLite can't handle concurrent writes.

2. **Report artifacts sit on a shared Docker volume** — the garak container writes JSONL/HTML files, the backend reads them from the same mount. This is filesystem coupling.

```
BEFORE H1:     Everything on shared filesystem (bad)
AFTER H1:      Metadata in embedded SQLite, artifacts on shared volume (better)
AFTER H1.1:    Metadata in PostgreSQL container, artifacts in Minio container (clean)
```

### Inter-Container Communication

This is a critical architectural decision. Each communication pattern has trade-offs:

#### Current Communication (Before H1.1)

```
Frontend ──WebSocket──► Backend ──HTTP/SSE──► Garak Service
                           │                       │
                           ├── file read ──────────┤  (shared volume = coupling)
                           └── SQLite (embedded) ──┘
```

| Path | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| Frontend → Backend | WebSocket + HTTP REST | Request/Response | UI operations, progress streaming |
| Backend → Garak Service | HTTP REST + SSE | Request/Stream | Start scan, cancel, progress events |
| Backend ↔ Reports | Filesystem (shared vol) | Read/Write | JSONL/HTML report access |
| Backend ↔ SQLite | In-process (embedded) | Read/Write | Metadata queries |

#### Target Communication (After H1.1)

```
Frontend ──WebSocket──► Backend ──HTTP/SSE──► Garak Service
                           │                       │
                           ├── SQL (TCP) ─► PostgreSQL
                           │                       │
                           └── S3 API (HTTP) ─► Minio ◄── S3 API ─┘
```

#### Protocol Analysis: Which Pattern for What?

| Communication | Options | Decision | Rationale |
|---------------|---------|----------|-----------|
| **Backend → PostgreSQL** | SQL over TCP | **Direct SQL (SQLAlchemy)** | Standard, mature, connection pooling built-in. No reason to add a layer. |
| **Backend → Minio** | S3 API (HTTP) | **Direct S3 client** | Minio speaks S3 natively. `minio` Python SDK handles auth, streaming, retries. |
| **Garak Service → Minio** | S3 API (HTTP) | **Direct S3 client** | Upload after scan completion. Same SDK. |
| **Backend → Garak Service** | HTTP REST + SSE | **Keep current** | Already works well. SSE for progress streaming is the right pattern. |
| **Scan lifecycle events** | HTTP callbacks / Message queue / SSE | **Keep SSE (current)** | See analysis below. |

#### Deep Dive: Scan Lifecycle Event Communication

The most interesting question is how the garak service tells the backend "scan completed, reports uploaded." Three options:

**Option 1: Keep SSE (Current — Recommended for now)**
```
Garak Service ──SSE stream──► Backend
  "status: complete"
  "report_path: s3://hydra-reports/{scan_id}/report.jsonl"
```
- Already implemented and working
- Garak service emits events as they happen
- Backend consumes the SSE stream in `_consume_progress_stream()`
- Just add Minio object keys to the existing event payloads
- **Pro:** Zero new infrastructure. **Con:** Tight coupling — backend must be listening.

**Option 2: Message Queue (Redis/RabbitMQ/NATS)**
```
Garak Service ──publish──► Message Queue ──subscribe──► Backend
  {"event": "scan_complete", "scan_id": "...", "report_key": "..."}
```
- Decoupled: garak service doesn't need to know about backend
- Durable: messages survive container restarts
- Supports multiple consumers (if backend scales)
- **Pro:** True decoupling, guaranteed delivery. **Con:** Another container, more complexity.

**Option 3: Webhook/HTTP Callback**
```
Garak Service ──POST /webhook──► Backend
  {"event": "scan_complete", "scan_id": "...", "report_key": "..."}
```
- Simple: just an HTTP POST from garak to backend
- **Pro:** Easy to implement. **Con:** If backend is down, event is lost. Needs retry logic.

**Decision: Keep SSE for H1.1, plan message queue for future.**

Rationale:
- SSE is already working and battle-tested in the codebase
- Hydra is currently single-backend-instance — no fan-out needed
- Adding a message queue is justified when we need: multi-instance backend (horizontal scaling), durable event replay, or webhook notifications (H3)
- The SSE event payload just needs a new field: `"report_key": "s3://..."` — minimal change

**Future evolution path:**
```
H1.1:  SSE (current, works)
H3:    Add Redis/NATS for webhook event bus (when implementing webhook support)
VH1:   Redis becomes shared session store for multi-instance auth
```

#### Docker Networking

All containers communicate over a single bridge network (`hydra-network`). No ports exposed between containers — only through Docker DNS:

```yaml
services:
  backend:     → connects to postgres:5432, minio:9000, garak:9090
  garak:       → connects to minio:9000, ollama:11434
  postgres:    → listens on 5432 (internal only)
  minio:       → listens on 9000 (internal), 9001 (console, optional external)
  ollama:      → listens on 11434 (host or container)
```

No shared volumes between any containers. Each has its own named volume for persistence.

### Why Minio?

| Factor | Shared Volume | Minio (S3-compatible) |
|--------|--------------|----------------------|
| **Coupling** | Backend + garak both mount same path | Each service talks to Minio independently |
| **Scaling** | Single-node only (shared filesystem) | Works across nodes (network storage) |
| **Interface** | OS-specific file paths | Standard S3 API (portable to AWS/GCS) |
| **Lifecycle** | Manual cleanup, no retention policies | Built-in versioning, TTL, lifecycle rules |
| **Access control** | Unix permissions only | Per-bucket policies, pre-signed URLs |
| **Observability** | `ls -la`, `du` | Dashboard, metrics, audit logs |
| **Backup/Export** | Manual `tar` | `mc mirror`, S3-compatible tools |

### What Goes Where

```
┌─────────────────────────────────────┐
│            SQLite (hydra.db)        │
│  • Scan metadata (status, times)    │
│  • Config templates                 │
│  • Custom probe metadata            │
│  • Schema version, backfill state   │
├─────────────────────────────────────┤
│           Minio (S3 buckets)        │
│  • garak.{id}.report.jsonl  (3-5MB) │
│  • garak.{id}.hitlog.jsonl  (16-600KB) │
│  • garak.{id}.report.html   (6-32KB)  │
├─────────────────────────────────────┤
│         Filesystem (no sharing)     │
│  • Custom probe .py files (local)   │
│  • Garak CLI temp output (ephemeral)│
└─────────────────────────────────────┘
```

### Architecture

```
┌──────────────┐        ┌──────────────┐
│ Garak Service│        │   Backend    │
│  (port 9090) │        │  (port 8888) │
│              │        │              │
│ garak CLI    │        │  DB (SQLite) │
│   ↓ writes   │        │    ↑ read    │
│ /tmp/reports/│        │              │
│   ↓ uploads  │        │  Minio ←─────│── read/stream
│   ↓          │        │              │
└──────┬───────┘        └──────────────┘
       │  upload via S3 API
       ▼
┌──────────────┐
│    Minio     │
│  (port 9000) │
│              │
│ Bucket:      │
│  hydra-reports│
│   ├ {id}/report.jsonl │
│   ├ {id}/hitlog.jsonl │
│   └ {id}/report.html  │
└──────────────┘
       ▲
       │ persistent volume
   minio-data (Docker named volume)
```

**Key flow change:** Garak service writes to local `/tmp`, then uploads to Minio after scan completes. Backend reads from Minio (with local caching for parsed JSONL).

### Docker Compose: New Services

```yaml
# docker-compose.yml additions

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-hydra}
      POSTGRES_USER: ${POSTGRES_USER:-hydra}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg-data:/var/lib/postgresql/data
    networks:
      - hydra-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hydra"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9001:9001"   # Web console (optional, for debugging)
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-hydra}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio-data:/data
    networks:
      - hydra-network
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  backend:
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-hydra}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-hydra}
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-hydra}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      MINIO_BUCKET: hydra-reports
      STORAGE_BACKEND: minio   # or "local" for dev without Minio

  garak:
    depends_on:
      minio:
        condition: service_healthy
    environment:
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-hydra}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      MINIO_BUCKET: hydra-reports

volumes:
  pg-data:       # PostgreSQL data (persistent)
  minio-data:    # Minio object data (persistent)
```

**Credentials:** All secrets come from env vars / `.env` file — never hardcoded in compose.

### Implementation Phases

#### Phase A: Minio Container + Client Library
- Add `minio` Python package to requirements.txt
- Add Minio container to docker-compose.yml
- Create `backend/services/object_store.py` — S3 client wrapper
- Auto-create `hydra-reports` bucket on startup
- Config: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`

#### Phase B: Garak Service Upload
- After scan completes, garak service uploads report files to Minio
- Object key pattern: `{scan_id}/report.jsonl`, `{scan_id}/hitlog.jsonl`, `{scan_id}/report.html`
- Delete local temp files after successful upload
- Update progress event to include Minio paths

#### Phase C: Backend Read from Minio
- Modify `_get_report_entries()` to fetch JSONL from Minio (with local cache)
- Modify HTML report endpoint to stream from Minio
- Keep Layer 1 cache (parsed JSONL entries) — now populated from Minio fetch
- Add `object_key` column to `Scan` DB model

#### Phase D: Remove Shared Volume
- Remove `garak-reports` shared volume from docker-compose
- Garak container gets its own local temp volume
- Backend no longer needs filesystem access to reports
- Backfill: migrate existing files from volume to Minio

### Effort Estimate

| Phase | Effort | Description |
|-------|--------|-------------|
| A | 2-3 hours | Minio container + client library |
| B | 3-4 hours | Garak service upload after scan |
| C | 3-4 hours | Backend reads from Minio + caching |
| D | 1-2 hours | Remove shared volume, migration |
| **Total** | **~1 day** | |

### Analysis: Bottlenecks, Security Risks & Concerns

#### Bottleneck 1 (CRITICAL): File Rename Flow Breaks with S3

**Current flow** (`garak_wrapper.py:413-451`):
```
1. Garak CLI writes:  garak.{UUID}.report.jsonl   (random UUID)
2. Progress parser detects "report closed" event
3. Backend calls _rename_report_file()
4. Renames atomically:  garak.{UUID}... → garak.{scan_id}...
5. Same for hitlog:     garak.{UUID}.hitlog.jsonl → garak.{scan_id}.hitlog.jsonl
```

`Path.rename()` is atomic on a filesystem. **S3 has no rename operation.** You must copy-to-new-key then delete-old-key — two operations with a race window where the file exists under neither name.

**Mitigation options:**

| Option | Approach | Trade-off |
|--------|----------|-----------|
| **A: Upload after rename (Recommended)** | Keep local rename on garak container's temp volume, upload the already-renamed file to Minio | Simplest — no rename logic changes. Requires local temp volume on garak container |
| B: Upload with scan_id directly | Pass `--report_prefix` to garak CLI so it writes `garak.{scan_id}...` from the start | Changes garak invocation protocol; may not be supported by garak fork |
| C: Copy-then-delete in Minio | Upload with UUID, then S3 copy + delete | Race condition window; two Minio calls; orphan risk on partial failure |

**Recommendation: Option A.** Garak service keeps a local temp volume, renames locally (atomic), then uploads the final file. The local temp is ephemeral — Minio is the source of truth.

---

#### Bottleneck 2 (HIGH): `get_scan_statistics()` Downloads ALL Reports

**Current** (`garak_wrapper.py:1070`): For every completed scan, calls `_get_report_entries(scan_id)` which reads the full JSONL file. With 100 scans × 5 MB each = **500 MB of sequential Minio downloads** on every stats request.

The Layer 1 cache mitigates repeat calls, but the **first cold call** after restart is brutal.

**Mitigations:**

| Approach | Impact | Effort |
|----------|--------|--------|
| **Materialize stats in DB (Recommended)** | Compute pass/fail/probe counts at scan completion, store in `scans` table. Stats endpoint becomes a SQL query — zero Minio reads | Medium (add columns to Scan model, compute during `_sync_scan_to_db`) |
| Parallel Minio downloads | Use `asyncio.gather()` to fetch N files concurrently | Low effort, but still downloads all files |
| Pagination | Only aggregate last N scans | Changes API contract |

**Recommendation:** Materialize aggregate stats in the DB at scan completion time. The `scans` table already has `passed`/`failed` columns — extend with `total_probes`, probe-level breakdown stored as JSON. Stats endpoint becomes `SELECT SUM(passed), SUM(failed) FROM scans WHERE ...`.

---

#### Bottleneck 3 (HIGH): Cache Invalidation Uses `st_mtime`

**Current** (`garak_wrapper.py:624`):
```python
file_mtime = report_file.stat().st_mtime
cached = self._report_cache.get(scan_id)
if cached and cached["mtime"] == file_mtime and (now - cached["cached_at"]) < self._cache_ttl:
    return cached["entries"]  # cache hit
```

S3 objects don't have `st_mtime`. They have `LastModified` and `ETag` — but checking these requires a `HEAD` request per object.

**Mitigation:** Since JSONL files are **write-once** (never modified after creation), the cache strategy simplifies:
- If scan status is `completed` in the DB → report is immutable → cache forever (no invalidation needed)
- If scan is active → don't read from Minio (use in-memory active_scans data)
- Drop mtime checks entirely. Use scan status as the invalidation signal.

---

#### Bottleneck 4 (MEDIUM): HTML Report Full-Read into Memory

**Current** (`scan.py:393`):
```python
with open(report_file, 'r') as f:
    html_content = f.read()   # entire file into memory
return HTMLResponse(content=html_content)
```

The `/report/html` endpoint uses `FileResponse` (streaming) — good. But `/report/detailed` reads the entire file into memory. With Minio, this becomes a full S3 GET buffered in RAM.

**Mitigation:** Use `StreamingResponse` with Minio's `get_object()` which returns an iterable stream. Never buffer the full file.

---

#### Security Risk 1 (CRITICAL): DB ↔ Minio Consistency

If Minio upload succeeds but DB write fails (or vice versa), we get:
- **Orphaned Minio objects** — files in Minio with no DB reference (waste storage, never cleaned)
- **Dangling DB references** — DB points to Minio key that doesn't exist (404 on read)

**Mitigation:**
1. **Write order:** DB first (with `report_path = s3://...`), then upload to Minio, then update DB status to `completed`
2. **On upload failure:** Mark scan as `error` in DB with message. Leave DB record for retry.
3. **Cleanup job:** Periodic background task lists Minio objects, cross-references DB, deletes orphans.
4. **Idempotent uploads:** Use scan_id as Minio key — re-upload overwrites safely.

---

#### Security Risk 2 (HIGH): Minio Credentials Exposure

**Status: MITIGATED** — Credentials are now loaded from `.env` file (gitignored), not hardcoded in compose files. Docker-compose uses `${VAR:?error}` syntax to fail fast if credentials are missing.

Both backend and garak service containers need these credentials to talk to Minio.

**Further hardening:**
- Create a dedicated service account with limited permissions (not root)
- Bucket policy: `hydra-reports` bucket is private, no public access
- TLS between containers (Minio supports `--certs-dir`)
- In production: use external secret management (Vault, AWS Secrets Manager)

---

#### Security Risk 3 (MEDIUM): Partial Upload on Network Failure

Garak service uploads a 5 MB JSONL file to Minio. Network drops mid-upload. Result: partial/corrupt object in Minio that the backend later tries to parse.

**Mitigation:**
- Use Minio's **multipart upload with commit/abort** — only committed uploads become visible
- Verify upload with `ETag` comparison (MD5 checksum)
- On failed upload, retry up to 3 times before marking scan as `error`
- Backend: if JSONL parsing fails (truncated JSON), return error instead of partial results

---

#### Security Risk 4 (LOW): Hitlog File Loss

**Current** (`garak_wrapper.py:442-445`): If hitlog rename fails, the error is silently swallowed. With Minio, if JSONL upload succeeds but hitlog upload fails, the hitlog is lost.

**Mitigation:** Log a warning but don't fail the scan. Hitlog is supplementary data (subset of JSONL attempt entries where `status=1`). It can be regenerated from the JSONL report if needed.

---

#### Concern 1: Concurrent Scan Uploads

With `max_concurrent_scans = 5`, up to 5 garak processes can complete near-simultaneously. Each triggers a Minio upload.

**Impact:** Low risk. Minio handles concurrent PUT requests to different keys well. Each scan has a unique `scan_id`, so no key collisions. The only concern is bandwidth — 5 × 5 MB = 25 MB simultaneous upload, which is fine for Docker bridge networking.

---

#### Concern 2: Minio Adds Operational Complexity

A new container to monitor, configure, backup, and troubleshoot.

**Mitigation:**
- Minio is lightweight (~200 MB image, <100 MB RAM at idle)
- Built-in health check (`mc ready local`)
- Web console on port 9001 for debugging
- `minio-data` Docker named volume handles persistence
- For development: can disable Minio and fall back to local volume (feature flag)

---

#### Concern 3: Development Experience

Developers now need Minio running locally. More containers = slower `docker compose up`.

**Mitigation:**
- Make Minio **optional** via `STORAGE_BACKEND` env var (`local` | `minio`)
- Default to `local` in development (`docker-compose.dev.yml`)
- Default to `minio` in production (`docker-compose.yml` or `docker-compose.prod.yml`)
- `object_store.py` abstracts the backend — callers don't know which is active

---

### Summary: Issue Severity Matrix

| # | Issue | Severity | Category | Mitigation |
|---|-------|----------|----------|------------|
| 1 | File rename not atomic on S3 | **Critical** | Bottleneck | Upload after local rename (Option A) |
| 2 | DB ↔ Minio consistency | **Critical** | Security | Write-order protocol + cleanup job |
| 3 | `get_scan_statistics()` downloads all files | **High** | Bottleneck | Materialize stats in DB |
| 4 | Cache invalidation uses `st_mtime` | **High** | Bottleneck | Use scan status (write-once = cache forever) |
| 5 | Minio credentials hardcoded | **High** | Security | Docker secrets / `.env` / service accounts |
| 6 | HTML report full-read into memory | **Medium** | Bottleneck | `StreamingResponse` from Minio stream |
| 7 | Partial upload on network failure | **Medium** | Security | Multipart upload + ETag verify + retry |
| 8 | Hitlog file loss on upload failure | **Low** | Security | Log warning; regenerable from JSONL |
| 9 | Concurrent scan uploads | **Low** | Concern | No action — Minio handles this |
| 10 | Dev experience / extra container | **Low** | Concern | `STORAGE_BACKEND` feature flag |

### Revised Implementation Phases

Based on the analysis, phases are reordered to address critical issues first:

#### Phase 0: SQLite → PostgreSQL Migration
- Add `postgres:16-alpine` container to docker-compose.yml with health check
- Add `psycopg2-binary` to requirements.txt
- Change `session.py`: connection string from `sqlite:///` → `postgresql://` via `DATABASE_URL` env var
- Remove SQLite-specific pragmas (WAL mode, `check_same_thread`)
- Change `AUTOINCREMENT` → `SERIAL` (SQLAlchemy handles this automatically via dialect)
- Add `backend depends_on postgres condition: service_healthy`
- Update `init_db()` to accept `DATABASE_URL` env var
- Tests keep using SQLite in-memory (`:memory:`) for speed — no change
- Backfill migration still works (same SQLAlchemy ORM, just different dialect)

**Code changes:** Only `session.py` + docker-compose + requirements. All ORM queries stay identical.

#### Phase A: Object Store Abstraction + Minio Container
- Create `backend/services/object_store.py` with `StorageBackend` interface
- Two implementations: `LocalStorage` (current behavior) and `MinioStorage`
- `STORAGE_BACKEND` env var to switch (`local` for dev without Minio, `minio` for full setup)
- Add Minio container to docker-compose.yml with health check
- Add `minio` Python package to requirements.txt
- Auto-create `hydra-reports` bucket on startup

#### Phase B: Garak Service — Local Rename + Upload
- Garak service keeps local temp volume for garak CLI output
- After "report closed" event: rename locally (atomic), then upload to Minio via S3 API
- Multipart upload with ETag verification
- Retry logic (3 attempts) before marking scan as `error`
- Upload JSONL, hitlog, and HTML as `{scan_id}/report.jsonl`, etc.
- Add `report_key` field to SSE progress events (so backend knows the Minio key)

#### Phase C: Backend — Read from Object Store
- Modify `_get_report_entries()` to call `object_store.get(key)` instead of `open(path)`
- Simplify cache: completed scans = immutable = cache forever (no mtime check)
- HTML endpoints: `StreamingResponse` from object store stream
- Add `report_key` column to `Scan` DB model (Minio object key)

#### Phase D: Materialize Stats in DB
- Compute aggregate stats (pass/fail/probe counts) at scan completion time
- Store in `scans` table (extend existing `passed`/`failed` columns)
- `get_scan_statistics()` becomes SQL aggregation — zero Minio reads
- Backfill existing scans from JSONL on first startup

#### Phase E: Remove Shared Volume + Cleanup
- Remove `garak-reports` shared volume from docker-compose
- Garak container gets its own ephemeral temp volume
- Backend no longer needs filesystem access to reports
- Add background cleanup job: list Minio objects, cross-reference DB, delete orphans
- Backfill: migrate existing files from volume to Minio

### Revised Effort Estimate

| Phase | Effort | Addresses |
|-------|--------|-----------|
| 0 | 1-2 hours | SQLite → PostgreSQL (clean separation for DB) |
| A | 3-4 hours | Object store abstraction + Minio container |
| B | 4-5 hours | Bottleneck #1 (rename), Risk #3 (partial upload), Risk #4 (hitlog) |
| C | 3-4 hours | Bottleneck #4 (cache), Bottleneck #4 (HTML streaming) |
| D | 2-3 hours | Bottleneck #2 (stats), biggest performance win |
| E | 2-3 hours | Risk #2 (consistency), cleanup |
| **Total** | **~2.5 days** | |

---

## Implementation Summary (H1 — Database Backend, SQLite Prototype)

### Files Created

| File | Purpose |
|------|---------|
| `backend/database/__init__.py` | Package init, exports `get_db`, `init_db`, `DatabaseSession` |
| `backend/database/models.py` | SQLAlchemy ORM models: `Scan`, `ConfigTemplateRow`, `CustomProbeRow`, `DBMeta` |
| `backend/database/session.py` | Engine creation (WAL mode), session factory, `get_db()` context manager |
| `backend/database/migrations.py` | Backfill functions: scans from JSONL, templates from JSON, probes from metadata.json |
| `backend/tests/test_database.py` | 30 tests: models, CRUD, backfill, DB-backed ConfigTemplateStore |

### Files Modified

| File | Changes |
|------|---------|
| `backend/main.py` | Added `init_db()` + `run_backfill_if_needed()` in lifespan |
| `backend/requirements.txt` | Added `sqlalchemy>=2.0,<3.0` |
| `backend/docker-compose.dev.yml` | Added `database/` volume mount + reload-dir |
| `backend/services/garak_wrapper.py` | DB sync on scan lifecycle (start/complete/error/cancel); DB-first reads for `get_scan_status()`, `get_all_scans()`; removed Layer 2 scan info cache |
| `backend/services/config_template_store.py` | All CRUD methods: DB-first with file fallback |
| `backend/services/custom_probe_service.py` | All CRUD methods: DB-first with file fallback; `.py` files stay on disk |
| `backend/tests/test_report_cache.py` | Removed Layer 2 (`_scan_info_cache`) tests, updated remaining tests |

### Design Decisions Made

1. **SQLite as prototype**: Validates ORM models and migration logic. All code uses SQLAlchemy ORM — **zero raw SQL** — so switching to PostgreSQL in Phase 0 requires only `session.py` changes
2. **Fallback pattern**: Every DB-backed method tries DB first, falls back to file-based storage if `_SessionFactory is None`
3. **Active scans stay in-memory**: Real-time WebSocket data comes from `active_scans` dict; DB is synced at lifecycle boundaries
4. **Layer 2 cache removed**: With scan metadata in DB, the `_scan_info_cache` is no longer needed. Layer 1 (JSONL entries) and Layer 3 (full results) kept for detailed data parsing
5. **Backfill is one-time**: `run_backfill_if_needed()` runs once and marks completion in `db_meta` table

### Test Results

```
tests/test_database.py         — 30 passed
tests/test_config_templates.py — 45 passed
tests/test_report_cache.py     — 35 passed
tests/test_scan_statistics.py  — passed
tests/test_cli_flags.py        — passed
tests/test_logging_config.py   — passed
```

---

## Implementation Summary (H1.1 — PostgreSQL + Minio)

### What Was Done

Migrated from embedded SQLite + shared Docker volume to PostgreSQL (own container) + Minio S3-compatible object store (own container). The backend and garak service no longer share any filesystem — all data flows through network protocols (SQL over TCP, S3 over HTTP).

### Phase 0: SQLite → PostgreSQL

- Changed `session.py` to read `DATABASE_URL` env var and create the appropriate SQLAlchemy engine (PostgreSQL or SQLite fallback)
- Removed SQLite-specific pragmas (WAL mode, `check_same_thread`)
- Added `postgres:16-alpine` container to `docker-compose.yml` with health check
- Added `psycopg2-binary>=2.9` to `requirements.txt`
- Backend `depends_on` postgres with `condition: service_healthy`
- Tests continue using in-memory SQLite for speed — zero test changes

### Phase A: Object Store Abstraction + Minio Container

- Created `backend/services/object_store.py` with `StorageBackend` abstract base class
- Two implementations: `LocalStorage` (filesystem) and `MinioStorage` (S3 API)
- `STORAGE_BACKEND` env var selects backend (`local` or `minio`)
- Singleton pattern: `init_object_store()` at startup, `get_object_store()` for access
- Added `minio/minio:latest` container to `docker-compose.yml` with health check
- Auto-creates `hydra-reports` bucket on startup
- Added `minio>=7.0` to `requirements.txt`

### Phase B: Garak Service — Local Rename + Upload to Minio

- Created `backend/services/garak_service/report_uploader.py` — uploads JSONL, hitlog, HTML to Minio after local rename
- Object key pattern: `{scan_id}/garak.{scan_id}.report.jsonl`
- Updated `scan_manager.py` to call uploader after scan completion
- Added `report_keys` field to SSE "complete" event (JSONL and HTML object keys)
- Garak container writes to local scratch volume, uploads to Minio, local files are ephemeral

### Phase C: Backend — Read from Object Store

- Added `report_key` and `html_report_key` columns to `Scan` model
- Updated `_sync_scan_to_db()` to persist object store keys on both INSERT and UPDATE
- Updated `_update_scan_from_event()` to capture `report_keys` from "complete" SSE event
- Modified `_get_report_entries()`: immutable cache check → object store → local filesystem fallback
- Modified `get_scan_results()`: immutable cache → local filesystem → object store fallback
- Modified HTML report endpoint: local filesystem → Minio `StreamingResponse` fallback
- Modified `delete_scan()`: also deletes from object store using `list_keys()` + `delete()`
- Fixed cache bug: removed early TTL-only check that bypassed mtime validation

### Phase D: Materialize Stats in DB

- Added `probe_stats_json` column to `Scan` model (TEXT, nullable)
- Created `_compute_probe_stats()`: parses JSONL, returns `{category: {passed: N, failed: N}}`
- Created `_get_materialized_probe_stats()`: checks DB first, computes from JSONL if not found, stores in DB for next time
- Updated `get_scan_statistics()` to use materialized stats — zero Minio reads for aggregate queries
- Added idempotent schema migration: `_add_column_if_missing()` for ALTER TABLE across PostgreSQL and SQLite

### Phase E: Remove Shared Volume + Cleanup

- Removed `garak-reports` shared volume from `docker-compose.yml`
- Garak container gets its own `garak-scratch` named volume (ephemeral, not shared)
- Backend `GARAK_REPORTS_DIR` changed to `/tmp/garak_reports` (local fallback only)
- Updated `docker-compose.dev.yml` similarly — removed backend report bind mount
- No containers share any volumes

### Files Created

| File | Purpose |
|------|---------|
| `backend/services/object_store.py` | `StorageBackend` ABC + `LocalStorage` + `MinioStorage` implementations |
| `backend/services/garak_service/report_uploader.py` | Upload renamed reports to Minio after scan completion |
| `backend/tests/test_h1_1_object_store.py` | 37 tests: LocalStorage, MinioStorage (mocked), init factory, schema migrations, object store integration, materialized stats, report keys from events, delete with store |

### Files Modified

| File | Changes |
|------|---------|
| `backend/database/models.py` | Added `report_key`, `html_report_key`, `probe_stats_json` columns; updated `to_dict()` |
| `backend/database/session.py` | `DATABASE_URL` env var selects dialect; removed SQLite-specific pragmas |
| `backend/database/migrations.py` | Added `_add_column_if_missing()`, `_run_schema_migrations()` for idempotent ALTER TABLE |
| `backend/main.py` | Added `init_object_store()` in lifespan startup |
| `backend/requirements.txt` | Added `psycopg2-binary>=2.9`, `minio>=7.0` |
| `backend/services/garak_wrapper.py` | Object store reads/writes, immutable caching, materialized probe stats, report key capture |
| `backend/services/garak_service/scan_manager.py` | Calls report uploader after scan completion |
| `backend/api/routes/scan.py` | HTML/JSONL endpoints fallback to Minio `StreamingResponse` |
| `backend/docker-compose.yml` | Added postgres + minio containers, removed shared volume, 4 services |
| `backend/docker-compose.dev.yml` | Updated for new architecture (no shared volume, postgres port exposed) |

### Design Decisions

1. **Object store abstraction**: `StorageBackend` ABC lets us swap `LocalStorage` ↔ `MinioStorage` via env var. Tests use `LocalStorage` with temp dirs — no Minio needed.
2. **Upload after local rename (Bottleneck #1)**: Garak CLI writes with random UUID → garak service renames locally (atomic) → uploads already-renamed file to Minio. No S3 rename needed.
3. **Immutable caching (Bottleneck #4)**: Completed scan reports are write-once. Object-store-sourced entries are cached forever — no TTL, no mtime checks, no HEAD requests.
4. **Materialized stats (Bottleneck #2)**: Per-probe `{passed, failed}` counts stored as JSON in DB. `get_scan_statistics()` becomes a SQL query — zero Minio reads.
5. **Idempotent migrations**: `_add_column_if_missing()` checks column existence before ALTER TABLE. Safe to run on every startup across both PostgreSQL and SQLite.
6. **No shared volumes**: Minio bridges the containers. Each container has its own ephemeral storage. Clean separation of concerns.

### Test Results

```
288 tests passed, 0 failed

tests/test_h1_1_object_store.py  — 37 passed (new)
tests/test_database.py           — 30 passed
tests/test_report_cache.py       — 65 passed (4 fixed: removed buggy TTL-only cache check)
tests/test_config_templates.py   — 45 passed
tests/test_scan_statistics.py    — passed
tests/test_concurrent_scans.py   — passed
tests/test_cli_flags.py          — passed
tests/test_logging_config.py     — passed
```
