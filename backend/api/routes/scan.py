"""
Scan management endpoints.

All scan data is tenant-scoped — the ``TenantContext`` is extracted from the
request by the ``TenantMiddleware`` and passed to the ``GarakWrapper`` so
queries only return data belonging to the requesting tenant.
"""
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from models.schemas import (
    ScanConfigRequest,
    ScanResponse,
    ScanStatusResponse,
    ScanStatus,
    ScanResult,
    ScanHistoryResponse,
    ScanHistoryItem,
    PaginationMeta,
    ScanSortField,
    SortOrder,
    ProbeDetailsResponse,
    ProbeAttemptsResponse,
    ScanStatisticsResponse,
)
from services.garak_wrapper import garak_wrapper, MaxConcurrentScansError
from services.gate_evaluator import GatePolicy, evaluate_gate, build_findings_summary
from services.report_generator import (
    generate_vulnerability_report,
    store_report_in_prism,
    load_report_from_prism,
)
from services.comparison_engine import compare_reports
from services.pdf_renderer import render_pdf, store_pdf_in_prism
from middleware.tenant import get_tenant
from datetime import datetime
from typing import Optional
import asyncio
import logging
import math
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=ScanResponse)
async def start_scan(request: Request, config: ScanConfigRequest):
    """
    Start a new garak vulnerability scan.

    The scan is scoped to the tenant extracted from the JWT token.

    Args:
        request: FastAPI request (carries TenantContext).
        config: Scan configuration.

    Returns:
        ScanResponse with scan_id and initial status.
    """
    tenant = get_tenant(request)
    try:
        # Validate garak is installed
        if not garak_wrapper.check_garak_installed():
            raise HTTPException(
                status_code=500,
                detail="Garak is not installed or not accessible"
            )

        # Start the scan (enforces concurrent scan limit)
        scan_id = await garak_wrapper.start_scan(config, tenant_id=tenant.tenant_id)

        return ScanResponse(
            scan_id=scan_id,
            status=ScanStatus.PENDING,
            message="Scan initiated successfully",
            created_at=datetime.now().isoformat()
        )

    except MaxConcurrentScansError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=ScanStatisticsResponse)
async def get_scan_statistics(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days for daily trend data"),
):
    """
    Get aggregate scan statistics including pass rates, trends,
    top failing probes, and per-target breakdowns.

    Results are scoped to the requesting tenant.
    """
    tenant = get_tenant(request)
    return garak_wrapper.get_scan_statistics(days=days, tenant_id=tenant.tenant_id)


@router.get("/{scan_id}/status", response_model=ScanStatusResponse)
async def get_scan_status(request: Request, scan_id: str):
    """
    Get current status of a scan.

    Args:
        request: FastAPI request (carries TenantContext).
        scan_id: Unique scan identifier.

    Returns:
        ScanStatusResponse with current status and progress.
    """
    tenant = get_tenant(request)
    scan_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)

    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    return ScanStatusResponse(
        scan_id=scan_info['scan_id'],
        status=scan_info['status'],
        progress=scan_info['progress'],
        current_probe=scan_info.get('current_probe'),
        completed_probes=scan_info.get('completed_probes', 0),
        total_probes=scan_info.get('total_probes', 0),
        passed=scan_info.get('passed', 0),
        failed=scan_info.get('failed', 0),
        error_message=scan_info.get('error_message')
    )


@router.delete("/{scan_id}/cancel")
async def cancel_scan(request: Request, scan_id: str):
    """
    Cancel a running scan.

    Args:
        request: FastAPI request (carries TenantContext).
        scan_id: Unique scan identifier.

    Returns:
        Success message.
    """
    tenant = get_tenant(request)
    success = await garak_wrapper.cancel_scan(scan_id, tenant_id=tenant.tenant_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel scan {scan_id}. It may not exist or already completed."
        )

    return {"message": f"Scan {scan_id} cancelled successfully"}


@router.delete("/{scan_id}")
async def delete_scan(request: Request, scan_id: str):
    """
    Delete a scan and all its associated reports.

    Args:
        request: FastAPI request (carries TenantContext).
        scan_id: Unique scan identifier.

    Returns:
        Success message.
    """
    tenant = get_tenant(request)
    success = garak_wrapper.delete_scan(scan_id, tenant_id=tenant.tenant_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Scan {scan_id} not found or could not be deleted."
        )

    return {"message": f"Scan {scan_id} deleted successfully"}


