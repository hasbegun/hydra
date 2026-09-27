"""
Database session management.

Supports PostgreSQL (production) and SQLite (testing/fallback).
The engine is selected by the DATABASE_URL environment variable:
  - postgresql://user:pass@host:5432/db  → PostgreSQL
  - sqlite:///path/to/file.db            → SQLite (file)
  - sqlite:///:memory:                   → SQLite (in-memory, tests only)

If DATABASE_URL is not set, falls back to a SQLite file in the
garak reports directory.
"""
import logging
import os
from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from database.models import Base, DBMeta

logger = logging.getLogger(__name__)

# Current schema version — bump when models change
SCHEMA_VERSION = "2"

# Module-level engine and session factory (initialized by init_db)
_engine = None
_SessionFactory = None


def _get_default_db_url() -> str:
    """Build a SQLite URL as fallback when DATABASE_URL is not set.

    Stored inside garak_reports_path (the Docker shared volume at
    /data/garak_reports) so it persists across container restarts.
    """
    from config import settings
    db_dir = settings.garak_reports_path
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "hydra.db"
    return f"sqlite:///{db_path}"


def init_db(db_path: str | Path | None = None) -> None:
    """Initialize the database: create engine, create tables, store schema version.

    Args:
        db_path: Optional override.
                 - ":memory:" for in-memory SQLite (tests).
                 - A file path for file-based SQLite (legacy/fallback).
                 - A full URL string like "postgresql://..." or "sqlite:///...".
                 - None to auto-detect from DATABASE_URL env var or settings.
    """
    global _engine, _SessionFactory

    # Determine the database URL
    if db_path is not None:
        path_str = str(db_path)
        if path_str.startswith(("postgresql://", "sqlite://")):
            db_url = path_str
        elif path_str == ":memory:":
            db_url = "sqlite:///:memory:"
        else:
            db_url = f"sqlite:///{path_str}"
    else:
        db_url = os.environ.get("DATABASE_URL") or _get_default_db_url()

    is_sqlite = db_url.startswith("sqlite")

    # Build engine kwargs
    engine_kwargs = {"echo": False}
    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    _engine = create_engine(db_url, **engine_kwargs)

    # SQLite-specific pragmas (WAL for concurrency, FK enforcement)
    if is_sqlite:
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Create all tables (safe no-op if they already exist)
    Base.metadata.create_all(_engine)

    _SessionFactory = sessionmaker(bind=_engine)

    # Store schema version
    with get_db() as db:
        existing = db.query(DBMeta).filter_by(key="schema_version").first()
        if not existing:
            db.add(DBMeta(key="schema_version", value=SCHEMA_VERSION))
            db.commit()

    # Log which backend we're using
    if is_sqlite:
        logger.info(f"Database initialized: SQLite ({db_url})")
    else:
        # Redact password in log output
        safe_url = db_url
        if "@" in safe_url:
            prefix, rest = safe_url.split("://", 1)
            if "@" in rest:
                creds, host_part = rest.rsplit("@", 1)
                user = creds.split(":")[0] if ":" in creds else creds
                safe_url = f"{prefix}://{user}:***@{host_part}"
        logger.info(f"Database initialized: {safe_url}")


@contextmanager
def get_db():
    """Yield a SQLAlchemy session, auto-closing on exit.

    Usage:
        with get_db() as db:
            db.query(Scan).all()
    """
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    session: Session = _SessionFactory()
    try:
        yield session
    finally:
        session.close()


def db_available() -> bool:
    """Check if the database has been initialized.

    Centralized check — use this instead of duplicating the logic
    in individual service modules.
    """
    return _SessionFactory is not None


class DatabaseSession:
    """Convenience wrapper for dependency-injection-friendly access."""

    @staticmethod
    def get():
        """Get a context-managed session."""
        return get_db()
