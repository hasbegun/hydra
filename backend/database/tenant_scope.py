"""
Tenant-scoped query helpers.

Provides ``scoped_query()`` to filter any SQLAlchemy query by ``tenant_id``,
ensuring tenant isolation at the data access layer.

Usage::

    from database.tenant_scope import scoped_query

    with get_db() as db:
        # Returns only scans belonging to the given tenant
        scans = scoped_query(db, Scan, tenant_id).all()

        # Combine with additional filters
        running = (
            scoped_query(db, Scan, tenant_id)
            .filter(Scan.status == "running")
            .all()
        )
"""
import logging
from typing import TypeVar

from sqlalchemy.orm import Session, Query

logger = logging.getLogger(__name__)

T = TypeVar("T")


def scoped_query(db: Session, model: type, tenant_id: str) -> Query:
    """Return a query on ``model`` filtered by ``tenant_id``.

    Args:
        db: SQLAlchemy session.
        model: ORM model class (must have a ``tenant_id`` column).
        tenant_id: Tenant identifier to filter by.

    Returns:
        A SQLAlchemy Query pre-filtered to the given tenant.
    """
    if not hasattr(model, "tenant_id"):
        raise AttributeError(
            f"{model.__name__} does not have a 'tenant_id' column — "
            "cannot apply tenant scoping"
        )
    return db.query(model).filter(model.tenant_id == tenant_id)
