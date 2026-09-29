"""
Target management service — credential separation logic.

Handles the split between non-sensitive metadata (Postgres) and
sensitive credentials (Prism). Ensures credentials never appear in
Postgres or API responses.

Credential fields (``headers``, ``cookies``, ``query_params``) are
extracted from the target creation payload, stored in Prism under
the key ``target:{target_id}:credentials``, and referenced by a
Prism key stored on the Postgres row (``credential_prism_key``).

Usage::

    svc = TargetService()
    target = svc.create_target(tenant_id, payload)
    creds = svc.fetch_credentials(tenant_id, target_id)
    svc.rotate_credentials(tenant_id, target_id, new_creds)
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Fields that are considered sensitive and must go to Prism
SENSITIVE_FIELDS = frozenset({"headers", "cookies", "query_params"})


def _prism_credential_key(target_id: str) -> str:
    """Build the Prism key for a target's credentials."""
    return f"target:{target_id}:credentials"


def _extract_credentials(payload: dict) -> Optional[dict]:
    """Extract sensitive credential fields from the payload.

    Returns a dict of sensitive fields if any are present, else None.
    """
    creds = payload.get("credentials")
    if not creds or not isinstance(creds, dict):
        return None
    # Only keep known sensitive sub-fields
    filtered = {k: v for k, v in creds.items() if k in SENSITIVE_FIELDS and v}
    return filtered if filtered else None


def _strip_credentials(payload: dict) -> dict:
    """Return a copy of the payload with credential fields removed."""
    clean = dict(payload)
    clean.pop("credentials", None)
    return clean


