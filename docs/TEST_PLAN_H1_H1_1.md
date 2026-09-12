# Test Plan: H1 + H1.1 (Database Backend + Containerized Data Services)

**Created:** 2026-02-14
**Scope:** H1 (SQLite prototype) + H1.1 (PostgreSQL + Minio)
**Branch:** `h1`

---

## 1. Automated Test Summary

### 1.1 Test Suites

| Suite | File | Tests | Layer | What It Covers |
|-------|------|------:|-------|----------------|
| Database models & CRUD | `tests/test_database.py` | 30 | Unit + Integration | ORM models, session factory, backfill migrations, DB-backed ConfigTemplateStore |
| Object store & H1.1 | `tests/test_h1_1_object_store.py` | 37 | Unit + Integration | LocalStorage, MinioStorage (mocked), init factory, schema migrations, object store reads, materialized stats, report keys, delete with store |
| Report cache | `tests/test_report_cache.py` | 65 | Unit + Integration | JSONL parsing, cache TTL, mtime invalidation, immutable cache, results cache, edge cases |
| Config templates | `tests/test_config_templates.py` | 45 | Unit + Integration | CRUD, file fallback, DB-backed store, reserved name validation |
| Scan statistics | `tests/test_scan_statistics.py` | 18 | Integration | Aggregate stats, trends, probe category breakdown |
| Concurrent scans | `tests/test_concurrent_scans.py` | 18 | Integration | Max concurrent scan enforcement, HTTP 429 |
| CLI flags | `tests/test_cli_flags.py` | ~30 | Unit | ScanConfig → CLI flag generation |
| Logging | `tests/test_logging_config.py` | ~4 | Unit | Structured logging setup |
| **Total** | | **247** | | |

### 1.2 How to Run

```bash
# All tests locally (host machine, no Docker needed)
cd backend
python3 -m pytest tests/test_database.py tests/test_h1_1_object_store.py \
  tests/test_report_cache.py tests/test_config_templates.py \
  tests/test_scan_statistics.py tests/test_concurrent_scans.py \
  tests/test_cli_flags.py tests/test_logging_config.py -v

# Inside container (requires make hydra-dev)
make test

# Single suite
python3 -m pytest tests/test_h1_1_object_store.py -v
```

### 1.3 Test Environment

- All automated tests use **in-memory SQLite** (no PostgreSQL required)
- Object store tests use **LocalStorage with tmp_path** (no Minio required)
- MinioStorage tests use **mocked Minio client** (no network calls)
- Tests are fast (~0.6s for all 247)

---

## 2. Automated Test Details

### 2.1 Database Models (`test_database.py`)

| # | Test | Verifies |
|---|------|----------|
| 1 | `TestDatabaseInit.test_init_creates_tables` | All 4 tables (scans, config_templates, custom_probes, db_meta) created |
| 2 | `TestDatabaseInit.test_init_sets_schema_version` | Schema version "1" stored in db_meta |
| 3 | `TestDatabaseInit.test_init_file_based` | SQLite file DB created on disk |
| 4 | `TestDatabaseInit.test_get_db_raises_without_init` | RuntimeError if `init_db()` not called |
| 5 | `TestScanModel.test_create_scan` | Scan row INSERT + SELECT |
| 6 | `TestScanModel.test_scan_to_dict` | Serialization: total_tests = passed + failed, progress |
| 7 | `TestScanModel.test_scan_to_dict_defaults` | Default 0 for passed/failed |
| 8 | `TestScanModel.test_scan_unique_id` | Duplicate ID raises IntegrityError |
| 9 | `TestScanModel.test_scan_query_by_status` | WHERE status = 'running' filter |
| 10 | `TestScanModel.test_scan_query_by_target` | WHERE target_type + target_name filter |
| 11-13 | `TestConfigTemplateModel.*` | Create, to_dict (JSON unpacking), unique name constraint |
| 14-16 | `TestCustomProbeModel.*` | Create, to_dict, unique name constraint |
| 17-24 | `TestDBConfigTemplateStore.*` | Full CRUD: save/get/list/update/delete, duplicates rejected, no file fallback when DB active |
| 25-28 | `TestBackfillMigrations.*` | Backfill from JSONL/JSON/metadata.json, idempotent (no duplicates on re-run) |
| 29-30 | `TestDBMeta.*` | Schema version persistence, arbitrary key-value |

