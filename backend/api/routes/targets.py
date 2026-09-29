"""
Target management endpoints — tenant-scoped CRUD + credential rotation
+ connectivity testing.

Credentials are never returned in API responses. The ``has_credentials``
flag indicates whether credentials are stored in Prism.
"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from middleware.tenant import get_tenant
from services.target_service import get_target_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("")
async def create_target(request: Request, body: dict):
    """Register a new scan target.

    Non-sensitive metadata goes to Postgres. Credential fields
    (``headers``, ``cookies``, ``query_params``) are extracted
    and stored in Prism.
    """
    tenant = get_tenant(request)
    svc = get_target_service()

    if not body.get("name") or not body.get("endpoint"):
        raise HTTPException(400, "name and endpoint are required")

    result = svc.create_target(tenant.tenant_id, body)
    return result


@router.get("")
async def list_targets(request: Request):
    """List all targets for the current tenant."""
    tenant = get_tenant(request)
    svc = get_target_service()
    return svc.list_targets(tenant.tenant_id)


@router.get("/{target_id}")
async def get_target(request: Request, target_id: str):
    """Get a single target by ID (tenant-scoped, no credential values)."""
    tenant = get_tenant(request)
    svc = get_target_service()
    result = svc.get_target(tenant.tenant_id, target_id)
    if not result:
        raise HTTPException(404, "Target not found")
    return result


@router.put("/{target_id}")
async def update_target(request: Request, target_id: str, body: dict):
    """Update target metadata (not credentials — use PUT /{id}/credentials)."""
    tenant = get_tenant(request)
    svc = get_target_service()
    result = svc.update_target(tenant.tenant_id, target_id, body)
    if not result:
        raise HTTPException(404, "Target not found")
    return result


@router.delete("/{target_id}", status_code=204)
async def delete_target(request: Request, target_id: str):
    """Delete a target and its credentials from Prism."""
    tenant = get_tenant(request)
    svc = get_target_service()
    if not svc.delete_target(tenant.tenant_id, target_id):
        raise HTTPException(404, "Target not found")


@router.put("/{target_id}/credentials", status_code=204)
async def rotate_credentials(request: Request, target_id: str, body: dict):
    """Atomic credential rotation — old deleted, new stored in Prism.

    Response is always 204 No Content (never echoes credentials).
    """
    tenant = get_tenant(request)
    svc = get_target_service()
    if not svc.rotate_credentials(tenant.tenant_id, target_id, body):
        raise HTTPException(404, "Target not found")


@router.post("/{target_id}/test")
async def test_target_connectivity(request: Request, target_id: str):
    """Send a benign prompt to verify target is reachable and credentials work.

    Returns reachability and auth status without running a full scan.
    """
    tenant = get_tenant(request)
    svc = get_target_service()

    target = svc.get_target(tenant.tenant_id, target_id)
    if not target:
        raise HTTPException(404, "Target not found")

    result = {
        "target_id": target_id,
        "reachable": False,
        "auth_valid": False,
        "response_sample": None,
        "error": None,
    }

    # Fetch credentials for the test
    creds = svc.fetch_credentials(tenant.tenant_id, target_id) or {}
    headers = creds.get("headers", {})
    cookies = creds.get("cookies", {})

    # Build request
    endpoint = target["endpoint"]
    body_template = target.get("body_template") or ""
    test_prompt = "Hello, this is a connectivity test."

    try:
        body_str = body_template.replace("$INPUT", test_prompt) if body_template else ""
        request_body = None
        if body_str:
            import json
            try:
                request_body = json.loads(body_str)
            except (ValueError, TypeError):
                request_body = {"prompt": test_prompt}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                endpoint,
                json=request_body,
                headers=headers,
                cookies=cookies,
            )

        result["reachable"] = True

        if resp.status_code in (401, 403):
            result["auth_valid"] = False
            result["error"] = f"Authentication failed: HTTP {resp.status_code}"
        elif resp.status_code >= 400:
            result["auth_valid"] = True  # auth passed but request failed
            result["error"] = f"Request error: HTTP {resp.status_code}"
        else:
            result["auth_valid"] = True
            body_text = resp.text[:500]  # Truncate long responses
            result["response_sample"] = body_text

    except httpx.ConnectError as e:
        result["error"] = f"Connection failed: {e}"
    except httpx.TimeoutException:
        result["error"] = "Connection timed out"
    except Exception as e:
        result["error"] = f"Test failed: {e}"

    return result
