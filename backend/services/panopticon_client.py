"""
Panopticon client — emit trace events for scan lifecycle observability.

Design principles:
  - **Fire-and-forget:** Panopticon unavailability NEVER blocks scans.
  - **Batch buffering:** Events are buffered in memory and flushed
    periodically or when the buffer reaches ``batch_size``.
  - **Span hierarchy:** scan trace → probe spans → (future) LLM call spans.
  - **Tenant mapping:** ``project_id = tenant_id`` for per-project isolation.

Trace lifecycle:
  1. ``scan_started``  — root span opened when scan begins
  2. ``probe_running``  — child span opened per probe
  3. ``probe_completed`` — child span closed with pass/fail stats
  4. ``scan_completed`` — root span closed with final stats
  5. ``scan_failed``   — root span closed with error info
  6. ``security_flag``  — emitted when a critical finding is detected

All functions are synchronous (called from Celery worker context).
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class PanopticonClient:
    """Non-blocking trace emitter for the Panopticon observability platform.

    All public methods catch exceptions and log warnings rather than
    propagating — a Panopticon outage must never break scan execution.
    """

    def __init__(
        self,
        url: str = "",
        api_key: str = "",
        timeout: float = 5.0,
        batch_size: int = 50,
        enabled: bool = False,
    ):
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._batch_size = batch_size
        self._enabled = enabled
        self._buffer: list[dict] = []
        self._active_traces: dict[str, dict] = {}  # scan_id → trace metadata

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._url)

    # ------------------------------------------------------------------
    # Public API — scan lifecycle
    # ------------------------------------------------------------------

    def scan_started(
        self,
        scan_id: str,
        tenant_id: str,
        config: Optional[dict] = None,
    ) -> str:
        """Emit a scan_started event (opens the root trace span).

        Returns the trace_id for correlation with child spans.
        """
        trace_id = uuid.uuid4().hex
        self._active_traces[scan_id] = {
            "trace_id": trace_id,
            "tenant_id": tenant_id,
            "started_at": time.time(),
        }
        self._emit({
            "event": "scan_started",
            "trace_id": trace_id,
            "span_id": trace_id,  # root span = trace
            "project_id": tenant_id,
            "scan_id": scan_id,
            "timestamp": _now_iso(),
            "attributes": {
                "model_type": (config or {}).get("model_type", ""),
                "model_name": (config or {}).get("model_name", ""),
                "probe_count": len((config or {}).get("probes", [])),
            },
        })
        return trace_id

    def probe_running(
        self,
        scan_id: str,
        probe_name: str,
    ) -> str:
        """Emit a probe_running event (opens a child span).

        Returns the span_id for the probe span.
        """
        trace = self._active_traces.get(scan_id, {})
        span_id = uuid.uuid4().hex[:16]
        self._emit({
            "event": "probe_running",
            "trace_id": trace.get("trace_id", ""),
            "span_id": span_id,
            "parent_span_id": trace.get("trace_id", ""),
            "project_id": trace.get("tenant_id", ""),
            "scan_id": scan_id,
            "probe_name": probe_name,
            "timestamp": _now_iso(),
        })
        return span_id

    def probe_completed(
        self,
        scan_id: str,
        probe_name: str,
        passed: int = 0,
        failed: int = 0,
        duration_ms: float = 0.0,
    ) -> None:
        """Emit a probe_completed event (closes the probe span)."""
        trace = self._active_traces.get(scan_id, {})
        self._emit({
            "event": "probe_completed",
            "trace_id": trace.get("trace_id", ""),
            "project_id": trace.get("tenant_id", ""),
            "scan_id": scan_id,
            "probe_name": probe_name,
            "timestamp": _now_iso(),
            "attributes": {
                "passed": passed,
                "failed": failed,
                "duration_ms": duration_ms,
            },
        })

    def scan_completed(
        self,
        scan_id: str,
        passed: int = 0,
        failed: int = 0,
    ) -> None:
        """Emit a scan_completed event (closes the root trace span)."""
        trace = self._active_traces.pop(scan_id, {})
        duration = time.time() - trace.get("started_at", time.time())
        self._emit({
            "event": "scan_completed",
            "trace_id": trace.get("trace_id", ""),
            "project_id": trace.get("tenant_id", ""),
            "scan_id": scan_id,
            "timestamp": _now_iso(),
            "attributes": {
                "passed": passed,
                "failed": failed,
                "duration_s": round(duration, 2),
            },
        })
        self._flush()

    def scan_failed(
        self,
        scan_id: str,
        error_message: str = "",
    ) -> None:
        """Emit a scan_failed event (closes the root trace span with error)."""
        trace = self._active_traces.pop(scan_id, {})
        duration = time.time() - trace.get("started_at", time.time())
        self._emit({
            "event": "scan_failed",
            "trace_id": trace.get("trace_id", ""),
            "project_id": trace.get("tenant_id", ""),
            "scan_id": scan_id,
            "timestamp": _now_iso(),
            "attributes": {
                "error": error_message[:500],
                "duration_s": round(duration, 2),
            },
        })
        self._flush()

    def security_flag(
        self,
        scan_id: str,
        flag_type: str,
        probe_name: str,
        severity: str = "high",
        details: str = "",
    ) -> None:
        """Emit a security flag event (critical finding detected)."""
        trace = self._active_traces.get(scan_id, {})
        self._emit({
            "event": "security_flag",
            "trace_id": trace.get("trace_id", ""),
            "project_id": trace.get("tenant_id", ""),
            "scan_id": scan_id,
            "timestamp": _now_iso(),
            "attributes": {
                "flag_type": flag_type,
                "probe_name": probe_name,
                "severity": severity,
                "details": details[:500],
            },
        })

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, event: dict) -> None:
        """Buffer an event. Flushes automatically when batch is full."""
        if not self.enabled:
            return
        self._buffer.append(event)
        if len(self._buffer) >= self._batch_size:
            self._flush()

    def _flush(self) -> None:
        """Send buffered events to Panopticon.

        Best-effort: failures are logged, never raised.
        """
        if not self._buffer:
            return

        batch = self._buffer[:]
        self._buffer.clear()

        if not self.enabled:
            return

        try:
            import httpx
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._url}/api/v1/ingest/traces",
                    json={"events": batch},
                    headers=headers,
                )
                if resp.status_code >= 400:
                    logger.warning(
                        "Panopticon ingest returned %d: %s",
                        resp.status_code, resp.text[:200],
                    )
                else:
                    logger.debug("Flushed %d events to Panopticon", len(batch))
        except Exception as e:
            logger.warning("Panopticon flush failed (non-critical): %s", e)

    def get_buffered_count(self) -> int:
        """Return the number of buffered events (for testing)."""
        return len(self._buffer)


def _now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_panopticon_client: Optional[PanopticonClient] = None


def get_panopticon_client() -> PanopticonClient:
    """Get or create the Panopticon client singleton.

    Reads settings on first call. Returns a disabled client if
    Panopticon is not configured.
    """
    global _panopticon_client
    if _panopticon_client is None:
        try:
            from config import settings
            _panopticon_client = PanopticonClient(
                url=settings.panopticon_url,
                api_key=settings.panopticon_api_key,
                timeout=settings.panopticon_timeout,
                batch_size=settings.panopticon_batch_size,
                enabled=settings.panopticon_enabled,
            )
        except Exception:
            _panopticon_client = PanopticonClient(enabled=False)
    return _panopticon_client