@router.get("/history", response_model=ScanHistoryResponse)
async def get_scan_history(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: ScanSortField = Query(ScanSortField.STARTED_AT, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    status: Optional[str] = Query(None, description="Filter by status (completed, running, failed, cancelled)"),
    search: Optional[str] = Query(None, description="Search by target name or scan ID"),
    start_date: Optional[str] = Query(None, description="Filter scans started on or after this date (ISO 8601, e.g. 2026-01-15)"),
    end_date: Optional[str] = Query(None, description="Filter scans started on or before this date (ISO 8601, e.g. 2026-02-08)"),
):
    """
    Get paginated list of all scans (active and completed).

    Results are scoped to the requesting tenant.

    Args:
        request: FastAPI request (carries TenantContext).
        page: Page number (1-indexed).
        page_size: Number of items per page (max 100).
        sort_by: Field to sort by.
        sort_order: Sort order (asc or desc).
        status: Optional status filter.
        search: Optional search query for target name or scan ID.
        start_date: Optional start date filter (ISO 8601).
        end_date: Optional end date filter (ISO 8601).

    Returns:
        Paginated list of scan information.
    """
    tenant = get_tenant(request)
    # Get all scans (tenant-scoped)
    all_scans = garak_wrapper.get_all_scans(tenant_id=tenant.tenant_id)

    # Apply status filter
    if status:
        status_lower = status.lower()
        all_scans = [s for s in all_scans if s.get('status', '').lower() == status_lower]

    # Apply search filter
    if search:
        search_lower = search.lower()
        all_scans = [
            s for s in all_scans
            if search_lower in s.get('target_name', '').lower()
            or search_lower in s.get('scan_id', '').lower()
            or search_lower in s.get('target_type', '').lower()
        ]

    # Apply date range filter
    if start_date or end_date:
        filtered = []
        for s in all_scans:
            started_at = s.get('started_at', '')
            if not started_at:
                continue
            try:
                scan_date = datetime.fromisoformat(started_at)
            except (ValueError, TypeError):
                continue
            if start_date:
                start_dt = datetime.fromisoformat(start_date)
                if scan_date < start_dt:
                    continue
            if end_date:
                # Include the entire end date (up to 23:59:59)
                end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
                if scan_date > end_dt:
                    continue
            filtered.append(s)
        all_scans = filtered

    # Sort scans
    def get_sort_key(scan):
        if sort_by == ScanSortField.STARTED_AT:
            return scan.get('started_at', '') or ''
        elif sort_by == ScanSortField.COMPLETED_AT:
            return scan.get('completed_at', '') or ''
        elif sort_by == ScanSortField.STATUS:
            return scan.get('status', '') or ''
        elif sort_by == ScanSortField.TARGET_NAME:
            return scan.get('target_name', '') or ''
        elif sort_by == ScanSortField.PASS_RATE:
            passed = scan.get('passed', 0)
            failed = scan.get('failed', 0)
            total = passed + failed
            return (passed / total * 100) if total > 0 else 0
        return ''

    reverse_sort = sort_order == SortOrder.DESC
    all_scans.sort(key=get_sort_key, reverse=reverse_sort)

    # Calculate pagination
    total_items = len(all_scans)
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    # Get page slice
    page_scans = all_scans[start_idx:end_idx]

    # Convert to response model
    scan_items = [
        ScanHistoryItem(
            scan_id=s.get('scan_id', ''),
            status=s.get('status', 'unknown'),
            target_type=s.get('target_type'),
            target_name=s.get('target_name'),
            started_at=s.get('started_at'),
            completed_at=s.get('completed_at'),
            passed=s.get('passed', 0),
            failed=s.get('failed', 0),
            total_tests=s.get('passed', 0) + s.get('failed', 0),
            progress=s.get('progress', 0.0),
            html_report_path=s.get('html_report_path'),
            jsonl_report_path=s.get('jsonl_report_path'),
        )
        for s in page_scans
    ]

    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )

    return ScanHistoryResponse(
        scans=scan_items,
        pagination=pagination,
        total_count=total_items,
    )


@router.get("/{scan_id}/results", response_model=ScanResult)
async def get_scan_results(request: Request, scan_id: str):
    """
    Get detailed scan results including probe-level information.

    Args:
        request: FastAPI request (carries TenantContext).
        scan_id: Unique scan identifier.

    Returns:
        Detailed scan results with probe breakdown.
    """
    tenant = get_tenant(request)
    scan_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)

    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    # Get full scan details
    full_results = garak_wrapper.get_scan_results(scan_id)

    if not full_results:
        raise HTTPException(
            status_code=404,
            detail=f"Results not available for scan {scan_id}"
        )

    return full_results