### 2.2 Object Store & H1.1 (`test_h1_1_object_store.py`)

| # | Test | Verifies |
|---|------|----------|
| 1-11 | `TestLocalStorage.*` | put/get, nested dirs, put_file, exists, delete, list_keys (with prefix), get_stream, error cases (missing file, nonexistent key) |
| 12-17 | `TestMinioStorageMocked.*` | get (success + NoSuchKey), put (correct params), exists (true/false), delete, list_keys — all via mocked Minio client |
| 18 | `TestInitObjectStore.test_local_backend` | `init_object_store()` creates LocalStorage when STORAGE_BACKEND=local |
| 19 | `TestInitObjectStore.test_get_object_store_raises_when_not_initialized` | RuntimeError before init |
| 20-22 | `TestScanModelNewColumns.*` | report_key, html_report_key, probe_stats_json columns persist and appear in to_dict() |
| 23-24 | `TestSchemaMigrations.*` | `_add_column_if_missing()` idempotent, `_run_schema_migrations()` idempotent |
| 25-28 | `TestObjectStoreIntegration.*` | GarakWrapper reads JSONL from object store, immutable cache flag set, falls back to local filesystem when store unavailable |
| 29-32 | `TestMaterializedProbeStats.*` | `_compute_probe_stats()` from JSONL, missing scan returns None, falls back to JSONL when no DB, reads from DB when available |
| 33-34 | `TestReportKeysFromEvent.*` | `_update_scan_from_event()` captures report_keys from "complete" event, handles missing keys |
| 35-36 | `TestDeleteScanObjectStore.*` | Delete removes from object store, graceful error handling on store failure |

### 2.3 Report Cache (`test_report_cache.py`)

| # | Test | Verifies |
|---|------|----------|
| 1-4 | `TestGetReportEntries.*` | JSONL parsing, None for missing, cache hit (object identity), cache dict structure |
| 5-6 | `TestCacheTTL.*` | Entries expire after TTL, valid within TTL |
| 7 | `TestCacheMtimeInvalidation.*` | File modification detected, cache refreshed |
| 8-11 | `TestManualInvalidation.*` | invalidate_cache removes entry, noop for missing, clear_cache empties all, delete_scan clears cache |
| 12-15 | `TestSharedCache.*` | parse_report, probe_details, probe_attempts all share same cached parse |
| 16-19 | `TestCachedResultsCorrectness.*` | Pass/fail counting, per-probe stats, attempt filtering by status |
| 20-24 | `TestCacheEdgeCases.*` | Empty file, malformed lines skipped, file deleted after cache, default TTL=300, custom TTL |
| 25-26 | `TestParseReportFile.*` | Correct data returned, file changes detected |
| 27-35 | `TestResultsCache.*` | Layer 3: populates, cache hit, correct data, active scan bypasses, mtime refresh, invalidation, clear, nonexistent, both layers cleared |

---

## 3. Manual Verification Plan (Docker Integration)

These tests require running containers. They verify what automated tests cannot: real container networking, actual PostgreSQL, actual Minio, and end-to-end data flow.

### 3.1 Prerequisites

```bash
# Ensure Ollama is running on host (for target model)
ollama serve &
ollama pull llama3.2:1b   # or any small model

# Start the full stack
cd backend
make hydra-dev
```

