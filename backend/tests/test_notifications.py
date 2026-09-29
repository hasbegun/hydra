"""
Tests for Phase 3 Week 9: Webhook notification service.
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def svc():
    from services.notifier import NotificationService
    return NotificationService()


class TestWebhookRegistration:
    """Test webhook CRUD."""

    def test_register_webhook(self, svc):
        result = svc.register_webhook("t1", {
            "url": "https://hooks.slack.com/abc",
            "events": ["scan_complete", "gate_failed"],
            "name": "Slack Alert",
        })
        assert result["webhook_id"].startswith("hook_")
        assert result["url"] == "https://hooks.slack.com/abc"
        assert "scan_complete" in result["events"]

    def test_register_webhook_missing_url(self, svc):
        with pytest.raises(ValueError, match="url is required"):
            svc.register_webhook("t1", {"events": ["scan_complete"]})

    def test_list_webhooks_tenant_scoped(self, svc):
        svc.register_webhook("t1", {"url": "https://t1.hook"})
        svc.register_webhook("t2", {"url": "https://t2.hook"})
        assert len(svc.list_webhooks("t1")) == 1
        assert len(svc.list_webhooks("t2")) == 1

    def test_delete_webhook(self, svc):
        created = svc.register_webhook("t1", {"url": "https://del.hook"})
        assert svc.delete_webhook("t1", created["webhook_id"]) is True
        assert len(svc.list_webhooks("t1")) == 0

    def test_delete_webhook_cross_tenant_denied(self, svc):
        created = svc.register_webhook("t1", {"url": "https://private.hook"})
        assert svc.delete_webhook("t2", created["webhook_id"]) is False


class TestNotificationFiring:
    """Test webhook notification delivery."""

    @pytest.mark.asyncio
    async def test_webhook_fires_on_scan_complete(self, svc):
        """scan_complete event -> POST to registered URL."""
        svc.register_webhook("t1", {
            "url": "https://hooks.example.com/scan",
            "events": ["scan_complete"],
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await svc.fire("t1", "scan_complete", {
                "scan_id": "scan-123",
                "status": "completed",
                "pass_rate": 95.0,
            })

        assert len(results) == 1
        assert results[0]["status"] == "delivered"
        assert results[0]["http_status"] == 200

    @pytest.mark.asyncio
    async def test_webhook_fires_on_regression(self, svc):
        """regression_detected event fires webhook."""
        svc.register_webhook("t1", {
            "url": "https://hooks.example.com/alert",
            "events": ["regression_detected"],
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await svc.fire("t1", "regression_detected", {
                "scan_id": "scan-456",
                "pass_rate_delta": -10.0,
            })

        assert len(results) == 1
        assert results[0]["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_webhook_fires_on_gate_failure(self, svc):
        """gate_failed event fires webhook."""
        svc.register_webhook("t1", {
            "url": "https://hooks.example.com/gate",
            "events": ["gate_failed"],
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await svc.fire("t1", "gate_failed", {
                "scan_id": "gate-789",
                "reasons": ["Pass rate below threshold"],
            })

        assert len(results) == 1
        assert results[0]["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_webhook_scoped_to_tenant(self, svc):
        """Only tenant's own webhooks fire."""
        svc.register_webhook("t1", {
            "url": "https://t1.hook",
            "events": ["scan_complete"],
        })
        svc.register_webhook("t2", {
            "url": "https://t2.hook",
            "events": ["scan_complete"],
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await svc.fire("t1", "scan_complete", {"scan_id": "s1"})

        # Only t1's webhook should fire
        assert len(results) == 1
        assert results[0]["url"] == "https://t1.hook"

    @pytest.mark.asyncio
    async def test_webhook_no_match_no_fire(self, svc):
        """No matching webhooks -> empty results."""
        svc.register_webhook("t1", {
            "url": "https://hook.example.com",
            "events": ["scan_complete"],
        })

        results = await svc.fire("t1", "gate_failed", {"data": "test"})
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_webhook_delivery_failure_handled(self, svc):
        """Failed delivery reported but doesn't crash."""
        svc.register_webhook("t1", {
            "url": "https://unreachable.invalid",
            "events": ["scan_complete"],
        })

        with patch("httpx.AsyncClient") as mock_client:
            ctx = AsyncMock()
            ctx.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await svc.fire("t1", "scan_complete", {"scan_id": "s1"})

        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "Connection refused" in results[0]["error"]

    def test_webhook_to_dict_excludes_secret(self, svc):
        """Webhook to_dict never includes the secret."""
        result = svc.register_webhook("t1", {
            "url": "https://hook.example.com",
            "secret": "super-secret-key",
        })
        assert "secret" not in result
