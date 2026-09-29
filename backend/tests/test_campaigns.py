"""
Tests for Phase 3 Week 7: Campaign CRUD + fan-out execution.
"""
import json
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


class TestCampaignCRUD:
    """Test campaign create/read/update/delete."""

    def _create(self, svc, tenant="t1", name="Test Campaign", targets=None):
        return svc.create_campaign(tenant, {
            "name": name,
            "target_ids": targets or ["tgt_1", "tgt_2"],
            "probe_sets": ["dan.Dan_11_0", "encoding.InjectBase64"],
            "strategy": "parallel",
        })

    def test_create_campaign_with_targets_and_probes(self, db):
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        result = self._create(svc)

        assert result["campaign_id"].startswith("cmp_")
        assert result["name"] == "Test Campaign"
        assert result["target_ids"] == ["tgt_1", "tgt_2"]
        assert result["probe_sets"] == ["dan.Dan_11_0", "encoding.InjectBase64"]
        assert result["strategy"] == "parallel"

    def test_campaign_scoped_to_tenant(self, db):
        """Tenant A cannot see tenant B campaigns."""
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        a_camp = self._create(svc, tenant="tenant-a", name="A Campaign")
        self._create(svc, tenant="tenant-b", name="B Campaign")

        assert svc.get_campaign("tenant-b", a_camp["campaign_id"]) is None
        a_list = svc.list_campaigns("tenant-a")
        b_list = svc.list_campaigns("tenant-b")
        assert len(a_list) == 1
        assert a_list[0]["name"] == "A Campaign"
        assert len(b_list) == 1
        assert b_list[0]["name"] == "B Campaign"

    def test_update_campaign(self, db):
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = self._create(svc)

        result = svc.update_campaign("t1", created["campaign_id"], {
            "name": "Updated Campaign",
            "strategy": "sequential",
        })
        assert result is not None
        assert result["name"] == "Updated Campaign"
        assert result["strategy"] == "sequential"

    def test_update_campaign_cross_tenant_denied(self, db):
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = self._create(svc, tenant="tenant-a")

        result = svc.update_campaign("tenant-b", created["campaign_id"], {"name": "hacked"})
        assert result is None

    def test_delete_campaign(self, db):
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = self._create(svc)

        assert svc.delete_campaign("t1", created["campaign_id"]) is True
        assert svc.get_campaign("t1", created["campaign_id"]) is None

    def test_delete_campaign_cross_tenant_denied(self, db):
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = self._create(svc, tenant="tenant-a")

        assert svc.delete_campaign("tenant-b", created["campaign_id"]) is False

    def test_list_campaigns_ordered(self, db):
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        self._create(svc, name="First")
        self._create(svc, name="Second")
        results = svc.list_campaigns("t1")
        assert len(results) == 2
        # Most recent first
        assert results[0]["name"] == "Second"