### 3.2 Container Health (T1)

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T1.1 | All 4 containers running | backend, garak, postgres, minio all "Up" | `make hydra-ps` |
| T1.2 | Backend health | `{"status": "ok"}` | `curl http://localhost:8888/health` |
| T1.3 | Garak health (via backend) | "healthy" response | `make hydra-garak-health` |
| T1.4 | PostgreSQL accepting connections | `pg_isready` succeeds | `docker compose exec postgres pg_isready -U hydra` |
| T1.5 | Minio console accessible | Web UI loads | Open `http://localhost:9001` (credentials from `.env`: MINIO_ROOT_USER / MINIO_ROOT_PASSWORD) |
| T1.6 | Minio bucket exists | `hydra-reports` bucket listed | Check Minio console > Buckets |

### 3.3 Database Connectivity (T2)

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T2.1 | Connect to PostgreSQL | psql prompt opens | `docker compose exec postgres psql -U hydra -d hydra` |
| T2.2 | Tables exist | scans, config_templates, custom_probes, db_meta | `\dt` in psql |
| T2.3 | Schema version set | Row: key=schema_version, value=1 | `SELECT * FROM db_meta;` |
| T2.4 | Scans table has new columns | report_key, html_report_key, probe_stats_json | `\d scans` in psql |
| T2.5 | Empty scans table on fresh start | 0 rows | `SELECT count(*) FROM scans;` |

### 3.4 Scan Lifecycle — End-to-End (T3)

This is the critical path. Run a real scan and verify data flows through all components.

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T3.1 | Start a scan | HTTP 200, scan_id returned | `curl -X POST http://localhost:8888/api/v1/scan/start -H 'Content-Type: application/json' -d '{"target_type":"ollama","target_name":"llama3.2:1b","probes":["dan.DAN_Jailbreak"]}'` |
| T3.2 | Poll scan progress | Status transitions: pending → running → completed | `curl http://localhost:8888/api/v1/scan/{scan_id}/status` (poll every 5s) |
| T3.3 | WebSocket progress | Events streamed (progress %, probe names) | `websocat ws://localhost:8888/api/v1/scan/{scan_id}/progress` |
| T3.4 | Scan appears in DB | Row with correct target_type, target_name, status | `SELECT id, status, target_type, target_name FROM scans;` (in psql) |
| T3.5 | Report uploaded to Minio | Objects under `{scan_id}/` prefix | Check Minio console > hydra-reports > browse |
| T3.6 | Report keys stored in DB | report_key and html_report_key populated | `SELECT id, report_key, html_report_key FROM scans WHERE id='{scan_id}';` |
| T3.7 | Scan results endpoint works | JSON with passed/failed counts, entries | `curl http://localhost:8888/api/v1/scan/{scan_id}/results` |
| T3.8 | HTML report accessible | HTML content returned | `curl http://localhost:8888/api/v1/scan/{scan_id}/report/html` |
| T3.9 | Scan history lists it | Scan appears in list | `curl http://localhost:8888/api/v1/scan/history` |
| T3.10 | Statistics include it | Totals include this scan's pass/fail | `curl http://localhost:8888/api/v1/scan/statistics` |
| T3.11 | Materialized stats in DB | probe_stats_json populated after stats call | `SELECT id, probe_stats_json FROM scans WHERE id='{scan_id}';` |

### 3.5 Object Store Fallback (T4)

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T4.1 | Stop Minio container | Minio goes down | `docker compose stop minio` |
| T4.2 | Previously cached scan results still accessible | Cached results returned (immutable cache) | `curl http://localhost:8888/api/v1/scan/{scan_id}/results` |
| T4.3 | New scan can still start | Scan starts (garak runs, but upload will fail) | Start a new scan via curl |
| T4.4 | Scan completes but upload fails | Scan status=completed, report_key=null, warning in logs | Check `docker compose logs backend --tail=50` |
| T4.5 | Restart Minio | Minio comes back | `docker compose start minio` |

### 3.6 Database Persistence (T5)

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T5.1 | Note current scan count | N scans in DB | `SELECT count(*) FROM scans;` |
| T5.2 | Restart backend container | Backend restarts | `docker compose restart backend` |
| T5.3 | Scan history preserved | Same N scans returned | `curl http://localhost:8888/api/v1/scan/history` |
| T5.4 | Restart all containers | Full stack restart | `make hydra-dev-down && make hydra-dev` |
| T5.5 | Scan history still preserved | Same N scans (pg-data volume persists) | `curl http://localhost:8888/api/v1/scan/history` |

