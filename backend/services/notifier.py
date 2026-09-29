"""
Webhook notification service.

Fires HTTP POST notifications to registered webhook URLs on events:
  - scan_complete: scan finished successfully
  - scan_failed: scan encountered an error
  - regression_detected: pass rate dropped vs previous scan
  - gate_failed: CI/CD gate verdict is "fail"
  - campaign_complete: all campaign scans finished

Notifications are tenant-scoped and fire asynchronously (best-effort).
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class WebhookConfig:
    """A registered webhook endpoint."""

    def __init__(self, webhook_id: str, tenant_id: str, url: str,
                 events: list, name: str = "", secret: str = "",
                 enabled: bool = True, created_at: str = ""):
        self.webhook_id = webhook_id
        self.tenant_id = tenant_id
        self.url = url
        self.events = events  # e.g. ["scan_complete", "gate_failed"]
        self.name = name
        self.secret = secret
        self.enabled = enabled
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "webhook_id": self.webhook_id,
            "tenant_id": self.tenant_id,
            "url": self.url,
            "events": self.events,
            "name": self.name,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


class NotificationService:
    """Manages webhook registrations and fires notifications."""

    def __init__(self):
        self._webhooks: dict[str, WebhookConfig] = {}

    def register_webhook(self, tenant_id: str, payload: dict) -> dict:
        """Register a new webhook endpoint."""
        url = payload.get("url")
        if not url:
            raise ValueError("url is required")

        webhook_id = f"hook_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        wh = WebhookConfig(
            webhook_id=webhook_id,
            tenant_id=tenant_id,
            url=url,
            events=payload.get("events", ["scan_complete"]),
            name=payload.get("name", ""),
            secret=payload.get("secret", ""),
            enabled=payload.get("enabled", True),
            created_at=now,
        )
        self._webhooks[webhook_id] = wh
        logger.info(f"Registered webhook {webhook_id} for tenant {tenant_id}: {url}")
        return wh.to_dict()

    def list_webhooks(self, tenant_id: str) -> list[dict]:
        """List all webhooks for a tenant."""
        return [
            wh.to_dict() for wh in self._webhooks.values()
            if wh.tenant_id == tenant_id
        ]

    def delete_webhook(self, tenant_id: str, webhook_id: str) -> bool:
        """Delete a webhook (tenant-scoped)."""
        wh = self._webhooks.get(webhook_id)
        if wh and wh.tenant_id == tenant_id:
            del self._webhooks[webhook_id]
            return True
        return False

    async def fire(self, tenant_id: str, event_type: str, payload: dict) -> list[dict]:
        """Fire notifications for an event to all matching webhooks.

        Returns list of delivery results.
        """
        results = []

        matching = [
            wh for wh in self._webhooks.values()
            if wh.tenant_id == tenant_id
            and wh.enabled
            and event_type in wh.events
        ]

        if not matching:
            return results

        notification = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "data": payload,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            for wh in matching:
                delivery = {
                    "webhook_id": wh.webhook_id,
                    "url": wh.url,
                    "event": event_type,
                }
                try:
                    headers = {"Content-Type": "application/json"}
                    if wh.secret:
                        import hashlib
                        import hmac
                        body_bytes = json.dumps(notification).encode()
                        sig = hmac.new(
                            wh.secret.encode(), body_bytes, hashlib.sha256
                        ).hexdigest()
                        headers["X-Webhook-Signature"] = f"sha256={sig}"

                    resp = await client.post(wh.url, json=notification, headers=headers)
                    delivery["status"] = "delivered"
                    delivery["http_status"] = resp.status_code
                except Exception as e:
                    delivery["status"] = "failed"
                    delivery["error"] = str(e)
                    logger.warning(f"Webhook delivery failed for {wh.webhook_id}: {e}")

                results.append(delivery)

        return results


# Module-level singleton
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create the NotificationService singleton."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