class TargetService:
    """Manages target CRUD with credential separation.

    Non-sensitive metadata goes to Postgres. Sensitive credentials
    go to Prism. The Postgres row stores a reference key
    (``credential_prism_key``) pointing to the Prism secret.
    """

    def create_target(
        self,
        tenant_id: str,
        payload: dict,
    ) -> dict:
        """Create a new target, storing credentials in Prism.

        Args:
            tenant_id: Tenant identifier.
            payload: Target creation payload with optional ``credentials``.

        Returns:
            Target dict (never includes credential values).
        """
        from database.session import get_db
        from database.models import Target

        target_id = f"tgt_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        # Extract and store credentials in Prism
        creds = _extract_credentials(payload)
        prism_key = None
        has_creds = False

        if creds:
            prism_key = self._store_credentials(tenant_id, target_id, creds)
            has_creds = prism_key is not None

        # Build non-sensitive config
        clean_payload = _strip_credentials(payload)
        non_sensitive_config = {
            k: v for k, v in clean_payload.items()
            if k not in ("name", "type", "endpoint", "body_template", "response_json_field")
        }

        with get_db() as db:
            target = Target(
                id=target_id,
                tenant_id=tenant_id,
                name=payload.get("name", "unnamed"),
                target_type=payload.get("type", "rest"),
                endpoint=payload.get("endpoint", ""),
                body_template=payload.get("body_template"),
                response_json_field=payload.get("response_json_field"),
                config_json=json.dumps(non_sensitive_config) if non_sensitive_config else None,
                credential_prism_key=prism_key,
                has_credentials=has_creds,
                created_at=now,
                updated_at=now,
            )
            db.add(target)
            db.commit()
            db.refresh(target)
            result = target.to_dict()

        logger.info(
            f"Created target {target_id} for tenant {tenant_id} "
            f"(credentials={'stored in Prism' if has_creds else 'none'})"
        )
        return result

    def get_target(self, tenant_id: str, target_id: str) -> Optional[dict]:
        """Get a target by ID (tenant-scoped, never returns credentials)."""
        from database.session import get_db
        from database.models import Target

        with get_db() as db:
            target = (
                db.query(Target)
                .filter_by(id=target_id, tenant_id=tenant_id)
                .first()
            )
            if not target:
                return None
            return target.to_dict()

    def list_targets(self, tenant_id: str) -> list[dict]:
        """List all targets for a tenant (never returns credentials)."""
        from database.session import get_db
        from database.models import Target

        with get_db() as db:
            targets = (
                db.query(Target)
                .filter_by(tenant_id=tenant_id)
                .order_by(Target.created_at.desc())
                .all()
            )
            return [t.to_dict() for t in targets]

    def delete_target(self, tenant_id: str, target_id: str) -> bool:
        """Delete a target and its credentials from Prism."""
        from database.session import get_db
        from database.models import Target

        with get_db() as db:
            target = (
                db.query(Target)
                .filter_by(id=target_id, tenant_id=tenant_id)
                .first()
            )
            if not target:
                return False

            # Delete credentials from Prism
            if target.credential_prism_key:
                self._delete_credentials(tenant_id, target_id)

            db.delete(target)
            db.commit()

        logger.info(f"Deleted target {target_id} for tenant {tenant_id}")
        return True

    def rotate_credentials(
        self,
        tenant_id: str,
        target_id: str,
        new_credentials: dict,
    ) -> bool:
        """Atomic credential rotation: delete old, store new in Prism.

        Args:
            tenant_id: Tenant identifier.
            target_id: Target to rotate credentials for.
            new_credentials: New credential dict (headers, cookies, etc.).

        Returns:
            True if successful, False if target not found.
        """
        from database.session import get_db
        from database.models import Target

        with get_db() as db:
            target = (
                db.query(Target)
                .filter_by(id=target_id, tenant_id=tenant_id)
                .first()
            )
            if not target:
                return False

            # Delete old credentials from Prism
            if target.credential_prism_key:
                self._delete_credentials(tenant_id, target_id)

            # Store new credentials
            creds = {k: v for k, v in new_credentials.items() if k in SENSITIVE_FIELDS and v}
            if creds:
                prism_key = self._store_credentials(tenant_id, target_id, creds)
                target.credential_prism_key = prism_key
                target.has_credentials = prism_key is not None
            else:
                target.credential_prism_key = None
                target.has_credentials = False

            target.updated_at = datetime.utcnow().isoformat()
            db.commit()

        logger.info(f"Rotated credentials for target {target_id}")
        return True

    def fetch_credentials(self, tenant_id: str, target_id: str) -> Optional[dict]:
        """Fetch credentials from Prism for use during scan execution.

        This is called by the Celery worker at scan start. Credentials
        are held in memory only for the duration of the scan.

        Args:
            tenant_id: Tenant identifier.
            target_id: Target whose credentials to fetch.

        Returns:
            Credential dict or None if no credentials stored.
        """
        from database.session import get_db
        from database.models import Target

        with get_db() as db:
            target = (
                db.query(Target)
                .filter_by(id=target_id, tenant_id=tenant_id)
                .first()
            )
            if not target or not target.credential_prism_key:
                return None

        # Fetch from Prism
        try:
            from services.prism_client import get_prism_client, prism_available
            if not prism_available():
                return None

            client = get_prism_client()
            key = _prism_credential_key(target_id)
            data = client.fetch_sync(tenant_id, key)
            if data is None:
                logger.warning(f"Credentials not found in Prism for target {target_id}")
                return None
            return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to fetch credentials for target {target_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal Prism operations
    # ------------------------------------------------------------------

    def _store_credentials(self, tenant_id: str, target_id: str, creds: dict) -> Optional[str]:
        """Store credentials in Prism. Returns the Prism key or None on failure."""
        try:
            from services.prism_client import get_prism_client, prism_available
            if not prism_available():
                logger.warning("Prism not available, credentials not stored securely")
                return None

            client = get_prism_client()
            key = _prism_credential_key(target_id)
            data = json.dumps(creds).encode("utf-8")
            full_key = client.store_sync(tenant_id, key, data)
            logger.debug(f"Stored credentials in Prism: {full_key}")
            return full_key
        except Exception as e:
            logger.error(f"Failed to store credentials in Prism for target {target_id}: {e}")
            return None

    def _delete_credentials(self, tenant_id: str, target_id: str) -> None:
        """Delete credentials from Prism. Best-effort."""
        try:
            from services.prism_client import get_prism_client, prism_available
            if not prism_available():
                return

            client = get_prism_client()
            key = _prism_credential_key(target_id)
            client.delete_sync(tenant_id, key)
            logger.debug(f"Deleted credentials from Prism for target {target_id}")
        except Exception as e:
            logger.warning(f"Failed to delete credentials from Prism for target {target_id}: {e}")


# Module-level singleton
_target_service: Optional[TargetService] = None


def get_target_service() -> TargetService:
    """Get or create the module-level TargetService singleton."""
    global _target_service
    if _target_service is None:
        _target_service = TargetService()
    return _target_service
