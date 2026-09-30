"""
Phase 5 Week 14 — Panopticon trace emission tests.

Tests the trace lifecycle, span hierarchy, fire-and-forget resilience,
project-to-tenant mapping, and security flag emission.
"""
import sys
import os
from unittest.mock import MagicMock, patch, call
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.panopticon_client import PanopticonClient, get_panopticon_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(enabled: bool = True, batch_size: int = 50) -> PanopticonClient:
    """Create a test Panopticon client (no real HTTP)."""
    return PanopticonClient(
        url="http://panopticon-test:8080",
        api_key="test-key",
        timeout=1.0,
        batch_size=batch_size,
        enabled=enabled,
    )


# ===================================================================
# Trace Lifecycle
# ===================================================================

class TestTraceLifecycle:
    def test_scan_started_emits_event(self):
        """scan_started buffers an event with correct fields."""
        client = _make_client()
        trace_id = client.scan_started("scan-1", "tenant-a", {"model_name": "gpt4"})
        assert isinstance(trace_id, str)
        assert len(trace_id) == 32  # hex UUID
        assert client.get_buffered_count() == 1

    def test_scan_completed_emits_event(self):
        """scan_completed buffers event and flushes."""
        client = _make_client()
        client.scan_started("scan-1", "tenant-a")
        client.scan_completed("scan-1", passed=10, failed=5)
        # Flush happens on scan_completed, buffer should be empty
        # (but without httpx it won't actually send, just clears buffer)
        assert client.get_buffered_count() == 0

    def test_scan_failed_emits_event(self):
        """scan_failed buffers event with error info."""
        client = _make_client()
        client.scan_started("scan-1", "tenant-a")
        client.scan_failed("scan-1", error_message="Connection lost")
        assert client.get_buffered_count() == 0  # flushed

    def test_probe_running_emits_child_span(self):
        """probe_running creates a child span with parent trace_id."""
        client = _make_client()
        trace_id = client.scan_started("scan-1", "tenant-a")
        span_id = client.probe_running("scan-1", "dan.Dan_11_0")
        assert isinstance(span_id, str)
        assert len(span_id) == 16
        assert client.get_buffered_count() == 2  # started + probe_running

    def test_probe_completed_emits_stats(self):
        """probe_completed includes pass/fail counts."""
        client = _make_client()
        client.scan_started("scan-1", "tenant-a")
        client.probe_running("scan-1", "dan.Dan_11_0")
        client.probe_completed("scan-1", "dan.Dan_11_0", passed=8, failed=2)
        assert client.get_buffered_count() == 3

    def test_full_scan_lifecycle(self):
        """Complete scan lifecycle: start → probes → complete."""
        client = _make_client()
        client.scan_started("scan-1", "tenant-a", {"probes": ["p1", "p2"]})
        client.probe_running("scan-1", "p1")
        client.probe_completed("scan-1", "p1", passed=10, failed=0)
        client.probe_running("scan-1", "p2")
        client.probe_completed("scan-1", "p2", passed=5, failed=5)
        client.scan_completed("scan-1", passed=15, failed=5)
        # All events flushed on completion
        assert client.get_buffered_count() == 0


# ===================================================================
# Project-Tenant Mapping
# ===================================================================

class TestProjectTenantMapping:
    def test_project_id_matches_tenant_id(self):
        """Trace project_id == scan's tenant_id."""
        client = _make_client(batch_size=100)  # Large batch to inspect buffer
        client.scan_started("scan-1", "tenant-xyz", {})
        event = client._buffer[0]
        assert event["project_id"] == "tenant-xyz"

    def test_probe_inherits_tenant_from_trace(self):
        """Probe span inherits project_id from the parent trace."""
        client = _make_client(batch_size=100)
        client.scan_started("scan-1", "tenant-abc")
        client.probe_running("scan-1", "dan.Dan_11_0")
        probe_event = client._buffer[1]
        assert probe_event["project_id"] == "tenant-abc"

    def test_completed_event_has_tenant(self):
        """scan_completed includes correct project_id."""
        client = _make_client(batch_size=100)
        client.scan_started("scan-1", "tenant-abc")
        # scan_completed will flush, so we patch _flush to keep events
        original_flush = client._flush
        client._flush = lambda: None
        client.scan_completed("scan-1", passed=5, failed=0)
        complete_event = client._buffer[-1]
        assert complete_event["project_id"] == "tenant-abc"
        client._flush = original_flush


# ===================================================================
# Security Flags
# ===================================================================

class TestSecurityFlags:
    def test_security_flag_emitted(self):
        """Critical finding → security flag in buffer."""
        client = _make_client(batch_size=100)
        client.scan_started("scan-1", "tenant-a")
        client.security_flag(
            "scan-1", "jailbreak", "dan.Dan_11_0",
            severity="critical", details="7 failures detected",
        )
        flag_event = client._buffer[-1]
        assert flag_event["event"] == "security_flag"
        assert flag_event["attributes"]["flag_type"] == "jailbreak"
        assert flag_event["attributes"]["severity"] == "critical"

    def test_security_flag_includes_probe_name(self):
        """Flag event includes the probe that triggered it."""
        client = _make_client(batch_size=100)
        client.scan_started("scan-1", "tenant-a")
        client.security_flag("scan-1", "prompt_injection", "encoding.InjectBase64")
        flag_event = client._buffer[-1]
        assert flag_event["attributes"]["probe_name"] == "encoding.InjectBase64"


