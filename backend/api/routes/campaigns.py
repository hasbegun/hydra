"""
Campaign management endpoints — tenant-scoped CRUD + trigger execution.

A campaign fans out scans across multiple targets with a shared probe set.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from middleware.tenant import get_tenant
from services.campaign_executor import get_campaign_service
from services.compliance_mapper import build_compliance_package
from services.report_generator import load_report_from_prism, generate_vulnerability_report
from services.pdf_renderer import render_evidence_pdf

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


@router.get("/{campaign_id}/evidence")
async def get_campaign_evidence(request: Request, campaign_id: str):
    """Generate a compliance evidence package for a campaign.

    Aggregates findings from the latest campaign run, maps to SOC 2 and
    ISO 27001 controls, and returns the evidence as a PDF (or HTML fallback).
    """
    from fastapi.responses import Response

    tenant = get_tenant(request)
    svc = get_campaign_service()

    campaign = svc.get_campaign(tenant.tenant_id, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Get the latest run
    runs = svc.list_runs(tenant.tenant_id, campaign_id)
    if not runs:
        raise HTTPException(400, "Campaign has no runs yet")

    latest_run = runs[0]  # Most recent
    scan_ids = latest_run.get("scan_ids", [])
    if not scan_ids:
        raise HTTPException(400, "Latest run has no scans")

    # Load the first scan's report as the primary evidence
    report = load_report_from_prism(scan_ids[0], tenant.tenant_id)
    if not report:
        # Try generating from raw data
        from services.garak_wrapper import garak_wrapper
        entries = garak_wrapper._get_report_entries(scan_ids[0])
        if entries:
            report = generate_vulnerability_report(
                scan_ids[0], entries, tenant_id=tenant.tenant_id,
            )
    if not report:
        raise HTTPException(404, "No report data available for campaign scans")

    # Build compliance package
    package = build_compliance_package(report)

    # Render evidence PDF (uses shared Jinja2 env from pdf_renderer)
    try:
        from services.portfolio_service import get_branding_for_pdf
        branding = get_branding_for_pdf(tenant.tenant_id)
    except Exception:
        branding = None
    pdf_bytes = render_evidence_pdf(package, branding)

    is_pdf = pdf_bytes[:5] == b"%PDF-"
    content_type = "application/pdf" if is_pdf else "text/html; charset=utf-8"
    filename = f"hydra-evidence-{campaign_id}.{'pdf' if is_pdf else 'html'}"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
