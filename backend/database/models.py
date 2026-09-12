"""
SQLAlchemy ORM models for Hydra database.

Tables:
  - scans: Scan metadata (replaces parsing JSONL first entries)
  - config_templates: User config templates (replaces individual JSON files)
  - custom_probes: Custom probe metadata (replaces metadata.json)
  - db_meta: Schema version tracking
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean,
    Index, create_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Scan(Base):
    """Scan metadata — one row per scan (active or historical)."""
    __tablename__ = "scans"

    id = Column(String, primary_key=True)
    target_type = Column(String, nullable=False, default="unknown")
    target_name = Column(String, nullable=False, default="unknown")
    status = Column(String, nullable=False, default="pending")
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
    total_probes = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    pass_rate = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    report_path = Column(String, nullable=True)  # local path to JSONL (legacy/fallback)
    html_report_path = Column(String, nullable=True)  # local path to HTML (legacy/fallback)
    report_key = Column(String, nullable=True)  # object store key for JSONL
    html_report_key = Column(String, nullable=True)  # object store key for HTML
    probe_stats_json = Column(Text, nullable=True)  # materialized per-probe stats as JSON
    config_json = Column(Text, nullable=True)  # ScanConfig snapshot as JSON
    created_at = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_scans_status", "status"),
        Index("idx_scans_target", "target_type", "target_name"),
        Index("idx_scans_started", "started_at"),
    )

    def to_dict(self):
        """Convert to dict matching the shape expected by existing code."""
        import json as _json
        total = (self.passed or 0) + (self.failed or 0)
        config = None
        if self.config_json:
            try:
                config = _json.loads(self.config_json)
            except (ValueError, TypeError):
                pass
        return {
            "scan_id": self.id,
            "status": self.status,
            "target_type": self.target_type,
            "target_name": self.target_name,
            "started_at": self.started_at or "",
            "completed_at": self.completed_at or "",
            "passed": self.passed or 0,
            "failed": self.failed or 0,
            "total_tests": total,
            "progress": 100.0 if self.status == "completed" else 0.0,
            "config": config,
            "html_report_path": self.html_report_path,
            "jsonl_report_path": self.report_path,
            "report_key": self.report_key,
            "html_report_key": self.html_report_key,
            "error_message": self.error_message,
        }


class ConfigTemplateRow(Base):
    """User config template — replaces individual JSON files."""
    __tablename__ = "config_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    config_json = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    def to_dict(self):
        """Convert to dict matching the shape expected by existing code."""
        import json
        return {
            "name": self.name,
            "description": self.description,
            "config": json.loads(self.config_json),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CustomProbeRow(Base):
    """Custom probe metadata — replaces metadata.json."""
    __tablename__ = "custom_probes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String, nullable=False)
    goal = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "file_path": self.file_path,
            "goal": self.goal,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DBMeta(Base):
    """Simple schema version tracking."""
    __tablename__ = "db_meta"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
