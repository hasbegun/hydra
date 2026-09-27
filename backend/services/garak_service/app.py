"""
Garak Service - Thin REST/SSE API wrapping the garak CLI.
Runs inside the garak container on port 9090.
"""
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "9090")),
        reload=os.environ.get("LOG_LEVEL", "").upper() == "DEBUG",
    )
