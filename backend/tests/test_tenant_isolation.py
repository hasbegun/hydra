"""
Tests for Phase 1: Multi-tenant isolation.

Covers:
- TenantContext dataclass (construction, is_admin property)
- JWT payload decoding (valid, malformed, missing claims)
- TenantMiddleware in single mode (bypass, optional JWT extraction)
- TenantMiddleware in multi mode (require JWT, reject missing/invalid)
- get_tenant() helper function
- Tenant-scoped DB queries (scoped_query filters correctly)
- DB migration adds tenant_id column to all tables
- Backfill assigns 'default' tenant to existing rows
- Scan creation includes tenant_id
- db_available() centralized helper
"""
import base64
import json
import os
import sys
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.models import Base, Scan, ConfigTemplateRow, CustomProbeRow
from database.session import init_db, get_db, db_available, SCHEMA_VERSION


# ---------------------------------------------------------------------------
# JWT test helpers
# ---------------------------------------------------------------------------

def _make_jwt(payload: dict) -> str:
    """Build a fake JWT (header.payload.signature) with the given payload.

    Not cryptographically valid — signature is a placeholder.  Sufficient
    for testing payload extraction without Anima JWKS verification.
    """
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
# TenantContext
# ---------------------------------------------------------------------------

class TestTenantContext:
    """Tests for the TenantContext dataclass."""

    def test_default_values(self):
        from middleware.tenant import TenantContext
        ctx = TenantContext()
        assert ctx.tenant_id == "default"
        assert ctx.user_id == ""
        assert ctx.roles == []

    def test_custom_values(self):
        from middleware.tenant import TenantContext
        ctx = TenantContext(tenant_id="acme", user_id="u1", roles=["admin"])
        assert ctx.tenant_id == "acme"
        assert ctx.user_id == "u1"
        assert ctx.roles == ["admin"]

    def test_is_admin_true(self):
        from middleware.tenant import TenantContext
        ctx = TenantContext(roles=["viewer", "SYSTEM_ADMIN"])
        assert ctx.is_admin is True

    def test_is_admin_false(self):
        from middleware.tenant import TenantContext
        ctx = TenantContext(roles=["viewer", "editor"])
        assert ctx.is_admin is False

    def test_is_admin_empty_roles(self):
        from middleware.tenant import TenantContext
        ctx = TenantContext()
        assert ctx.is_admin is False

    def test_immutable(self):
        """TenantContext is frozen — attributes cannot be reassigned."""
        from middleware.tenant import TenantContext
        ctx = TenantContext()
        with pytest.raises(AttributeError):
            ctx.tenant_id = "new"


# ---------------------------------------------------------------------------
# JWT decoding
# ---------------------------------------------------------------------------

class TestJWTDecoding:
    """Tests for _decode_jwt_payload."""

    def test_decode_valid_jwt(self):
        from middleware.tenant import _decode_jwt_payload
        payload = {"sub": "user1", "tenant_id": "t1", "roles": ["admin"]}
        token = _make_jwt(payload)
        decoded = _decode_jwt_payload(token)
        assert decoded["sub"] == "user1"
        assert decoded["tenant_id"] == "t1"
        assert decoded["roles"] == ["admin"]

    def test_decode_malformed_jwt_no_dots(self):
        from middleware.tenant import _decode_jwt_payload
        with pytest.raises(ValueError, match="3 dot-separated parts"):
            _decode_jwt_payload("not-a-jwt")

    def test_decode_malformed_jwt_two_dots(self):
        from middleware.tenant import _decode_jwt_payload
        with pytest.raises(ValueError, match="3 dot-separated parts"):
            _decode_jwt_payload("a.b")

    def test_decode_jwt_with_padding(self):
        """JWT base64url often omits padding — should still decode."""
        from middleware.tenant import _decode_jwt_payload
        payload = {"sub": "u", "tenant_id": "x"}
        token = _make_jwt(payload)
        decoded = _decode_jwt_payload(token)
        assert decoded["tenant_id"] == "x"


# ---------------------------------------------------------------------------
# _extract_tenant_context
# ---------------------------------------------------------------------------

