"""
Report generator — assembles a complete ``VulnerabilityReport`` from
raw scan data.

Orchestrates:
  1. ``finding_builder.build_findings`` — JSONL → structured findings
  2. ``risk_scorer.score_findings`` — findings → 0-100 risk score
  3. ``_build_owasp_matrix`` — findings → OWASP LLM Top 10 compliance
  4. ``_build_executive_summary`` — summary stats

Reports are stored in Prism with tenant-scoped keys.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from models.report_schemas import (
    ExecutiveSummary,
    Finding,
    OWASPCategory,
    VulnerabilityReport,
)
from services.finding_builder import build_findings
from services.risk_scorer import score_findings

logger = logging.getLogger(__name__)

# OWASP LLM Top 10 (2025) categories
OWASP_LLM_TOP_10 = [
    ("LLM01", "Prompt Injection"),
    ("LLM02", "Insecure Output Handling"),
    ("LLM03", "Training Data Poisoning"),
    ("LLM04", "Model Denial of Service"),
    ("LLM05", "Supply Chain Vulnerabilities"),
    ("LLM06", "Sensitive Information Disclosure"),
    ("LLM07", "Insecure Plugin Design"),
    ("LLM08", "Excessive Agency"),
    ("LLM09", "Overreliance"),
    ("LLM10", "Model Theft"),
]


def _build_owasp_matrix(findings: list[Finding]) -> list[OWASPCategory]:
    """Build the OWASP LLM Top 10 compliance matrix from findings.

    For each OWASP category, determines:
      - Which probes tested it
      - Whether any probe targeting it failed
      - "pass" / "fail" / "not_tested"
    """
    # Collect probes per OWASP category
    category_probes: dict[str, list[str]] = {cat_id: [] for cat_id, _ in OWASP_LLM_TOP_10}
    category_failures: dict[str, int] = {cat_id: 0 for cat_id, _ in OWASP_LLM_TOP_10}

    for finding in findings:
        for owasp_id in finding.owasp_llm:
            if owasp_id in category_probes:
                if finding.probe not in category_probes[owasp_id]:
                    category_probes[owasp_id].append(finding.probe)
                if finding.failed_attempts > 0:
                    category_failures[owasp_id] += finding.failed_attempts

    matrix: list[OWASPCategory] = []
    for cat_id, cat_name in OWASP_LLM_TOP_10:
        probes = category_probes[cat_id]
        failures = category_failures[cat_id]
        if not probes:
            status = "not_tested"
        elif failures > 0:
            status = "fail"
        else:
            status = "pass"

        matrix.append(OWASPCategory(
            id=cat_id,
            name=cat_name,
            status=status,
            probes_tested=probes,
            finding_count=failures,
        ))

    return matrix


def _build_executive_summary(
    findings: list[Finding], risk_score: float,
) -> ExecutiveSummary:
    """Build the executive summary from findings and risk score."""
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_tests = 0
    passed = 0
    failed = 0

    for f in findings:
        total_tests += f.total_attempts
        passed += f.total_attempts - f.failed_attempts
        failed += f.failed_attempts
        if f.severity in severity_counts and f.failed_attempts > 0:
            severity_counts[f.severity] += 1

    pass_rate = round((passed / total_tests * 100) if total_tests > 0 else 100.0, 1)

    # Top risks: up to 5 findings with highest severity + failure rate
    top_risks = [
        f"{f.probe} ({f.severity}, {round(f.failure_rate * 100, 1)}% failure)"
        for f in findings
        if f.failed_attempts > 0
    ][:5]

    return ExecutiveSummary(
        risk_score=risk_score,
        total_tests=total_tests,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        critical_count=severity_counts["critical"],
        high_count=severity_counts["high"],
        medium_count=severity_counts["medium"],
        low_count=severity_counts["low"],
        top_risks=top_risks,
    )


def generate_vulnerability_report(
    scan_id: str,
    entries: list[dict],
    tenant_id: str = "default",
    target_name: str = "",
    target_type: str = "",
) -> VulnerabilityReport:
    """Generate a full vulnerability report from raw JSONL entries.

    Parameters
    ----------
    scan_id : str
        The scan identifier.
    entries : list[dict]
        Raw JSONL entries from the garak report.
    tenant_id : str
        Tenant identifier for scoping.
    target_name : str
        Display name of the scanned target.
    target_type : str
        Target type (e.g., "rest", "openai").

    Returns
    -------
    VulnerabilityReport
        Fully populated report with executive summary, findings, and
        OWASP compliance matrix.
    """
    findings = build_findings(entries)
    risk_score = score_findings([f.model_dump() for f in findings])
    compliance = _build_owasp_matrix(findings)
    executive_summary = _build_executive_summary(findings, risk_score)

    return VulnerabilityReport(
        scan_id=scan_id,
        tenant_id=tenant_id,
        target_name=target_name,
        target_type=target_type,
        generated_at=datetime.now(timezone.utc).isoformat(),
        executive_summary=executive_summary,
        findings=findings,
        compliance=compliance,
    )


def _set_tenant_if_supported(store: object, tenant_id: str) -> None:
    """Call ``set_tenant`` on the store if it supports it (PrismStorage)."""
    setter = getattr(store, "set_tenant", None)
    if callable(setter):
        setter(tenant_id)


def store_report_in_prism(
    report: VulnerabilityReport, tenant_id: str,
) -> bool:
    """Store a vulnerability report in Prism (tenant-scoped).

    Key format: ``{tenant_id}/report:{scan_id}:vuln``

    Returns True if stored successfully, False on failure.
    """
    try:
        from services.object_store import get_object_store

        store = get_object_store()
        _set_tenant_if_supported(store, tenant_id)

        key = f"{tenant_id}/report:{report.scan_id}:vuln"
        data = report.model_dump_json().encode("utf-8")
        store.store(key, data)
        logger.info("Stored vulnerability report in Prism: %s", key)
        return True
    except Exception as e:
        logger.warning("Failed to store vulnerability report: %s", e)
        return False


def load_report_from_prism(
    scan_id: str, tenant_id: str,
) -> Optional[VulnerabilityReport]:
    """Load a vulnerability report from Prism.

    Returns None if not found or on error.
    """
    try:
        from services.object_store import get_object_store

        store = get_object_store()
        _set_tenant_if_supported(store, tenant_id)

        key = f"{tenant_id}/report:{scan_id}:vuln"
        data = store.fetch(key)
        if data is None:
            return None
        return VulnerabilityReport.model_validate_json(data)
    except Exception as e:
        logger.warning("Failed to load vulnerability report: %s", e)
        return None
