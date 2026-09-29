"""
Deployment hook endpoints — receive deploy events and trigger gate scans.

Supported sources: GitHub Actions, ArgoCD, GitLab CI, generic webhooks.
"""
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from middleware.tenant import get_tenant

logger = logging.getLogger(__name__)
router = APIRouter()


def _extract_target_from_event(event: dict) -> Optional[str]:
    """Extract target_id from a deployment event payload.

    Looks in multiple places to support different CI/CD providers.
    """
    # Direct target_id field
    if event.get("target_id"):
        return event["target_id"]
    # GitHub Actions: event.deployment.payload.target_id
    deployment = event.get("deployment", {})
    if isinstance(deployment, dict):
        payload = deployment.get("payload", {})
        if isinstance(payload, dict) and payload.get("target_id"):
            return payload["target_id"]
    # ArgoCD: event.application.metadata.annotations.hydra/target-id
    app_meta = event.get("application", {})
    if isinstance(app_meta, dict):
        annotations = app_meta.get("metadata", {}).get("annotations", {})
        if isinstance(annotations, dict) and annotations.get("hydra/target-id"):
            return annotations["hydra/target-id"]
    return None


def _extract_probes_from_event(event: dict) -> list:
    """Extract probe list from deployment event, with fallback to defaults."""
    if event.get("probes"):
        return event["probes"]
    return ["dan.Dan_11_0", "encoding.InjectBase64", "knownbadsignatures.EICAR"]


@router.post("/deployment")
async def deployment_webhook(request: Request, body: dict):
    """Receive a deployment event and trigger a gate scan.

    The webhook maps the event to a registered target and enqueues a
    scan via the express queue.
    """
    tenant = get_tenant(request)

    target_id = _extract_target_from_event(body)
    if not target_id:
        raise HTTPException(400, "Cannot determine target_id from event payload")

    # Verify target exists and belongs to this tenant
    from services.target_service import get_target_service
    svc = get_target_service()
    target = svc.get_target(tenant.tenant_id, target_id)
    if not target:
        raise HTTPException(404, f"Target {target_id} not found for this tenant")

    probes = _extract_probes_from_event(body)
    scan_id = f"gate_{uuid.uuid4().hex[:12]}"

    config = {
        "target_id": target_id,
        "probes": probes,
        "preset": body.get("preset", "fast"),
        "source": "deployment_webhook",
        "event_id": body.get("event_id") or body.get("delivery_id"),
    }

    try:
        from tasks.scan_task import execute_scan
        from tasks import route_to_queue
        queue = route_to_queue(config)
        execute_scan.apply_async(
            args=[scan_id, config],
            kwargs={"tenant_id": tenant.tenant_id},
            queue=queue,
        )
    except Exception as e:
        logger.error(f"Failed to enqueue gate scan: {e}")
        raise HTTPException(500, f"Failed to enqueue scan: {e}")

    return {
        "scan_id": scan_id,
        "target_id": target_id,
        "status": "enqueued",
        "queue": queue,
    }
