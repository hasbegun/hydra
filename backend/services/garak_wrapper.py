"""
Garak service client.
Communicates with the garak container over HTTP/SSE instead of
spawning local subprocesses.
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx

from models.schemas import ScanStatus, ScanConfigRequest
from services.workflow_analyzer import workflow_analyzer
from config import settings

logger = logging.getLogger(__name__)

# Default TTL for report cache (seconds)
REPORT_CACHE_TTL = 300  # 5 minutes


from database.session import db_available as _db_available


class MaxConcurrentScansError(Exception):
    """Raised when the concurrent scan limit is reached."""

    def __init__(self, running: int, limit: int):
        self.running = running
        self.limit = limit
        super().__init__(
            f"Concurrent scan limit reached: {running}/{limit} scans running. "
            f"Wait for a scan to finish or cancel one before starting a new scan."
        )


class GarakWrapper:
    """HTTP client for the garak container service."""

    def __init__(self, garak_service_url: Optional[str] = None, cache_ttl: int = REPORT_CACHE_TTL):
        self.garak_service_url = garak_service_url or settings.garak_service_url
        self.active_scans: Dict[str, Dict[str, Any]] = {}
        self.garak_reports_dir = settings.garak_reports_path
        # Layer 1: raw JSONL entries  scan_id → {"entries": [...], "mtime": float, "cached_at": float}
        self._report_cache: Dict[str, Dict[str, Any]] = {}
        # Layer 2 (scan info) removed — DB handles metadata queries now
        # Layer 3: full results      scan_id → {"data": {...}, "mtime": float}
        self._results_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = cache_ttl
        logger.info(f"Garak service URL: {self.garak_service_url}")
        logger.info(f"Garak reports directory: {self.garak_reports_dir}")

    # ------------------------------------------------------------------
    # Database sync helpers
    # ------------------------------------------------------------------

    def _sync_scan_to_db(self, scan_id: str, scan_info: Optional[Dict[str, Any]] = None) -> None:
        """Write current scan state to the database (upsert).

        Called at key lifecycle points: start, complete, error, cancel, report.
        Delegates to the shared ``database.scan_ops.upsert_scan`` to avoid
        duplicating upsert logic with the Celery scan task.
        """
        if scan_info is None:
            scan_info = self.active_scans.get(scan_id)
        if not scan_info:
            return

        from database.scan_ops import upsert_scan

        status = scan_info.get("status", ScanStatus.PENDING)
        status_str = status.value if hasattr(status, "value") else str(status)

        config = scan_info.get("config")
        config_json = None
        if config:
            config_json = json.dumps(
                config.model_dump() if hasattr(config, "model_dump") else config
            )

        target_type = "unknown"
        target_name = "unknown"
        if config:
            cfg = config if isinstance(config, dict) else (
                config.model_dump() if hasattr(config, "model_dump") else {}
            )
            target_type = cfg.get("target_type", "unknown")
            target_name = cfg.get("target_name", "unknown")

        upsert_scan(
            scan_id,
            tenant_id=scan_info.get("tenant_id", "default"),
            status=status_str,
            target_type=target_type,
            target_name=target_name,
            passed=scan_info.get("passed", 0),
            failed=scan_info.get("failed", 0),
            total_probes=scan_info.get("total_probes", 0),
            error_message=scan_info.get("error_message"),
            started_at=scan_info.get("started_at") or scan_info.get("created_at"),
            completed_at=scan_info.get("completed_at"),
            report_path=scan_info.get("jsonl_report_path"),
            html_report_path=scan_info.get("html_report_path"),
            report_key=scan_info.get("report_key"),
            html_report_key=scan_info.get("html_report_key"),
            config_json=config_json,
            created_at=scan_info.get("created_at"),
        )

    def _delete_scan_from_db(self, scan_id: str) -> None:
        """Remove a scan row from the database."""
        if not _db_available():
            return
        try:
            from database.session import get_db
            from database.models import Scan
            with get_db() as db:
                db.query(Scan).filter_by(id=scan_id).delete()
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to delete scan {scan_id} from DB: {e}")

    # ------------------------------------------------------------------
    # Health / Version / Plugins  (delegate to garak service)
    # ------------------------------------------------------------------

    def check_garak_installed(self) -> bool:
        """Check if garak service is available and garak is installed."""
        try:
            with httpx.Client(base_url=self.garak_service_url, timeout=5.0) as client:
                response = client.get("/health")
                if response.status_code == 200:
                    return response.json().get("garak_installed", False)
        except Exception as e:
            logger.error(f"Error checking garak service health: {e}")
        return False

    def get_garak_version(self) -> Optional[str]:
        """Get garak version from the service."""
        try:
            with httpx.Client(base_url=self.garak_service_url, timeout=5.0) as client:
                response = client.get("/version")
                if response.status_code == 200:
                    return response.json().get("version")
        except Exception as e:
            logger.error(f"Error getting garak version: {e}")
        return None

    def list_plugins(self, plugin_type: str) -> List[str]:
        """List plugins via garak service."""
        try:
            with httpx.Client(base_url=self.garak_service_url, timeout=60.0) as client:
                response = client.get(f"/plugins/{plugin_type}")
                if response.status_code == 200:
                    plugins = response.json().get("plugins", [])
                    logger.info(f"Found {len(plugins)} {plugin_type}")
                    return plugins
        except Exception as e:
            logger.error(f"Error listing {plugin_type}: {e}")
        return []

    # ------------------------------------------------------------------
    # Scan lifecycle
    # ------------------------------------------------------------------

    def _count_running_scans(self) -> int:
        """Count scans in PENDING or RUNNING state."""
        return sum(
            1 for s in self.active_scans.values()
            if s.get("status") in (ScanStatus.PENDING, ScanStatus.RUNNING)
        )

    async def start_scan(self, config: ScanConfigRequest, tenant_id: str = "default") -> str:
        """Start a scan via the garak service.

        Args:
            config: Scan configuration.
            tenant_id: Tenant that owns this scan.

        Raises MaxConcurrentScansError if the concurrent scan limit is reached.
        """
        # Enforce concurrent scan limit
        running = self._count_running_scans()
        limit = settings.max_concurrent_scans
        if running >= limit:
            raise MaxConcurrentScansError(running, limit)

        scan_id = str(uuid.uuid4())

        # Send scan config to garak service
        async with httpx.AsyncClient(
            base_url=self.garak_service_url, timeout=30.0
        ) as client:
            response = await client.post(
                "/scans",
                json={
                    "scan_id": scan_id,
                    "config": config.model_dump(),
                },
            )
            response.raise_for_status()

        # Initialize local tracking (same shape as before for WebSocket compat)
        total_probes = len(config.probes) if config.probes else 0
        self.active_scans[scan_id] = {
            "scan_id": scan_id,
            "tenant_id": tenant_id,
            "status": ScanStatus.PENDING,
            "config": config,
            "progress": 0.0,
            "current_probe": None,
            "completed_probes": 0,
            "total_probes": total_probes,
            "current_iteration": 0,
            "total_iterations": 0,
            "passed": 0,
            "failed": 0,
            "elapsed_time": None,
            "estimated_remaining": None,
            "html_report_path": None,
            "jsonl_report_path": None,
            "created_at": datetime.now().isoformat(),
            "output_lines": [],
            "error_message": None,
        }

        # Persist initial scan state to DB
        self._sync_scan_to_db(scan_id)

        # Start background task to consume SSE progress stream
        asyncio.create_task(self._consume_progress_stream(scan_id))

        return scan_id

    async def _consume_progress_stream(self, scan_id: str):
        """Connect to garak service SSE and update local scan state."""
        scan_info = self.active_scans.get(scan_id)
        if not scan_info:
            return

        # Small delay to let the garak service register the scan
        await asyncio.sleep(0.5)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    base_url=self.garak_service_url,
                    timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
                ) as client:
                    async with client.stream(
                        "GET", f"/scans/{scan_id}/progress"
                    ) as response:
                        if response.status_code != 200:
                            body = await response.aread()
                            logger.error(
                                f"SSE endpoint returned {response.status_code} for {scan_id}: {body.decode()}"
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 * (attempt + 1))
                                continue
                            scan_info["status"] = ScanStatus.FAILED
                            scan_info["error_message"] = (
                                f"Garak service error: {response.status_code}"
                            )
                            scan_info["completed_at"] = datetime.now().isoformat()
                            self._sync_scan_to_db(scan_id)
                            return

                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                data = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue

                            self._update_scan_from_event(scan_id, data)

                            # Forward raw output to workflow analyzer
                            raw_line = data.get("raw_line")
                            if raw_line:
                                workflow_analyzer.process_garak_output(scan_id, raw_line)

                # Stream ended normally -- if scan isn't in a terminal state, mark completed
                if scan_info.get("status") in [ScanStatus.RUNNING, ScanStatus.PENDING]:
                    scan_info["status"] = ScanStatus.COMPLETED
                    scan_info["progress"] = 100.0
                    scan_info["completed_at"] = datetime.now().isoformat()
                self._sync_scan_to_db(scan_id)
                return

            except Exception as e:
                logger.error(f"Error consuming progress stream for {scan_id} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                if scan_info.get("status") in [ScanStatus.RUNNING, ScanStatus.PENDING]:
                    scan_info["status"] = ScanStatus.FAILED
                    scan_info["error_message"] = (
                        f"Lost connection to garak service: {e}"
                    )
                    scan_info["completed_at"] = datetime.now().isoformat()
                    self._sync_scan_to_db(scan_id)

    def _update_scan_from_event(self, scan_id: str, event: dict):
        """Update local scan state from an SSE event."""
        scan_info = self.active_scans.get(scan_id)
        if not scan_info:
            return

        etype = event.get("event_type")

        if etype == "status":
            status_str = event.get("status", "")
            scan_info["status"] = self._map_status(status_str)

        elif etype == "progress":
            scan_info["current_probe"] = event.get("probe")
            scan_info["progress"] = float(event.get("percent", scan_info["progress"]))
            scan_info["current_iteration"] = event.get("current", 0)
            scan_info["total_iterations"] = event.get("total", 0)
            scan_info["elapsed_time"] = event.get("elapsed")
            scan_info["estimated_remaining"] = event.get("remaining")
            scan_info["status"] = ScanStatus.RUNNING

        elif etype == "probe_count":
            scan_info["completed_probes"] = event.get("completed", 0)
            scan_info["total_probes"] = event.get("total", 0)

        elif etype == "current_probe":
            scan_info["current_probe"] = event.get("probe")

        elif etype == "result":
            scan_info["passed"] = event.get("total_passed", scan_info.get("passed", 0))
            scan_info["failed"] = event.get("total_failed", scan_info.get("failed", 0))

        elif etype == "report":
            rtype = event.get("report_type")
            original_path = event.get("path")
            if original_path:
                renamed = self._rename_report_file(scan_id, original_path, rtype)
                final_path = renamed or original_path
            else:
                final_path = None
            if rtype == "html":
                scan_info["html_report_path"] = final_path
            elif rtype == "jsonl":
                scan_info["jsonl_report_path"] = final_path
            self._sync_scan_to_db(scan_id)

        elif etype == "complete":
            scan_info["status"] = ScanStatus.COMPLETED
            scan_info["progress"] = 100.0
            scan_info["completed_at"] = datetime.now().isoformat()
            scan_info["passed"] = event.get("passed", scan_info.get("passed", 0))
            scan_info["failed"] = event.get("failed", scan_info.get("failed", 0))
            # Store object store keys from garak service upload
            report_keys = event.get("report_keys", {})
            if report_keys.get("jsonl"):
                scan_info["report_key"] = report_keys["jsonl"]
            if report_keys.get("html"):
                scan_info["html_report_key"] = report_keys["html"]
            self._sync_scan_to_db(scan_id)

        elif etype == "error":
            scan_info["status"] = ScanStatus.FAILED
            scan_info["error_message"] = event.get("message")
            scan_info["completed_at"] = datetime.now().isoformat()
            self._sync_scan_to_db(scan_id)

        elif etype == "output":
            scan_info.setdefault("output_lines", []).append(
                event.get("line", "")
            )

    @staticmethod
    def _map_status(status_str: str) -> ScanStatus:
        mapping = {
            "pending": ScanStatus.PENDING,
            "running": ScanStatus.RUNNING,
            "completed": ScanStatus.COMPLETED,
            "failed": ScanStatus.FAILED,
            "cancelled": ScanStatus.CANCELLED,
        }
        return mapping.get(status_str, ScanStatus.PENDING)

    def _rename_report_file(self, scan_id: str, original_path: str, report_type: str) -> Optional[str]:
        """Rename a garak report file to use our scan_id.

        Garak generates its own UUID for filenames (e.g. garak.{garak_uuid}.report.jsonl).
        We rename to garak.{our_scan_id}.report.jsonl so all lookups by scan_id work.
        Also renames the hitlog file if found alongside the jsonl.
        """
        src = Path(original_path)
        if not src.exists():
            logger.warning(f"Report file not found for rename: {original_path}")
            return None

        ext_map = {"html": "report.html", "jsonl": "report.jsonl"}
        suffix = ext_map.get(report_type)
        if not suffix:
            return None

        dst = src.parent / f"garak.{scan_id}.{suffix}"

        if src == dst:
            return str(dst)

        try:
            src.rename(dst)
            logger.info(f"Renamed report: {src.name} -> {dst.name}")

            # Also rename the hitlog if this is the jsonl report
            if report_type == "jsonl":
                garak_uuid = src.stem.replace("garak.", "").replace(".report", "")
                hitlog_src = src.parent / f"garak.{garak_uuid}.hitlog.jsonl"
                if hitlog_src.exists():
                    hitlog_dst = src.parent / f"garak.{scan_id}.hitlog.jsonl"
                    hitlog_src.rename(hitlog_dst)
                    logger.info(f"Renamed hitlog: {hitlog_src.name} -> {hitlog_dst.name}")

            return str(dst)
        except Exception as e:
            logger.error(f"Error renaming report file {src} -> {dst}: {e}")
            return None

    async def cancel_scan(self, scan_id: str, tenant_id: Optional[str] = None) -> bool:
        """Cancel a scan via the garak service.

        Args:
            scan_id: Scan identifier.
            tenant_id: If provided, only cancel if the scan belongs to this
                       tenant (access control).
        """
        scan_info = self.active_scans.get(scan_id)
        if not scan_info:
            logger.warning(f"Cannot cancel scan {scan_id}: not found")
            return False

        if tenant_id and scan_info.get("tenant_id", "default") != tenant_id:
            logger.warning(f"Cannot cancel scan {scan_id}: tenant mismatch")
            return False

        if scan_info["status"] not in [ScanStatus.RUNNING, ScanStatus.PENDING]:
            logger.warning(f"Cannot cancel scan {scan_id}: status is {scan_info['status']}")
            return False

        try:
            async with httpx.AsyncClient(
                base_url=self.garak_service_url, timeout=10.0
            ) as client:
                response = await client.delete(f"/scans/{scan_id}")
                if response.status_code == 200:
                    scan_info["status"] = ScanStatus.CANCELLED
                    scan_info["completed_at"] = datetime.now().isoformat()
                    self._sync_scan_to_db(scan_id)
                    logger.info(f"Scan {scan_id} cancelled")
                    return True
                else:
                    logger.error(
                        f"Failed to cancel scan {scan_id}: {response.status_code}"
                    )
        except Exception as e:
            logger.error(f"Error cancelling scan {scan_id}: {e}")
        return False

    # ------------------------------------------------------------------
    # Report reading (object store → local filesystem fallback)
    # ------------------------------------------------------------------

    def get_scan_status(self, scan_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get current status of a scan (active or historical).

        Args:
            scan_id: Scan identifier.
            tenant_id: If provided, only return the scan if it belongs to this
                       tenant (access control). If None, no tenant check is
                       performed (backward-compatible).
        """
        # Check active scans first (real-time data)
        scan_info = self.active_scans.get(scan_id)
        if scan_info:
            if tenant_id and scan_info.get("tenant_id", "default") != tenant_id:
                return None
            return {k: v for k, v in scan_info.items() if k != "process"}

        # Check database for historical scans
        if _db_available():
            try:
                from database.session import get_db
                from database.models import Scan
                with get_db() as db:
                    query = db.query(Scan).filter_by(id=scan_id)
                    if tenant_id:
                        query = query.filter(Scan.tenant_id == tenant_id)
                    row = query.first()
                    if row:
                        return row.to_dict()
            except Exception as e:
                logger.warning(f"DB lookup failed for scan {scan_id}, falling back to file: {e}")

        # Fallback: check historical scans on disk (no tenant scoping for file-based)
        if self.garak_reports_dir.exists():
            report_file = self.garak_reports_dir / f"garak.{scan_id}.report.jsonl"
            if report_file.exists():
                return self._parse_report_file(report_file, scan_id)

        return None

    def delete_scan(self, scan_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete a scan and all its associated reports.

        Args:
            scan_id: Scan identifier.
            tenant_id: If provided, only delete if the scan belongs to this
                       tenant (access control).
        """
        # Tenant access check
        if tenant_id:
            scan_info = self.active_scans.get(scan_id)
            if scan_info and scan_info.get("tenant_id", "default") != tenant_id:
                return False
            if not scan_info and _db_available():
                try:
                    from database.session import get_db
                    from database.models import Scan
                    with get_db() as db:
                        row = db.query(Scan).filter_by(id=scan_id).first()
                        if row and row.tenant_id != tenant_id:
                            return False
                except Exception:
                    pass

        # Invalidate cache
        self.invalidate_cache(scan_id)

        # Remove from database
        self._delete_scan_from_db(scan_id)

        # Remove from active scans
        if scan_id in self.active_scans:
            scan_info = self.active_scans[scan_id]
            if scan_info.get("status") in [ScanStatus.RUNNING, ScanStatus.PENDING]:
                try:
                    asyncio.create_task(self.cancel_scan(scan_id))
                except Exception as e:
                    logger.warning(f"Failed to cancel running scan {scan_id}: {e}")
            del self.active_scans[scan_id]
            logger.info(f"Removed scan {scan_id} from active scans")

        # Delete report files from local filesystem
        if self.garak_reports_dir.exists():
            deleted_files = []
            try:
                for file_pattern in [
                    f"garak.{scan_id}.report.jsonl",
                    f"garak.{scan_id}.report.html",
                    f"garak.{scan_id}.*",
                ]:
                    for file_path in self.garak_reports_dir.glob(file_pattern):
                        try:
                            file_path.unlink()
                            deleted_files.append(str(file_path))
                        except Exception as e:
                            logger.error(f"Failed to delete file {file_path}: {e}")
                if deleted_files:
                    logger.info(f"Deleted {len(deleted_files)} local file(s) for scan {scan_id}")
            except Exception as e:
                logger.error(f"Error deleting local report files for scan {scan_id}: {e}")

        # Delete report files from object store
        try:
            from services.object_store import object_store_available, get_object_store
            if object_store_available():
                store = get_object_store()
                keys = store.list_keys(prefix=f"{scan_id}/")
                for key in keys:
                    store.delete(key)
                if keys:
                    logger.info(f"Deleted {len(keys)} object(s) from store for scan {scan_id}")
        except Exception as e:
            logger.warning(f"Error deleting objects from store for scan {scan_id}: {e}")

        return True

    def get_all_scans(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get information about all scans (active and historical).

        Args:
            tenant_id: If provided, only return scans belonging to this tenant.
                       If None, return all scans (backward-compatible for
                       single-tenant mode).

        Active scans come from in-memory dict (real-time).
        Historical scans come from DB (fast indexed query).
        Falls back to file-based scanning if DB is unavailable.
        """
        all_scans = []
        active_ids = set()

        # Active scans (real-time data)
        for scan_info in self.active_scans.values():
            if tenant_id and scan_info.get("tenant_id", "default") != tenant_id:
                continue
            scan_copy = {k: v for k, v in scan_info.items() if k != "process"}
            all_scans.append(scan_copy)
            active_ids.add(scan_info.get("scan_id"))

        # Historical scans from database
        if _db_available():
            try:
                from database.session import get_db
                from database.models import Scan
                with get_db() as db:
                    query = db.query(Scan)
                    if tenant_id:
                        query = query.filter(Scan.tenant_id == tenant_id)
                    rows = query.order_by(Scan.started_at.desc()).all()
                    for row in rows:
                        if row.id not in active_ids:
                            all_scans.append(row.to_dict())
                return sorted(all_scans, key=lambda x: x.get("started_at", ""), reverse=True)
            except Exception as e:
                logger.warning(f"DB query failed for scan list, falling back to files: {e}")

        # Fallback: historical scans from reports directory
        if not self.garak_reports_dir.exists():
            logger.warning(f"Reports directory not found: {self.garak_reports_dir}")
            return sorted(all_scans, key=lambda x: x.get("started_at", ""), reverse=True)

        try:
            report_files = list(self.garak_reports_dir.glob("garak.*.report.jsonl"))
            for report_file in report_files:
                try:
                    scan_id = report_file.stem.replace("garak.", "").replace(".report", "")
                    if scan_id in active_ids:
                        continue
                    scan_info = self._parse_report_file(report_file, scan_id)
                    if scan_info:
                        all_scans.append(scan_info)
                except Exception as e:
                    logger.error(f"Error parsing report file {report_file}: {e}")
        except Exception as e:
            logger.error(f"Error reading reports directory: {e}")

        return sorted(all_scans, key=lambda x: x.get("started_at", ""), reverse=True)

    # ------------------------------------------------------------------
    # Report cache
    # ------------------------------------------------------------------

    def _get_report_entries(self, scan_id: str) -> Optional[List[dict]]:
        """Get parsed JSONL entries for a scan, using cache when valid.

        Lookup order:
        1. In-memory cache (immutable for object-store-sourced data)
        2. Object store (Minio)
        3. Local filesystem
        4. Garak service HTTP fallback (fetches from garak container and
           uploads to Minio for future access)

        Cache is invalidated when:
        - File mtime changes (file was rewritten) — local filesystem only
        - TTL expires — local filesystem only
        - invalidate_cache() is called (e.g. on delete)
        """
        # Check in-memory cache first
        now = time.monotonic()
        cached = self._report_cache.get(scan_id)
        if cached and cached.get("immutable"):
            # Object-store-sourced data — cache forever (write-once)
            return cached["entries"]

        # Try object store (Minio)
        entries = self._read_entries_from_object_store(scan_id)
        if entries is not None:
            self._report_cache[scan_id] = {
                "entries": entries,
                "immutable": True,  # Objects in Minio are write-once
                "cached_at": now,
            }
            return entries

        # Fallback: local filesystem
        report_file = self.garak_reports_dir / f"garak.{scan_id}.report.jsonl"
        if report_file.exists():
            try:
                file_mtime = report_file.stat().st_mtime
            except OSError:
                file_mtime = None

            if file_mtime is not None:
                # Check if local file cache is still valid
                if (
                    cached
                    and cached.get("mtime") == file_mtime
                    and (now - cached["cached_at"]) < self._cache_ttl
                ):
                    return cached["entries"]

                # Parse local file
                entries = self._parse_local_report(report_file)
                if entries is not None:
                    self._report_cache[scan_id] = {
                        "entries": entries,
                        "mtime": file_mtime,
                        "cached_at": now,
                    }
                    return entries

        # Fallback: fetch from garak service via HTTP
        entries = self._fetch_report_from_garak_service(scan_id)
        if entries is not None:
            self._report_cache[scan_id] = {
                "entries": entries,
                "immutable": True,
                "cached_at": now,
            }
            return entries

        return None

    def _read_entries_from_object_store(self, scan_id: str) -> Optional[List[dict]]:
        """Try to read JSONL entries from the object store (Minio).

        Returns None if object store is not available or file not found.
        """
        try:
            from services.object_store import object_store_available, get_object_store
            if not object_store_available():
                return None

            store = get_object_store()
            key = f"{scan_id}/garak.{scan_id}.report.jsonl"
            data = store.get(key)
            if data is None:
                return None

            entries = []
            for line in data.decode("utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return entries if entries else None

        except Exception as e:
            logger.debug(f"Object store read failed for {scan_id}: {e}")
            return None

    @staticmethod
    def _parse_local_report(report_file: Path) -> Optional[List[dict]]:
        """Parse a local JSONL report file into entries.

        Returns a list (possibly empty) on success, or None on read error.
        """
        entries = []
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error reading report file {report_file}: {e}")
            return None
        return entries

    def _fetch_report_from_garak_service(self, scan_id: str) -> Optional[List[dict]]:
        """Fetch a report file from the garak service via HTTP.

        When Minio and local filesystem both miss, the report may still exist
        on the garak container. The DB stores the original garak file path
        (e.g. /data/garak_reports/garak.{garak_uuid}.report.jsonl). We extract
        the filename and fetch it via the garak service's /reports/{filename}
        endpoint, then upload to Minio so future reads hit the cache.
        """
        # Look up the original report path from the DB
        report_path = self._get_report_path_from_db(scan_id)
        if not report_path:
            return None

        filename = Path(report_path).name
        url = f"{self.garak_service_url}/reports/{filename}"

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url)
            if resp.status_code != 200:
                logger.debug(f"Garak service returned {resp.status_code} for {filename}")
                return None

            content = resp.text
            entries = []
            for line in content.splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            if not entries:
                return None

            logger.info(f"Fetched {len(entries)} entries from garak service for {scan_id}")

            # Upload to Minio so future reads don't need the garak service
            self._upload_fetched_report_to_object_store(scan_id, content.encode("utf-8"))

            return entries

        except Exception as e:
            logger.debug(f"Garak service fetch failed for {scan_id}: {e}")
            return None

    @staticmethod
    def _get_report_path_from_db(scan_id: str) -> Optional[str]:
        """Get the original report file path from the database."""
        if not _db_available():
            return None
        try:
            from database.session import get_db
            from database.models import Scan
            with get_db() as db:
                scan = db.query(Scan).filter_by(id=scan_id).first()
                if scan and scan.report_path:
                    return scan.report_path
        except Exception as e:
            logger.debug(f"DB lookup failed for report path of {scan_id}: {e}")
        return None

    def _upload_fetched_report_to_object_store(self, scan_id: str, data: bytes) -> None:
        """Upload report data to the object store and update the DB key."""
        try:
            from services.object_store import object_store_available, get_object_store
            if not object_store_available():
                return

            store = get_object_store()
            key = f"{scan_id}/garak.{scan_id}.report.jsonl"
            store.put(key, data, content_type="application/jsonl")
            logger.info(f"Uploaded fetched report to object store: {key}")

            # Update DB with the object store key
            if _db_available():
                from database.session import get_db
                from database.models import Scan
                with get_db() as db:
                    scan = db.query(Scan).filter_by(id=scan_id).first()
                    if scan:
                        scan.report_key = key
                        db.commit()
        except Exception as e:
            logger.warning(f"Failed to upload fetched report to object store: {e}")

    def invalidate_cache(self, scan_id: str):
        """Remove all cached data for a scan."""
        self._report_cache.pop(scan_id, None)
        self._results_cache.pop(scan_id, None)

    def clear_cache(self):
        """Remove all cached data."""
        self._report_cache.clear()
        self._results_cache.clear()

    def _parse_report_file(self, report_file: Path, scan_id: str) -> Optional[Dict[str, Any]]:
        """Parse a garak report.jsonl file to extract scan information.

        This is the file fallback path — only used when the DB is unavailable.
        Uses Layer 1 (raw entries) for processing.
        """
        entries = self._get_report_entries(scan_id)
        if not entries:
            return None

        try:
            first_entry = entries[0]

            scan_info = {
                "scan_id": scan_id,
                "status": "completed",
                "target_type": first_entry.get("plugins.target_type", "unknown"),
                "target_name": first_entry.get("plugins.target_name", "unknown"),
                "started_at": first_entry.get("transient.starttime_iso", ""),
                "completed_at": first_entry.get("transient.endtime_iso", ""),
                "passed": 0,
                "failed": 0,
                "total_tests": 0,
                "progress": 100.0,
            }

            html_report_path = report_file.parent / f"garak.{scan_id}.report.html"
            if html_report_path.exists():
                scan_info["html_report_path"] = str(html_report_path)

            scan_info["jsonl_report_path"] = str(report_file)

            for entry in entries:
                entry_type = entry.get("entry_type")
                if entry_type == "attempt" and entry.get("status") in [1, 2]:
                    scan_info["total_tests"] += 1
                    if entry["status"] == 2:
                        scan_info["passed"] += 1
                    elif entry["status"] == 1:
                        scan_info["failed"] += 1
                elif entry_type == "digest":
                    scan_info["digest"] = entry.get("eval", {})

            if not scan_info["started_at"]:
                try:
                    file_mtime = report_file.stat().st_mtime
                    file_mtime_dt = datetime.fromtimestamp(file_mtime)
                    scan_info["started_at"] = file_mtime_dt.isoformat()
                except OSError:
                    pass

            return scan_info

        except Exception as e:
            logger.error(f"Error parsing report file {report_file}: {e}")
            return None

    def get_scan_results(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed scan results including probe-level breakdown.

        For completed (historical) scans the result is cached in Layer 3.
        Active scans always return live data.
        """
        # Active scans → live data, no cache
        if scan_id in self.active_scans:
            return self._build_results(scan_id)

        # Check Layer 3 cache (immutable entries cached forever)
        cached = self._results_cache.get(scan_id)
        if cached and cached.get("immutable"):
            return cached["data"]

        # Check local filesystem for mtime-based cache
        report_file = self.garak_reports_dir / f"garak.{scan_id}.report.jsonl"
        if report_file.exists():
            try:
                file_mtime = report_file.stat().st_mtime
            except OSError:
                file_mtime = None

            if file_mtime is not None and cached and cached.get("mtime") == file_mtime:
                return cached["data"]

            result = self._build_results(scan_id)
            if result and file_mtime is not None:
                self._results_cache[scan_id] = {"data": result, "mtime": file_mtime}
            return result

        # Delegate to _get_report_entries which handles Minio, local, and
        # garak service fallback. If entries are found, build results.
        entries = self._get_report_entries(scan_id)
        if entries is not None:
            result = self._build_results(scan_id)
            if result:
                self._results_cache[scan_id] = {"data": result, "immutable": True}
            return result

        return None

    def _build_results(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Build the results dict from scan info (uncached)."""
        scan_info = self.get_scan_status(scan_id)
        if not scan_info:
            return None

        config_data = None
        if "config" in scan_info and scan_info["config"] is not None:
            config = scan_info["config"]
            config_data = config.model_dump() if hasattr(config, "model_dump") else config

        # Fallback: reconstruct config from top-level fields or JSONL first entry
        if config_data is None:
            config_data = self._extract_config(scan_id, scan_info)

        # DB rows don't store digest; extract from JSONL when missing
        digest = scan_info.get("digest")
        if digest is None:
            digest = self._extract_digest(scan_id)

        return {
            "scan_id": scan_id,
            "status": scan_info["status"],
            "config": config_data,
            "created_at": scan_info.get("created_at"),
            "started_at": scan_info.get("started_at"),
            "completed_at": scan_info.get("completed_at"),
            "duration": self._calculate_duration(scan_info),
            "results": {
                "passed": scan_info.get("passed", 0),
                "failed": scan_info.get("failed", 0),
                "total_probes": scan_info.get("total_probes", 0),
                "completed_probes": scan_info.get("completed_probes", 0),
                "current_probe": scan_info.get("current_probe"),
                "progress": scan_info.get("progress", 0.0),
            },
            "summary": {
                "total_tests": scan_info.get("passed", 0) + scan_info.get("failed", 0),
                "pass_rate": self._calculate_pass_rate(scan_info),
                "status": scan_info["status"],
                "error_message": scan_info.get("error_message"),
            },
            "digest": digest,
            "html_report_path": scan_info.get("html_report_path"),
            "jsonl_report_path": scan_info.get("jsonl_report_path"),
            "report_key": scan_info.get("report_key"),
            "html_report_key": scan_info.get("html_report_key"),
            "output_lines": scan_info.get("output_lines", []),
        }

    def _calculate_duration(self, scan_info: Dict[str, Any]) -> Optional[float]:
        if not scan_info.get("started_at") or not scan_info.get("completed_at"):
            return None
        try:
            start = datetime.fromisoformat(scan_info["started_at"])
            end = datetime.fromisoformat(scan_info["completed_at"])
            return (end - start).total_seconds()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Per-probe details (parsed from JSONL on demand)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_prompt_text(entry: dict) -> str:
        """Extract prompt text from an attempt entry."""
        prompt = entry.get("prompt", {})
        turns = prompt.get("turns", [])
        if turns:
            content = turns[0].get("content", {})
            if isinstance(content, dict):
                return content.get("text", "")
            return str(content)
        return ""

    @staticmethod
    def _extract_output_text(entry: dict) -> str:
        """Extract first output text from an attempt entry."""
        outputs = entry.get("outputs", [])
        if outputs:
            first = outputs[0]
            if isinstance(first, dict):
                return first.get("text", "")
            return str(first)
        return ""

    @staticmethod
    def _extract_all_outputs(entry: dict) -> List[str]:
        """Extract all output texts from an attempt entry."""
        outputs = entry.get("outputs", [])
        result = []
        for o in outputs:
            if isinstance(o, dict):
                result.append(o.get("text", ""))
            else:
                result.append(str(o))
        return result

    def get_probe_details(
        self,
        scan_id: str,
        probe_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Optional[Dict[str, Any]]:
        """Parse JSONL report and return per-probe breakdown with security context.

        Uses cached JSONL entries when available.
        """
        from services.probe_knowledge import get_probe_metadata

        entries = self._get_report_entries(scan_id)
        if entries is None:
            return None

        probes_data: Dict[str, Dict[str, Any]] = {}

        for entry in entries:
            etype = entry.get("entry_type")

            if etype == "attempt":
                probe = entry.get("probe_classname", "unknown")
                if probe not in probes_data:
                    probes_data[probe] = {
                        "passed": 0,
                        "failed": 0,
                        "goal": entry.get("goal"),
                    }
                status = entry.get("status")
                if status == 2:
                    probes_data[probe]["passed"] += 1
                elif status == 1:
                    probes_data[probe]["failed"] += 1

            elif etype == "eval":
                probe = entry.get("probe")
                if probe and probe in probes_data:
                    probes_data[probe]["eval"] = {
                        "detector": entry.get("detector"),
                        "passed": entry.get("passed"),
                        "total": entry.get("total") or entry.get("total_evaluated"),
                    }

        # Build response with knowledge base enrichment
        probe_results = []
        for probe_name, data in probes_data.items():
            total = data["passed"] + data["failed"]
            pass_rate = (data["passed"] / total * 100) if total > 0 else 0

            metadata = get_probe_metadata(probe_name)

            probe_results.append({
                "probe_classname": probe_name,
                "category": probe_name.split(".")[0],
                "passed": data["passed"],
                "failed": data["failed"],
                "total": total,
                "pass_rate": round(pass_rate, 1),
                "goal": data.get("goal"),
                "security": metadata,
            })

        # Apply optional filter
        if probe_filter:
            pf = probe_filter.lower()
            probe_results = [
                p for p in probe_results
                if pf in p["probe_classname"].lower()
                or pf in p["security"]["category"].lower()
            ]

        # Sort: worst pass rate first
        probe_results.sort(key=lambda p: p["pass_rate"])

        # Paginate
        total_probes = len(probe_results)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "scan_id": scan_id,
            "total_probes": total_probes,
            "page": page,
            "page_size": page_size,
            "probes": probe_results[start:end],
        }

    def get_probe_attempts(
        self,
        scan_id: str,
        probe_classname: str,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Optional[Dict[str, Any]]:
        """Get individual test attempts for a specific probe.

        Uses cached JSONL entries when available.
        """
        from services.probe_knowledge import get_probe_metadata

        entries = self._get_report_entries(scan_id)
        if entries is None:
            return None

        # First pass: count totals (before any status filter)
        total_passed = 0
        total_failed = 0
        all_attempts = []
        for entry in entries:
            if entry.get("entry_type") != "attempt":
                continue
            if entry.get("probe_classname") != probe_classname:
                continue

            status_val = entry.get("status")
            status_str = "failed" if status_val == 1 else "passed" if status_val == 2 else "unknown"

            if status_str == "passed":
                total_passed += 1
            elif status_str == "failed":
                total_failed += 1

            if status_filter and status_str != status_filter:
                continue

            all_attempts.append({
                "uuid": entry.get("uuid", ""),
                "seq": entry.get("seq", 0),
                "status": status_str,
                "prompt_text": self._extract_prompt_text(entry),
                "output_text": self._extract_output_text(entry),
                "all_outputs": self._extract_all_outputs(entry),
                "triggers": entry.get("notes", {}).get("triggers") if isinstance(entry.get("notes"), dict) else [],
                "detector_results": entry.get("detector_results", {}),
                "goal": entry.get("goal"),
            })

        metadata = get_probe_metadata(probe_classname)

        filtered_total = len(all_attempts)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "scan_id": scan_id,
            "probe_classname": probe_classname,
            "security": metadata,
            "total_attempts": total_passed + total_failed,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "filtered_total": filtered_total,
            "page": page,
            "page_size": page_size,
            "attempts": all_attempts[start:end],
        }

    # ------------------------------------------------------------------
    # Materialized probe stats
    # ------------------------------------------------------------------

    def _compute_probe_stats(self, scan_id: str) -> Optional[Dict[str, Dict[str, int]]]:
        """Compute per-category probe stats from JSONL entries.

        Returns dict like: {"dan": {"passed": 10, "failed": 3}, ...}
        Returns None if JSONL is unavailable.
        """
        entries = self._get_report_entries(scan_id)
        if not entries:
            return None

        stats: Dict[str, Dict[str, int]] = {}
        for entry in entries:
            if entry.get("entry_type") != "attempt":
                continue
            probe_name = entry.get("probe_classname", "unknown")
            category = probe_name.split(".")[0]
            if category not in stats:
                stats[category] = {"passed": 0, "failed": 0}
            status_val = entry.get("status")
            if status_val == 2:
                stats[category]["passed"] += 1
            elif status_val == 1:
                stats[category]["failed"] += 1
        return stats if stats else None

    def _get_materialized_probe_stats(self, scan_id: str) -> Optional[Dict[str, Dict[str, int]]]:
        """Get probe stats for a scan, using DB-materialized data when available.

        On first access, computes from JSONL and stores in DB for future use.
        """
        # Check DB for pre-computed stats
        if _db_available():
            try:
                from database.session import get_db
                from database.models import Scan
                with get_db() as db:
                    row = db.query(Scan.probe_stats_json).filter_by(id=scan_id).first()
                    if row and row[0]:
                        return json.loads(row[0])
            except Exception as e:
                logger.debug(f"Failed to read materialized probe stats for {scan_id}: {e}")

        # Compute from JSONL
        stats = self._compute_probe_stats(scan_id)
        if stats is None:
            return None

        # Materialize to DB for next time
        if _db_available():
            try:
                from database.session import get_db
                from database.models import Scan
                with get_db() as db:
                    row = db.query(Scan).filter_by(id=scan_id).first()
                    if row and not row.probe_stats_json:
                        row.probe_stats_json = json.dumps(stats)
                        db.commit()
            except Exception as e:
                logger.debug(f"Failed to materialize probe stats for {scan_id}: {e}")

        return stats

    # ------------------------------------------------------------------
    # Aggregate statistics
    # ------------------------------------------------------------------

    def get_scan_statistics(self, days: int = 30, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Compute aggregate statistics across scans.

        Args:
            days: Number of days of daily trend data to return.
            tenant_id: If provided, only include scans belonging to this
                       tenant. If None, aggregate all scans.
        """
        all_scans = self.get_all_scans(tenant_id=tenant_id)

        # --- Counters ---
        status_counts: Dict[str, int] = {
            "completed": 0, "failed": 0, "cancelled": 0, "running": 0, "pending": 0,
        }
        total_passed = 0
        total_failed = 0
        pass_rates: List[float] = []

        # For probe failure aggregation we need JSONL data from completed scans
        probe_agg: Dict[str, Dict[str, int]] = {}  # category → {passed, failed}

        # For target breakdown
        target_agg: Dict[str, Dict[str, Any]] = {}  # "type::name" → {scan_count, pass_rates, last_scanned}

        # For daily trends
        from collections import defaultdict
        daily: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"scan_count": 0, "total_passed": 0, "total_failed": 0, "pass_rates": []}
        )

        for scan in all_scans:
            status = scan.get("status", "unknown").lower()
            status_counts[status] = status_counts.get(status, 0) + 1

            passed = scan.get("passed", 0)
            failed = scan.get("failed", 0)
            total_passed += passed
            total_failed += failed

            scan_total = passed + failed
            if scan_total > 0 and status == "completed":
                rate = (passed / scan_total) * 100.0
                pass_rates.append(rate)

            # Daily trend
            started_at = scan.get("started_at", "")
            if started_at:
                try:
                    day_key = datetime.fromisoformat(started_at).strftime("%Y-%m-%d")
                    daily[day_key]["scan_count"] += 1
                    daily[day_key]["total_passed"] += passed
                    daily[day_key]["total_failed"] += failed
                    if scan_total > 0:
                        daily[day_key]["pass_rates"].append((passed / scan_total) * 100.0)
                except (ValueError, TypeError):
                    pass

            # Target breakdown
            t_type = scan.get("target_type", "unknown")
            t_name = scan.get("target_name", "unknown")
            key = f"{t_type}::{t_name}"
            if key not in target_agg:
                target_agg[key] = {
                    "target_type": t_type,
                    "target_name": t_name,
                    "scan_count": 0,
                    "pass_rates": [],
                    "last_scanned": started_at,
                }
            target_agg[key]["scan_count"] += 1
            if scan_total > 0 and status == "completed":
                target_agg[key]["pass_rates"].append((passed / scan_total) * 100.0)
            if started_at and started_at > (target_agg[key]["last_scanned"] or ""):
                target_agg[key]["last_scanned"] = started_at

            # Probe failure aggregation (only for completed scans with reports)
            if status == "completed":
                scan_id = scan.get("scan_id", "")
                probe_stats = self._get_materialized_probe_stats(scan_id)
                if probe_stats:
                    for category, counts in probe_stats.items():
                        if category not in probe_agg:
                            probe_agg[category] = {"passed": 0, "failed": 0}
                        probe_agg[category]["passed"] += counts.get("passed", 0)
                        probe_agg[category]["failed"] += counts.get("failed", 0)

        # --- Build response ---
        total_tests = total_passed + total_failed
        overall_pass_rate = (total_passed / total_tests * 100.0) if total_tests > 0 else 0.0

        avg_pass_rate = (sum(pass_rates) / len(pass_rates)) if pass_rates else 0.0
        min_pass_rate = min(pass_rates) if pass_rates else None
        max_pass_rate = max(pass_rates) if pass_rates else None

        # Daily trends (last N days, sorted ascending)
        today = datetime.now()
        trend_points = []
        for i in range(days - 1, -1, -1):
            from datetime import timedelta
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            d = daily.get(day, {"scan_count": 0, "total_passed": 0, "total_failed": 0, "pass_rates": []})
            rates = d["pass_rates"] if isinstance(d.get("pass_rates"), list) else []
            trend_points.append({
                "date": day,
                "scan_count": d["scan_count"],
                "total_passed": d["total_passed"],
                "total_failed": d["total_failed"],
                "avg_pass_rate": round(sum(rates) / len(rates), 1) if rates else 0.0,
            })

        # Top failing probes (sorted by failure count descending, top 10)
        top_probes = []
        for category, counts in probe_agg.items():
            cat_total = counts["passed"] + counts["failed"]
            if cat_total > 0:
                top_probes.append({
                    "probe_category": category,
                    "failure_count": counts["failed"],
                    "total_count": cat_total,
                    "failure_rate": round(counts["failed"] / cat_total * 100.0, 1),
                })
        top_probes.sort(key=lambda p: p["failure_count"], reverse=True)

        # Target breakdown (sorted by scan count descending)
        targets = []
        for info in target_agg.values():
            rates = info.pop("pass_rates", [])
            info["avg_pass_rate"] = round(sum(rates) / len(rates), 1) if rates else 0.0
            targets.append(info)
        targets.sort(key=lambda t: t["scan_count"], reverse=True)

        return {
            "total_scans": len(all_scans),
            "completed_scans": status_counts.get("completed", 0),
            "failed_scans": status_counts.get("failed", 0),
            "cancelled_scans": status_counts.get("cancelled", 0),
            "running_scans": status_counts.get("running", 0) + status_counts.get("pending", 0),
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "overall_pass_rate": round(overall_pass_rate, 1),
            "avg_pass_rate": round(avg_pass_rate, 1),
            "min_pass_rate": round(min_pass_rate, 1) if min_pass_rate is not None else None,
            "max_pass_rate": round(max_pass_rate, 1) if max_pass_rate is not None else None,
            "daily_trends": trend_points,
            "top_failing_probes": top_probes[:10],
            "target_breakdown": targets,
        }

    def _calculate_pass_rate(self, scan_info: Dict[str, Any]) -> float:
        passed = scan_info.get("passed", 0)
        failed = scan_info.get("failed", 0)
        total = passed + failed
        if total == 0:
            return 0.0
        return (passed / total) * 100.0

    def _extract_digest(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Extract just the digest entry from a JSONL report file.

        This is used when scan_info comes from the DB (which doesn't
        store digest).  Since _build_results output is cached, this
        only runs once per scan.
        """
        entries = self._get_report_entries(scan_id)
        if entries is None:
            return None
        for entry in entries:
            if entry.get("entry_type") == "digest":
                return entry.get("eval", {})
        return None

    def _extract_config(
        self, scan_id: str, scan_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Reconstruct scan config from JSONL first entry or scan_info fields.

        Tries the JSONL first entry (which has the full garak config),
        then falls back to top-level target_type/target_name from scan_info.
        """
        # Try JSONL first entry
        entries = self._get_report_entries(scan_id)
        if entries:
            first = entries[0]
            probe_spec = first.get("plugins.probe_spec", "")
            probes = [probe_spec] if probe_spec else []
            return {
                "target_type": first.get("plugins.target_type", "unknown"),
                "target_name": first.get("plugins.target_name", "unknown"),
                "probes": probes,
                "generations": first.get("run.generations"),
                "eval_threshold": first.get("run.eval_threshold"),
            }

        # Fallback: use top-level fields from scan_info (DB row)
        target_type = scan_info.get("target_type")
        target_name = scan_info.get("target_name")
        if target_type or target_name:
            return {
                "target_type": target_type or "unknown",
                "target_name": target_name or "unknown",
                "probes": None,
                "generations": None,
                "eval_threshold": None,
            }

        return None


# Global instance
try:
    garak_wrapper = GarakWrapper()
except Exception:
    garak_wrapper = GarakWrapper()
