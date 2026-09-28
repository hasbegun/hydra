"""
Shared scan database operations.

Provides a single ``upsert_scan`` function used by both the
``GarakWrapper`` (FastAPI process) and the ``execute_scan`` Celery task.
This avoids duplicating the upsert logic across two code paths.
"""
import json
import logging
from typing import Optional

from database.session import db_available, get_db
from database.models import Scan

logger = logging.getLogger(__name__)


def upsert_scan(
    scan_id: str,
    *,
    tenant_id: str = "default",
    status: str = "pending",
    target_type: str = "unknown",
    target_name: str = "unknown",
    passed: int = 0,
    failed: int = 0,
    total_probes: int = 0,
    error_message: Optional[str] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    report_path: Optional[str] = None,
    html_report_path: Optional[str] = None,
    report_key: Optional[str] = None,
    html_report_key: Optional[str] = None,
    config_json: Optional[str] = None,
    created_at: Optional[str] = None,
) -> None:
    """Insert or update a scan row in the database.

    If a row with ``scan_id`` exists, update mutable fields.
    Otherwise insert a new row with the provided values.

    Args:
        scan_id: Primary key.
        tenant_id: Owning tenant (default ``"default"``).
        status: Scan status string (e.g. ``"pending"``, ``"completed"``).
        target_type: Target type (e.g. ``"ollama"``, ``"rest"``).
        target_name: Target display name.
        passed / failed: Probe pass/fail counts.
        total_probes: Total number of probes in the scan.
        error_message: Human-readable error (set on failure).
        started_at / completed_at: ISO 8601 timestamps.
        report_path / html_report_path: Local filesystem paths.
        report_key / html_report_key: Object store keys.
        config_json: Serialized scan config (set once, never overwritten).
        created_at: Creation timestamp (defaults to ``started_at``).
    """
    if not db_available():
        return

    try:
        total = passed + failed
        pass_rate = (passed / total * 100.0) if total > 0 else None

        with get_db() as db:
            existing = db.query(Scan).filter_by(id=scan_id).first()
            if existing:
                existing.status = status
                existing.started_at = started_at or existing.started_at
                existing.completed_at = completed_at or existing.completed_at
                existing.passed = passed
                existing.failed = failed
                existing.pass_rate = pass_rate
                existing.total_probes = total_probes or existing.total_probes or 0
                existing.error_message = error_message or existing.error_message
                existing.report_path = report_path or existing.report_path
                existing.html_report_path = html_report_path or existing.html_report_path
                existing.report_key = report_key or existing.report_key
                existing.html_report_key = html_report_key or existing.html_report_key
                if config_json and not existing.config_json:
                    existing.config_json = config_json
            else:
                scan_row = Scan(
                    id=scan_id,
                    tenant_id=tenant_id,
                    target_type=target_type,
                    target_name=target_name,
                    status=status,
                    started_at=started_at,
                    completed_at=completed_at,
                    total_probes=total_probes,
                    passed=passed,
                    failed=failed,
                    pass_rate=pass_rate,
                    error_message=error_message,
                    report_path=report_path,
                    html_report_path=html_report_path,
                    report_key=report_key,
                    html_report_key=html_report_key,
                    config_json=config_json,
                    created_at=created_at or started_at,
                )
                db.add(scan_row)
            db.commit()
    except Exception as e:
        logger.warning(f"Failed to upsert scan {scan_id} to DB: {e}")
