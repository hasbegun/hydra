"""
Tests for Phase 2 Week 5: PrismClient + PrismStorage + Redis cache.

Covers:
- PrismClient store/fetch/delete with base64 encoding
- Tenant-prefixed keys
- SHA-256 integrity validation on fetch
- Cross-tenant access denied (403)
- PrismUnavailable on connection failure
- PrismStorage StorageBackend implementation
- Redis cache hit/miss/invalidation
- Cache TTL expiry
- Minio fallback when Prism is unreachable
- PrismStorage.set_tenant for multi-tenant switching
- Health check endpoint integration
"""
import base64
import hashlib
import io
import json
import os
import sys
import time
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock config.settings before importing prism modules
_mock_settings = MagicMock()
_mock_settings.prism_url = "http://prism-test:8080"
_mock_settings.prism_api_key = "test-api-key"
_mock_settings.prism_timeout = 5.0
_mock_settings.prism_cache_ttl = 300
_mock_settings.prism_enabled = True
_mock_settings.prism_fallback_to_minio = True
_mock_settings.redis_url = "redis://localhost:6379/0"
_mock_settings.garak_reports_path = "/tmp/test_reports"
_mock_settings.storage_backend = "prism"
_mock_settings.minio_endpoint = "minio:9000"
_mock_settings.minio_access_key = "test"
_mock_settings.minio_secret_key = "test"
_mock_settings.minio_bucket = "test-bucket"
_mock_settings.minio_secure = False


# ---------------------------------------------------------------------------
# PrismClient unit tests
# ---------------------------------------------------------------------------

class TestPrismClientKeyFormat:
    """Test that tenant-prefixed keys are built correctly."""

    def test_full_key_format(self):
        with patch("config.settings", _mock_settings):
            from services.prism_client import PrismClient
            client = PrismClient(base_url="http://test:8080")
            assert client._full_key("tenant-a", "report:abc:jsonl") == "tenant-a/report:abc:jsonl"

    def test_full_key_default_tenant(self):
        with patch("config.settings", _mock_settings):
            from services.prism_client import PrismClient
            client = PrismClient(base_url="http://test:8080")
            assert client._full_key("default", "key") == "default/key"


class TestPrismClientHeaders:
    """Test HTTP header construction."""

    def test_headers_include_api_key(self):
        with patch("config.settings", _mock_settings):
            from services.prism_client import PrismClient
            client = PrismClient(base_url="http://test:8080", api_key="my-key")
            headers = client._headers()
            assert headers["X-Prism-Key"] == "my-key"
            assert headers["Content-Type"] == "application/json"

    def test_headers_without_api_key(self):
        mock_no_key = MagicMock()
        mock_no_key.prism_url = "http://test:8080"
        mock_no_key.prism_api_key = ""
        mock_no_key.prism_timeout = 5.0
        with patch("config.settings", mock_no_key):
            from services.prism_client import PrismClient
            client = PrismClient(base_url="http://test:8080")
            headers = client._headers()
            assert "X-Prism-Key" not in headers


class TestPrismClientHash:
    """Test SHA-256 hash computation."""

    def test_compute_hash(self):
        from services.prism_client import PrismClient
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert PrismClient._compute_hash(data) == expected

    def test_compute_hash_empty(self):
        from services.prism_client import PrismClient
        expected = hashlib.sha256(b"").hexdigest()
        assert PrismClient._compute_hash(b"") == expected


class TestPrismClientStoreSync:
    """Test synchronous store operations."""

    def test_store_sends_base64_data(self):
        """Data is base64-encoded in the request body."""
        import httpx
        from services.prism_client import PrismClient

        data = b"report content here"
        expected_b64 = base64.b64encode(data).decode("ascii")
        expected_hash = hashlib.sha256(data).hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080", api_key="k")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.put.return_value = mock_response

            result = client.store_sync("tenant-a", "report:scan1:jsonl", data)

            assert result == "tenant-a/report:scan1:jsonl"
            call_args = ctx.put.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert payload["data"] == expected_b64
            assert payload["sha256"] == expected_hash
            assert payload["tenant_id"] == "tenant-a"

    def test_store_includes_tenant_prefix(self):
        """Key starts with {tenant_id}/."""
        import httpx
        from services.prism_client import PrismClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.put.return_value = mock_response

            key = client.store_sync("org-xyz", "cred:api-key", b"secret")
            assert key.startswith("org-xyz/")
            assert key == "org-xyz/cred:api-key"

    def test_store_access_denied_raises(self):
        """403 from Prism raises PrismAccessDenied."""
        from services.prism_client import PrismClient, PrismAccessDenied

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.put.return_value = mock_response

            with pytest.raises(PrismAccessDenied):
                client.store_sync("tenant-a", "key", b"data")

    def test_store_connection_error_raises_unavailable(self):
        """Connection failure raises PrismUnavailable."""
        import httpx
        from services.prism_client import PrismClient, PrismUnavailable

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.put.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(PrismUnavailable):
                client.store_sync("tenant-a", "key", b"data")


