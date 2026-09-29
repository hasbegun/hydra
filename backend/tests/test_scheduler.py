"""
Tests for Phase 3 Week 9: Schedule service — CRUD + trigger.
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def svc():
    from services.scheduler import ScheduleService
    return ScheduleService()


class TestScheduleCRUD:
    """Test schedule create/get/list/delete."""

    def test_create_schedule_stores_cron(self, svc):
        """Schedule created with cron expression."""
        result = svc.create_schedule("t1", {
            "name": "Monday 2AM",
            "cron_expr": "0 2 * * 1",
            "action_type": "scan",
            "action_config": {"target_id": "tgt_1", "probes": ["dan"]},
        })
        assert result["schedule_id"].startswith("sched_")
        assert result["cron_expr"] == "0 2 * * 1"
        assert result["action_type"] == "scan"
        assert result["enabled"] is True

    def test_create_schedule_invalid_cron(self, svc):
        """Invalid cron expression -> ValueError."""
        with pytest.raises(ValueError, match="Invalid cron"):
            svc.create_schedule("t1", {
                "name": "bad",
                "cron_expr": "not-a-cron",
            })

    def test_create_schedule_empty_cron(self, svc):
        """Empty cron -> ValueError."""
        with pytest.raises(ValueError):
            svc.create_schedule("t1", {"name": "empty", "cron_expr": ""})

    def test_schedule_scoped_to_tenant(self, svc):
        """Tenant A cannot see tenant B schedules."""
        a = svc.create_schedule("tenant-a", {
            "name": "A schedule",
            "cron_expr": "0 0 * * *",
        })
        svc.create_schedule("tenant-b", {
            "name": "B schedule",
            "cron_expr": "0 0 * * *",
        })

        assert svc.get_schedule("tenant-b", a["schedule_id"]) is None
        assert len(svc.list_schedules("tenant-a")) == 1
        assert len(svc.list_schedules("tenant-b")) == 1

    def test_delete_schedule_removes_job(self, svc):
        """Delete removes the schedule."""
        created = svc.create_schedule("t1", {
            "name": "delete-me",
            "cron_expr": "0 0 * * *",
        })
        assert svc.delete_schedule("t1", created["schedule_id"]) is True
        assert svc.get_schedule("t1", created["schedule_id"]) is None

    def test_delete_schedule_cross_tenant_denied(self, svc):
        """Tenant B cannot delete Tenant A's schedule."""
        created = svc.create_schedule("tenant-a", {
            "name": "protected",
            "cron_expr": "0 0 * * *",
        })
        assert svc.delete_schedule("tenant-b", created["schedule_id"]) is False


class TestScheduleTrigger:
    """Test manual schedule triggering."""

    def test_manual_trigger(self, svc):
        """POST /schedules/{id}/trigger -> immediate execution."""
        created = svc.create_schedule("t1", {
            "name": "trigger-test",
            "cron_expr": "0 0 * * *",
            "action_type": "scan",
            "action_config": {"target_id": "tgt_1", "probes": ["dan"]},
        })

        with patch("tasks.scan_task.execute_scan") as mock_task, \
             patch("tasks.route_to_queue", return_value="default"):
            mock_task.apply_async = MagicMock()
            result = svc.trigger("t1", created["schedule_id"])

        assert result is not None
        assert result["type"] == "scan"
        assert result["scan_id"].startswith("sched_")

    def test_trigger_updates_last_run(self, svc):
        """Trigger updates last_run_at."""
        created = svc.create_schedule("t1", {
            "name": "run-track",
            "cron_expr": "0 0 * * *",
            "action_type": "scan",
            "action_config": {"target_id": "tgt_1"},
        })

        with patch("tasks.scan_task.execute_scan") as mock_task, \
             patch("tasks.route_to_queue", return_value="default"):
            mock_task.apply_async = MagicMock()
            svc.trigger("t1", created["schedule_id"])

        updated = svc.get_schedule("t1", created["schedule_id"])
        assert updated["last_run_at"] is not None

    def test_trigger_campaign_action(self, svc):
        """Schedule with action_type=campaign triggers campaign run."""
        created = svc.create_schedule("t1", {
            "name": "campaign-sched",
            "cron_expr": "0 0 * * *",
            "action_type": "campaign",
            "action_config": {"campaign_id": "cmp_abc"},
        })

        mock_campaign_svc = MagicMock()
        mock_campaign_svc.trigger_run.return_value = {"run_id": "run_123"}

        with patch("services.campaign_executor.get_campaign_service", return_value=mock_campaign_svc):
            result = svc.trigger("t1", created["schedule_id"])

        assert result["type"] == "campaign_run"
        assert result["run_id"] == "run_123"

    def test_trigger_nonexistent_returns_none(self, svc):
        """Trigger nonexistent schedule returns None."""
        assert svc.trigger("t1", "sched_nonexistent") is None


class TestCronValidation:
    """Test cron expression validation."""

    def test_valid_cron_expressions(self):
        from services.scheduler import _validate_cron
        assert _validate_cron("0 2 * * 1") is True       # Monday 2AM
        assert _validate_cron("*/5 * * * *") is True      # Every 5 min
        assert _validate_cron("0 0 1 * *") is True        # Monthly
        assert _validate_cron("30 4 * * 0,6") is True     # Weekend 4:30

    def test_invalid_cron_expressions(self):
        from services.scheduler import _validate_cron
        assert _validate_cron("") is False
        assert _validate_cron("not-cron") is False
        assert _validate_cron("0 0 *") is False           # Too few fields
        assert _validate_cron("0 0 * * * *") is False     # Too many fields