### 3.7 Config Templates — DB Persistence (T6)

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T6.1 | Create a config template | HTTP 200 | `curl -X POST http://localhost:8888/api/v1/config/templates -H 'Content-Type: application/json' -d '{"name":"test-tpl","description":"test","config":{"target_type":"ollama","target_name":"llama3.2:1b"}}'` |
| T6.2 | Template in DB | Row with name=test-tpl | `SELECT name, description FROM config_templates;` |
| T6.3 | Template in API | Listed in response | `curl http://localhost:8888/api/v1/config/templates` |
| T6.4 | Restart backend | Template survives restart | `docker compose restart backend` then `curl http://localhost:8888/api/v1/config/templates` |
| T6.5 | Delete template | HTTP 200 | `curl -X DELETE http://localhost:8888/api/v1/config/templates/test-tpl` |

### 3.8 Scan Deletion — Cross-Service Cleanup (T7)

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T7.1 | Note a completed scan_id | Has report_key in DB | `SELECT id, report_key FROM scans WHERE status='completed' LIMIT 1;` |
| T7.2 | Verify objects in Minio | Objects exist under scan_id prefix | Minio console or `docker compose exec backend python -c "..."` |
| T7.3 | Delete the scan | HTTP 200 | `curl -X DELETE http://localhost:8888/api/v1/scan/{scan_id}` |
| T7.4 | Scan removed from DB | No row with that id | `SELECT * FROM scans WHERE id='{scan_id}';` → 0 rows |
| T7.5 | Objects removed from Minio | No objects under scan_id prefix | Check Minio console |
| T7.6 | History no longer lists it | Scan gone from list | `curl http://localhost:8888/api/v1/scan/history` |

### 3.9 Volume Isolation (T8)

| ID | Step | Expected | Command |
|----|------|----------|---------|
| T8.1 | Backend has no shared volume with garak | No `garak-reports` or `garak-scratch` mount on backend | `docker inspect hydra-backend \| grep -i mount` |
| T8.2 | Garak has own scratch volume | `garak-scratch` mounted at `/data/garak_reports` | `docker inspect hydra-garak \| grep -i mount` |
| T8.3 | Backend reports dir is /tmp | GARAK_REPORTS_DIR=/tmp/garak_reports | `docker compose exec backend env \| grep GARAK_REPORTS` |

---

## 4. Coverage Gaps (Known Limitations)

### 4.1 No Automated Tests

| Component | Gap | Risk | Mitigation |
|-----------|-----|------|------------|
| `report_uploader.py` | 0% coverage — upload logic, retry, content-type mapping | Medium | Covered by manual T3.5, T3.6. Logic is straightforward (call `fput_object` in a loop). |
| MinioStorage real connection | All tests use mock — no real S3 calls | Medium | Covered by manual T1.5, T3.5. Mock tests verify correct Minio SDK method calls. |
| PostgreSQL dialect | All tests use SQLite — no PG-specific behavior | Low | SQLAlchemy abstracts dialect. Covered by manual T2.1-T2.5. Only risk: `_add_column_if_missing()` SQL generation for PG vs SQLite (tested idempotency, not dialect). |
| `init_object_store()` Minio path | Only local backend tested | Low | Minio init is 5 lines: create client, call `_ensure_bucket()`. Covered by manual T1.5, T1.6. |
| `session.py` PostgreSQL URL | Not tested (only SQLite) | Low | URL comes from `DATABASE_URL` env var, passed directly to SQLAlchemy `create_engine()`. Covered by manual T2.1. |
| Container networking | Cannot test Docker DNS resolution in unit tests | Low | Covered by manual T1.1-T1.3. All inter-container communication uses Docker DNS (postgres:5432, minio:9000, garak:9090). |

### 4.2 Edge Cases Not Tested