class TestPrismClientFetchSync:
    """Test synchronous fetch operations."""

    def test_fetch_returns_decoded_data(self):
        """Base64 response is decoded correctly."""
        from services.prism_client import PrismClient

        original = b"decoded report content"
        encoded = base64.b64encode(original).decode("ascii")
        sha = hashlib.sha256(original).hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": encoded, "sha256": sha}

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.get.return_value = mock_response

            data = client.fetch_sync("tenant-a", "report:scan1:jsonl")
            assert data == original

    def test_fetch_validates_integrity(self):
        """SHA-256 mismatch raises PrismIntegrityError."""
        from services.prism_client import PrismClient, PrismIntegrityError

        original = b"data"
        encoded = base64.b64encode(original).decode("ascii")
        wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": encoded, "sha256": wrong_hash}

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.get.return_value = mock_response

            with pytest.raises(PrismIntegrityError, match="SHA-256 mismatch"):
                client.fetch_sync("tenant-a", "key")

    def test_fetch_404_returns_none(self):
        """Non-existent key returns None."""
        from services.prism_client import PrismClient

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.get.return_value = mock_response

            result = client.fetch_sync("tenant-a", "nonexistent")
            assert result is None

    def test_fetch_cross_tenant_denied(self):
        """403 from Prism raises PrismAccessDenied (cross-tenant fetch)."""
        from services.prism_client import PrismClient, PrismAccessDenied

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.get.return_value = mock_response

            with pytest.raises(PrismAccessDenied):
                client.fetch_sync("tenant-b", "tenant-a/secret")


class TestPrismClientDeleteSync:
    """Test synchronous delete operations."""

    def test_delete_returns_true(self):
        """Successful delete returns True."""
        from services.prism_client import PrismClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.delete.return_value = mock_response

            assert client.delete_sync("tenant-a", "key") is True

    def test_delete_404_returns_false(self):
        """Deleting non-existent key returns False."""
        from services.prism_client import PrismClient

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.delete.return_value = mock_response

            assert client.delete_sync("tenant-a", "nonexistent") is False


class TestPrismClientHealthSync:
    """Test synchronous health check."""

    def test_health_connected(self):
        """Prism responding 200 returns True."""
        from services.prism_client import PrismClient

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.get.return_value = mock_response

            assert client.health_sync() is True

    def test_health_disconnected(self):
        """Connection error returns False."""
        import httpx
        from services.prism_client import PrismClient

        with patch("config.settings", _mock_settings):
            client = PrismClient(base_url="http://test:8080")

        with patch("httpx.Client") as MockClient:
            ctx = MockClient.return_value.__enter__.return_value
            ctx.get.side_effect = httpx.ConnectError("refused")

            assert client.health_sync() is False


class TestPrismClientSingleton:
    """Test module-level singleton and availability check."""

    def test_get_prism_client_returns_instance(self):
        import services.prism_client as mod
        old = mod._prism_client
        mod._prism_client = None
        try:
            with patch("config.settings", _mock_settings):
                client = mod.get_prism_client()
                assert client is not None
                assert isinstance(client, mod.PrismClient)
                # Second call returns same instance
                assert mod.get_prism_client() is client
        finally:
            mod._prism_client = old

    def test_prism_available_true(self):
        from services.prism_client import prism_available
        with patch("config.settings", _mock_settings):
            assert prism_available() is True

    def test_prism_available_false(self):
        from services.prism_client import prism_available
        mock_disabled = MagicMock()
        mock_disabled.prism_enabled = False
        with patch("config.settings", mock_disabled):
            assert prism_available() is False


# ---------------------------------------------------------------------------
# PrismStorage unit tests
# ---------------------------------------------------------------------------

