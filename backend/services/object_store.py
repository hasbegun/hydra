"""
Object storage abstraction for report artifacts (JSONL, HTML, hitlog).

Three backends:
  - LocalStorage: reads/writes files on a local/shared filesystem (legacy)
  - MinioStorage: reads/writes objects via S3-compatible Minio API
  - PrismStorage: reads/writes via Prism SMPC with Redis cache + Minio fallback

Selected by the STORAGE_BACKEND env var ("local", "minio", or "prism").
"""
import io
import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract interface for object/file storage."""

    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """Retrieve an object by key. Returns None if not found."""

    @abstractmethod
    def get_stream(self, key: str):
        """Return a file-like readable stream for the given key.

        Returns None if the object does not exist.
        Caller is responsible for closing the stream.
        """

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Store an object."""

    @abstractmethod
    def put_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> None:
        """Upload a local file to the store."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if an object exists."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete an object. Returns True if deleted, False if not found."""

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        """List object keys matching a prefix."""


class LocalStorage(StorageBackend):
    """File-system-backed storage (legacy shared volume)."""

    def __init__(self, base_dir: str | Path):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage initialized: {self._base}")

    def _path(self, key: str) -> Path:
        # Flatten key: "abc123/report.jsonl" → "abc123/report.jsonl" as nested dir
        # But for backward compat, also support flat keys like "garak.abc123.report.jsonl"
        return self._base / key

    def get(self, key: str) -> Optional[bytes]:
        p = self._path(key)
        if not p.exists():
            return None
        return p.read_bytes()

    def get_stream(self, key: str):
        p = self._path(key)
        if not p.exists():
            return None
        return open(p, "rb")

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def put_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> None:
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        self.put(key, src.read_bytes(), content_type)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> bool:
        p = self._path(key)
        if not p.exists():
            return False
        p.unlink()
        return True

    def list_keys(self, prefix: str = "") -> list[str]:
        keys = []
        for p in self._base.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(self._base))
                if rel.startswith(prefix):
                    keys.append(rel)
        return sorted(keys)


