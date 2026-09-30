"""
SQLAlchemy ORM models for Hydra database.

Tables:
  - scans: Scan metadata (replaces parsing JSONL first entries)
  - config_templates: User config templates (replaces individual JSON files)
  - custom_probes: Custom probe metadata (replaces metadata.json)
  - targets: Registered scan targets (credentials in Prism)
  - campaigns: Multi-target scan campaigns
  - campaign_runs: Individual campaign execution records
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
    tenant_id = Column(String, nullable=False, default="default", index=True)
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
        Index("idx_scans_tenant", "tenant_id"),
        Index("idx_scans_tenant_status", "tenant_id", "status"),
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
            "tenant_id": self.tenant_id or "default",
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
    tenant_id = Column(String, nullable=False, default="default", index=True)
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
    tenant_id = Column(String, nullable=False, default="default", index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String, nullable=False)
    goal = Column(Text, nullable=True)
    scope = Column(String, nullable=False, default="tenant")  # "global" or "tenant"
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "file_path": self.file_path,
            "goal": self.goal,
            "scope": self.scope or "tenant",
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Target(Base):
    """Registered scan target — stores non-sensitive metadata in Postgres.

    Sensitive fields (API keys, auth tokens) are stored in Prism and
    referenced via ``credential_prism_key``. The ``config_json`` column
    holds non-sensitive target configuration only (endpoint, body
    template, response extraction path).
    """
    __tablename__ = "targets"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default", index=True)
    name = Column(String, nullable=False)
    target_type = Column(String, nullable=False, default="rest")
    endpoint = Column(String, nullable=False)
    body_template = Column(Text, nullable=True)
    response_json_field = Column(String, nullable=True)
    tags = Column(Text, nullable=True)  # JSON array of string tags
    config_json = Column(Text, nullable=True)  # Non-sensitive config only
    credential_prism_key = Column(String, nullable=True)  # Prism key ref
    has_credentials = Column(Boolean, default=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_targets_tenant", "tenant_id"),
        Index("idx_targets_name_tenant", "name", "tenant_id"),
    )

    def to_dict(self):
        """Convert to API response dict (never includes credential values)."""
        import json as _json
        config = None
        if self.config_json:
            try:
                config = _json.loads(self.config_json)
            except (ValueError, TypeError):
                pass
        tags = []
        if self.tags:
            try:
                tags = _json.loads(self.tags)
            except (ValueError, TypeError):
                pass
        return {
            "target_id": self.id,
            "tenant_id": self.tenant_id or "default",
            "name": self.name,
            "type": self.target_type,
            "endpoint": self.endpoint,
            "body_template": self.body_template,
            "response_json_field": self.response_json_field,
            "tags": tags,
            "config": config,
            "has_credentials": self.has_credentials or False,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Campaign(Base):
    """Multi-target scan campaign configuration."""
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default", index=True)
    name = Column(String, nullable=False)
    target_ids_json = Column(Text, nullable=False)  # JSON array of target IDs
    probe_sets_json = Column(Text, nullable=True)   # JSON array of probe names
    strategy = Column(String, nullable=False, default="parallel")  # parallel|sequential
    schedule_cron = Column(String, nullable=True)    # Cron expression
    comparison_config_json = Column(Text, nullable=True)  # Comparison settings
    notification_config_json = Column(Text, nullable=True)  # Webhook URLs etc.
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_campaigns_tenant", "tenant_id"),
    )

    def to_dict(self):
        import json as _json
        def _safe_loads(s):
            if not s:
                return None
            try:
                return _json.loads(s)
            except (ValueError, TypeError):
                return None
        return {
            "campaign_id": self.id,
            "tenant_id": self.tenant_id or "default",
            "name": self.name,
            "target_ids": _safe_loads(self.target_ids_json) or [],
            "probe_sets": _safe_loads(self.probe_sets_json) or [],
            "strategy": self.strategy,
            "schedule_cron": self.schedule_cron,
            "comparison_config": _safe_loads(self.comparison_config_json),
            "notification_config": _safe_loads(self.notification_config_json),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CampaignRun(Base):
    """Record of a single campaign execution."""
    __tablename__ = "campaign_runs"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, default="default", index=True)
    status = Column(String, nullable=False, default="pending")  # pending|running|completed|failed
    scan_ids_json = Column(Text, nullable=True)   # JSON array of spawned scan IDs
    results_json = Column(Text, nullable=True)    # Per-target summary
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_campaign_runs_campaign", "campaign_id"),
        Index("idx_campaign_runs_tenant", "tenant_id"),
    )

    def to_dict(self):
        import json as _json
        def _safe_loads(s):
            if not s:
                return None
            try:
                return _json.loads(s)
            except (ValueError, TypeError):
                return None
        return {
            "run_id": self.id,
            "campaign_id": self.campaign_id,
            "tenant_id": self.tenant_id or "default",
            "status": self.status,
            "scan_ids": _safe_loads(self.scan_ids_json) or [],
            "results": _safe_loads(self.results_json),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }


class TenantSummary(Base):
    """Materialized per-tenant risk summary.

    Updated on every scan completion to avoid N+1 queries in the
    portfolio dashboard. One row per tenant.
    """
    __tablename__ = "tenant_summaries"

    tenant_id = Column(String, primary_key=True)
    risk_score = Column(Float, default=0.0)            # Latest scan risk score
    previous_risk_score = Column(Float, default=0.0)   # Previous scan risk score (for delta)
    risk_delta = Column(Float, default=0.0)            # risk_score - previous_risk_score
    total_scans = Column(Integer, default=0)
    completed_scans = Column(Integer, default=0)
    failed_scans = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    total_findings = Column(Integer, default=0)
    latest_scan_id = Column(String, nullable=True)
    latest_scan_at = Column(String, nullable=True)
    next_scheduled_scan = Column(String, nullable=True)  # ISO datetime of next scheduled scan
    updated_at = Column(String, nullable=False)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "risk_score": self.risk_score or 0.0,
            "previous_risk_score": self.previous_risk_score or 0.0,
            "risk_delta": self.risk_delta or 0.0,
            "total_scans": self.total_scans or 0,
            "completed_scans": self.completed_scans or 0,
            "failed_scans": self.failed_scans or 0,
            "critical_count": self.critical_count or 0,
            "high_count": self.high_count or 0,
            "medium_count": self.medium_count or 0,
            "low_count": self.low_count or 0,
            "total_findings": self.total_findings or 0,
            "latest_scan_id": self.latest_scan_id,
            "latest_scan_at": self.latest_scan_at,
            "next_scheduled_scan": self.next_scheduled_scan,
            "updated_at": self.updated_at,
        }


class TenantBranding(Base):
    """Per-tenant branding configuration for PDF reports.

    One row per tenant. Stored in Postgres (no secrets here).
    """
    __tablename__ = "tenant_branding"

    tenant_id = Column(String, primary_key=True)
    company_name = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    primary_color = Column(String, nullable=True, default="#16213e")
    footer_text = Column(String, nullable=True)
    analyst_name = Column(String, nullable=True)
    updated_at = Column(String, nullable=False)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "company_name": self.company_name or "",
            "logo_url": self.logo_url or "",
            "primary_color": self.primary_color or "#16213e",
            "footer_text": self.footer_text or "",
            "analyst_name": self.analyst_name or "",
            "updated_at": self.updated_at,
        }

    def to_branding_dict(self) -> dict:
        """Return dict in the format expected by pdf_renderer."""
        return {
            "company_name": self.company_name or "Hydra Security",
            "logo_url": self.logo_url or "",
            "primary_color": self.primary_color or "#16213e",
            "footer": self.footer_text or "Generated by Hydra — LLM Security Assessment Platform",
            "analyst": self.analyst_name or "",
        }


class DBMeta(Base):
    """Simple schema version tracking."""
    __tablename__ = "db_meta"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
