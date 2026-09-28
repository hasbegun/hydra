"""
Tests for Phase 1 Week 2: Scan Task + Tenant-Aware Persistence.

Covers:
- execute_scan Celery task registration and configuration
- Task DB persistence with tenant_id (PENDING → RUNNING → COMPLETED)
- Task DB persistence on failure (PENDING → RUNNING → FAILED)
- SSE event processing (_process_sse_event)
- Tenant-scoped scan queries (get_all_scans, get_scan_status, get_scan_statistics)
- Tenant-scoped scan deletion and cancellation
- Scan history endpoint scoped to tenant
- Scan statistics endpoint scoped to tenant
- start_scan stores tenant_id in active_scans
"""
import base64
import json
import os
import sys
import time
from datetime import datetime
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.models import Base, Scan
from database.session import init_db, get_db


# ---------------------------------------------------------------------------
# JWT helper (same as test_tenant_isolation.py)
# ---------------------------------------------------------------------------

def _make_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{body}.{signature}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db():
    """Reset the database module-level state between tests."""
    import database.session as sess
    old_engine = sess._engine
    old_factory = sess._SessionFactory
    yield
    sess._engine = old_engine
    sess._SessionFactory = old_factory


@pytest.fixture
def db():
    """Initialize an in-memory DB and yield the session factory."""
    init_db(":memory:")
    return get_db


@pytest.fixture
def db_session(db):
    """Yield a session for direct DB manipulation."""
    with db() as session:
        yield session


# ---------------------------------------------------------------------------
# Celery task registration
# ---------------------------------------------------------------------------

class TestCeleryTaskRegistration:
    """Verify the execute_scan task is discoverable."""

    def test_execute_scan_registered(self):
        from tasks.scan_task import execute_scan  # noqa: F401 — trigger registration
        from tasks import celery_app
        assert "tasks.execute_scan" in celery_app.tasks

    def test_execute_scan_importable(self):
        from tasks.scan_task import execute_scan
        assert callable(execute_scan)

    def test_task_max_retries(self):
        from tasks.scan_task import execute_scan
        assert execute_scan.max_retries == 2

    def test_task_default_retry_delay(self):
        from tasks.scan_task import execute_scan
        assert execute_scan.default_retry_delay == 60


# ---------------------------------------------------------------------------
# _sync_scan_to_db (task-internal DB persistence)
# ---------------------------------------------------------------------------

class TestTaskSyncScanToDB:
    """Tests for the task's self-contained DB write function."""

    def test_creates_new_scan_with_tenant_id(self, db_session):
        from tasks.scan_task import _sync_scan_to_db

        _sync_scan_to_db(
            scan_id="task-001",
            tenant_id="acme",
            status="pending",
            config_dict={"target_type": "ollama", "target_name": "llama3"},
            started_at="2025-01-01T00:00:00",
        )

        row = db_session.query(Scan).filter_by(id="task-001").first()
        assert row is not None
        assert row.tenant_id == "acme"
        assert row.target_type == "ollama"
        assert row.target_name == "llama3"
        assert row.status == "pending"

    def test_updates_existing_scan(self, db_session):
        from tasks.scan_task import _sync_scan_to_db

        _sync_scan_to_db(
            scan_id="task-002", tenant_id="acme", status="pending",
            config_dict={"target_type": "x", "target_name": "y"},
            started_at="2025-01-01T00:00:00",
        )
        _sync_scan_to_db(
            scan_id="task-002", tenant_id="acme", status="running",
            passed=5, failed=2,
        )

        row = db_session.query(Scan).filter_by(id="task-002").first()
        assert row.status == "running"
        assert row.passed == 5
        assert row.failed == 2

    def test_upsert_preserves_config_json(self, db_session):
        from tasks.scan_task import _sync_scan_to_db

        _sync_scan_to_db(
            scan_id="task-003", tenant_id="acme", status="pending",
            config_dict={"target_type": "a", "target_name": "b", "probes": ["dan"]},
        )
        # Update without config — should not overwrite
        _sync_scan_to_db(
            scan_id="task-003", tenant_id="acme", status="completed",
            passed=10, failed=0,
        )

        row = db_session.query(Scan).filter_by(id="task-003").first()
        config = json.loads(row.config_json)
        assert config["probes"] == ["dan"]

    def test_computes_pass_rate(self, db_session):
        from tasks.scan_task import _sync_scan_to_db

        _sync_scan_to_db(
            scan_id="task-004", tenant_id="t", status="completed",
            passed=8, failed=2,
        )

        row = db_session.query(Scan).filter_by(id="task-004").first()
        assert row.pass_rate == pytest.approx(80.0)

    def test_handles_zero_total(self, db_session):
        from tasks.scan_task import _sync_scan_to_db

        _sync_scan_to_db(
            scan_id="task-005", tenant_id="t", status="pending",
            passed=0, failed=0,
        )

        row = db_session.query(Scan).filter_by(id="task-005").first()
        assert row.pass_rate is None