class MinioStorage(StorageBackend):
    """S3-compatible Minio object storage."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ):
        from minio import Minio

        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket
        self._ensure_bucket()
        logger.info(f"MinioStorage initialized: {endpoint}/{bucket}")

    def _ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info(f"Created Minio bucket: {self._bucket}")

    def get(self, key: str) -> Optional[bytes]:
        try:
            response = self._client.get_object(self._bucket, key)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception as e:
            if "NoSuchKey" in str(e) or "not found" in str(e).lower():
                return None
            logger.error(f"MinioStorage.get error for key '{key}': {e}")
            raise

    def get_stream(self, key: str):
        try:
            response = self._client.get_object(self._bucket, key)
            return response
        except Exception as e:
            if "NoSuchKey" in str(e) or "not found" in str(e).lower():
                return None
            logger.error(f"MinioStorage.get_stream error for key '{key}': {e}")
            raise

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def put_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> None:
        self._client.fput_object(
            self._bucket,
            key,
            file_path,
            content_type=content_type,
        )

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self.exists(key):
            return False
        self._client.remove_object(self._bucket, key)
        return True

    def list_keys(self, prefix: str = "") -> list[str]:
        objects = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
        return sorted(obj.object_name for obj in objects)


class PrismStorage(StorageBackend):
    """Prism SMPC-backed storage with Redis read cache and Minio fallback.

    Read path:  Redis cache (5 min TTL) -> Prism -> Minio fallback
    Write path: Prism -> Minio fallback (if Prism unreachable)
    Delete:     Prism + Redis cache invalidation

    All keys are scoped by tenant_id to enforce data isolation.
    Uses a default tenant_id for backward compatibility when the caller
    does not supply one.
    """

    def __init__(
        self,
        tenant_id: str = "default",
        fallback: Optional[StorageBackend] = None,
        cache_ttl: int = 300,
    ):
        from services.prism_client import PrismClient

        self._prism = PrismClient()
        self._tenant_id = tenant_id
        self._fallback = fallback
        self._cache_ttl = cache_ttl
        self._redis = self._init_redis()
        logger.info(
            f"PrismStorage initialized (tenant={tenant_id}, "
            f"cache_ttl={cache_ttl}s, fallback={'yes' if fallback else 'no'})"
        )

    @staticmethod
    def _init_redis():
        """Create a Redis client for caching. Returns None if unavailable."""
        try:
            import redis as redis_lib
            from config import settings
            return redis_lib.from_url(settings.redis_url, decode_responses=False)
        except Exception as e:
            logger.warning(f"Redis unavailable for PrismStorage cache: {e}")
            return None

    def _cache_key(self, key: str) -> str:
        """Build the Redis cache key."""
        return f"prism:cache:{self._tenant_id}/{key}"

    def _cache_get(self, key: str) -> Optional[bytes]:
        """Read from Redis cache. Returns None on miss or error."""
        if not self._redis:
            return None
        try:
            data = self._redis.get(self._cache_key(key))
            if data is not None:
                logger.debug(f"PrismStorage cache hit: {key}")
            return data
        except Exception as e:
            logger.debug(f"PrismStorage cache read error: {e}")
            return None

    def _cache_set(self, key: str, data: bytes) -> None:
        """Write to Redis cache with TTL. Best-effort."""
        if not self._redis:
            return
        try:
            self._redis.setex(self._cache_key(key), self._cache_ttl, data)
        except Exception as e:
            logger.debug(f"PrismStorage cache write error: {e}")

    def _cache_delete(self, key: str) -> None:
        """Invalidate Redis cache entry. Best-effort."""
        if not self._redis:
            return
        try:
            self._redis.delete(self._cache_key(key))
        except Exception as e:
            logger.debug(f"PrismStorage cache delete error: {e}")

    def get(self, key: str) -> Optional[bytes]:
        # 1. Redis cache
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        # 2. Prism
        try:
            data = self._prism.fetch_sync(self._tenant_id, key)
            if data is not None:
                self._cache_set(key, data)
                return data
        except Exception as e:
            logger.warning(f"PrismStorage.get Prism error for '{key}': {e}")

        # 3. Minio fallback
        if self._fallback:
            try:
                data = self._fallback.get(key)
                if data is not None:
                    logger.info(f"PrismStorage.get fallback hit: {key}")
                    return data
            except Exception as e:
                logger.warning(f"PrismStorage.get fallback error for '{key}': {e}")

        return None

    def get_stream(self, key: str):
        data = self.get(key)
        if data is None:
            return None
        return io.BytesIO(data)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        try:
            self._prism.store_sync(self._tenant_id, key, data)
            self._cache_set(key, data)
            return
        except Exception as e:
            logger.warning(f"PrismStorage.put Prism error for '{key}': {e}")

        # Fallback to Minio
        if self._fallback:
            self._fallback.put(key, data, content_type)
            logger.info(f"PrismStorage.put fallback used for '{key}'")
        else:
            raise

    def put_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> None:
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        self.put(key, src.read_bytes(), content_type)

    def exists(self, key: str) -> bool:
        # Check cache first
        if self._cache_get(key) is not None:
            return True
        # Check Prism
        try:
            data = self._prism.fetch_sync(self._tenant_id, key)
            if data is not None:
                self._cache_set(key, data)
                return True
        except Exception as e:
            logger.debug(f"PrismStorage.exists Prism error for '{key}': {e}")
        # Fallback
        if self._fallback:
            return self._fallback.exists(key)
        return False

    def delete(self, key: str) -> bool:
        self._cache_delete(key)
        try:
            result = self._prism.delete_sync(self._tenant_id, key)
            if result:
                return True
        except Exception as e:
            logger.warning(f"PrismStorage.delete Prism error for '{key}': {e}")
        # Also try fallback delete
        if self._fallback:
            return self._fallback.delete(key)
        return False

    def list_keys(self, prefix: str = "") -> list[str]:
        # Prism doesn't support listing — delegate to fallback
        if self._fallback:
            return self._fallback.list_keys(prefix)
        return []

    def set_tenant(self, tenant_id: str) -> None:
        """Update the tenant context for subsequent operations.

        Allows a single PrismStorage instance to serve multiple tenants
        by switching tenant_id between calls (e.g. in route handlers).
        """
        self._tenant_id = tenant_id


# ---------------------------------------------------------------------------
# Singleton: initialized once at startup, used by all services
# ---------------------------------------------------------------------------

_store: Optional[StorageBackend] = None


def init_object_store() -> StorageBackend:
    """Initialize the global object store based on configuration.

    Called once at application startup (in main.py lifespan).
    Supports three backends: "local", "minio", and "prism".
    When "prism" is selected, MinioStorage is created as a fallback.
    """
    global _store

    from config import settings

    backend = settings.storage_backend.lower()

    if backend == "prism":
        # Build Minio fallback (if credentials are configured)
        fallback = None
        if settings.prism_fallback_to_minio and settings.minio_secret_key:
            try:
                fallback = MinioStorage(
                    endpoint=settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    bucket=settings.minio_bucket,
                    secure=settings.minio_secure,
                )
            except Exception as e:
                logger.warning(f"Minio fallback init failed (non-fatal): {e}")

        _store = PrismStorage(
            tenant_id="default",
            fallback=fallback,
            cache_ttl=settings.prism_cache_ttl,
        )
    elif backend == "minio":
        _store = MinioStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
        )
    else:
        _store = LocalStorage(settings.garak_reports_path)

    return _store


def get_object_store() -> StorageBackend:
    """Get the initialized object store. Raises if not initialized."""
    if _store is None:
        raise RuntimeError("Object store not initialized. Call init_object_store() first.")
    return _store


def object_store_available() -> bool:
    """Check if the object store has been initialized."""
    return _store is not None