# ===================================================================
# Fire-and-Forget Resilience
# ===================================================================

class TestResilience:
    def test_disabled_client_does_not_buffer(self):
        """When disabled, no events are buffered."""
        client = _make_client(enabled=False)
        client.scan_started("scan-1", "tenant-a")
        assert client.get_buffered_count() == 0

    def test_flush_failure_does_not_raise(self):
        """HTTP failure during flush → logged, not raised."""
        client = _make_client()
        client.scan_started("scan-1", "tenant-a")

        with patch("httpx.Client") as mock_httpx:
            mock_ctx = MagicMock()
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.side_effect = ConnectionError("Panopticon unreachable")

            # Should not raise
            client._flush()
            assert client.get_buffered_count() == 0  # Buffer cleared even on failure

    def test_panopticon_unavailable_doesnt_block_scan(self):
        """Panopticon down → scan task still works (no exception propagation)."""
        from tasks.scan_task import _process_sse_event

        scan_state = {
            "status": "running", "passed": 0, "failed": 0,
            "total_probes": 0, "progress": 0.0, "current_probe": None,
            "error_message": None, "started_at": "", "completed_at": None,
            "report_path": None, "html_report_path": None,
            "report_key": None, "html_report_key": None,
        }

        # Mock panopticon to raise
        with patch("services.panopticon_client.get_panopticon_client") as mock_pano:
            mock_client = MagicMock()
            mock_client.enabled = True
            mock_client.probe_running.side_effect = Exception("Panopticon crash")
            mock_pano.return_value = mock_client

            event = {"event_type": "progress", "probe": "dan.Dan_11_0", "percent": 50}
            # Should not raise — the try/except in _process_sse_event catches it
            _process_sse_event("scan-1", "t1", event, scan_state, {}, "", db_config={})
            assert scan_state["current_probe"] == "dan.Dan_11_0"
            assert scan_state["progress"] == 50.0


# ===================================================================
# Batch Flushing
# ===================================================================

class TestBatching:
    def test_auto_flush_at_batch_size(self):
        """Buffer flushes automatically when batch_size is reached."""
        client = _make_client(batch_size=3)
        # Emit 3 events — should trigger auto-flush
        client.scan_started("scan-1", "t1")
        client.probe_running("scan-1", "p1")
        client.probe_completed("scan-1", "p1")  # This is the 3rd event → flush
        # Buffer cleared after flush (even without real HTTP)
        assert client.get_buffered_count() == 0

    def test_manual_flush_clears_buffer(self):
        """_flush clears the buffer."""
        client = _make_client(batch_size=100)
        client.scan_started("scan-1", "t1")
        assert client.get_buffered_count() == 1
        client._flush()
        assert client.get_buffered_count() == 0


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_panopticon_client_returns_instance(self):
        """get_panopticon_client returns a PanopticonClient."""
        import services.panopticon_client as mod
        mod._panopticon_client = None  # reset singleton

        mock_settings = MagicMock()
        mock_settings.panopticon_enabled = False
        mock_settings.panopticon_url = "http://test:8080"
        mock_settings.panopticon_api_key = ""
        mock_settings.panopticon_timeout = 5.0
        mock_settings.panopticon_batch_size = 50

        with patch.dict("sys.modules", {}), \
             patch("config.settings", mock_settings):
            # Reset and get fresh client
            mod._panopticon_client = None
            client = get_panopticon_client()
            assert isinstance(client, PanopticonClient)
            assert not client.enabled  # panopticon_enabled=False

        # Clean up
        mod._panopticon_client = None


# ===================================================================
# Span Hierarchy
# ===================================================================

class TestSpanHierarchy:
    def test_probe_span_has_parent(self):
        """Probe span references the root trace as parent."""
        client = _make_client(batch_size=100)
        trace_id = client.scan_started("scan-1", "t1")
        client.probe_running("scan-1", "p1")
        probe_event = client._buffer[1]
        assert probe_event["parent_span_id"] == trace_id
        assert probe_event["trace_id"] == trace_id

    def test_scan_completed_includes_duration(self):
        """scan_completed event includes duration_s."""
        client = _make_client(batch_size=100)
        client.scan_started("scan-1", "t1")
        time.sleep(0.05)  # Small delay for measurable duration
        client._flush = lambda: None  # Prevent flush to inspect buffer
        client.scan_completed("scan-1")
        complete_event = client._buffer[-1]
        assert "duration_s" in complete_event["attributes"]
        assert complete_event["attributes"]["duration_s"] >= 0.0
