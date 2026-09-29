"""
Prism SMPC secret-sharing client.

Provides ``PrismClient`` — an async/sync HTTP wrapper for the Prism
service. All data is base64-encoded before storage and SHA-256 integrity
is verified on fetch.

Key format: ``{tenant_id}/{key}`` — tenant prefix is enforced by the
client to guarantee data isolation.

Usage::

    client = PrismClient()
    await client.store("tenant-a", "report:abc:jsonl", b"data")
    data = await client.fetch("tenant-a", "report:abc:jsonl")
    await client.delete("tenant-a", "report:abc:jsonl")
"""
import base64
import hashlib
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class PrismError(Exception):
    """Base exception for Prism operations."""


class PrismIntegrityError(PrismError):
    """SHA-256 integrity check failed on fetch."""


class PrismAccessDenied(PrismError):
    """Cross-tenant access denied by Prism."""


class PrismUnavailable(PrismError):
    """Prism service is unreachable."""


class PrismClient:
    """HTTP client for the Prism SMPC secret-sharing service.

    All public methods enforce tenant-prefixed keys so that tenant A
    cannot access tenant B's data.

    Provides both async and sync APIs. Sync variants (``*_sync``) are
    for use in Celery workers and other non-async contexts. The shared
    request-building and response-processing logic is in private helpers
    to avoid duplication between the two API surfaces.

    Args:
        base_url: Prism service base URL.
        api_key: Prism API key for authentication.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        from config import settings

        self._base_url = (base_url or settings.prism_url).rstrip("/")
        self._api_key = api_key or settings.prism_api_key
        self._timeout = timeout or settings.prism_timeout

    # ------------------------------------------------------------------
    # Shared helpers (no async/sync split)
    # ------------------------------------------------------------------

    def _full_key(self, tenant_id: str, key: str) -> str:
        """Build the full Prism key with tenant prefix."""
        return f"{tenant_id}/{key}"

    def _headers(self) -> dict:
        """Build HTTP headers for Prism requests."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-Prism-Key"] = self._api_key
        return headers

    @staticmethod
    def _compute_hash(data: bytes) -> str:
        """Compute SHA-256 hex digest of raw data."""
        return hashlib.sha256(data).hexdigest()

    def _build_store_payload(self, tenant_id: str, key: str, data: bytes) -> Tuple[str, dict]:
        """Build the store request payload. Returns (full_key, payload_dict)."""
        full_key = self._full_key(tenant_id, key)
        encoded = base64.b64encode(data).decode("ascii")
        sha256 = self._compute_hash(data)
        payload = {
            "key": full_key,
            "data": encoded,
            "sha256": sha256,
            "tenant_id": tenant_id,
        }
        return full_key, payload

    def _decode_fetch_response(self, full_key: str, body: dict) -> bytes:
        """Decode a Prism fetch response and verify integrity.

        Raises PrismIntegrityError on SHA-256 mismatch.
        """
        encoded = body.get("data", "")
        expected_hash = body.get("sha256", "")
        data = base64.b64decode(encoded)

        if expected_hash:
            actual_hash = self._compute_hash(data)
            if actual_hash != expected_hash:
                raise PrismIntegrityError(
                    f"SHA-256 mismatch for key '{full_key}': "
                    f"expected {expected_hash[:12]}..., got {actual_hash[:12]}..."
                )
        return data

    @staticmethod
    def _handle_error(e: Exception, operation: str, full_key: str):
        """Translate httpx exceptions into Prism-specific exceptions."""
        if isinstance(e, (PrismAccessDenied, PrismUnavailable, PrismIntegrityError)):
            raise
        if isinstance(e, httpx.ConnectError):
            raise PrismUnavailable(f"Prism unreachable: {e}") from e
        if isinstance(e, httpx.HTTPStatusError):
            raise PrismError(
                f"Prism {operation} failed ({e.response.status_code}): {e}"
            ) from e
        raise PrismUnavailable(f"Prism request failed: {e}") from e

    @staticmethod
    def _check_status(response: httpx.Response, full_key: str, operation: str):
        """Check response status for 403/404, raise_for_status otherwise.

        Returns:
            "not_found" if 404, None otherwise.
        """
        if response.status_code == 404:
            return "not_found"
        if response.status_code == 403:
            raise PrismAccessDenied(
                f"Access denied {operation} key '{full_key}'"
            )
        response.raise_for_status()
        return None

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------

    async def store(self, tenant_id: str, key: str, data: bytes) -> str:
        """Store data in Prism with base64 encoding and SHA-256 hash.

        Args:
            tenant_id: Tenant identifier (used as key prefix).
            key: Logical key (e.g. ``report:scan-id:jsonl``).
            data: Raw bytes to store.

        Returns:
            The full Prism key under which data was stored.

        Raises:
            PrismUnavailable: Prism service is unreachable.
            PrismError: Any other Prism error.
        """
        full_key, payload = self._build_store_payload(tenant_id, key, data)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = await client.put(
                    "/v1/secrets", json=payload, headers=self._headers(),
                )
                self._check_status(response, full_key, "storing")
        except Exception as e:
            self._handle_error(e, "store", full_key)

        logger.debug(f"Prism store: {full_key} ({len(data)} bytes)")
        return full_key

    async def fetch(self, tenant_id: str, key: str) -> Optional[bytes]:
        """Fetch data from Prism, decode base64, and verify SHA-256 integrity.

        Returns None if the key does not exist.

        Raises:
            PrismIntegrityError: SHA-256 mismatch (data corruption).
            PrismAccessDenied: Cross-tenant access denied.
            PrismUnavailable: Prism service is unreachable.
        """
        full_key = self._full_key(tenant_id, key)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = await client.get(
                    "/v1/secrets",
                    params={"key": full_key, "tenant_id": tenant_id},
                    headers=self._headers(),
                )
                result = self._check_status(response, full_key, "fetching")
                if result == "not_found":
                    return None
        except Exception as e:
            self._handle_error(e, "fetch", full_key)

        data = self._decode_fetch_response(full_key, response.json())
        logger.debug(f"Prism fetch: {full_key} ({len(data)} bytes)")
        return data

    async def delete(self, tenant_id: str, key: str) -> bool:
        """Delete a key from Prism. Returns True if deleted, False if not found.

        Raises:
            PrismAccessDenied: Cross-tenant delete denied.
            PrismUnavailable: Prism service is unreachable.
        """
        full_key = self._full_key(tenant_id, key)
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = await client.delete(
                    "/v1/secrets",
                    params={"key": full_key, "tenant_id": tenant_id},
                    headers=self._headers(),
                )
                result = self._check_status(response, full_key, "deleting")
                if result == "not_found":
                    return False
        except Exception as e:
            self._handle_error(e, "delete", full_key)

        logger.debug(f"Prism delete: {full_key}")
        return True

    async def health(self) -> bool:
        """Check if Prism service is reachable."""
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=5.0
            ) as client:
                response = await client.get("/health", headers=self._headers())
                return response.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Sync API (for Celery workers / non-async contexts)
    # ------------------------------------------------------------------

    def store_sync(self, tenant_id: str, key: str, data: bytes) -> str:
        """Synchronous version of ``store()``."""
        full_key, payload = self._build_store_payload(tenant_id, key, data)
        try:
            with httpx.Client(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = client.put(
                    "/v1/secrets", json=payload, headers=self._headers(),
                )
                self._check_status(response, full_key, "storing")
        except Exception as e:
            self._handle_error(e, "store", full_key)

        logger.debug(f"Prism store (sync): {full_key} ({len(data)} bytes)")
        return full_key

    def fetch_sync(self, tenant_id: str, key: str) -> Optional[bytes]:
        """Synchronous version of ``fetch()``."""
        full_key = self._full_key(tenant_id, key)
        try:
            with httpx.Client(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = client.get(
                    "/v1/secrets",
                    params={"key": full_key, "tenant_id": tenant_id},
                    headers=self._headers(),
                )
                result = self._check_status(response, full_key, "fetching")
                if result == "not_found":
                    return None
        except Exception as e:
            self._handle_error(e, "fetch", full_key)

        return self._decode_fetch_response(full_key, response.json())

    def delete_sync(self, tenant_id: str, key: str) -> bool:
        """Synchronous version of ``delete()``."""
        full_key = self._full_key(tenant_id, key)
        try:
            with httpx.Client(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = client.delete(
                    "/v1/secrets",
                    params={"key": full_key, "tenant_id": tenant_id},
                    headers=self._headers(),
                )
                result = self._check_status(response, full_key, "deleting")
                if result == "not_found":
                    return False
        except Exception as e:
            self._handle_error(e, "delete", full_key)

        return True

    def health_sync(self) -> bool:
        """Synchronous version of ``health()``."""
        try:
            with httpx.Client(
                base_url=self._base_url, timeout=5.0
            ) as client:
                response = client.get("/health", headers=self._headers())
                return response.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Module-level singleton (initialized lazily)
# ---------------------------------------------------------------------------

_prism_client: Optional[PrismClient] = None


def get_prism_client() -> PrismClient:
    """Get or create the module-level PrismClient singleton."""
    global _prism_client
    if _prism_client is None:
        _prism_client = PrismClient()
    return _prism_client


def prism_available() -> bool:
    """Check if Prism integration is enabled in settings."""
    from config import settings
    return settings.prism_enabled
