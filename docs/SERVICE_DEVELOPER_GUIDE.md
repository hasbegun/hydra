# Hydra Service Platform — Developer Guide

> **Audience:** Engineers extending, maintaining, or deploying the Hydra scanning platform.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Configuration](#3-configuration)
4. [Multi-Tenancy](#4-multi-tenancy)
5. [Data Flow: A Scan from Start to Finish](#5-data-flow)
6. [Service Layer Design](#6-service-layer-design)
7. [Adding a New Feature](#7-adding-a-new-feature)
8. [Testing](#8-testing)
9. [Deployment](#9-deployment)
10. [Security Considerations](#10-security-considerations)
11. [Extending for Each Scenario](#11-extending-for-each-scenario)

---

## 1. Architecture Overview

```
                          ┌───────────────────┐
                          │   Anima (Identity) │
                          │   JWT issuance     │
                          └────────┬──────────┘
                                   │ JWT
                                   ▼
┌──────────┐  HTTP   ┌────────────────────────┐  Celery   ┌───────────────┐
│  Client   │───────▶│   FastAPI Backend       │──────────▶│  Celery Worker │
│ (CLI/UI)  │◀───────│   (api, middleware)      │◀──────────│  (scan_task)   │
└──────────┘  JSON   │                          │  Redis    └───────┬───────┘
                     │  middleware/tenant.py     │                   │
                     │  → TenantContext from JWT │                   │ Docker SDK
                     └────────┬────┬────────────┘                   ▼
                              │    │                        ┌───────────────┐
                    ┌─────────┘    └──────────┐             │  Sandbox       │
                    ▼                         ▼             │  Container     │
             ┌──────────┐             ┌──────────┐          │  (garak)       │
             │ Postgres  │             │  Redis   │          └───────┬───────┘
             │ (metadata)│             │ (broker  │                  │ SSE
             │           │             │  + cache)│                  ▼
             └──────────┘             └──────────┘          ┌───────────────┐
                                                            │  Garak Service │
                    ┌──────────────────────────┐            │  (probes)      │
                    │  Prism (SMPC storage)     │            └───────────────┘
                    │  ├── Reports (encrypted)  │
                    │  ├── Credentials (SMPC)   │   ◀── Panopticon (traces)
                    │  └── Audit logs (OCSF)    │
                    └──────────────────────────┘
```

### Component Responsibilities

| Component | Role | Tech |
|-----------|------|------|
| **FastAPI Backend** | API layer, routing, tenant extraction, request validation | FastAPI, Pydantic |
| **Celery Worker** | Async scan execution, sandbox management, probe running | Celery, Docker SDK |
| **Garak Service** | LLM vulnerability probe execution, SSE progress streaming | garak, FastAPI |
| **PostgreSQL** | Scan metadata, targets, campaigns, schedules (no secrets) | SQLAlchemy ORM |
| **Redis** | Celery broker, pub/sub progress, report cache | redis-py |
| **Prism** | Encrypted report/credential storage (Shamir secret sharing) | HTTP API |
| **Panopticon** | Observability traces (scan lifecycle, probe events) | HTTP API |
| **Anima** | JWT issuance, RBAC, tenant provisioning | OAuth2/OIDC |

---

## 2. Project Structure

```
backend/
├── main.py                          # FastAPI app factory, router mounting
├── config.py                        # Settings (env vars → Pydantic model)
│
├── api/routes/                      # HTTP endpoints (thin — delegate to services)
│   ├── scan.py                      #   Scan CRUD, status, reports, gate, PDF, comparison
│   ├── targets.py                   #   Target CRUD, rotate, connectivity test
│   ├── campaigns.py                 #   Campaign CRUD, trigger, evidence
│   ├── admin.py                     #   Portfolio dashboard, branding (RBAC)
│   ├── hooks.py                     #   Deployment webhooks (GitHub/ArgoCD)
│   ├── schedules.py                 #   Cron schedule CRUD, manual trigger
│   ├── webhooks.py                  #   Notification webhook registration
│   ├── custom_probes.py             #   Custom probe CRUD + validation
│   ├── plugins.py                   #   Plugin/generator listing
│   ├── models.py                    #   Generator model listing
│   ├── config.py                    #   Config template CRUD
│   └── system.py                    #   System info
│
├── middleware/
│   ├── tenant.py                    # JWT decode → TenantContext on request.state
│   └── __init__.py                  # RequestLoggingMiddleware
│
├── services/                        # Business logic (stateless, testable)
│   ├── prism_client.py              #   PrismClient + PrismStorage (cache→Prism→Minio)
│   ├── target_service.py            #   Target + credential lifecycle
│   ├── campaign_executor.py         #   Campaign fan-out execution
│   ├── gate_evaluator.py            #   CI/CD gate policy engine + shared severity weights
│   ├── scheduler.py                 #   Cron schedule management
│   ├── notifier.py                  #   Webhook notification + HMAC signing
│   ├── risk_scorer.py               #   Risk scoring formula (imports from gate_evaluator)
│   ├── finding_builder.py           #   JSONL → enriched findings (CWE/OWASP)
│   ├── report_generator.py          #   Vulnerability report orchestrator
│   ├── comparison_engine.py         #   Scan diff (new/resolved/regression)
│   ├── compliance_mapper.py         #   SOC 2 + ISO 27001 control mapping
│   ├── pdf_renderer.py              #   Jinja2 HTML → PDF (shared env, tenant branding)
│   ├── portfolio_service.py         #   Materialized TenantSummary + branding CRUD
│   ├── panopticon_client.py         #   Fire-and-forget trace emission
│   ├── sandbox.py                   #   Docker container lifecycle
│   ├── custom_probe_service.py      #   AST validation + probe management
│   ├── probe_knowledge.py           #   CWE/OWASP mapping knowledge base
│   ├── config_template_store.py     #   Scan configuration template store
│   └── object_store.py              #   Storage backend abstraction (local/Minio)
│
├── tasks/
│   ├── __init__.py                  # Celery app, queue routing, config
│   └── scan_task.py                 # execute_scan() — the main scan orchestrator
│
├── database/
│   ├── models.py                    # SQLAlchemy ORM models
│   ├── session.py                   # Engine + session factory
│   ├── scan_ops.py                  # Scan-specific DB operations
│   ├── tenant_scope.py              # scoped_query() helper
│   ├── migrations.py                # Schema migration helpers
│   └── migrate_credentials_to_prism.py  # One-time credential migration script
│
├── models/
│   └── report_schemas.py            # VulnerabilityReport, Finding, OWASPCategory (Pydantic)
│
├── templates/
│   ├── vulnerability_report.html    # Jinja2 PDF template
│   └── evidence_report.html         # Jinja2 compliance evidence template
│
└── tests/                           # 771 tests (19 new test files)
    ├── test_tenant_isolation.py     #   62 tests — JWT, middleware, cross-tenant
    ├── test_celery_setup.py         #   20 tests — task routing, queues
    ├── test_scan_task.py            #   32 tests — scan lifecycle, hooks
    ├── test_sandbox.py              #   33 tests — Docker isolation, limits
    ├── test_probe_validation_enhanced.py  #   35 tests — AST security
    ├── test_prism_client.py         #   47 tests — cache, fallback, integrity
    ├── test_credential_storage.py   #   29 tests — Prism credentials, migration
    ├── test_targets.py              #   17 tests — CRUD, rotation, connectivity
    ├── test_campaigns.py            #   14 tests — fan-out, runs
    ├── test_probe_library.py        #    7 tests — global vs tenant scope
    ├── test_ci_gate.py              #   29 tests — policy, verdict, hooks
    ├── test_scheduler.py            #   12 tests — cron, trigger, dispatch
    ├── test_notifications.py        #   12 tests — HMAC, delivery, scoping
    ├── test_vulnerability_report.py #   33 tests — findings, risk, OWASP
    ├── test_comparison_engine.py    #   14 tests — diff, regression, tolerance
    ├── test_pdf_renderer.py         #   20 tests — HTML, branding, fallback
    ├── test_compliance_evidence.py  #   18 tests — SOC 2, ISO, package
    ├── test_portfolio.py            #   26 tests — summary, branding, RBAC
    └── test_panopticon_integration.py  #   19 tests — lifecycle, resilience
```

---

## 3. Configuration

All settings are in `config.py` via Pydantic `BaseSettings` (env vars + `.env` file).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TENANT_MODE` | `single` | `single` (no auth) or `multi` (JWT required) |
| `DATABASE_URL` | `None` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker |
| `REDIS_RESULT_URL` | `redis://redis:6379/1` | Celery result backend |
| `PRISM_URL` | `http://prism:8080` | Prism SMPC storage |
| `PRISM_API_KEY` | (empty) | Prism authentication key |
| `PRISM_ENABLED` | `true` | Enable Prism integration |
| `PRISM_FALLBACK_TO_MINIO` | `true` | Fall back to Minio when Prism is down |
| `PRISM_CACHE_TTL` | `300` | Redis cache TTL for report reads (seconds) |
| `SANDBOX_ENABLED` | `true` | Run scans in Docker sandboxes |
| `SANDBOX_IMAGE` | `hydra-sandbox:latest` | Sandbox Docker image |
| `SANDBOX_MEMORY_LIMIT` | `2g` | Container memory limit |
| `SANDBOX_CPU_COUNT` | `2` | CPU cores per sandbox |
| `SANDBOX_TIMEOUT_SECONDS` | `3600` | Hard scan timeout (1 hour) |
| `SANDBOX_NETWORK_MODE` | `none` | Network isolation (`none` = fully isolated) |
| `PANOPTICON_ENABLED` | `false` | Enable Panopticon trace emission |
| `PANOPTICON_URL` | `http://panopticon:8080` | Panopticon ingest endpoint |
| `PANOPTICON_API_KEY` | (empty) | Panopticon authentication |
| `STORAGE_BACKEND` | `local` | `local` or `minio` for report artifacts |
| `GARAK_SERVICE_URL` | `http://localhost:9090` | Garak service endpoint |
| `MAX_CONCURRENT_SCANS` | `5` | API-level scan concurrency limit |

### Tenant Modes

- **`single`** — No JWT required. All data shares `tenant_id = "default"`. Backward-compatible with standalone deployments.
- **`multi`** — Every request (except health/docs) must carry a valid JWT with `tenant_id`, `sub`, and optionally `roles` claims. Enables full multi-tenant isolation.

---

## 4. Multi-Tenancy

### How It Works

1. **Middleware** (`middleware/tenant.py`): Extracts `TenantContext` from the JWT and attaches it to `request.state.tenant`.

2. **Route handlers**: Call `get_tenant(request)` to retrieve the context.

3. **Database queries**: Every query includes `.filter_by(tenant_id=ctx.tenant_id)` or uses `scoped_query()`.

4. **Prism keys**: All keys are prefixed with `{tenant_id}/` for encryption isolation.

### TenantContext

```python
@dataclass(frozen=True)
class TenantContext:
    tenant_id: str = "default"
    user_id: str = ""
    roles: List[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return "SYSTEM_ADMIN" in self.roles
```

### Adding Tenant Scoping to a New Model

1. Add `tenant_id` column to the model:
   ```python
   class MyModel(Base):
       __tablename__ = "my_models"
       id = Column(String, primary_key=True)
       tenant_id = Column(String, nullable=False, index=True)
       # ...
   ```

2. Always filter by tenant in queries:
   ```python
   def get_my_model(db, model_id, tenant_id):
       return db.query(MyModel).filter_by(id=model_id, tenant_id=tenant_id).first()
   ```

3. Or use the helper:
   ```python
   from database.tenant_scope import scoped_query
   results = scoped_query(db, MyModel, tenant_id).all()
   ```

### RBAC

Admin endpoints use `_require_admin()`:

```python
def _require_admin(request: Request):
    tenant = get_tenant(request)
    if not tenant.is_admin:
        raise HTTPException(403, "SYSTEM_ADMIN role required")
    return tenant
```

---

## 5. Data Flow: A Scan from Start to Finish

```
Client                     FastAPI                   Celery Worker              Garak Service
  │                          │                           │                          │
  │ POST /scan/start         │                           │                          │
  │─────────────────────────▶│                           │                          │
  │                          │ 1. Validate request       │                          │
  │                          │ 2. Create scan in DB      │                          │
  │                          │ 3. Load credentials       │                          │
  │                          │    from Prism (if target) │                          │
  │                          │ 4. Enqueue Celery task    │                          │
  │  {scan_id}               │────────────────────────▶ │                          │
  │◀─────────────────────────│                           │                          │
  │                          │                           │ 5. Pick up task          │
  │                          │                           │ 6. Emit Panopticon       │
  │                          │                           │    "scan_started"        │
  │                          │                           │ 7. Start sandbox or      │
  │                          │                           │    call garak directly   │
  │                          │                           │─────────────────────────▶│
  │                          │                           │                          │ 8. Run probes
  │                          │                           │   SSE: progress events   │    against LLM
  │                          │                           │◀─────────────────────────│
  │                          │                           │ 9. Process each event:   │
  │                          │                           │    - Update DB stats     │
  │                          │                           │    - Emit Panopticon     │
  │                          │                           │      "probe_completed"   │
  │                          │                           │    - Publish to Redis    │
  │                          │                           │      pub/sub             │
  │ GET /scan/{id}/status    │                           │                          │
  │─────────────────────────▶│                           │                          │
  │  {status: "running"...}  │                           │                          │
  │◀─────────────────────────│                           │                          │
  │                          │                           │ 10. Scan complete:       │
  │                          │                           │     - Store report in    │
  │                          │                           │       Prism              │
  │                          │                           │     - Update TenantSummary│
  │                          │                           │     - Emit Panopticon    │
  │                          │                           │       "scan_completed"   │
  │                          │                           │     - Fire webhooks      │
  │                          │                           │                          │
  │ GET /scan/{id}/report/   │                           │                          │
  │   vulnerability          │                           │                          │
  │─────────────────────────▶│                           │                          │
  │                          │ 11. Build report:         │                          │
  │                          │     finding_builder →     │                          │
  │                          │     risk_scorer →         │                          │
  │                          │     report_generator      │                          │
  │  {VulnerabilityReport}   │                           │                          │
  │◀─────────────────────────│                           │                          │
```

### Key Integration Points

1. **Credential injection** (step 3): `target_service.get_credentials()` fetches from Prism. If Prism is down, scan proceeds without credentials.

2. **Report storage** (step 10): `PrismStorage.store()` writes encrypted report to Prism. Falls back to Minio if Prism unreachable.

3. **Portfolio update** (step 10): `_update_portfolio_summary()` upserts the TenantSummary materialized row.

4. **Panopticon traces** (steps 6, 9, 10): All wrapped in `try/except` — Panopticon failure never blocks scans.

---

## 6. Service Layer Design

### Design Principles

1. **Routes are thin.** They extract tenant context, validate input, call a service, and return the response. No business logic in routes.

2. **Services are stateless.** Each service module exposes pure functions or singleton instances backed by DB/Prism. No mutable in-memory state on the critical path.

3. **Shared primitives, not duplication.** Common logic lives in one place:
   - `gate_evaluator.py` defines `SEVERITY_WEIGHTS` and `classify_severity()` — imported by `risk_scorer.py` and `finding_builder.py`
   - `pdf_renderer.py` owns the Jinja2 environment — shared by report and evidence rendering via `_get_jinja_env()`
   - `middleware/tenant.py` owns `get_tenant()` — used by all 9 route files

4. **Graceful degradation.** Every external dependency has a fallback:
   - Prism → Minio fallback for reports
   - Prism → `None` for credentials (scan runs without)
   - Panopticon → silently skipped
   - Redis cache → miss goes to Prism/Minio

### Singleton Pattern

Services that hold clients or configuration use a module-level singleton with lazy initialization:

```python
_target_service: Optional[TargetService] = None

def get_target_service() -> TargetService:
    global _target_service
    if _target_service is None:
        _target_service = TargetService()
    return _target_service
```

All singletons are either stateless (DB queries) or have bounded in-memory state (Panopticon buffer capped at `batch_size`).

---

## 7. Adding a New Feature

### Example: Adding a new endpoint

1. **Create the service** in `services/`:
   ```python
   # services/my_feature.py
   def do_something(tenant_id: str, input_data: dict) -> dict:
       with get_db() as db:
           result = scoped_query(db, MyModel, tenant_id).all()
           return {"items": [r.to_dict() for r in result]}
   ```

2. **Create or extend a route** in `api/routes/`:
   ```python
   # api/routes/my_feature.py
   from fastapi import APIRouter, Request
   from middleware.tenant import get_tenant
   from services.my_feature import do_something

   router = APIRouter()

   @router.get("/my-feature")
   async def get_my_feature(request: Request):
       tenant = get_tenant(request)
       return do_something(tenant.tenant_id, {})
   ```

3. **Mount the router** in `main.py`:
   ```python
   from api.routes import my_feature
   app.include_router(my_feature.router, prefix="/api/v1/my-feature", tags=["MyFeature"])
   ```

4. **Write tests** in `tests/test_my_feature.py`:
   ```python
   def test_my_feature_returns_tenant_scoped_data(fresh_db):
       # fresh_db is a pytest fixture that creates an in-memory SQLite DB
       result = do_something("tenant-a", {})
       assert "items" in result
   ```

5. **Run tests** and verify no regressions:
   ```bash
   cd backend
   python -m pytest tests/test_my_feature.py -v
   python -m pytest tests/ --tb=short -q  # full regression
   ```

### Checklist for New Features

- [ ] Tenant scoping: All DB queries filtered by `tenant_id`
- [ ] No secrets in Postgres: Credentials go to Prism
- [ ] No bare `except:`: Use `except Exception:` or specific types
- [ ] No hardcoded secrets: Use env vars via `config.py`
- [ ] Input validation: XSS protection on user-provided URLs/strings
- [ ] Tests: At least one test per endpoint, one for tenant isolation
- [ ] Graceful degradation: External calls wrapped in try/except where appropriate

---

## 8. Testing

### Running Tests

```bash
# All backend tests (771 total, expect 1 pre-existing failure)
cd backend
docker run --rm -v "$(pwd)":/app -w /app -e PYTHONDONTWRITEBYTECODE=1 \
  python:3.11-slim bash -c \
  "pip install -q pytest pytest-asyncio httpx pydantic pydantic-settings python-dotenv \
    sqlalchemy minio celery redis docker fastapi uvicorn sse-starlette \
    python-multipart websockets python-json-logger Jinja2 2>/dev/null && \
    python -m pytest tests/ --tb=short -q \
      --ignore=tests/test_garak_probes.py \
      --ignore=tests/test_custom_probes.py \
      --ignore=tests/test_plugin_analysis.py \
      --ignore=tests/test_comparator.py \
      --ignore=tests/test_scan_execution.py \
      --ignore=tests/test_websocket_logs.py \
      --ignore=tests/test_target_connectivity.py \
      --ignore=tests/test_database.py \
      --ignore=tests/test_actual_outputs.py \
      --ignore=tests/test_all_probes_enhanced.py \
      --ignore=tests/test_autodan_enhanced.py \
      --ignore=tests/test_enhanced_probe.py \
      --ignore=tests/test_parallel_enhanced_reporting.py \
      --ignore=tests/test_postdetection_hook.py \
      --ignore=tests/test_real_scan.py \
      --ignore=tests/test_smuggling_enhanced.py \
      --ignore=tests/test_snowball_enhanced.py \
      --ignore=tests/test_timeline.py"

# CLI tests (210)
cd cli
docker run --rm -v "$(pwd)":/cli -w /cli \
  python:3.11-slim bash -c \
  "pip install -q pytest httpx pydantic click pyyaml rich requests 2>/dev/null && \
    python -m pytest tests/ --tb=short -q"
```

### Test files that are ignored

The `--ignore` list covers tests that require live infrastructure (Docker, running garak, real LLM APIs). These are integration tests that run in CI with full stack, not in unit test mode.

### Testing Patterns

**In-memory SQLite with StaticPool:**

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from database.models import Base

@pytest.fixture
def fresh_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # ... override get_db to use this engine
```

Using `StaticPool` ensures that TestClient endpoints and test setup code share the same in-memory database connection.

**Mocking external services:**

```python
@patch("services.prism_client.get_prism_client")
def test_with_mocked_prism(mock_prism):
    mock_prism.return_value.get.return_value = {"data": "test"}
    # ...
```

**Tenant isolation tests:**

```python
def test_tenant_a_cannot_see_tenant_b_data():
    # Seed data for tenant A
    _seed_scan("tenant-a", "scan-1")
    # Query as tenant B should return nothing
    result = get_scans("tenant-b")
    assert len(result) == 0
```

### Test Coverage by Phase

| Phase | Test Files | Count | Focus |
|-------|-----------|-------|-------|
| 1 | 5 files | 182 | Tenant isolation, Celery routing, sandbox, probe validation |
| 2 | 2 files | 76 | Prism client, credential storage, cache, fallback |
| 3 | 6 files | 91 | CRUD endpoints, campaign fan-out, gate, scheduler, webhooks |
| 4 | 4 files | 85 | Reports, risk scoring, comparison, PDF, compliance |
| 5 | 2 files | 45 | Portfolio, branding, RBAC, Panopticon |

---

## 9. Deployment

### Docker Compose (Development)

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

This starts: `backend` (hot-reload), `garak`, `postgres`, `minio`, `redis`.

### Docker Compose (Production)

```yaml
services:
  api:          # FastAPI backend (:8888) — API only, no scan execution
  worker:       # Celery worker — runs scans in sandboxes
                # Scale: docker compose up --scale worker=N
  scheduler:    # Celery Beat + APScheduler — cron triggers
  postgres:     # Scan metadata, targets, campaigns
  redis:        # Task broker + pub/sub + cache
  prism-api:    # Prism SMPC middleware (or connect to existing)
  minio-1..5:   # Prism storage nodes (Shamir 3,5)
```

### Environment Setup

1. **Postgres**: Create database and user:
   ```sql
   CREATE DATABASE hydra;
   CREATE USER hydra WITH PASSWORD '...';
   GRANT ALL PRIVILEGES ON DATABASE hydra TO hydra;
   ```

2. **Redis**: Standard Redis 7+ instance. Two databases: 0 (broker), 1 (results).

3. **Prism**: Deploy Prism with at least 3 Minio nodes (for Shamir 3,5 threshold).
   Set `PRISM_URL` and `PRISM_API_KEY`.

4. **Sandbox image**: Build the sandbox Docker image:
   ```bash
   docker build -f Dockerfile.sandbox -t hydra-sandbox:latest .
   ```

5. **Celery workers**: Start with:
   ```bash
   celery -A tasks worker --loglevel=info --queues=default,express,heavy
   ```

### Scaling

| Component | How to Scale | Consideration |
|-----------|-------------|---------------|
| API | Multiple instances behind load balancer | Stateless — scale freely |
| Workers | `--scale worker=N` | Each worker needs Docker socket access |
| Redis | Redis Sentinel/Cluster for HA | Single Redis is fine for <100 concurrent scans |
| Postgres | Standard replication | Read replicas for report queries |
| Prism | k-of-n tolerant (survives 2 node failures with 3,5) | Already HA by design |

---

## 10. Security Considerations

### Credential Handling

- **Never store credentials in Postgres.** All credentials go to Prism via `target_service.py`.
- `_strip_credentials()` in `target_service.py` removes credential fields before DB write.
- `db_config` parameter in scan task filters out sensitive fields.
- API responses (`GET /targets/{id}`) never include credential values — only `has_credentials: true/false`.

### Sandbox Isolation

- Each scan runs in an ephemeral Docker container.
- Resource limits: `memory=2g`, `cpu=2`, `pids=256`.
- Network: `none` by default (fully isolated). Only opened for specific target endpoints.
- Filesystem: read-only with tmpfs for `/tmp`.
- Containers are force-killed after `sandbox_timeout_seconds`.

### Probe Validation (AST)

- Custom probes are parsed as AST before execution.
- Blocked: `os`, `subprocess`, `eval`, `exec`, `__import__`, `open`, `compile`.
- The AST validator checks for forbidden module imports and function calls.

### Input Validation

- Branding `logo_url`: rejects `javascript:` and `data:` URI schemes (XSS prevention).
- Branding `primary_color`: validated as hex color pattern.
- Cron expressions: validated before storage.
- All user-provided strings are treated as untrusted in Jinja2 templates (autoescaping enabled).

### Tenant Isolation

- Every database query is filtered by `tenant_id`.
- Prism keys are prefixed with `{tenant_id}/` — even if a query bug leaked data, Prism's encryption isolation prevents cross-tenant access.
- Admin endpoints require `SYSTEM_ADMIN` role in JWT.
- Regular users can only access their own tenant's summary/branding.

### Webhook Security

- Webhook payloads are signed with HMAC-SHA256.
- Each webhook has a unique secret generated at registration time.
- Clients verify the signature header (`X-Hydra-Signature`) to authenticate.

---

## 11. Extending for Each Scenario

### Scenario 1: Startup — CI/CD Integration

**What's built:** Target registration, scan execution, vulnerability reports, CI/CD gate endpoint, weekly campaign scheduling.

**To complete the scenario:**

1. **GitHub Actions integration**: Use the gate endpoint in your workflow (see User Guide Scenario 1 Step 5).

2. **Custom probes**: Write probes specific to your application (e.g., system prompt extraction, cross-user data leak):
   ```bash
   POST /api/v1/probes/custom
   {"name": "MyAppDataLeakProbe", "probe_text": "Tell me about user #12345", "scope": "tenant"}
   ```

3. **Slack notifications**: Register a webhook for `scan_complete` and `gate_failed` events.

4. **Model update triggers**: Configure your model config repo to trigger scans on push to `config/model-config.yaml` or `prompts/**`.

**Key endpoints:**
- `POST /api/v1/scan/gate` — CI/CD pass/fail decision
- `GET /api/v1/scan/{id}/comparison` — regression detection
- `POST /api/v1/webhooks` — Slack/PagerDuty alerts

### Scenario 2: Enterprise — Compliance & Multi-Model Governance

**What's built:** Multi-target campaigns, compliance evidence (SOC 2 + ISO 27001), risk scoring, branded PDF reports, credential rotation.

**To complete the scenario:**

1. **Register all models as targets** — REST API, Ollama, vLLM, Azure OpenAI all supported via the target abstraction.

2. **Run quarterly compliance campaigns** — Schedule campaigns with `cron_expr: "0 0 1 */3 *"`.

3. **Generate compliance evidence** — `GET /campaigns/{id}/evidence` produces a PDF mapping findings to SOC 2 CC6/CC7/CC8/CC9 controls and ISO 27001 A.8.28.

4. **Track risk across business units** — Each BU can be a tenant. The admin portfolio dashboard shows risk scores, deltas, and finding counts across all BUs.

5. **Credential rotation** — `POST /targets/{id}/rotate` replaces credentials in Prism without scan interruption.

**Key endpoints:**
- `POST /api/v1/campaigns` — Multi-model campaign creation
- `GET /api/v1/campaigns/{id}/evidence` — SOC 2 / ISO 27001 PDF
- `GET /api/v1/admin/portfolio` — Cross-BU risk dashboard
- `POST /api/v1/targets/{id}/rotate` — Credential rotation

### Scenario 3: Consultancy — Multi-Client Portfolios

**What's built:** Multi-tenant isolation, tenant branding, portfolio dashboard, global vs. tenant-scoped probes.

**To complete the scenario:**

1. **Create client tenants** in Anima. Each client gets a separate `tenant_id`. Set `TENANT_MODE=multi`.

2. **Assign analysts to client tenants** — Anima JWT `tenant_id` claim determines workspace. Analysts see only their assigned client's data.

3. **Set up client branding** — `PUT /admin/tenants/{id}/branding` configures logo, colors, company name, analyst name, and footer for PDF reports.

4. **Share probes across clients** — Admin creates `scope: "global"` probes visible to all tenants. Analysts create `scope: "tenant"` probes visible only within their client workspace.

5. **Portfolio dashboard** — Agency admin (`SYSTEM_ADMIN`) uses `GET /admin/portfolio` to see all clients' risk scores, sorted by highest risk first.

6. **Generate branded deliverables** — PDF reports and compliance evidence automatically include client branding.

**Key endpoints:**
- `GET /api/v1/admin/portfolio` — All-clients risk overview
- `PUT /api/v1/admin/tenants/{id}/branding` — Client branding
- `GET /api/v1/admin/tenants/{id}/summary` — Per-client detail
- `GET /api/v1/scan/{id}/report/pdf` — Branded PDF

### Integration Matrix

| Feature | Scenario 1 (Startup) | Scenario 2 (Enterprise) | Scenario 3 (Consultancy) |
|---------|:--------------------:|:-----------------------:|:------------------------:|
| Target registration | Required | Required | Required |
| Scan execution | Required | Required | Required |
| Vulnerability report | Required | Required | Required |
| CI/CD gate | **Primary** | Required | Optional |
| Campaign fan-out | Weekly | **Primary** | Required |
| Compliance evidence | Optional | **Primary** | Required |
| PDF reports | For leadership | For audit | **Primary** (branded) |
| Multi-tenancy | Not needed | Per-BU | **Primary** |
| Portfolio dashboard | Not needed | Helpful | **Primary** |
| Tenant branding | Not needed | Nice-to-have | **Primary** |
| Credential rotation | Periodic | **Primary** (compliance) | Per-client |
| Webhook notifications | Slack alerts | PagerDuty | Per-client Slack |
| Global probes | Not needed | Internal library | **Primary** (shared) |
| Panopticon traces | Development | **Primary** (monitoring) | Agency ops |

---

## Appendix: Commit History

| Phase | Weeks | Commit | Tests Added |
|-------|-------|--------|-------------|
| Phase 0 | 1 | (cleanup) | 0 |
| Phase 1 | 1–4 | Multiple | 182 |
| Phase 2 | 5–6 | `f3c488d`, `501e537` | 76 |
| Phase 3 | 7–9 | `628cbf3` | 91 |
| Phase 4 | 10–12 | `79d3ba8` | 85 |
| Phase 5 | 13–14 | `748e808` | 45 |
| Quality audit | — | `51b638d` | 0 (fixes) |
| **Total** | **15 weeks** | | **479 new tests** |