class TestExtractTenantContext:
    """Tests for building TenantContext from JWT claims."""

    def test_extracts_tenant_id(self):
        from middleware.tenant import _extract_tenant_context
        token = _make_jwt({"tenant_id": "acme", "sub": "u1"})
        ctx = _extract_tenant_context(token)
        assert ctx.tenant_id == "acme"
        assert ctx.user_id == "u1"

    def test_falls_back_to_org_id(self):
        from middleware.tenant import _extract_tenant_context
        token = _make_jwt({"org_id": "org-99", "sub": "u2"})
        ctx = _extract_tenant_context(token)
        assert ctx.tenant_id == "org-99"

    def test_defaults_tenant_when_missing(self):
        from middleware.tenant import _extract_tenant_context
        token = _make_jwt({"sub": "u3"})
        ctx = _extract_tenant_context(token)
        assert ctx.tenant_id == "default"

    def test_extracts_roles_list(self):
        from middleware.tenant import _extract_tenant_context
        token = _make_jwt({"sub": "u", "roles": ["a", "b"]})
        ctx = _extract_tenant_context(token)
        assert ctx.roles == ["a", "b"]

    def test_extracts_role_single_string(self):
        from middleware.tenant import _extract_tenant_context
        token = _make_jwt({"sub": "u", "role": "editor"})
        ctx = _extract_tenant_context(token)
        assert ctx.roles == ["editor"]

    def test_empty_roles_when_missing(self):
        from middleware.tenant import _extract_tenant_context
        token = _make_jwt({"sub": "u"})
        ctx = _extract_tenant_context(token)
        assert ctx.roles == []


# ---------------------------------------------------------------------------
# TenantMiddleware — integration with FastAPI TestClient
# ---------------------------------------------------------------------------