# ---------------------------------------------------------------------------
# _process_sse_event
# ---------------------------------------------------------------------------

class TestProcessSSEEvent:
    """Tests for SSE event processing in the Celery task."""

    def _make_state(self):
        return {
            "scan_id": "s1", "tenant_id": "t", "status": "running",
            "passed": 0, "failed": 0, "total_probes": 0,
            "progress": 0.0, "current_probe": None,
            "error_message": None, "completed_at": None,
            "report_path": None, "html_report_path": None,
            "report_key": None, "html_report_key": None,
        }

    def test_status_event(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event("s1", "t", {"event_type": "status", "status": "running"}, state, {}, "")
        assert state["status"] == "running"

    def test_progress_event(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event(
            "s1", "t",
            {"event_type": "progress", "probe": "dan.DAN", "percent": 45.0},
            state, {}, "",
        )
        assert state["current_probe"] == "dan.DAN"
        assert state["progress"] == 45.0
        assert state["status"] == "running"

    def test_probe_count_event(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event(
            "s1", "t", {"event_type": "probe_count", "total": 15}, state, {}, "",
        )
        assert state["total_probes"] == 15

    def test_result_event(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event(
            "s1", "t",
            {"event_type": "result", "total_passed": 10, "total_failed": 3},
            state, {}, "",
        )
        assert state["passed"] == 10
        assert state["failed"] == 3

    def test_complete_event(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event(
            "s1", "t",
            {
                "event_type": "complete",
                "passed": 20, "failed": 5,
                "report_keys": {"jsonl": "key/jsonl", "html": "key/html"},
            },
            state, {}, "",
        )
        assert state["status"] == "completed"
        assert state["progress"] == 100.0
        assert state["passed"] == 20
        assert state["failed"] == 5
        assert state["report_key"] == "key/jsonl"
        assert state["html_report_key"] == "key/html"
        assert state["completed_at"] is not None

    def test_error_event(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event(
            "s1", "t",
            {"event_type": "error", "message": "probe crashed"},
            state, {}, "",
        )
        assert state["status"] == "failed"
        assert state["error_message"] == "probe crashed"
        assert state["completed_at"] is not None

    def test_report_event_jsonl(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event(
            "s1", "t",
            {"event_type": "report", "report_type": "jsonl", "path": "/tmp/report.jsonl"},
            state, {}, "",
        )
        assert state["report_path"] == "/tmp/report.jsonl"

    def test_report_event_html(self):
        from tasks.scan_task import _process_sse_event
        state = self._make_state()
        _process_sse_event(
            "s1", "t",
            {"event_type": "report", "report_type": "html", "path": "/tmp/report.html"},
            state, {}, "",
        )
        assert state["html_report_path"] == "/tmp/report.html"


# ---------------------------------------------------------------------------
# Tenant-scoped GarakWrapper methods
# ---------------------------------------------------------------------------

class TestTenantScopedGetAllScans:
    """Tests for get_all_scans(tenant_id=...) filtering."""

    def test_returns_only_tenant_scans_from_db(self, db_session):
        from services.garak_wrapper import GarakWrapper

        db_session.add(Scan(
            id="s1", tenant_id="acme", target_type="a", target_name="b",
            status="completed", started_at="2025-01-01T00:00:00",
        ))
        db_session.add(Scan(
            id="s2", tenant_id="globex", target_type="a", target_name="b",
            status="completed", started_at="2025-01-02T00:00:00",
        ))
        db_session.add(Scan(
            id="s3", tenant_id="acme", target_type="a", target_name="b",
            status="completed", started_at="2025-01-03T00:00:00",
        ))
        db_session.commit()

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            acme_scans = w.get_all_scans(tenant_id="acme")
            assert len(acme_scans) == 2
            assert {s["scan_id"] for s in acme_scans} == {"s1", "s3"}

    def test_returns_all_when_no_tenant_id(self, db_session):
        from services.garak_wrapper import GarakWrapper

        db_session.add(Scan(
            id="s1", tenant_id="acme", target_type="a", target_name="b",
            status="completed", started_at="2025-01-01T00:00:00",
        ))
        db_session.add(Scan(
            id="s2", tenant_id="globex", target_type="a", target_name="b",
            status="completed", started_at="2025-01-02T00:00:00",
        ))
        db_session.commit()

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            all_scans = w.get_all_scans()
            assert len(all_scans) == 2

    def test_filters_active_scans_by_tenant(self, db_session):
        from services.garak_wrapper import GarakWrapper

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            w.active_scans["active-1"] = {
                "scan_id": "active-1", "tenant_id": "acme",
                "status": "running", "started_at": "2025-01-01T00:00:00",
            }
            w.active_scans["active-2"] = {
                "scan_id": "active-2", "tenant_id": "globex",
                "status": "running", "started_at": "2025-01-01T00:00:00",
            }

            acme = w.get_all_scans(tenant_id="acme")
            assert len(acme) == 1
            assert acme[0]["scan_id"] == "active-1"


class TestTenantScopedGetScanStatus:
    """Tests for get_scan_status(scan_id, tenant_id=...) access control."""

    def test_returns_scan_for_correct_tenant(self, db_session):
        from services.garak_wrapper import GarakWrapper

        db_session.add(Scan(
            id="s1", tenant_id="acme", target_type="a", target_name="b", status="completed",
        ))
        db_session.commit()

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            result = w.get_scan_status("s1", tenant_id="acme")
            assert result is not None
            assert result["scan_id"] == "s1"

    def test_returns_none_for_wrong_tenant(self, db_session):
        from services.garak_wrapper import GarakWrapper

        db_session.add(Scan(
            id="s1", tenant_id="acme", target_type="a", target_name="b", status="completed",
        ))
        db_session.commit()

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            result = w.get_scan_status("s1", tenant_id="globex")
            assert result is None

    def test_active_scan_tenant_check(self):
        from services.garak_wrapper import GarakWrapper

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            w = GarakWrapper()

            w.active_scans["s1"] = {
                "scan_id": "s1", "tenant_id": "acme",
                "status": "running", "progress": 50.0,
            }

            # Correct tenant
            assert w.get_scan_status("s1", tenant_id="acme") is not None
            # Wrong tenant
            assert w.get_scan_status("s1", tenant_id="globex") is None
            # No tenant filter (backward compat)
            assert w.get_scan_status("s1") is not None


class TestTenantScopedScanStatistics:
    """Tests for get_scan_statistics(tenant_id=...) filtering."""

    def test_statistics_scoped_to_tenant(self, db_session):
        from services.garak_wrapper import GarakWrapper

        # acme: 2 scans, both completed
        db_session.add(Scan(
            id="s1", tenant_id="acme", target_type="a", target_name="b",
            status="completed", passed=8, failed=2, started_at="2025-01-01T00:00:00",
        ))
        db_session.add(Scan(
            id="s2", tenant_id="acme", target_type="a", target_name="b",
            status="completed", passed=6, failed=4, started_at="2025-01-02T00:00:00",
        ))
        # globex: 1 scan
        db_session.add(Scan(
            id="s3", tenant_id="globex", target_type="c", target_name="d",
            status="completed", passed=10, failed=0, started_at="2025-01-03T00:00:00",
        ))
        db_session.commit()

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            acme_stats = w.get_scan_statistics(tenant_id="acme")
            assert acme_stats["total_scans"] == 2

            globex_stats = w.get_scan_statistics(tenant_id="globex")
            assert globex_stats["total_scans"] == 1

            all_stats = w.get_scan_statistics()
            assert all_stats["total_scans"] == 3


class TestTenantScopedDeleteScan:
    """Tests for delete_scan(scan_id, tenant_id=...) access control."""

    def test_delete_denied_for_wrong_tenant(self, db_session):
        from services.garak_wrapper import GarakWrapper

        db_session.add(Scan(
            id="s1", tenant_id="acme", target_type="a", target_name="b", status="completed",
        ))
        db_session.commit()

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            result = w.delete_scan("s1", tenant_id="globex")
            assert result is False

            # Verify scan still exists
            row = db_session.query(Scan).filter_by(id="s1").first()
            assert row is not None

    def test_delete_allowed_for_correct_tenant(self, db_session):
        from services.garak_wrapper import GarakWrapper

        db_session.add(Scan(
            id="s1", tenant_id="acme", target_type="a", target_name="b", status="completed",
        ))
        db_session.commit()

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.garak_reports_path.exists.return_value = False
            w = GarakWrapper()

            result = w.delete_scan("s1", tenant_id="acme")
            assert result is True


class TestTenantScopedCancelScan:
    """Tests for cancel_scan(scan_id, tenant_id=...) access control."""

    def test_cancel_denied_for_wrong_tenant(self):
        from services.garak_wrapper import GarakWrapper

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            w = GarakWrapper()

            from models.schemas import ScanStatus
            w.active_scans["s1"] = {
                "scan_id": "s1", "tenant_id": "acme",
                "status": ScanStatus.RUNNING,
            }

            import asyncio
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(w.cancel_scan("s1", tenant_id="globex"))
            loop.close()
            assert result is False


class TestStartScanStoresTenantId:
    """Tests for start_scan storing tenant_id in active_scans."""

    def test_start_scan_stores_tenant_id(self):
        """start_scan() includes tenant_id in the active_scans dict."""
        import asyncio
        from unittest.mock import AsyncMock
        from services.garak_wrapper import GarakWrapper
        from models.schemas import ScanConfigRequest

        with patch("services.garak_wrapper.settings") as mock_settings:
            mock_settings.garak_service_url = "http://localhost:9090"
            mock_settings.garak_reports_path = MagicMock()
            mock_settings.max_concurrent_scans = 5
            w = GarakWrapper()

            config = ScanConfigRequest(
                target_type="ollama",
                target_name="llama3",
                probes=["dan"],
            )

            # Mock the async HTTP client context manager
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response

            async def run():
                with patch("httpx.AsyncClient") as mock_cls, \
                     patch("asyncio.create_task"):
                    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
                    return await w.start_scan(config, tenant_id="acme")

            loop = asyncio.new_event_loop()
            scan_id = loop.run_until_complete(run())
            loop.close()

            assert scan_id in w.active_scans
            assert w.active_scans[scan_id]["tenant_id"] == "acme"


# ---------------------------------------------------------------------------
# Scan route endpoints with tenant scoping
# ---------------------------------------------------------------------------

class TestScanRouteTenantScoping:
    """Integration tests for scan routes with TenantMiddleware.

    These tests mock the garak_wrapper methods to verify that the route
    handlers correctly extract tenant_id from JWT and pass it through.
    The actual tenant-scoped DB queries are tested in the
    TestTenantScoped* classes above.
    """

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from middleware.tenant import TenantMiddleware
        from api.routes.scan import router

        app = FastAPI()
        app.add_middleware(TenantMiddleware, tenant_mode="multi")
        app.include_router(router, prefix="/scan")
        return TestClient(app)

    def _auth_header(self, tenant_id="acme"):
        token = _make_jwt({"tenant_id": tenant_id, "sub": "user1"})
        return {"Authorization": f"Bearer {token}"}

    def test_scan_history_passes_tenant_id(self, client):
        """Route handler passes tenant_id from JWT to garak_wrapper."""
        acme_scan = {
            "scan_id": "s1", "tenant_id": "acme", "status": "completed",
            "target_type": "a", "target_name": "b",
            "started_at": "2025-01-01T00:00:00", "completed_at": "2025-01-02T00:00:00",
            "passed": 10, "failed": 0,
            "html_report_path": None, "jsonl_report_path": None,
        }
        with patch("api.routes.scan.garak_wrapper") as mock_gw:
            mock_gw.get_all_scans.return_value = [acme_scan]
            resp = client.get("/scan/history", headers=self._auth_header("acme"))

        assert resp.status_code == 200
        # Verify get_all_scans was called with the correct tenant_id
        mock_gw.get_all_scans.assert_called_once_with(tenant_id="acme")
        data = resp.json()
        assert data["total_count"] == 1
        assert data["scans"][0]["scan_id"] == "s1"

    def test_scan_history_different_tenant(self, client):
        """Different JWT → different tenant_id passed to wrapper."""
        with patch("api.routes.scan.garak_wrapper") as mock_gw:
            mock_gw.get_all_scans.return_value = []
            resp = client.get("/scan/history", headers=self._auth_header("globex"))

        assert resp.status_code == 200
        mock_gw.get_all_scans.assert_called_once_with(tenant_id="globex")

    def test_scan_status_passes_tenant_id(self, client):
        """GET /scan/{id}/status passes tenant_id to garak_wrapper."""
        with patch("api.routes.scan.garak_wrapper") as mock_gw:
            mock_gw.get_scan_status.return_value = {
                "scan_id": "s1", "status": "completed", "progress": 100.0,
                "current_probe": None, "completed_probes": 5, "total_probes": 5,
                "passed": 10, "failed": 0, "error_message": None,
            }
            resp = client.get("/scan/s1/status", headers=self._auth_header("acme"))

        assert resp.status_code == 200
        mock_gw.get_scan_status.assert_called_once_with("s1", tenant_id="acme")

    def test_scan_status_404_for_wrong_tenant(self, client):
        """Scan exists but belongs to different tenant → 404."""
        with patch("api.routes.scan.garak_wrapper") as mock_gw:
            mock_gw.get_scan_status.return_value = None
            resp = client.get("/scan/s1/status", headers=self._auth_header("globex"))

        assert resp.status_code == 404

    def test_delete_passes_tenant_id(self, client):
        """DELETE /scan/{id} passes tenant_id to garak_wrapper."""
        with patch("api.routes.scan.garak_wrapper") as mock_gw:
            mock_gw.delete_scan.return_value = True
            resp = client.delete("/scan/s1", headers=self._auth_header("acme"))

        assert resp.status_code == 200
        mock_gw.delete_scan.assert_called_once_with("s1", tenant_id="acme")

    def test_delete_denied_returns_404(self, client):
        """Wrapper returns False (wrong tenant) → route returns 404."""
        with patch("api.routes.scan.garak_wrapper") as mock_gw:
            mock_gw.delete_scan.return_value = False
            resp = client.delete("/scan/s1", headers=self._auth_header("globex"))

        assert resp.status_code == 404

    def test_statistics_passes_tenant_id(self, client):
        """GET /scan/statistics passes tenant_id to garak_wrapper."""
        with patch("api.routes.scan.garak_wrapper") as mock_gw:
            mock_gw.get_scan_statistics.return_value = {
                "total_scans": 1, "status_breakdown": {},
                "overall_pass_rate": 80.0, "total_passed": 8,
                "total_failed": 2, "average_pass_rate": 80.0,
                "daily_trend": [], "top_failing_probes": [],
                "target_breakdown": [],
            }
            resp = client.get("/scan/statistics", headers=self._auth_header("acme"))

        assert resp.status_code == 200
        mock_gw.get_scan_statistics.assert_called_once_with(days=30, tenant_id="acme")

    def test_history_requires_auth_in_multi_mode(self, client):
        resp = client.get("/scan/history")
        assert resp.status_code == 401
