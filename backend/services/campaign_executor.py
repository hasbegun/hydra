"""
Campaign management + execution service.

Handles campaign CRUD and fan-out execution (parallel or sequential).
Each campaign run spawns one scan per target via the Celery task queue.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def route_to_queue(config: dict) -> str:
    """Route a scan config to the appropriate Celery queue.

    Delegates to ``tasks.route_to_queue`` at call time to avoid
    circular imports at module load.
    """
    from tasks import route_to_queue as _route
    return _route(config)


class CampaignService:
    """Manages campaign CRUD and fan-out execution."""

    def create_campaign(self, tenant_id: str, payload: dict) -> dict:
        """Create a new campaign."""
        from database.session import get_db
        from database.models import Campaign

        campaign_id = f"cmp_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        with get_db() as db:
            campaign = Campaign(
                id=campaign_id,
                tenant_id=tenant_id,
                name=payload["name"],
                target_ids_json=json.dumps(payload.get("target_ids", [])),
                probe_sets_json=json.dumps(payload.get("probe_sets", [])),
                strategy=payload.get("strategy", "parallel"),
                schedule_cron=payload.get("schedule_cron"),
                comparison_config_json=json.dumps(payload.get("comparison_config"))
                    if payload.get("comparison_config") else None,
                notification_config_json=json.dumps(payload.get("notification_config"))
                    if payload.get("notification_config") else None,
                created_at=now,
                updated_at=now,
            )
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            result = campaign.to_dict()

        logger.info(f"Created campaign {campaign_id} for tenant {tenant_id}")
        return result

    def get_campaign(self, tenant_id: str, campaign_id: str) -> Optional[dict]:
        """Get a campaign by ID (tenant-scoped)."""
        from database.session import get_db
        from database.models import Campaign

        with get_db() as db:
            c = db.query(Campaign).filter_by(id=campaign_id, tenant_id=tenant_id).first()
            return c.to_dict() if c else None

    def list_campaigns(self, tenant_id: str) -> list[dict]:
        """List all campaigns for a tenant."""
        from database.session import get_db
        from database.models import Campaign

        with get_db() as db:
            rows = (
                db.query(Campaign)
                .filter_by(tenant_id=tenant_id)
                .order_by(Campaign.created_at.desc())
                .all()
            )
            return [r.to_dict() for r in rows]

    def update_campaign(self, tenant_id: str, campaign_id: str, payload: dict) -> Optional[dict]:
        """Update campaign configuration."""
        from database.session import get_db
        from database.models import Campaign

        with get_db() as db:
            c = db.query(Campaign).filter_by(id=campaign_id, tenant_id=tenant_id).first()
            if not c:
                return None
            if "name" in payload:
                c.name = payload["name"]
            if "target_ids" in payload:
                c.target_ids_json = json.dumps(payload["target_ids"])
            if "probe_sets" in payload:
                c.probe_sets_json = json.dumps(payload["probe_sets"])
            if "strategy" in payload:
                c.strategy = payload["strategy"]
            if "schedule_cron" in payload:
                c.schedule_cron = payload["schedule_cron"]
            if "comparison_config" in payload:
                c.comparison_config_json = json.dumps(payload["comparison_config"])
            if "notification_config" in payload:
                c.notification_config_json = json.dumps(payload["notification_config"])
            c.updated_at = datetime.utcnow().isoformat()
            db.commit()
            db.refresh(c)
            return c.to_dict()

    def delete_campaign(self, tenant_id: str, campaign_id: str) -> bool:
        """Delete a campaign."""
        from database.session import get_db
        from database.models import Campaign

        with get_db() as db:
            c = db.query(Campaign).filter_by(id=campaign_id, tenant_id=tenant_id).first()
            if not c:
                return False
            db.delete(c)
            db.commit()
        return True

    def trigger_run(self, tenant_id: str, campaign_id: str) -> dict:
        """Trigger a campaign run — fans out scans per target.

        Each target gets a separate scan task enqueued via Celery.
        The run tracks all spawned scan IDs.
        """
        from database.session import get_db
        from database.models import Campaign, CampaignRun

        with get_db() as db:
            campaign = db.query(Campaign).filter_by(
                id=campaign_id, tenant_id=tenant_id
            ).first()
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")
            campaign_dict = campaign.to_dict()

        target_ids = campaign_dict.get("target_ids", [])
        probe_sets = campaign_dict.get("probe_sets", [])
        strategy = campaign_dict.get("strategy", "parallel")

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        # Spawn scans
        scan_ids = []
        for target_id in target_ids:
            scan_id = f"scan_{uuid.uuid4().hex[:12]}"
            scan_ids.append(scan_id)

            config = {
                "target_id": target_id,
                "probes": probe_sets,
                "campaign_id": campaign_id,
                "run_id": run_id,
            }

            try:
                from tasks.scan_task import execute_scan
                queue = route_to_queue(config)
                execute_scan.apply_async(
                    args=[scan_id, config],
                    kwargs={"tenant_id": tenant_id},
                    queue=queue,
                )
            except Exception as e:
                logger.error(f"Failed to enqueue scan for target {target_id}: {e}")

        # Record the run
        with get_db() as db:
            run = CampaignRun(
                id=run_id,
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                status="running",
                scan_ids_json=json.dumps(scan_ids),
                started_at=now,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            result = run.to_dict()

        logger.info(
            f"Triggered campaign run {run_id}: "
            f"{len(scan_ids)} scans ({strategy})"
        )
        return result

    def list_runs(self, tenant_id: str, campaign_id: str) -> list[dict]:
        """List all runs for a campaign."""
        from database.session import get_db
        from database.models import CampaignRun

        with get_db() as db:
            rows = (
                db.query(CampaignRun)
                .filter_by(campaign_id=campaign_id, tenant_id=tenant_id)
                .order_by(CampaignRun.started_at.desc())
                .all()
            )
            return [r.to_dict() for r in rows]

    def get_run(self, tenant_id: str, run_id: str) -> Optional[dict]:
        """Get a specific campaign run."""
        from database.session import get_db
        from database.models import CampaignRun

        with get_db() as db:
            r = db.query(CampaignRun).filter_by(id=run_id, tenant_id=tenant_id).first()
            return r.to_dict() if r else None


# Module-level singleton
_campaign_service: Optional[CampaignService] = None


def get_campaign_service() -> CampaignService:
    """Get or create the CampaignService singleton."""
    global _campaign_service
    if _campaign_service is None:
        _campaign_service = CampaignService()
    return _campaign_service