class TestTenantMiddlewareSingleMode:
    """Tests for TenantMiddleware in single-tenant mode (no auth required)."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from middleware.tenant import TenantMiddleware, get_tenant

        app = FastAPI()
        app.add_middleware(TenantMiddleware, tenant_mode="single")

        @app.get("/test")
        async def test_endpoint(request: Request):
            t = get_tenant(request)
            return {"tenant_id": t.tenant_id, "user_id": t.user_id}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return TestClient(app)

    def test_no_auth_header_returns_default_tenant(self, client):
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "default"

    def test_valid_jwt_extracts_tenant(self, client):
        token = _make_jwt({"tenant_id": "acme", "sub": "u1"})
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "acme"
        assert resp.json()["user_id"] == "u1"

    def test_invalid_jwt_falls_back_to_default(self, client):
        """In single mode, a bad JWT doesn't cause a 401 — just defaults."""
        resp = client.get("/test", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "default"

    def test_public_paths_bypass(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


class TestTenantMiddlewareMultiMode:
    """Tests for TenantMiddleware in multi-tenant mode (JWT required)."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from middleware.tenant import TenantMiddleware, get_tenant

        app = FastAPI()
        app.add_middleware(TenantMiddleware, tenant_mode="multi")

        @app.get("/test")
        async def test_endpoint(request: Request):
            t = get_tenant(request)
            return {"tenant_id": t.tenant_id, "user_id": t.user_id}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return TestClient(app)

    def test_missing_auth_returns_401(self, client):
        resp = client.get("/test")
        assert resp.status_code == 401
        assert "Authorization" in resp.json()["detail"]

    def test_empty_bearer_returns_401(self, client):
        resp = client.get("/test", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401

    def test_non_bearer_returns_401(self, client):
        resp = client.get("/test", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401

    def test_invalid_jwt_returns_401(self, client):
        resp = client.get("/test", headers={"Authorization": "Bearer not.a.valid.jwt.at.all"})
        assert resp.status_code == 401

    def test_valid_jwt_accepted(self, client):
        token = _make_jwt({"tenant_id": "tenant-x", "sub": "user-1"})
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "tenant-x"

    def test_expired_jwt_decoded(self, client):
        """Phase 1 does not verify expiry in middleware — only decodes.
        Expiry validation will come with Anima JWKS integration."""
        token = _make_jwt({"tenant_id": "t", "sub": "u", "exp": 0})
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200  # No expiry check in Phase 1 middleware

    def test_public_paths_bypass_in_multi_mode(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tenant-scoped queries
# ---------------------------------------------------------------------------

class TestTenantScopedQuery:
    """Tests for scoped_query() filtering."""

    def test_returns_only_matching_tenant(self, db_session):
        from database.tenant_scope import scoped_query

        db_session.add(Scan(id="s1", tenant_id="acme", target_type="a", target_name="b"))
        db_session.add(Scan(id="s2", tenant_id="globex", target_type="a", target_name="b"))
        db_session.add(Scan(id="s3", tenant_id="acme", target_type="a", target_name="b"))
        db_session.commit()

        acme_scans = scoped_query(db_session, Scan, "acme").all()
        assert len(acme_scans) == 2
        assert {s.id for s in acme_scans} == {"s1", "s3"}

    def test_excludes_other_tenant(self, db_session):
        from database.tenant_scope import scoped_query

        db_session.add(Scan(id="s1", tenant_id="acme", target_type="a", target_name="b"))
        db_session.add(Scan(id="s2", tenant_id="globex", target_type="a", target_name="b"))
        db_session.commit()

        globex_scans = scoped_query(db_session, Scan, "globex").all()
        assert len(globex_scans) == 1
        assert globex_scans[0].id == "s2"

    def test_empty_result_for_unknown_tenant(self, db_session):
        from database.tenant_scope import scoped_query

        db_session.add(Scan(id="s1", tenant_id="acme", target_type="a", target_name="b"))
        db_session.commit()

        result = scoped_query(db_session, Scan, "nonexistent").all()
        assert result == []

    def test_works_with_config_templates(self, db_session):
        from database.tenant_scope import scoped_query

        db_session.add(ConfigTemplateRow(
            tenant_id="acme", name="t1", config_json="{}", created_at="now", updated_at="now"
        ))
        db_session.add(ConfigTemplateRow(
            tenant_id="globex", name="t2", config_json="{}", created_at="now", updated_at="now"
        ))
        db_session.commit()

        result = scoped_query(db_session, ConfigTemplateRow, "acme").all()
        assert len(result) == 1
        assert result[0].name == "t1"

    def test_works_with_custom_probes(self, db_session):
        from database.tenant_scope import scoped_query

        db_session.add(CustomProbeRow(
            tenant_id="acme", name="p1", file_path="/p1.py", created_at="now", updated_at="now"
        ))
        db_session.add(CustomProbeRow(
            tenant_id="globex", name="p2", file_path="/p2.py", created_at="now", updated_at="now"
        ))
        db_session.commit()

        result = scoped_query(db_session, CustomProbeRow, "globex").all()
        assert len(result) == 1
        assert result[0].name == "p2"

    def test_chainable_with_additional_filters(self, db_session):
        from database.tenant_scope import scoped_query

        db_session.add(Scan(id="s1", tenant_id="acme", target_type="a", target_name="b", status="completed"))
        db_session.add(Scan(id="s2", tenant_id="acme", target_type="a", target_name="b", status="failed"))
        db_session.add(Scan(id="s3", tenant_id="globex", target_type="a", target_name="b", status="completed"))
        db_session.commit()

        result = (
            scoped_query(db_session, Scan, "acme")
            .filter(Scan.status == "completed")
            .all()
        )
        assert len(result) == 1
        assert result[0].id == "s1"

    def test_raises_on_model_without_tenant_id(self, db_session):
        """Models that don't have tenant_id should raise AttributeError."""
        from database.tenant_scope import scoped_query
        from database.models import DBMeta

        with pytest.raises(AttributeError, match="tenant_id"):
            scoped_query(db_session, DBMeta, "acme")


# ---------------------------------------------------------------------------
# DB schema: tenant_id column
# ---------------------------------------------------------------------------

class TestTenantIdColumn:
    """Verify tenant_id exists on all entity tables."""

    def test_scan_has_tenant_id(self, db_session):
        scan = Scan(id="t1", tenant_id="acme", target_type="a", target_name="b")
        db_session.add(scan)
        db_session.commit()
        result = db_session.query(Scan).filter_by(id="t1").first()
        assert result.tenant_id == "acme"

    def test_scan_default_tenant_id(self, db_session):
        scan = Scan(id="t2", target_type="a", target_name="b")
        db_session.add(scan)
        db_session.commit()
        result = db_session.query(Scan).filter_by(id="t2").first()
        assert result.tenant_id == "default"

    def test_config_template_has_tenant_id(self, db_session):
        row = ConfigTemplateRow(
            tenant_id="acme", name="tmpl", config_json="{}", created_at="now", updated_at="now"
        )
        db_session.add(row)
        db_session.commit()
        result = db_session.query(ConfigTemplateRow).filter_by(name="tmpl").first()
        assert result.tenant_id == "acme"

    def test_custom_probe_has_tenant_id(self, db_session):
        row = CustomProbeRow(
            tenant_id="globex", name="probe1", file_path="/p.py", created_at="now", updated_at="now"
        )
        db_session.add(row)
        db_session.commit()
        result = db_session.query(CustomProbeRow).filter_by(name="probe1").first()
        assert result.tenant_id == "globex"

    def test_scan_to_dict_includes_tenant_id(self, db_session):
        scan = Scan(id="t3", tenant_id="acme", target_type="x", target_name="y", status="completed")
        db_session.add(scan)
        db_session.commit()
        d = scan.to_dict()
        assert d["tenant_id"] == "acme"

    def test_schema_version_bumped(self):
        assert SCHEMA_VERSION == "2"


# ---------------------------------------------------------------------------
# Migration: backfill tenant_id
# ---------------------------------------------------------------------------

class TestTenantBackfill:
    """Tests for the tenant_id backfill migration."""

    def test_backfill_sets_default_tenant(self):
        """Simulate an old DB without tenant_id, run migration, verify backfill."""
        from sqlalchemy import create_engine, text, Column, String, Integer
        from sqlalchemy.orm import sessionmaker, DeclarativeBase
        from database.migrations import _add_column_if_missing, _backfill_tenant_id

        # Create a minimal DB with a scans table missing tenant_id
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE scans (id VARCHAR PRIMARY KEY, status VARCHAR DEFAULT 'pending')"
            ))
            conn.execute(text("INSERT INTO scans (id) VALUES ('old-scan-1')"))
            conn.execute(text("INSERT INTO scans (id) VALUES ('old-scan-2')"))

        # Run the migration
        _add_column_if_missing(engine, "scans", "tenant_id", "VARCHAR DEFAULT 'default'")
        _backfill_tenant_id(engine, "scans")

        # Verify
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, tenant_id FROM scans ORDER BY id")).fetchall()
            assert len(rows) == 2
            for row in rows:
                assert row[1] == "default"

    def test_backfill_idempotent(self):
        """Running backfill twice doesn't change already-set values."""
        from sqlalchemy import create_engine, text
        from database.migrations import _add_column_if_missing, _backfill_tenant_id

        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE scans (id VARCHAR PRIMARY KEY, tenant_id VARCHAR DEFAULT 'default')"
            ))
            conn.execute(text("INSERT INTO scans (id, tenant_id) VALUES ('s1', 'acme')"))
            conn.execute(text("INSERT INTO scans (id, tenant_id) VALUES ('s2', NULL)"))

        _backfill_tenant_id(engine, "scans")

        with engine.connect() as conn:
            rows = {r[0]: r[1] for r in conn.execute(text("SELECT id, tenant_id FROM scans")).fetchall()}
            assert rows["s1"] == "acme"  # unchanged
            assert rows["s2"] == "default"  # backfilled


# ---------------------------------------------------------------------------
# db_available() centralized helper
# ---------------------------------------------------------------------------

class TestDbAvailable:
    """Tests for the centralized db_available() function."""

    def test_returns_false_before_init(self):
        import database.session as sess
        sess._SessionFactory = None
        assert db_available() is False

    def test_returns_true_after_init(self, db):
        assert db_available() is True