@router.get("/{scan_id}/report/html")
async def get_html_report(request: Request, scan_id: str):
    """
    Get HTML report for a scan.

    Tries local filesystem first, then falls back to object store (Minio).
    """
    from fastapi.responses import FileResponse, StreamingResponse
    from pathlib import Path

    tenant = get_tenant(request)
    scan_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)

    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    # Try local filesystem first
    html_report_path = scan_info.get('html_report_path')
    if html_report_path:
        report_file = Path(html_report_path)
        if report_file.exists():
            return FileResponse(
                path=str(report_file),
                media_type="text/html",
                filename=f"scan_{scan_id}_report.html"
            )

    # Fallback: read from object store
    html_key = scan_info.get('html_report_key') or f"{scan_id}/garak.{scan_id}.report.html"
    try:
        from services.object_store import object_store_available, get_object_store
        if object_store_available():
            store = get_object_store()
            stream = store.get_stream(html_key)
            if stream is not None:
                return StreamingResponse(
                    stream,
                    media_type="text/html",
                    headers={"Content-Disposition": f'inline; filename="scan_{scan_id}_report.html"'},
                )
    except Exception as e:
        logger.error(f"Error reading HTML report from object store: {e}")

    raise HTTPException(
        status_code=404,
        detail="HTML report not available for this scan"
    )


@router.get("/{scan_id}/report/detailed")
async def get_detailed_report(request: Request, scan_id: str):
    """
    Get detailed HTML report for a scan (inline content).

    Tries local filesystem first, then falls back to object store (Minio).
    """
    from fastapi.responses import HTMLResponse
    from pathlib import Path

    tenant = get_tenant(request)
    scan_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)

    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    # Try local filesystem first
    html_report_path = scan_info.get('html_report_path')
    if html_report_path:
        report_file = Path(html_report_path)
        if report_file.exists():
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    return HTMLResponse(content=f.read())
            except Exception as e:
                logger.error(f"Error reading local HTML report: {e}")

    # Fallback: read from object store
    html_key = scan_info.get('html_report_key') or f"{scan_id}/garak.{scan_id}.report.html"
    try:
        from services.object_store import object_store_available, get_object_store
        if object_store_available():
            store = get_object_store()
            data = store.get(html_key)
            if data is not None:
                return HTMLResponse(content=data.decode("utf-8"))
    except Exception as e:
        logger.error(f"Error reading HTML report from object store: {e}")

    raise HTTPException(
        status_code=404,
        detail="Detailed report not available for this scan"
    )


@router.get("/{scan_id}/probes", response_model=ProbeDetailsResponse)
async def get_probe_details(
    request: Request,
    scan_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    probe_filter: Optional[str] = Query(None, description="Filter by probe name or category"),
):
    """
    Get per-probe breakdown with security context for a scan.
    Sorted by pass rate ascending (worst first).
    """
    tenant = get_tenant(request)
    # Verify tenant has access to this scan
    if not garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    result = garak_wrapper.get_probe_details(
        scan_id, probe_filter=probe_filter, page=page, page_size=page_size
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Report not found for scan {scan_id}")
    return result


@router.get("/{scan_id}/probes/{probe_classname:path}/attempts", response_model=ProbeAttemptsResponse)
async def get_probe_attempts(
    request: Request,
    scan_id: str,
    probe_classname: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (passed, failed)"),
):
    """
    Get individual test attempts for a specific probe.
    Includes full prompt/output text, detector results, and security metadata.
    """
    tenant = get_tenant(request)
    # Verify tenant has access to this scan
    if not garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id):
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    result = garak_wrapper.get_probe_attempts(
        scan_id, probe_classname, status_filter=status, page=page, page_size=page_size
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No attempts found for probe {probe_classname} in scan {scan_id}",
        )
    return result


