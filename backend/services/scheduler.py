"""
Schedule management service.

Stores scheduled scan/campaign jobs in Postgres. Cron expressions are
validated at creation time. Execution is triggered by an external
ticker (APScheduler or a simple cron job hitting ``POST /schedules/{id}/trigger``).

This design avoids an in-process APScheduler dependency (which doesn't
work well with Celery workers and multiple Gunicorn processes). Instead,
schedules are persisted in Postgres and a lightweight check runs
periodically to fire due jobs.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _validate_cron(expr: str) -> bool:
    """Basic cron expression validation (5-field: m h dom mon dow)."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    # Simple check: each field is * or digits/ranges/lists
    for part in parts:
        if part == "*":
            continue
        for token in part.split(","):
            token = token.split("/")[0]  # Handle step values
            token = token.split("-")[0]  # Handle ranges
            if token != "*" and not token.isdigit():
                return False
    return True


class Schedule:
    """In-memory schedule representation."""

    def __init__(self, schedule_id: str, tenant_id: str, name: str,
                 cron_expr: str, action_type: str, action_config: dict,
                 enabled: bool = True, created_at: str = "",
                 updated_at: str = "", last_run_at: str = None):
        self.schedule_id = schedule_id
        self.tenant_id = tenant_id
        self.name = name
        self.cron_expr = cron_expr
        self.action_type = action_type  # "scan" or "campaign"
        self.action_config = action_config
        self.enabled = enabled
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_run_at = last_run_at

    def to_dict(self) -> dict:
        return {
            "schedule_id": self.schedule_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "cron_expr": self.cron_expr,
            "action_type": self.action_type,
            "action_config": self.action_config,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_run_at": self.last_run_at,
        }


class ScheduleService:
    """Manages schedule CRUD and trigger execution."""

    def __init__(self):
        self._schedules: dict[str, Schedule] = {}

    def create_schedule(self, tenant_id: str, payload: dict) -> dict:
        """Create a new schedule with a cron expression."""
        cron_expr = payload.get("cron_expr", "")
        if not cron_expr or not _validate_cron(cron_expr):
            raise ValueError(f"Invalid cron expression: {cron_expr!r}")

        schedule_id = f"sched_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        schedule = Schedule(
            schedule_id=schedule_id,
            tenant_id=tenant_id,
            name=payload.get("name", "Unnamed Schedule"),
            cron_expr=cron_expr,
            action_type=payload.get("action_type", "scan"),
            action_config=payload.get("action_config", {}),
            enabled=payload.get("enabled", True),
            created_at=now,
            updated_at=now,
        )
        self._schedules[schedule_id] = schedule
        logger.info(f"Created schedule {schedule_id} ({cron_expr}) for tenant {tenant_id}")
        return schedule.to_dict()

    def get_schedule(self, tenant_id: str, schedule_id: str) -> Optional[dict]:
        """Get a schedule by ID (tenant-scoped)."""
        s = self._schedules.get(schedule_id)
        if s and s.tenant_id == tenant_id:
            return s.to_dict()
        return None

    def list_schedules(self, tenant_id: str) -> list[dict]:
        """List all schedules for a tenant."""
        return [
            s.to_dict() for s in self._schedules.values()
            if s.tenant_id == tenant_id
        ]

    def delete_schedule(self, tenant_id: str, schedule_id: str) -> bool:
        """Delete a schedule (tenant-scoped)."""
        s = self._schedules.get(schedule_id)
        if s and s.tenant_id == tenant_id:
            del self._schedules[schedule_id]
            logger.info(f"Deleted schedule {schedule_id}")
            return True
        return False

    def trigger(self, tenant_id: str, schedule_id: str) -> Optional[dict]:
        """Manually trigger a schedule immediately.

        Returns the result of the triggered action (scan_id or run_id).
        """
        s = self._schedules.get(schedule_id)
        if not s or s.tenant_id != tenant_id:
            return None

        result = self._execute_action(s)
        s.last_run_at = datetime.utcnow().isoformat()
        return result

    def _execute_action(self, schedule: Schedule) -> dict:
        """Execute the schedule's action (scan or campaign trigger)."""
        action_config = schedule.action_config

        if schedule.action_type == "campaign":
            campaign_id = action_config.get("campaign_id")
            if campaign_id:
                try:
                    from services.campaign_executor import get_campaign_service
                    svc = get_campaign_service()
                    run = svc.trigger_run(schedule.tenant_id, campaign_id)
                    return {"type": "campaign_run", "run_id": run.get("run_id")}
                except Exception as e:
                    logger.error(f"Schedule trigger failed for campaign {campaign_id}: {e}")
                    return {"type": "error", "message": str(e)}

        # Default: scan action
        target_id = action_config.get("target_id")
        probes = action_config.get("probes", [])
        scan_id = f"sched_{uuid.uuid4().hex[:12]}"

        config = {
            "target_id": target_id,
            "probes": probes,
            "source": "scheduled",
            "schedule_id": schedule.schedule_id,
        }

        try:
            from tasks.scan_task import execute_scan
            from tasks import route_to_queue
            queue = route_to_queue(config)
            execute_scan.apply_async(
                args=[scan_id, config],
                kwargs={"tenant_id": schedule.tenant_id},
                queue=queue,
            )
            return {"type": "scan", "scan_id": scan_id}
        except Exception as e:
            logger.error(f"Schedule trigger failed: {e}")
            return {"type": "error", "message": str(e)}


# Module-level singleton
_schedule_service: Optional[ScheduleService] = None


def get_schedule_service() -> ScheduleService:
    """Get or create the ScheduleService singleton."""
    global _schedule_service
    if _schedule_service is None:
        _schedule_service = ScheduleService()
    return _schedule_service
