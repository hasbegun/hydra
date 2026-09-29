"""
Tests for Phase 3 Week 7: Probe library scope (global/tenant).

Covers:
- Global probes visible to all tenants
- Tenant probes visible only to owner
- scope column on CustomProbeRow
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def db():
    from database.session import init_db
    engine = init_db(":memory:")
    yield engine
    import database.session as sess
    sess._engine = None
    sess._SessionFactory = None


@pytest.fixture
def db_session(db):
    from database.session import get_db
    with get_db() as session:
        yield session


class TestProbeScope:
    """Test probe scope column and visibility logic."""

    def _create_probe(self, db_session, name, tenant_id="t1", scope="tenant"):
        from database.models import CustomProbeRow
        probe = CustomProbeRow(
            tenant_id=tenant_id,
            name=name,
            description=f"Test probe {name}",
            file_path=f"/probes/{name}.py",
            scope=scope,
            created_at="2025-01-01",
            updated_at="2025-01-01",
        )
        db_session.add(probe)
        db_session.commit()
        return probe

    def test_global_probe_visible_to_all_tenants(self, db_session):
        """scope=global probes listed for any tenant."""
        from database.models import CustomProbeRow

        self._create_probe(db_session, "global-probe", tenant_id="admin", scope="global")
        self._create_probe(db_session, "tenant-a-probe", tenant_id="tenant-a", scope="tenant")

        # Query: tenant-b should see global probes but not tenant-a's
        visible = (
            db_session.query(CustomProbeRow)
            .filter(
                (CustomProbeRow.scope == "global") |
                (CustomProbeRow.tenant_id == "tenant-b")
            )
            .all()
        )
        names = [p.name for p in visible]
        assert "global-probe" in names
        assert "tenant-a-probe" not in names

    def test_tenant_probe_visible_only_to_owner(self, db_session):
        """scope=tenant probes listed only for that tenant."""
        from database.models import CustomProbeRow

        self._create_probe(db_session, "a-private", tenant_id="tenant-a", scope="tenant")
        self._create_probe(db_session, "b-private", tenant_id="tenant-b", scope="tenant")

        # Tenant A should see only their own tenant probe
        a_probes = (
            db_session.query(CustomProbeRow)
            .filter(
                (CustomProbeRow.scope == "global") |
                (CustomProbeRow.tenant_id == "tenant-a")
            )
            .all()
        )
        names = [p.name for p in a_probes]
        assert "a-private" in names
        assert "b-private" not in names

    def test_tenant_sees_both_global_and_own(self, db_session):
        """Tenant sees global + own probes."""
        from database.models import CustomProbeRow

        self._create_probe(db_session, "shared", tenant_id="admin", scope="global")
        self._create_probe(db_session, "my-probe", tenant_id="t1", scope="tenant")
        self._create_probe(db_session, "other-probe", tenant_id="t2", scope="tenant")

        visible = (
            db_session.query(CustomProbeRow)
            .filter(
                (CustomProbeRow.scope == "global") |
                (CustomProbeRow.tenant_id == "t1")
            )
            .all()
        )
        names = [p.name for p in visible]
        assert "shared" in names
        assert "my-probe" in names
        assert "other-probe" not in names

    def test_scope_defaults_to_tenant(self, db_session):
        """New probes default to scope=tenant."""
        from database.models import CustomProbeRow
        probe = CustomProbeRow(
            tenant_id="t1",
            name="default-scope",
            file_path="/probes/default.py",
            created_at="2025-01-01",
            updated_at="2025-01-01",
        )
        db_session.add(probe)
        db_session.commit()

        assert probe.scope == "tenant"
        assert probe.to_dict()["scope"] == "tenant"

    def test_probe_to_dict_includes_scope(self, db_session):
        """to_dict includes scope field."""
        from database.models import CustomProbeRow
        probe = self._create_probe(db_session, "scoped", scope="global")
        d = probe.to_dict()
        assert d["scope"] == "global"

    def test_campaign_uses_global_and_tenant_probes(self, db_session):
        """Campaign probe sets can reference both global and tenant probes."""
        from database.models import CustomProbeRow

        self._create_probe(db_session, "global-dan", tenant_id="admin", scope="global")
        self._create_probe(db_session, "custom-injection", tenant_id="t1", scope="tenant")

        # Simulate campaign probe resolution
        probe_refs = ["global-dan", "custom-injection"]
        visible = (
            db_session.query(CustomProbeRow)
            .filter(
                CustomProbeRow.name.in_(probe_refs),
                (CustomProbeRow.scope == "global") | (CustomProbeRow.tenant_id == "t1")
            )
            .all()
        )
        assert len(visible) == 2

    def test_global_probe_not_editable_by_tenant(self, db_session):
        """Tenant users cannot modify global probes (query filter enforced)."""
        from database.models import CustomProbeRow
        self._create_probe(db_session, "admin-global", tenant_id="admin", scope="global")

        # Tenant trying to find and update — should not find it via tenant filter
        probe = (
            db_session.query(CustomProbeRow)
            .filter_by(name="admin-global", tenant_id="t1")
            .first()
        )
        assert probe is None  # Cannot find it — can't modify
