"""
Webhook notification management endpoints — register/list/delete webhook URLs.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from middleware.tenant import get_tenant
from services.notifier import get_notification_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("")
async def register_webhook(request: Request, body: dict):
    """Register a new webhook endpoint."""
    tenant = get_tenant(request)
    svc = get_notification_service()
    try:
        return svc.register_webhook(tenant.tenant_id, body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def list_webhooks(request: Request):
    """List all webhooks for the current tenant."""
    tenant = get_tenant(request)
    svc = get_notification_service()
    return svc.list_webhooks(tenant.tenant_id)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(request: Request, webhook_id: str):
    """Delete a webhook."""
    tenant = get_tenant(request)
    svc = get_notification_service()
    if not svc.delete_webhook(tenant.tenant_id, webhook_id):
        raise HTTPException(404, "Webhook not found")