class TestPrismStorageGet:
    """Test PrismStorage.get read path: cache -> Prism -> fallback."""

    def _make_storage(self, prism_mock=None, redis_mock=None, fallback=None):
        from services.object_store import PrismStorage
        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient") as PrismCls:
                with patch.object(PrismStorage, "_init_redis", return_value=redis_mock):
                    storage = PrismStorage(tenant_id="tenant-x", fallback=fallback, cache_ttl=300)
                    if prism_mock:
                        storage._prism = prism_mock
                    return storage

    def test_get_cache_hit(self):
        """Cache hit returns data without calling Prism."""
        redis_mock = MagicMock()
        redis_mock.get.return_value = b"cached-data"
        prism_mock = MagicMock()

        storage = self._make_storage(prism_mock=prism_mock, redis_mock=redis_mock)
        result = storage.get("some-key")

        assert result == b"cached-data"
        prism_mock.fetch_sync.assert_not_called()

    def test_get_cache_miss_prism_hit(self):
        """Cache miss falls through to Prism, then populates cache."""
        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        prism_mock = MagicMock()
        prism_mock.fetch_sync.return_value = b"prism-data"

        storage = self._make_storage(prism_mock=prism_mock, redis_mock=redis_mock)
        result = storage.get("key")

        assert result == b"prism-data"
        prism_mock.fetch_sync.assert_called_once_with("tenant-x", "key")
        redis_mock.setex.assert_called_once()

    def test_get_prism_error_falls_to_minio(self):
        """Prism error falls through to Minio fallback."""
        from services.prism_client import PrismUnavailable

        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        prism_mock = MagicMock()
        prism_mock.fetch_sync.side_effect = PrismUnavailable("down")
        fallback = MagicMock()
        fallback.get.return_value = b"minio-data"

        storage = self._make_storage(prism_mock=prism_mock, redis_mock=redis_mock, fallback=fallback)
        result = storage.get("key")

        assert result == b"minio-data"
        fallback.get.assert_called_once_with("key")

    def test_get_all_sources_miss(self):
        """All sources miss returns None."""
        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        prism_mock = MagicMock()
        prism_mock.fetch_sync.return_value = None

        storage = self._make_storage(prism_mock=prism_mock, redis_mock=redis_mock)
        assert storage.get("missing") is None

    def test_get_no_redis_still_works(self):
        """PrismStorage works without Redis (cache=None)."""
        prism_mock = MagicMock()
        prism_mock.fetch_sync.return_value = b"data"

        storage = self._make_storage(prism_mock=prism_mock, redis_mock=None)
        assert storage.get("key") == b"data"


class TestPrismStoragePut:
    """Test PrismStorage.put write path: Prism -> fallback."""

    def _make_storage(self, prism_mock=None, redis_mock=None, fallback=None):
        from services.object_store import PrismStorage
        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient") as PrismCls:
                with patch.object(PrismStorage, "_init_redis", return_value=redis_mock):
                    storage = PrismStorage(tenant_id="t1", fallback=fallback, cache_ttl=300)
                    if prism_mock:
                        storage._prism = prism_mock
                    return storage

    def test_put_stores_in_prism_and_cache(self):
        """Data is stored in Prism and cached in Redis."""
        redis_mock = MagicMock()
        prism_mock = MagicMock()
        prism_mock.store_sync.return_value = "t1/key"

        storage = self._make_storage(prism_mock=prism_mock, redis_mock=redis_mock)
        storage.put("key", b"data")

        prism_mock.store_sync.assert_called_once_with("t1", "key", b"data")
        redis_mock.setex.assert_called_once()

    def test_put_prism_down_falls_to_minio(self):
        """Prism failure falls to Minio fallback."""
        from services.prism_client import PrismUnavailable

        prism_mock = MagicMock()
        prism_mock.store_sync.side_effect = PrismUnavailable("down")
        fallback = MagicMock()

        storage = self._make_storage(prism_mock=prism_mock, fallback=fallback)
        storage.put("key", b"data")

        fallback.put.assert_called_once_with("key", b"data", "application/octet-stream")


