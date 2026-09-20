"""
Garak Service - Thin REST/SSE API wrapping the garak CLI.
Runs inside the garak container on port 9090.
"""
import json
import logging
import os
from pathlib import Path

import requests as http_requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from typing import Dict, List, Optional, Any

from scan_manager import scan_manager, REPORTS_DIR

from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Garak Service",
    description="Thin API wrapper around the garak LLM vulnerability scanner CLI",
    version="1.0.0",
)


# --- Models ---

class ScanRequest(BaseModel):
    scan_id: str
    config: Dict[str, Any]


class ScanResponse(BaseModel):
    scan_id: str
    status: str
    message: str


# --- Health & Info ---

@app.get("/health")
async def health():
    installed = scan_manager.check_garak_installed()
    return {
        "status": "healthy" if installed else "degraded",
        "garak_installed": installed,
    }


@app.get("/version")
async def version():
    ver = scan_manager.get_garak_version()
    return {"version": ver}


# --- Plugin Discovery ---

@app.get("/plugins/{plugin_type}")
async def list_plugins(plugin_type: str):
    if plugin_type not in ("probes", "detectors", "generators", "buffs"):
        raise HTTPException(status_code=400, detail=f"Invalid plugin type: {plugin_type}")
    plugins = scan_manager.list_plugins(plugin_type)
    return {"plugins": plugins, "total_count": len(plugins)}


# --- Scan Management ---

@app.post("/scans", response_model=ScanResponse)
async def start_scan(request: ScanRequest):
    if not scan_manager.check_garak_installed():
        raise HTTPException(status_code=503, detail="garak is not installed")

    try:
        state = await scan_manager.start_scan(request.scan_id, request.config)
        return ScanResponse(
            scan_id=state.scan_id,
            status=state.status,
            message="Scan started",
        )
    except Exception as e:
        logger.error(f"Failed to start scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scans/{scan_id}/progress")
async def scan_progress(scan_id: str):
    """SSE endpoint streaming real-time progress events."""
    state = scan_manager.active_scans.get(scan_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    async def event_generator():
        async for event in scan_manager.stream_progress(scan_id):
            yield {
                "event": event.get("event_type", "message"),
                "data": json.dumps(event),
            }

    return EventSourceResponse(event_generator())


@app.get("/scans/{scan_id}/status")
async def scan_status(scan_id: str):
    status = scan_manager.get_status(scan_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return status


@app.delete("/scans/{scan_id}")
async def cancel_scan(scan_id: str):
    success = await scan_manager.cancel_scan(scan_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Scan {scan_id} not found or not cancellable",
        )
    return {"scan_id": scan_id, "status": "cancelled"}


@app.get("/scans")
async def list_scans():
    return {"scans": scan_manager.list_active_scans()}


# --- Report Files ---

@app.get("/reports")
async def list_reports():
    files = scan_manager.list_report_files()
    return {"files": files}


@app.get("/reports/{filename}")
async def get_report(filename: str):
    """Download a specific report file."""
    # Prevent path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = REPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Report {filename} not found")

    media_type = "text/html" if filename.endswith(".html") else "application/json"
    return FileResponse(str(file_path), media_type=media_type, filename=filename)


# --- Nexus Proxy ---
# Garak's REST generator does naive $INPUT replacement without double-escaping.
# When the Nexus API requires a JSON-stringified object in the Prompt field,
# probe prompts containing quotes break the nested JSON.  This proxy accepts
# a simple {"prompt": "..."} body from garak, wraps it in the nested format
# the Nexus API expects, and forwards the request with all original headers.

_NEXUS_PROXY_FORWARD_HEADERS = {
    "authorization", "content-type", "cookie", "user-agent", "origin",
    "referer", "all-claims", "x-user-email", "x-user-name", "x-user-username",
    "x-user-id", "x-user-given-name", "x-user-family-name", "x-user-department",
}


@app.post("/nexus-proxy/{path:path}")
async def nexus_proxy(path: str, request: Request):
    """Proxy that wraps a simple prompt body into the Nexus nested format."""
    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    prompt_text = body.get("prompt", "")

    # Read config from query params or env
    target_url = request.query_params.get(
        "target_url",
        os.environ.get("NEXUS_TARGET_URL",
                        "https://isioaiffwwebuat07.azurewebsites.net"),
    )
    username = request.query_params.get(
        "username",
        os.environ.get("NEXUS_USERNAME", "Inho.Choi@intusurg.com"),
    )

    # Build the nested body format the Nexus API expects
    nexus_body = {
        "ConversationId": 0,
        "Prompt": json.dumps({
            "user_input_content": [{"type": "text", "text": prompt_text}]
        }),
        "Username": username,
        "ClientTime": "2026-01-01T00:00:00Z",
        "ClientTimeZone": "America/Los_Angeles",
        "ConversationMode": False,
        "ResponseMode": "Thoroughly",
        "IsWidgetOrigin": False,
    }

    # Forward original auth/identity headers
    fwd_headers = {}
    for key, val in request.headers.items():
        if key.lower() in _NEXUS_PROXY_FORWARD_HEADERS:
            fwd_headers[key] = val
    fwd_headers["Content-Type"] = "application/json"

    api_url = f"{target_url}/api/Nexus/{path}"
    try:
        resp = http_requests.post(
            api_url, json=nexus_body, headers=fwd_headers, timeout=120,
        )
        # Return the Nexus response as-is
        try:
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except ValueError:
            return JSONResponse(
                content={"error": resp.text}, status_code=resp.status_code,
            )
    except http_requests.Timeout:
        raise HTTPException(status_code=504, detail="Nexus API timeout")
    except http_requests.ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Nexus API unreachable: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "9090")),
        reload=os.environ.get("LOG_LEVEL", "").upper() == "DEBUG",
    )
