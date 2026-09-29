"""
One-time migration: extract plaintext credentials from Postgres
``config_json`` fields and store them in Prism.

After migration:
- Credential fields are removed from ``config_json`` in Postgres
- Prism holds the credentials under ``target:{id}:credentials``
- The ``credential_prism_key`` column is populated with the Prism key

Usage:
    python -m database.migrate_credentials_to_prism [--dry-run]

The ``--dry-run`` flag shows what would be migrated without making changes.
"""
import json
import logging
import sys

logger = logging.getLogger(__name__)

# Fields inside config_json that contain sensitive credentials
CREDENTIAL_FIELDS = {"headers", "cookies", "query_params", "api_key", "auth_token"}


def _extract_sensitive(config: dict) -> tuple[dict, dict]:
    """Split a config dict into (sensitive, non_sensitive).

    Returns:
        (credentials_dict, cleaned_config_dict)
    """
    creds = {}
    clean = {}

    for key, value in config.items():
        if key in CREDENTIAL_FIELDS and value:
            creds[key] = value
        elif key == "credentials" and isinstance(value, dict):
            # Nested credentials object
            for sub_key, sub_val in value.items():
                if sub_key in CREDENTIAL_FIELDS and sub_val:
                    creds[sub_key] = sub_val
        else:
            clean[key] = value

    return creds, clean


def migrate(dry_run: bool = False) -> dict:
    """Run the credential migration.

    Args:
        dry_run: If True, log what would happen without making changes.

    Returns:
        Summary dict with counts of migrated, skipped, and failed targets.
    """
    from database.session import get_db
    from database.models import Scan

    summary = {"migrated": 0, "skipped": 0, "failed": 0, "total": 0}

    with get_db() as db:
        # Find all scans with config_json that may contain credentials
        scans = db.query(Scan).filter(Scan.config_json.isnot(None)).all()
        summary["total"] = len(scans)

        for scan in scans:
            try:
                config = json.loads(scan.config_json)
            except (ValueError, TypeError):
                summary["skipped"] += 1
                continue

            creds, clean = _extract_sensitive(config)

            if not creds:
                summary["skipped"] += 1
                continue

            if dry_run:
                logger.info(
                    f"[DRY RUN] Scan {scan.id}: would migrate "
                    f"{list(creds.keys())} to Prism"
                )
                summary["migrated"] += 1
                continue

            # Store in Prism
            try:
                from services.prism_client import get_prism_client, prism_available
                if not prism_available():
                    logger.warning("Prism not available, skipping migration")
                    summary["failed"] += 1
                    continue

                client = get_prism_client()
                tenant_id = scan.tenant_id or "default"
                key = f"scan:{scan.id}:credentials"
                data = json.dumps(creds).encode("utf-8")
                client.store_sync(tenant_id, key, data)

                # Update Postgres: remove credentials from config_json
                scan.config_json = json.dumps(clean)
                db.commit()

                logger.info(
                    f"Migrated scan {scan.id}: {list(creds.keys())} -> Prism"
                )
                summary["migrated"] += 1
            except Exception as e:
                logger.error(f"Failed to migrate scan {scan.id}: {e}")
                summary["failed"] += 1

    return summary


def main():
    """CLI entry point."""
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    dry_run = "--dry-run" in sys.argv

    if dry_run:
        logger.info("=== DRY RUN MODE — no changes will be made ===")

    summary = migrate(dry_run=dry_run)

    logger.info(f"\nMigration complete:")
    logger.info(f"  Total scans:  {summary['total']}")
    logger.info(f"  Migrated:     {summary['migrated']}")
    logger.info(f"  Skipped:      {summary['skipped']}")
    logger.info(f"  Failed:       {summary['failed']}")

    if summary["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