class TestPrismStorageDelete:
    """Test PrismStorage.delete with cache invalidation."""

    def _make_storage(self, prism_mock=None, redis_mock=None, fallback=None):
        from services.object_store import PrismStorage
        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=redis_mock):
                    storage = PrismStorage(tenant_id="t1", fallback=fallback)
                    if prism_mock:
                        storage._prism = prism_mock
                    return storage

    def test_delete_invalidates_cache(self):
        """Delete removes Redis cache entry."""
        redis_mock = MagicMock()
        prism_mock = MagicMock()
        prism_mock.delete_sync.return_value = True

        storage = self._make_storage(prism_mock=prism_mock, redis_mock=redis_mock)
        result = storage.delete("key")

        assert result is True
        redis_mock.delete.assert_called_once()

    def test_delete_prism_miss_falls_to_minio(self):
        """If Prism returns not found, try Minio fallback."""
        prism_mock = MagicMock()
        prism_mock.delete_sync.return_value = False
        fallback = MagicMock()
        fallback.delete.return_value = True

        storage = self._make_storage(prism_mock=prism_mock, fallback=fallback)
        result = storage.delete("key")

        assert result is True
        fallback.delete.assert_called_once_with("key")


class TestPrismStorageCacheTTL:
    """Test Redis cache TTL behavior."""

    def test_cache_set_uses_configured_ttl(self):
        """Cache entries use the configured TTL."""
        from services.object_store import PrismStorage
        redis_mock = MagicMock()

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=redis_mock):
                    storage = PrismStorage(tenant_id="t1", cache_ttl=600)

        storage._cache_set("key", b"data")
        redis_mock.setex.assert_called_once()
        # TTL is the second argument
        args = redis_mock.setex.call_args
        assert args[0][1] == 600  # TTL = 600s

    def test_cache_key_includes_tenant(self):
        """Cache key includes tenant for isolation."""
        from services.object_store import PrismStorage
        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="acme-corp")

        cache_key = storage._cache_key("report:scan1:html")
        assert cache_key == "prism:cache:acme-corp/report:scan1:html"


class TestPrismStorageSetTenant:
    """Test tenant switching on PrismStorage."""

    def test_set_tenant_changes_context(self):
        """set_tenant updates the tenant_id for subsequent operations."""
        from services.object_store import PrismStorage
        prism_mock = MagicMock()
        prism_mock.fetch_sync.return_value = b"data"

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="tenant-a")
                    storage._prism = prism_mock

        storage.get("key1")
        prism_mock.fetch_sync.assert_called_with("tenant-a", "key1")

        storage.set_tenant("tenant-b")
        storage.get("key2")
        prism_mock.fetch_sync.assert_called_with("tenant-b", "key2")


class TestPrismStorageGetStream:
    """Test get_stream returns BytesIO."""

    def test_get_stream_returns_bytesio(self):
        from services.object_store import PrismStorage
        prism_mock = MagicMock()
        prism_mock.fetch_sync.return_value = b"stream-content"

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="t1")
                    storage._prism = prism_mock

        stream = storage.get_stream("key")
        assert stream is not None
        assert stream.read() == b"stream-content"

    def test_get_stream_returns_none_on_miss(self):
        from services.object_store import PrismStorage
        prism_mock = MagicMock()
        prism_mock.fetch_sync.return_value = None

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="t1")
                    storage._prism = prism_mock

        assert storage.get_stream("missing") is None


class TestPrismStorageExists:
    """Test exists check across all sources."""

    def test_exists_cache_hit(self):
        from services.object_store import PrismStorage
        redis_mock = MagicMock()
        redis_mock.get.return_value = b"cached"

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=redis_mock):
                    storage = PrismStorage(tenant_id="t1")

        assert storage.exists("key") is True

    def test_exists_prism_miss_fallback_hit(self):
        from services.object_store import PrismStorage
        redis_mock = MagicMock()
        redis_mock.get.return_value = None
        prism_mock = MagicMock()
        prism_mock.fetch_sync.return_value = None
        fallback = MagicMock()
        fallback.exists.return_value = True

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=redis_mock):
                    storage = PrismStorage(tenant_id="t1", fallback=fallback)
                    storage._prism = prism_mock

        assert storage.exists("key") is True
        fallback.exists.assert_called_once_with("key")


class TestPrismStoragePutFile:
    """Test put_file delegates to put."""

    def test_put_file_reads_and_stores(self, tmp_path):
        from services.object_store import PrismStorage
        prism_mock = MagicMock()

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="t1")
                    storage._prism = prism_mock

        # Create a temp file
        f = tmp_path / "report.html"
        f.write_bytes(b"<html>report</html>")

        storage.put_file("report-key", str(f))
        prism_mock.store_sync.assert_called_once_with("t1", "report-key", b"<html>report</html>")

    def test_put_file_missing_raises(self):
        from services.object_store import PrismStorage
        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="t1")

        with pytest.raises(FileNotFoundError):
            storage.put_file("key", "/nonexistent/file.txt")


