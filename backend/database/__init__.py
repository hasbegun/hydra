"""
Database package for Hydra backend.

Provides persistence via SQLAlchemy for scan metadata, config templates,
and custom probe metadata. Supports PostgreSQL (production) and SQLite
(testing/fallback).
"""
from database.session import get_db, init_db, DatabaseSession

__all__ = ["get_db", "init_db", "DatabaseSession"]
