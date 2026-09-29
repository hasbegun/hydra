"""
Schedule management endpoints — tenant-scoped CRUD + manual trigger.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from middleware.tenant import get_tenant
from services.scheduler import get_schedule_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("")
async def create_schedule(request: Request, body: dict):
    """Create a new scheduled scan or campaign."""
    tenant = get_tenant(request)
    svc = get_schedule_service()
    try:
        return svc.create_schedule(tenant.tenant_id, body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def list_schedules(request: Request):
    """List all schedules for the current tenant."""
    tenant = get_tenant(request)
    svc = get_schedule_service()
    return svc.list_schedules(tenant.tenant_id)


@router.get("/{schedule_id}")
async def get_schedule(request: Request, schedule_id: str):
    """Get a schedule by ID."""
    tenant = get_tenant(request)
    svc = get_schedule_service()
    result = svc.get_schedule(tenant.tenant_id, schedule_id)
    if not result:
        raise HTTPException(404, "Schedule not found")
    return result


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(request: Request, schedule_id: str):
    """Delete a schedule."""
    tenant = get_tenant(request)
    svc = get_schedule_service()
    if not svc.delete_schedule(tenant.tenant_id, schedule_id):
        raise HTTPException(404, "Schedule not found")


@router.post("/{schedule_id}/trigger")
async def trigger_schedule(request: Request, schedule_id: str):
    """Manually trigger a schedule immediately."""
    tenant = get_tenant(request)
    svc = get_schedule_service()
    result = svc.trigger(tenant.tenant_id, schedule_id)
    if result is None:
        raise HTTPException(404, "Schedule not found")
    return result
