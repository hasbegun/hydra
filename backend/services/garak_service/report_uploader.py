"""
Upload garak report files to Minio after scan completion.

After garak finishes and the report files have been renamed locally
(with the correct scan_id), this module uploads them to the configured
Minio bucket under the key pattern: {scan_id}/report.jsonl, etc.

If Minio is not configured, this is a no-op.
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Max upload retries on transient failures
MAX_RETRIES = 3


def _get_minio_client():
    """Create a Minio client from env vars. Returns None if not configured."""
    endpoint = os.environ.get("MINIO_ENDPOINT")
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    secret_key = os.environ.get("MINIO_SECRET_KEY")

    if not endpoint or not access_key or not secret_key:
        return None

    try:
        from minio import Minio
        secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
        return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
    except ImportError:
        logger.warning("minio package not installed, skipping upload")
        return None


def _get_bucket() -> str:
    return os.environ.get("MINIO_BUCKET", "hydra-reports")


def _ensure_bucket(client, bucket: str) -> None:
    """Create bucket if it doesn't exist."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info(f"Created Minio bucket: {bucket}")


def _resolve_report_files(
    scan_id: str,
    reports_dir: Path,
    jsonl_path: Optional[str] = None,
    html_path: Optional[str] = None,
) -> dict[str, Optional[Path]]:
    """Resolve actual report file paths.

    Garak CLI generates its own UUID for filenames (e.g. garak.{garak_uuid}.report.jsonl),
    which differs from our scan_id. The progress parser captures the actual paths during
    the scan. If explicit paths are provided, use those. Otherwise fall back to looking
    for files named with our scan_id (unlikely to match but kept for compatibility).

    Also derives the hitlog path from the JSONL path since garak uses the same UUID.
    """
    files: dict[str, Optional[Path]] = {"jsonl": None, "hitlog": None, "html": None}

    # Try explicit paths first (from garak CLI output captured by progress parser)
    if jsonl_path:
        p = Path(jsonl_path)
        if p.exists():
            files["jsonl"] = p
            # Derive hitlog from same garak UUID
            hitlog = p.parent / p.name.replace(".report.jsonl", ".hitlog.jsonl")
            if hitlog.exists():
                files["hitlog"] = hitlog

    if html_path:
        p = Path(html_path)
        if p.exists():
            files["html"] = p

    # Fall back to scan_id-based names (works if files were already renamed)
    fallback_map = {
        "jsonl": reports_dir / f"garak.{scan_id}.report.jsonl",
        "hitlog": reports_dir / f"garak.{scan_id}.hitlog.jsonl",
        "html": reports_dir / f"garak.{scan_id}.report.html",
    }
    for rtype, path in fallback_map.items():
        if files[rtype] is None and path.exists():
            files[rtype] = path

    return files


def upload_report_files(
    scan_id: str,
    reports_dir: Path,
    jsonl_path: Optional[str] = None,
    html_path: Optional[str] = None,
) -> dict[str, Optional[str]]:
    """Upload all report files for a scan to Minio.

    Uses explicit file paths from garak CLI output when available, falling back
    to files named with our scan_id. Always uploads under the scan_id key so the
    backend can find them.

    Returns a dict mapping report type → Minio object key (or None if not found/failed).
    """
    client = _get_minio_client()
    if client is None:
        logger.debug("Minio not configured, skipping upload")
        return {}

    bucket = _get_bucket()
    _ensure_bucket(client, bucket)

    files = _resolve_report_files(scan_id, reports_dir, jsonl_path, html_path)

    content_types = {
        "jsonl": "application/jsonl",
        "hitlog": "application/jsonl",
        "html": "text/html",
    }

    # Always upload under scan_id key so the backend can look up by scan_id
    key_names = {
        "jsonl": f"garak.{scan_id}.report.jsonl",
        "hitlog": f"garak.{scan_id}.hitlog.jsonl",
        "html": f"garak.{scan_id}.report.html",
    }

    results: dict[str, Optional[str]] = {}

    for report_type, local_path in files.items():
        if local_path is None:
            results[report_type] = None
            continue

        object_key = f"{scan_id}/{key_names[report_type]}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                client.fput_object(
                    bucket,
                    object_key,
                    str(local_path),
                    content_type=content_types.get(report_type, "application/octet-stream"),
                )
                results[report_type] = object_key
                logger.info(f"Uploaded {local_path.name} → s3://{bucket}/{object_key}")
                break
            except Exception as e:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"Upload attempt {attempt}/{MAX_RETRIES} failed for {local_path.name}: {e}"
                    )
                else:
                    logger.error(f"Upload failed after {MAX_RETRIES} attempts for {local_path.name}: {e}")
                    results[report_type] = None

    return results