@router.get("/{scan_id}/report/vulnerability")
async def get_vulnerability_report(request: Request, scan_id: str):
    """Return a structured vulnerability report for a completed scan.

    Checks Prism for a cached report first. If not found, generates from
    raw JSONL entries and stores in Prism for future requests.
    """
    tenant = get_tenant(request)

    # Verify tenant has access
    scan_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)
    if not scan_info:
        raise HTTPException(404, f"Scan {scan_id} not found")

    if scan_info.get("status") != "completed":
        raise HTTPException(
            400, f"Scan {scan_id} has status '{scan_info.get('status')}' — report requires completed scan"
        )

    # Try loading cached report from Prism
    cached = load_report_from_prism(scan_id, tenant.tenant_id)
    if cached:
        return cached.model_dump()

    # Generate from raw JSONL entries
    entries = garak_wrapper._get_report_entries(scan_id)
    if entries is None:
        raise HTTPException(404, f"No report data found for scan {scan_id}")

    # Extract target info from scan config
    config = scan_info.get("config")
    target_name = ""
    target_type = ""
    if config:
        cfg = config.model_dump() if hasattr(config, "model_dump") else config
        target_name = cfg.get("target_name", cfg.get("model_name", ""))
        target_type = cfg.get("target_type", cfg.get("model_type", ""))

    report = generate_vulnerability_report(
        scan_id=scan_id,
        entries=entries,
        tenant_id=tenant.tenant_id,
        target_name=target_name,
        target_type=target_type,
    )

    # Store in Prism for caching
    store_report_in_prism(report, tenant.tenant_id)

    return report.model_dump()


@router.get("/{scan_id}/report/comparison")
async def get_report_comparison(
    request: Request,
    scan_id: str,
    compare_to: str = Query(..., description="Scan ID to compare against (baseline)"),
):
    """Compare two scan reports — shows new findings, resolved, regressions, risk delta.

    The ``compare_to`` scan is the baseline; ``scan_id`` is the current.
    """
    tenant = get_tenant(request)

    # Verify current scan
    current_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)
    if not current_info:
        raise HTTPException(404, f"Scan {scan_id} not found")
    if current_info.get("status") != "completed":
        raise HTTPException(400, f"Scan {scan_id} is not completed")

    # Verify baseline scan
    baseline_info = garak_wrapper.get_scan_status(compare_to, tenant_id=tenant.tenant_id)
    if not baseline_info:
        raise HTTPException(404, f"Baseline scan {compare_to} not found")

    # Load or generate current report
    current_report = load_report_from_prism(scan_id, tenant.tenant_id)
    if not current_report:
        entries = garak_wrapper._get_report_entries(scan_id)
        if not entries:
            raise HTTPException(404, f"No report data for scan {scan_id}")
        current_report = generate_vulnerability_report(
            scan_id, entries, tenant_id=tenant.tenant_id,
        )

    # Load or generate baseline report
    baseline_report = load_report_from_prism(compare_to, tenant.tenant_id)
    if not baseline_report:
        entries = garak_wrapper._get_report_entries(compare_to)
        if entries:
            baseline_report = generate_vulnerability_report(
                compare_to, entries, tenant_id=tenant.tenant_id,
            )

    result = compare_reports(baseline_report, current_report)
    return result.to_dict()


@router.get("/{scan_id}/report/pdf")
async def get_report_pdf(request: Request, scan_id: str):
    """Generate and return a branded PDF vulnerability report.

    Returns ``application/pdf`` when weasyprint is available, otherwise
    ``text/html`` as a fallback.
    """
    from fastapi.responses import Response

    tenant = get_tenant(request)

    scan_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)
    if not scan_info:
        raise HTTPException(404, f"Scan {scan_id} not found")
    if scan_info.get("status") != "completed":
        raise HTTPException(400, f"Scan {scan_id} is not completed")

    # Load or generate the vulnerability report
    report = load_report_from_prism(scan_id, tenant.tenant_id)
    if not report:
        entries = garak_wrapper._get_report_entries(scan_id)
        if not entries:
            raise HTTPException(404, f"No report data for scan {scan_id}")
        config = scan_info.get("config")
        target_name = ""
        target_type = ""
        if config:
            cfg = config.model_dump() if hasattr(config, "model_dump") else config
            target_name = cfg.get("target_name", cfg.get("model_name", ""))
            target_type = cfg.get("target_type", cfg.get("model_type", ""))
        report = generate_vulnerability_report(
            scan_id, entries, tenant_id=tenant.tenant_id,
            target_name=target_name, target_type=target_type,
        )

    # Load tenant branding (if configured)
    try:
        from services.portfolio_service import get_branding_for_pdf
        branding = get_branding_for_pdf(tenant.tenant_id)
    except Exception:
        branding = None

    pdf_bytes = render_pdf(report, branding)

    # Store in Prism for caching
    store_pdf_in_prism(pdf_bytes, scan_id, tenant.tenant_id)

    # Detect if this is real PDF or HTML fallback
    is_pdf = pdf_bytes[:5] == b"%PDF-"
    content_type = "application/pdf" if is_pdf else "text/html; charset=utf-8"
    filename = f"hydra-report-{scan_id}.pdf" if is_pdf else f"hydra-report-{scan_id}.html"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.websocket("/{scan_id}/progress")
