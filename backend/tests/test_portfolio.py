"""
Phase 5 Week 13 — Portfolio dashboard, tenant summary, branding, RBAC tests.
"""
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import init_db, get_db
from database.models import TenantSummary, TenantBranding
from services.portfolio_service import (
    update_tenant_summary,
    get_portfolio,
    get_tenant_summary,
    upsert_branding,
    get_branding,
    get_branding_for_pdf,
    update_next_scheduled_scan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db():
    """Initialize a fresh in-memory DB for each test.

    Uses a file-based SQLite to avoid the per-connection-new-DB issue
    with ``:memory:`` and multiple sessions.
    """
    import tempfile, os
    db_file = tempfile.mktemp(suffix=".db")
    init_db(db_file)
    yield
    try:
        os.unlink(db_file)
    except OSError:
        pass


def _seed_tenant(tenant_id: str, risk: float = 50.0, scans: int = 5):
    """Seed a TenantSummary row directly."""
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        db.add(TenantSummary(
            tenant_id=tenant_id,
            risk_score=risk,
            previous_risk_score=risk - 10,
            risk_delta=10.0,
            total_scans=scans,
            completed_scans=scans,
            failed_scans=0,
            critical_count=2,
            high_count=3,
            medium_count=1,
            low_count=0,
            total_findings=6,
            latest_scan_id=f"scan-{tenant_id}-latest",
            latest_scan_at=now,
            updated_at=now,
        ))
        db.commit()


# ===================================================================
# TenantSummary Materialization
# ===================================================================

class TestTenantSummaryUpdate:
    def test_creates_summary_on_first_scan(self):
        """First completed scan creates a TenantSummary row."""
        update_tenant_summary("t1", "scan-1", risk_score=65.0,
                              critical=2, high=3, medium=1, low=0, total_findings=6)
        summary = get_tenant_summary("t1")
        assert summary is not None
        assert summary["risk_score"] == 65.0
        assert summary["total_scans"] == 1
        assert summary["completed_scans"] == 1
        assert summary["critical_count"] == 2
        assert summary["total_findings"] == 6

    def test_updates_risk_delta_on_subsequent_scan(self):
        """Second scan shifts previous → current risk score."""
        update_tenant_summary("t1", "scan-1", risk_score=70.0)
        update_tenant_summary("t1", "scan-2", risk_score=40.0)
        summary = get_tenant_summary("t1")
        assert summary["risk_score"] == 40.0
        assert summary["previous_risk_score"] == 70.0
        assert summary["risk_delta"] == -30.0

    def test_increments_scan_counts(self):
        """Each scan increments total_scans counter."""
        update_tenant_summary("t1", "scan-1", risk_score=50.0)
        update_tenant_summary("t1", "scan-2", risk_score=45.0)
        update_tenant_summary("t1", "scan-3", risk_score=30.0, status="failed")
        summary = get_tenant_summary("t1")
        assert summary["total_scans"] == 3
        assert summary["completed_scans"] == 2
        assert summary["failed_scans"] == 1

    def test_tracks_latest_scan_id(self):
        """Latest scan ID updated on completion."""
        update_tenant_summary("t1", "scan-1", risk_score=50.0)
        update_tenant_summary("t1", "scan-2", risk_score=45.0)
        summary = get_tenant_summary("t1")
        assert summary["latest_scan_id"] == "scan-2"

    def test_failed_scan_does_not_update_risk(self):
        """Failed scan increments counter but doesn't change risk score."""
        update_tenant_summary("t1", "scan-1", risk_score=70.0)
        update_tenant_summary("t1", "scan-2", risk_score=0.0, status="failed")
        summary = get_tenant_summary("t1")
        assert summary["risk_score"] == 70.0  # Unchanged
        assert summary["failed_scans"] == 1


# ===================================================================
# Portfolio Dashboard
# ===================================================================

class TestPortfolio:
    def test_returns_all_tenants(self):
        """Admin sees all tenants with risk scores."""
        _seed_tenant("tenant-a", risk=80.0)
        _seed_tenant("tenant-b", risk=30.0)
        _seed_tenant("tenant-c", risk=60.0)
        portfolio = get_portfolio()
        assert len(portfolio) == 3
        # Sorted by risk descending
        assert portfolio[0]["tenant_id"] == "tenant-a"
        assert portfolio[0]["risk_score"] == 80.0

    def test_includes_risk_trends(self):
        """Each tenant has risk_delta."""
        _seed_tenant("tenant-a", risk=50.0)
        portfolio = get_portfolio()
        assert portfolio[0]["risk_delta"] == 10.0

    def test_includes_finding_counts(self):
        """Critical/high/medium/low per tenant."""
        _seed_tenant("tenant-a")
        portfolio = get_portfolio()
        t = portfolio[0]
        assert t["critical_count"] == 2
        assert t["high_count"] == 3
        assert t["medium_count"] == 1
        assert t["low_count"] == 0

    def test_includes_next_scan(self):
        """Next scheduled scan datetime included."""
        _seed_tenant("tenant-a")
        update_next_scheduled_scan("tenant-a", "2024-12-01T00:00:00")
        portfolio = get_portfolio()
        assert portfolio[0]["next_scheduled_scan"] == "2024-12-01T00:00:00"

    def test_empty_portfolio(self):
        """No tenants → empty list."""
        portfolio = get_portfolio()
        assert portfolio == []


# ===================================================================
# Branding CRUD
# ===================================================================

class TestBranding:
    def test_upsert_creates_branding(self):
        """First branding update creates a new row."""
        result = upsert_branding("t1", {
            "company_name": "HealthCo",
            "logo_url": "https://example.com/logo.png",
            "analyst_name": "Jane Doe",
        })
        assert result["company_name"] == "HealthCo"
        assert result["logo_url"] == "https://example.com/logo.png"
        assert result["analyst_name"] == "Jane Doe"

    def test_upsert_updates_existing(self):
        """Second branding update modifies existing row."""
        upsert_branding("t1", {"company_name": "OldCo"})
        result = upsert_branding("t1", {"company_name": "NewCo"})
        assert result["company_name"] == "NewCo"

    def test_partial_update(self):
        """Only specified fields are updated."""
        upsert_branding("t1", {"company_name": "HealthCo", "analyst_name": "Alice"})
        result = upsert_branding("t1", {"analyst_name": "Bob"})
        assert result["company_name"] == "HealthCo"  # Unchanged
        assert result["analyst_name"] == "Bob"

    def test_get_branding_returns_none_when_not_set(self):
        """No branding set → None."""
        assert get_branding("t-nonexistent") is None

    def test_get_branding_for_pdf_format(self):
        """Branding dict formatted for pdf_renderer."""
        upsert_branding("t1", {
            "company_name": "Sentinel",
            "footer_text": "Confidential",
            "analyst_name": "Jane",
        })
        branding = get_branding_for_pdf("t1")
        assert branding["company_name"] == "Sentinel"
        assert branding["footer"] == "Confidential"
        assert branding["analyst"] == "Jane"

    def test_branding_persists(self):
        """PUT → GET returns same data."""
        upsert_branding("t1", {
            "company_name": "TestCo",
            "primary_color": "#ff0000",
        })
        result = get_branding("t1")
        assert result["company_name"] == "TestCo"
        assert result["primary_color"] == "#ff0000"


# ===================================================================
# Admin Endpoint RBAC
# ===================================================================

class TestAdminRBAC:
    def _make_app(self):
        from fastapi import FastAPI
        from api.routes.admin import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/admin")
        return app

    def _admin_tenant(self):
        mock = MagicMock()
        mock.tenant_id = "admin-tenant"
        mock.is_admin = True
        mock.roles = ["SYSTEM_ADMIN"]
        return mock

    def _regular_tenant(self, tid="user-tenant"):
        mock = MagicMock()
        mock.tenant_id = tid
        mock.is_admin = False
        mock.roles = []
        return mock

    def test_portfolio_requires_admin(self):
        """Non-admin → 403 on portfolio."""
        from fastapi.testclient import TestClient
        app = self._make_app()

        with patch("api.routes.admin.get_tenant", return_value=self._regular_tenant()):
            client = TestClient(app)
            resp = client.get("/api/v1/admin/portfolio")
            assert resp.status_code == 403

    def test_portfolio_allowed_for_admin(self):
        """Admin → 200 on portfolio."""
        from fastapi.testclient import TestClient
        app = self._make_app()

        with patch("api.routes.admin.get_tenant", return_value=self._admin_tenant()):
            client = TestClient(app)
            resp = client.get("/api/v1/admin/portfolio")
            assert resp.status_code == 200

    def test_tenant_summary_own_tenant_allowed(self):
        """Non-admin can view their own tenant summary."""
        from fastapi.testclient import TestClient
        app = self._make_app()
        _seed_tenant("user-tenant")

        with patch("api.routes.admin.get_tenant", return_value=self._regular_tenant("user-tenant")):
            client = TestClient(app)
            resp = client.get("/api/v1/admin/tenants/user-tenant/summary")
            assert resp.status_code == 200

    def test_tenant_summary_other_tenant_forbidden(self):
        """Non-admin cannot view another tenant's summary."""
        from fastapi.testclient import TestClient
        app = self._make_app()

        with patch("api.routes.admin.get_tenant", return_value=self._regular_tenant("user-tenant")):
            client = TestClient(app)
            resp = client.get("/api/v1/admin/tenants/other-tenant/summary")
            assert resp.status_code == 403

    def test_branding_update_requires_admin(self):
        """Non-admin → 403 on branding update."""
        from fastapi.testclient import TestClient
        app = self._make_app()

        with patch("api.routes.admin.get_tenant", return_value=self._regular_tenant()):
            client = TestClient(app)
            resp = client.put(
                "/api/v1/admin/tenants/t1/branding",
                json={"company_name": "Hack"},
            )
            assert resp.status_code == 403

    def test_branding_update_validates_logo_url(self):
        """javascript: in logo_url → 400."""
        from fastapi.testclient import TestClient
        app = self._make_app()

        with patch("api.routes.admin.get_tenant", return_value=self._admin_tenant()):
            client = TestClient(app)
            resp = client.put(
                "/api/v1/admin/tenants/t1/branding",
                json={"logo_url": "javascript:alert(1)"},
            )
            assert resp.status_code == 400

    def test_branding_update_validates_color(self):
        """Invalid hex color → 400."""
        from fastapi.testclient import TestClient
        app = self._make_app()

        with patch("api.routes.admin.get_tenant", return_value=self._admin_tenant()):
            client = TestClient(app)
            resp = client.put(
                "/api/v1/admin/tenants/t1/branding",
                json={"primary_color": "not-a-color"},
            )
            assert resp.status_code == 400

    def test_analyst_sees_only_own_branding(self):
        """Non-admin can only view their own branding."""
        from fastapi.testclient import TestClient
        app = self._make_app()

        with patch("api.routes.admin.get_tenant", return_value=self._regular_tenant("user-tenant")):
            client = TestClient(app)
            resp = client.get("/api/v1/admin/tenants/other-tenant/branding")
            assert resp.status_code == 403


# ===================================================================
# Scan Task Integration
# ===================================================================

class TestScanTaskIntegration:
    def test_portfolio_summary_called_from_task(self):
        """_update_portfolio_summary fires on scan complete."""
        from tasks.scan_task import _update_portfolio_summary

        with patch("services.portfolio_service.update_tenant_summary") as mock_update, \
             patch("services.report_generator.load_report_from_prism", return_value=None):
            _update_portfolio_summary("scan-1", "t1", "completed")
            mock_update.assert_called_once()
            call_kwargs = mock_update.call_args
            assert call_kwargs[1]["tenant_id"] == "t1" or call_kwargs[0][0] == "t1"

    def test_portfolio_summary_handles_failure(self):
        """_update_portfolio_summary doesn't raise on errors."""
        from tasks.scan_task import _update_portfolio_summary

        with patch("services.portfolio_service.update_tenant_summary", side_effect=Exception("DB error")):
            # Should not raise
            _update_portfolio_summary("scan-1", "t1", "completed")
