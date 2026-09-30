"""
Admin endpoints — portfolio dashboard, tenant summary, branding management.

All endpoints require SYSTEM_ADMIN role except where noted.
Non-admin users get a 403 Forbidden response.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from middleware.tenant import get_tenant
from services.portfolio_service import (
    get_portfolio,
    get_tenant_summary,
    get_branding,
    upsert_branding,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_admin(request: Request):
    """Enforce SYSTEM_ADMIN role. Raises 403 if not admin."""
    tenant = get_tenant(request)
    if not tenant.is_admin:
        raise HTTPException(403, "Admin access required")
    return tenant


# ---------------------------------------------------------------------------
# Portfolio Dashboard
# ---------------------------------------------------------------------------

@router.get("/portfolio")
async def admin_portfolio(request: Request):
    """Cross-tenant portfolio: all tenants' risk scores, scan counts, trends.

    Requires SYSTEM_ADMIN role.
    """
    _require_admin(request)
    summaries = get_portfolio()
    return {
        "tenants": summaries,
        "total_tenants": len(summaries),
    }


# ---------------------------------------------------------------------------
# Single-Tenant Summary
# ---------------------------------------------------------------------------

@router.get("/tenants/{tenant_id}/summary")
async def admin_tenant_summary(request: Request, tenant_id: str):
    """Detailed summary for a single tenant.

    SYSTEM_ADMIN can view any tenant. Non-admin users can only view
    their own tenant.
    """
    caller = get_tenant(request)

    if not caller.is_admin and caller.tenant_id != tenant_id:
        raise HTTPException(403, "You can only view your own tenant summary")

    summary = get_tenant_summary(tenant_id)
    if not summary:
        raise HTTPException(404, f"No summary found for tenant {tenant_id}")

    # Enrich with branding info
    branding = get_branding(tenant_id)
    summary["branding"] = branding

    return summary


# ---------------------------------------------------------------------------
# Tenant Branding
# ---------------------------------------------------------------------------

@router.get("/tenants/{tenant_id}/branding")
async def get_tenant_branding(request: Request, tenant_id: str):
    """Get branding config for a tenant.

    SYSTEM_ADMIN can read any tenant. Non-admin can read their own.
    """
    caller = get_tenant(request)
    if not caller.is_admin and caller.tenant_id != tenant_id:
        raise HTTPException(403, "You can only view your own branding")

    branding = get_branding(tenant_id)
    if not branding:
        return {
            "tenant_id": tenant_id,
            "company_name": "",
            "logo_url": "",
            "primary_color": "#16213e",
            "footer_text": "",
            "analyst_name": "",
            "updated_at": None,
        }
    return branding


@router.put("/tenants/{tenant_id}/branding")
async def update_tenant_branding(request: Request, tenant_id: str, body: dict):
    """Create or update branding config for a tenant.

    Requires SYSTEM_ADMIN role.

    Accepts any combination of:
    - company_name: str
    - logo_url: str (must be HTTPS or empty)
    - primary_color: str (CSS hex color)
    - footer_text: str
    - analyst_name: str
    """
    _require_admin(request)

    # Validate logo_url (basic security check — no javascript: or data: URIs)
    logo_url = body.get("logo_url", "")
    if logo_url:
        if not logo_url.startswith(("https://", "http://", "/")):
            raise HTTPException(400, "logo_url must be an HTTP(S) URL or relative path")
        if "javascript:" in logo_url.lower() or "data:" in logo_url.lower():
            raise HTTPException(400, "Invalid logo_url: disallowed scheme")

    # Validate primary_color (basic hex check)
    color = body.get("primary_color", "")
    if color and not (color.startswith("#") and len(color) in (4, 7)):
        raise HTTPException(400, "primary_color must be a CSS hex color (e.g. #16213e)")

    result = upsert_branding(tenant_id, body)
    return result
