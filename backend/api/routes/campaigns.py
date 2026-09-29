"""
Campaign management endpoints — tenant-scoped CRUD + trigger execution.

A campaign fans out scans across multiple targets with a shared probe set.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from middleware.tenant import get_tenant
from services.campaign_executor import get_campaign_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("")
async def create_campaign(request: Request, body: dict):
    """Create a new campaign."""
    tenant = get_tenant(request)
    svc = get_campaign_service()

    if not body.get("name"):
        raise HTTPException(400, "name is required")
    if not body.get("target_ids"):
        raise HTTPException(400, "target_ids is required")

    result = svc.create_campaign(tenant.tenant_id, body)
    return result


@router.get("")
async def list_campaigns(request: Request):
    """List all campaigns for the current tenant."""
    tenant = get_tenant(request)
    svc = get_campaign_service()
    return svc.list_campaigns(tenant.tenant_id)


@router.get("/{campaign_id}")
async def get_campaign(request: Request, campaign_id: str):
    """Get a single campaign by ID."""
    tenant = get_tenant(request)
    svc = get_campaign_service()
    result = svc.get_campaign(tenant.tenant_id, campaign_id)
    if not result:
        raise HTTPException(404, "Campaign not found")
    return result


@router.put("/{campaign_id}")
async def update_campaign(request: Request, campaign_id: str, body: dict):
    """Update campaign configuration."""
    tenant = get_tenant(request)
    svc = get_campaign_service()
    result = svc.update_campaign(tenant.tenant_id, campaign_id, body)
    if not result:
        raise HTTPException(404, "Campaign not found")
    return result


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(request: Request, campaign_id: str):
    """Delete a campaign."""
    tenant = get_tenant(request)
    svc = get_campaign_service()
    if not svc.delete_campaign(tenant.tenant_id, campaign_id):
        raise HTTPException(404, "Campaign not found")


@router.post("/{campaign_id}/run")
async def trigger_campaign_run(request: Request, campaign_id: str):
    """Trigger a campaign run — fans out scans to all campaign targets."""
    tenant = get_tenant(request)
    svc = get_campaign_service()

    campaign = svc.get_campaign(tenant.tenant_id, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    run = svc.trigger_run(tenant.tenant_id, campaign_id)
    return run


@router.get("/{campaign_id}/runs")
async def list_campaign_runs(request: Request, campaign_id: str):
    """List all runs for a campaign."""
    tenant = get_tenant(request)
    svc = get_campaign_service()
    return svc.list_runs(tenant.tenant_id, campaign_id)


@router.get("/{campaign_id}/runs/{run_id}")
async def get_campaign_run(request: Request, campaign_id: str, run_id: str):
    """Get a specific campaign run."""
    tenant = get_tenant(request)
    svc = get_campaign_service()
    result = svc.get_run(tenant.tenant_id, run_id)
    if not result:
        raise HTTPException(404, "Campaign run not found")
    return result