async def scan_progress_websocket(websocket: WebSocket, scan_id: str):
    """
    WebSocket endpoint for real-time scan progress updates

    Args:
        websocket: WebSocket connection
        scan_id: Unique scan identifier
    """
    await websocket.accept()

    try:
        while True:
            scan_info = garak_wrapper.get_scan_status(scan_id)

            if not scan_info:
                await websocket.send_json({
                    "error": f"Scan {scan_id} not found"
                })
                break

            is_finished = scan_info['status'] in [
                ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED
            ]

            # Send status update (always includes error_message)
            await websocket.send_json({
                "scan_id": scan_info['scan_id'],
                "status": scan_info['status'],
                "progress": scan_info['progress'],
                "current_probe": scan_info.get('current_probe'),
                "completed_probes": scan_info.get('completed_probes', 0),
                "total_probes": scan_info.get('total_probes', 0),
                "current_iteration": scan_info.get('current_iteration', 0),
                "total_iterations": scan_info.get('total_iterations', 0),
                "passed": scan_info.get('passed', 0),
                "failed": scan_info.get('failed', 0),
                "elapsed_time": scan_info.get('elapsed_time'),
                "estimated_remaining": scan_info.get('estimated_remaining'),
                "error_message": scan_info.get('error_message'),
                "timestamp": datetime.now().isoformat()
            })

            if is_finished:
                break

            # Wait before sending next update
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for scan {scan_id}")
    except Exception as e:
        logger.error(f"WebSocket error for scan {scan_id}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass


@router.post("/gate")
async def gate_scan(request: Request, body: dict):
    """CI/CD gate endpoint — enqueue scan, wait, evaluate policy, return verdict.

    This is a synchronous blocking endpoint. It:
    1. Enqueues a scan on the express queue
    2. Polls for completion (up to ``timeout`` seconds)
    3. Evaluates the gate policy against scan results
    4. Returns a pass/fail verdict

    Request body:
        target_id: str — registered target to scan
        probes: list[str] — probes to run (optional, defaults to fast set)
        policy: dict — gate policy (min_pass_rate, max_critical, max_high, ...)
        timeout: int — max seconds to wait (default 300)
        compare_to: str — "last" or a specific scan_id for regression check
    """
    tenant = get_tenant(request)

    target_id = body.get("target_id")
    if not target_id:
        raise HTTPException(400, "target_id is required")

    policy = GatePolicy.from_dict(body.get("policy", {}))
    timeout_secs = min(body.get("timeout", 300), 600)  # Cap at 10 minutes

    scan_id = f"gate_{uuid.uuid4().hex[:12]}"
    config = {
        "target_id": target_id,
        "probes": body.get("probes", ["dan.Dan_11_0"]),
        "preset": body.get("preset", "fast"),
        "source": "ci_gate",
    }

    # Enqueue on express queue for low latency
    try:
        from tasks.scan_task import execute_scan
        execute_scan.apply_async(
            args=[scan_id, config],
            kwargs={"tenant_id": tenant.tenant_id},
            queue="express",
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to enqueue gate scan: {e}")

    # Poll for completion
    elapsed = 0
    poll_interval = 2
    scan_result = None

    while elapsed < timeout_secs:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        scan_info = garak_wrapper.get_scan_status(scan_id, tenant_id=tenant.tenant_id)
        if scan_info and scan_info.get("status") in ("completed", "failed", "error"):
            scan_result = scan_info
            break

    if not scan_result:
        return {
            "gate_passed": False,
            "scan_id": scan_id,
            "error": f"Scan did not complete within {timeout_secs}s",
            "risk_score": None,
            "findings_summary": None,
        }

    if scan_result.get("status") in ("failed", "error"):
        return {
            "gate_passed": False,
            "scan_id": scan_id,
            "error": scan_result.get("error_message", "Scan failed"),
            "risk_score": None,
            "findings_summary": None,
        }

    # Fetch previous scan for regression comparison
    previous_result = None
    if policy.check_regression:
        if policy.compare_to == "last":
            scans = garak_wrapper.get_all_scans(tenant_id=tenant.tenant_id)
            completed = [
                s for s in scans
                if s.get("status") == "completed" and s.get("scan_id") != scan_id
            ]
            if completed:
                previous_result = completed[0]  # Most recent
        elif policy.compare_to:
            previous_result = garak_wrapper.get_scan_status(
                policy.compare_to, tenant_id=tenant.tenant_id
            )

    verdict = evaluate_gate(scan_result, policy, previous_result)
    result = verdict.to_dict()
    result["scan_id"] = scan_id
    return result
