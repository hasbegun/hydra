"""
Portfolio service — cross-tenant risk summary for the admin dashboard.

Responsibilities:
  1. Materialize ``TenantSummary`` rows on every scan completion
  2. Serve the portfolio dashboard (all tenants at a glance)
  3. Serve single-tenant detail views
  4. Manage ``TenantBranding`` CRUD

Design:
  - All mutations go through ``update_tenant_summary`` (called from
    scan_task on completion) to keep a single write path.
  - Portfolio reads are simple SELECTs on the materialized table —
    no fan-out queries across scans (O(tenants), not O(scans)).
  - Branding CRUD is trivially small — no caching needed.
"""
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def update_tenant_summary(
    tenant_id: str,
    scan_id: str,
    risk_score: float,
    critical: int = 0,
    high: int = 0,
    medium: int = 0,
    low: int = 0,
    total_findings: int = 0,
    status: str = "completed",
) -> None:
    """Update (upsert) the materialized TenantSummary row for a tenant.

    Called from the scan task when a scan completes (or fails).
    Uses an atomic upsert pattern — safe for concurrent workers.
    """
    from database.session import get_db, db_available
    from database.models import TenantSummary

    if not db_available():
        logger.debug("DB not available, skipping tenant summary update")
        return

    now = datetime.utcnow().isoformat()

    try:
        with get_db() as db:
            summary = db.query(TenantSummary).filter_by(tenant_id=tenant_id).first()

            if summary is None:
                summary = TenantSummary(
                    tenant_id=tenant_id,
                    risk_score=0.0,
                    previous_risk_score=0.0,
                    risk_delta=0.0,
                    total_scans=0,
                    completed_scans=0,
                    failed_scans=0,
                    critical_count=0,
                    high_count=0,
                    medium_count=0,
                    low_count=0,
                    total_findings=0,
                    updated_at=now,
                )
                db.add(summary)

            summary.total_scans = (summary.total_scans or 0) + 1

            if status == "completed":
                summary.completed_scans = (summary.completed_scans or 0) + 1

                # Shift risk scores for trend tracking
                summary.previous_risk_score = summary.risk_score or 0.0
                summary.risk_score = risk_score
                summary.risk_delta = round(risk_score - (summary.previous_risk_score or 0.0), 2)

                # Update finding counts (replace with latest scan counts)
                summary.critical_count = critical
                summary.high_count = high
                summary.medium_count = medium
                summary.low_count = low
                summary.total_findings = total_findings

                summary.latest_scan_id = scan_id
                summary.latest_scan_at = now

            elif status == "failed":
                summary.failed_scans = (summary.failed_scans or 0) + 1

            summary.updated_at = now
            db.commit()

        logger.info(
            "Updated tenant summary for %s: risk=%.1f, delta=%.1f",
            tenant_id, risk_score, risk_score - (summary.previous_risk_score or 0.0),
        )
    except Exception as e:
        logger.warning("Failed to update tenant summary for %s: %s", tenant_id, e)


def get_portfolio() -> list[dict]:
    """Return all tenant summaries for the admin portfolio dashboard.

    Returns a list of dicts sorted by risk_score descending (highest risk first).
    """
    from database.session import get_db, db_available
    from database.models import TenantSummary

    if not db_available():
        return []

    with get_db() as db:
        summaries = db.query(TenantSummary).order_by(
            TenantSummary.risk_score.desc()
        ).all()
        return [s.to_dict() for s in summaries]


def get_tenant_summary(tenant_id: str) -> Optional[dict]:
    """Return the detailed summary for a single tenant."""
    from database.session import get_db, db_available
    from database.models import TenantSummary

    if not db_available():
        return None

    with get_db() as db:
        summary = db.query(TenantSummary).filter_by(tenant_id=tenant_id).first()
        return summary.to_dict() if summary else None


def update_next_scheduled_scan(tenant_id: str, next_scan_at: Optional[str]) -> None:
    """Update the next scheduled scan datetime for a tenant.

    Called when schedules are created/modified/deleted.
    """
    from database.session import get_db, db_available
    from database.models import TenantSummary

    if not db_available():
        return

    try:
        with get_db() as db:
            summary = db.query(TenantSummary).filter_by(tenant_id=tenant_id).first()
            if summary:
                summary.next_scheduled_scan = next_scan_at
                summary.updated_at = datetime.utcnow().isoformat()
                db.commit()
    except Exception as e:
        logger.warning("Failed to update next scheduled scan: %s", e)


# ---------------------------------------------------------------------------
# Branding CRUD
# ---------------------------------------------------------------------------

def get_branding(tenant_id: str) -> Optional[dict]:
    """Get the branding config for a tenant (returns None if not set)."""
    from database.session import get_db, db_available
    from database.models import TenantBranding

    if not db_available():
        return None

    with get_db() as db:
        row = db.query(TenantBranding).filter_by(tenant_id=tenant_id).first()
        return row.to_dict() if row else None


def get_branding_for_pdf(tenant_id: str) -> Optional[dict]:
    """Get the branding config in the format expected by pdf_renderer."""
    from database.session import get_db, db_available
    from database.models import TenantBranding

    if not db_available():
        return None

    with get_db() as db:
        row = db.query(TenantBranding).filter_by(tenant_id=tenant_id).first()
        return row.to_branding_dict() if row else None


def upsert_branding(tenant_id: str, payload: dict) -> dict:
    """Create or update the branding config for a tenant.

    Accepts any combination of: company_name, logo_url, primary_color,
    footer_text, analyst_name.
    """
    from database.session import get_db, db_available
    from database.models import TenantBranding

    if not db_available():
        raise RuntimeError("Database not available")

    now = datetime.utcnow().isoformat()

    with get_db() as db:
        row = db.query(TenantBranding).filter_by(tenant_id=tenant_id).first()
        if row is None:
            row = TenantBranding(tenant_id=tenant_id, updated_at=now)
            db.add(row)

        # Only update fields that are present in the payload
        for field in ("company_name", "logo_url", "primary_color", "footer_text", "analyst_name"):
            if field in payload:
                setattr(row, field, payload[field])

        row.updated_at = now
        db.commit()

        # Re-read to get the final state
        db.refresh(row)
        return row.to_dict()