class TestCampaignExecution:
    """Test campaign fan-out execution."""

    def test_campaign_run_fans_out_scans(self, db):
        """3 targets -> 3 scans created."""
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = svc.create_campaign("t1", {
            "name": "Fan-out Test",
            "target_ids": ["tgt_1", "tgt_2", "tgt_3"],
            "probe_sets": ["dan"],
            "strategy": "parallel",
        })

        with patch("tasks.scan_task.execute_scan") as mock_task, \
             patch("services.campaign_executor.route_to_queue", return_value="default"):
            mock_task.apply_async = MagicMock()
            run = svc.trigger_run("t1", created["campaign_id"])

        assert run["status"] == "running"
        assert len(run["scan_ids"]) == 3
        assert mock_task.apply_async.call_count == 3

    def test_campaign_run_parallel_strategy(self, db):
        """All scans start simultaneously (apply_async called for each)."""
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = svc.create_campaign("t1", {
            "name": "Parallel",
            "target_ids": ["tgt_1", "tgt_2"],
            "probe_sets": ["dan"],
            "strategy": "parallel",
        })

        enqueue_calls = []
        with patch("tasks.scan_task.execute_scan") as mock_task, \
             patch("services.campaign_executor.route_to_queue", return_value="default"):
            mock_task.apply_async = MagicMock(side_effect=lambda **kw: enqueue_calls.append(kw))
            svc.trigger_run("t1", created["campaign_id"])

        # Both enqueued (parallel = all at once)
        assert len(enqueue_calls) == 2

    def test_campaign_run_collects_results(self, db):
        """Run summary has per-target scan IDs."""
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = svc.create_campaign("t1", {
            "name": "Results Test",
            "target_ids": ["tgt_a", "tgt_b"],
            "probe_sets": ["dan"],
        })

        with patch("tasks.scan_task.execute_scan") as mock_task, \
             patch("services.campaign_executor.route_to_queue", return_value="default"):
            mock_task.apply_async = MagicMock()
            run = svc.trigger_run("t1", created["campaign_id"])

        assert run["campaign_id"] == created["campaign_id"]
        assert len(run["scan_ids"]) == 2
        for sid in run["scan_ids"]:
            assert sid.startswith("scan_")

    def test_campaign_run_listed(self, db):
        """Runs are listable per campaign."""
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        created = svc.create_campaign("t1", {
            "name": "Runs List",
            "target_ids": ["tgt_1"],
            "probe_sets": ["dan"],
        })

        with patch("tasks.scan_task.execute_scan") as mock_task, \
             patch("services.campaign_executor.route_to_queue", return_value="default"):
            mock_task.apply_async = MagicMock()
            svc.trigger_run("t1", created["campaign_id"])
            svc.trigger_run("t1", created["campaign_id"])

        runs = svc.list_runs("t1", created["campaign_id"])
        assert len(runs) == 2

    def test_campaign_run_tenant_scoped(self, db):
        """Tenant A cannot see Tenant B's runs."""
        from services.campaign_executor import CampaignService
        svc = CampaignService()
        a_camp = svc.create_campaign("tenant-a", {
            "name": "A",
            "target_ids": ["tgt_1"],
            "probe_sets": ["dan"],
        })

        with patch("tasks.scan_task.execute_scan") as mock_task, \
             patch("services.campaign_executor.route_to_queue", return_value="default"):
            mock_task.apply_async = MagicMock()
            run = svc.trigger_run("tenant-a", a_camp["campaign_id"])

        assert svc.get_run("tenant-b", run["run_id"]) is None


class TestCampaignModel:
    """Test Campaign and CampaignRun models."""

    def test_campaign_to_dict_shape(self, db_session):
        from database.models import Campaign
        c = Campaign(
            id="cmp_test",
            tenant_id="t1",
            name="Test",
            target_ids_json='["tgt_1","tgt_2"]',
            probe_sets_json='["dan"]',
            strategy="parallel",
            created_at="2025-01-01",
            updated_at="2025-01-01",
        )
        db_session.add(c)
        db_session.commit()

        d = c.to_dict()
        assert d["campaign_id"] == "cmp_test"
        assert d["target_ids"] == ["tgt_1", "tgt_2"]
        assert d["probe_sets"] == ["dan"]
        assert d["strategy"] == "parallel"

    def test_campaign_run_to_dict_shape(self, db_session):
        from database.models import CampaignRun
        r = CampaignRun(
            id="run_test",
            campaign_id="cmp_1",
            tenant_id="t1",
            status="completed",
            scan_ids_json='["scan_a","scan_b"]',
            results_json='{"summary":"ok"}',
            started_at="2025-01-01",
            completed_at="2025-01-01",
        )
        db_session.add(r)
        db_session.commit()

        d = r.to_dict()
        assert d["run_id"] == "run_test"
        assert d["scan_ids"] == ["scan_a", "scan_b"]
        assert d["results"] == {"summary": "ok"}