| Scenario | Risk | Notes |
|----------|------|-------|
| Large report files (>50 MB) | Low | Minio handles streaming uploads/downloads. Not tested with large files. |
| Concurrent scan completion → parallel Minio uploads | Low | Each scan uploads to unique key prefix. No contention. |
| PostgreSQL connection pool exhaustion | Low | SQLAlchemy default pool size is 5. Unlikely with single-user desktop app. |
| Minio bucket policy / access control | Low | Single-user setup with root credentials. No multi-tenant access control. |
| Network partition between containers | Medium | If Minio is unreachable mid-scan, upload fails gracefully (logged warning). Backend falls back to local filesystem. |

---

## 5. Regression Checklist

These existing behaviors must not be broken by H1/H1.1:

| # | Behavior | How to Verify | Automated? |
|---|----------|---------------|:----------:|
| R1 | Scan start/progress/complete flow | Manual T3.1-T3.3 | Partially (unit tests for event handling) |
| R2 | WebSocket progress streaming | Manual T3.3 | No |
| R3 | Scan results with pass/fail counts | `test_report_cache.py` TestCachedResultsCorrectness | Yes |
| R4 | Probe details and attempts | `test_report_cache.py` TestSharedCache | Yes |
| R5 | Scan history listing | Manual T3.9 | No |
| R6 | HTML report viewing | Manual T3.8 | No |
| R7 | Config template CRUD | `test_config_templates.py` (45 tests) | Yes |
| R8 | Scan statistics endpoint | `test_scan_statistics.py` (18 tests) | Yes |
| R9 | Max concurrent scan enforcement | `test_concurrent_scans.py` (18 tests) | Yes |
| R10 | CLI flag generation from ScanConfig | `test_cli_flags.py` (~30 tests) | Yes |
| R11 | Cache invalidation on file changes | `test_report_cache.py` TestCacheMtimeInvalidation | Yes |
| R12 | Scan deletion cleans up all state | `test_h1_1_object_store.py` TestDeleteScanObjectStore | Yes |

---

## 6. Test Execution Record

Use this table to record results when running the full verification.

### 6.1 Automated Tests

| Date | Runner | All 247 Pass? | Failures | Notes |
|------|--------|:-------------:|----------|-------|
| 2026-02-14 | Claude | Yes | 0 | Initial implementation |
| | | | | |

### 6.2 Manual Tests

| Date | Runner | Section | Pass/Fail | Notes |
|------|--------|---------|-----------|-------|
| | | T1 Container Health | | |
| | | T2 Database Connectivity | | |
| | | T3 Scan Lifecycle E2E | | |
| | | T4 Object Store Fallback | | |
| | | T5 Database Persistence | | |
| | | T6 Config Templates | | |
| | | T7 Scan Deletion | | |
| | | T8 Volume Isolation | | |

---

## 7. Architecture Verification

Final sanity check that the architecture matches the design:

| # | Assertion | How to Verify |
|---|-----------|---------------|
| A1 | No shared volumes between backend and garak | `docker inspect` both containers, compare mounts (T8.1-T8.2) |
| A2 | Backend connects to PostgreSQL, not SQLite | Check `DATABASE_URL` env var in container: `docker compose exec backend env \| grep DATABASE` |
| A3 | Backend connects to Minio | Check `MINIO_ENDPOINT` env var: `docker compose exec backend env \| grep MINIO` |
| A4 | Garak service connects to Minio | Check `MINIO_ENDPOINT` env var: `docker compose exec garak env \| grep MINIO` |
| A5 | 4 containers on same network | `docker network inspect hydra_hydra-network` shows all 4 |
| A6 | PostgreSQL data persists across restarts | pg-data named volume: `docker volume inspect hydra_pg-data` |
| A7 | Minio data persists across restarts | minio-data named volume: `docker volume inspect hydra_minio-data` |
| A8 | Garak scratch is ephemeral (own volume) | garak-scratch not shared: `docker volume inspect hydra_garak-scratch` |