class TestPrismStorageListKeys:
    """Test list_keys delegates to fallback."""

    def test_list_keys_with_fallback(self):
        from services.object_store import PrismStorage
        fallback = MagicMock()
        fallback.list_keys.return_value = ["a", "b"]

        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="t1", fallback=fallback)

        assert storage.list_keys("prefix") == ["a", "b"]

    def test_list_keys_no_fallback(self):
        from services.object_store import PrismStorage
        with patch("config.settings", _mock_settings):
            with patch("services.prism_client.PrismClient"):
                with patch.object(PrismStorage, "_init_redis", return_value=None):
                    storage = PrismStorage(tenant_id="t1")

        assert storage.list_keys() == []


# ---------------------------------------------------------------------------
# init_object_store tests
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Health check endpoint tests
# ---------------------------------------------------------------------------

class TestHealthCheckEndpoint:
    """Test /health endpoint reports Prism connectivity."""

    def test_health_prism_connected(self):
        """Health endpoint shows prism: connected when Prism is up."""
        from fastapi.testclient import TestClient
        from main import app

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client") as mock_get:
                mock_client = MagicMock()
                async def mock_health():
                    return True
                mock_client.health = mock_health
                mock_get.return_value = mock_client

                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get("/health")
                data = resp.json()
                assert data["prism"] == "connected"
                assert data["status"] == "healthy"

    def test_health_prism_degraded(self):
        """Health endpoint shows prism: degraded when Prism is down."""
        from fastapi.testclient import TestClient

        with patch("services.prism_client.prism_available", return_value=True):
            with patch("services.prism_client.get_prism_client") as mock_get:
                mock_client = MagicMock()
                async def mock_health():
                    return False
                mock_client.health = mock_health
                mock_get.return_value = mock_client

                from main import app
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get("/health")
                data = resp.json()
                assert data["prism"] == "degraded"
                assert data["status"] == "degraded"

    def test_health_prism_disabled(self):
        """When Prism is disabled, health doesn't include prism field."""
        from fastapi.testclient import TestClient

        with patch("services.prism_client.prism_available", return_value=False):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
            data = resp.json()
            assert "prism" not in data
            assert data["status"] == "healthy"


class TestInitObjectStore:
    """Test that init_object_store creates the correct backend."""

    def test_init_prism_backend(self):
        from services import object_store as mod
        old = mod._store

        mock_s = MagicMock()
        mock_s.storage_backend = "prism"
        mock_s.prism_fallback_to_minio = False
        mock_s.prism_cache_ttl = 300
        mock_s.prism_url = "http://prism:8080"
        mock_s.prism_api_key = ""
        mock_s.prism_timeout = 5.0
        mock_s.prism_enabled = True
        mock_s.redis_url = "redis://localhost:6379/0"

        try:
            with patch("config.settings", mock_s):
                with patch.object(mod.PrismStorage, "_init_redis", return_value=None):
                    store = mod.init_object_store()
            assert isinstance(store, mod.PrismStorage)
        finally:
            mod._store = old

    def test_init_minio_backend(self):
        from services import object_store as mod
        old = mod._store

        mock_s = MagicMock()
        mock_s.storage_backend = "minio"
        mock_s.minio_endpoint = "minio:9000"
        mock_s.minio_access_key = "test"
        mock_s.minio_secret_key = "test"
        mock_s.minio_bucket = "bucket"
        mock_s.minio_secure = False

        try:
            with patch("config.settings", mock_s):
                with patch("minio.Minio") as MockMinio:
                    MockMinio.return_value.bucket_exists.return_value = True
                    store = mod.init_object_store()
            assert isinstance(store, mod.MinioStorage)
        finally:
            mod._store = old

    def test_init_local_backend(self, tmp_path):
        from services import object_store as mod
        old = mod._store

        mock_s = MagicMock()
        mock_s.storage_backend = "local"
        mock_s.garak_reports_path = tmp_path

        try:
            with patch("config.settings", mock_s):
                store = mod.init_object_store()
            assert isinstance(store, mod.LocalStorage)
        finally:
            mod._store = old
