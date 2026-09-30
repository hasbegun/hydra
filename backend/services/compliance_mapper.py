"""
Compliance mapper — maps vulnerability findings to regulatory controls.

Supports:
  - SOC 2 Trust Services Criteria (CC6.1, CC6.6, CC7.1, CC7.2, CC8.1, CC9.2)
  - ISO 27001:2022 (A.8.28)

Mapping logic:
  1. Each finding's OWASP LLM category maps to one or more SOC 2 controls
  2. All findings with failed attempts map to ISO 27001 A.8.28
     ("Security of network services")
  3. Gate verdicts contribute to CC9.2 (Change Management)
"""
import logging
from typing import Optional

from models.report_schemas import Finding, VulnerabilityReport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SOC 2 Control Definitions
# ---------------------------------------------------------------------------

SOC2_CONTROLS = {
    "CC6.1": {
        "id": "CC6.1",
        "name": "Logical and Physical Access Controls",
        "description": "The entity implements logical access security software, infrastructure, "
                       "and architectures over protected information assets.",
        "owasp_mapping": ["LLM01", "LLM06"],  # Prompt injection, data disclosure
    },
    "CC6.6": {
        "id": "CC6.6",
        "name": "System Boundary Protection",
        "description": "The entity implements boundary protection controls to restrict "
                       "access to, and from, the system.",
        "owasp_mapping": ["LLM02", "LLM07"],  # Output handling, plugin design
    },
    "CC7.1": {
        "id": "CC7.1",
        "name": "Detection and Monitoring",
        "description": "To meet its objectives, the entity uses detection and monitoring "
                       "procedures to identify changes to configurations that result in "
                       "the introduction of new vulnerabilities.",
        "owasp_mapping": ["LLM01", "LLM02", "LLM05", "LLM09"],
    },
    "CC7.2": {
        "id": "CC7.2",
        "name": "Incident Response",
        "description": "The entity monitors system components and the operation of those "
                       "components for anomalies.",
        "owasp_mapping": ["LLM01", "LLM06"],
    },
    "CC8.1": {
        "id": "CC8.1",
        "name": "Change Management",
        "description": "The entity authorizes, designs, develops or acquires, configures, "
                       "documents, tests, approves, and implements changes.",
        "owasp_mapping": ["LLM05"],  # Supply chain
    },
    "CC9.2": {
        "id": "CC9.2",
        "name": "Risk Mitigation",
        "description": "The entity assesses and manages risks associated with vendors and "
                       "business partners.",
        "owasp_mapping": ["LLM05", "LLM09"],  # Supply chain, overreliance
    },
}

# ---------------------------------------------------------------------------
# ISO 27001 Control Definitions
# ---------------------------------------------------------------------------

ISO27001_CONTROLS = {
    "A.8.28": {
        "id": "A.8.28",
        "name": "Secure Coding",
        "description": "Secure coding principles shall be applied to software development. "
                       "This includes AI/ML model security testing and adversarial robustness.",
        "applies_to": "all_findings",  # Any finding with failures maps here
    },
}


class ComplianceMapping:
    """A single control mapping with evidence from scan findings."""

    def __init__(
        self,
        control_id: str,
        framework: str,
        name: str,
        description: str,
        status: str = "not_assessed",
        findings: Optional[list[dict]] = None,
        evidence_summary: str = "",
    ):
        self.control_id = control_id
        self.framework = framework
        self.name = name
        self.description = description
        self.status = status  # "pass", "fail", "partial", "not_assessed"
        self.findings = findings or []
        self.evidence_summary = evidence_summary

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "framework": self.framework,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "finding_count": len(self.findings),
            "findings": self.findings,
            "evidence_summary": self.evidence_summary,
        }


def map_findings_to_soc2(findings: list[Finding]) -> list[ComplianceMapping]:
    """Map vulnerability findings to SOC 2 controls.

    Each control is assessed based on whether any mapped OWASP categories
    have failed findings:
      - "pass" — all mapped probes passed
      - "fail" — any mapped probe has critical/high failures
      - "partial" — only medium/low failures exist
      - "not_assessed" — no probes mapped to this control were tested
    """
    # Build OWASP → findings lookup
    owasp_findings: dict[str, list[Finding]] = {}
    for f in findings:
        for owasp_id in f.owasp_llm:
            owasp_findings.setdefault(owasp_id, []).append(f)

    mappings: list[ComplianceMapping] = []

    for ctrl_id, ctrl_def in SOC2_CONTROLS.items():
        relevant: list[Finding] = []
        for owasp_id in ctrl_def["owasp_mapping"]:
            relevant.extend(owasp_findings.get(owasp_id, []))

        # Deduplicate by probe name
        seen = set()
        unique: list[Finding] = []
        for f in relevant:
            if f.probe not in seen:
                seen.add(f.probe)
                unique.append(f)

        if not unique:
            status = "not_assessed"
            evidence = "No probes tested for this control."
        else:
            failed = [f for f in unique if f.failed_attempts > 0]
            if not failed:
                status = "pass"
                evidence = f"{len(unique)} probe(s) tested, all passed."
            else:
                has_critical_high = any(f.severity in ("critical", "high") for f in failed)
                if has_critical_high:
                    status = "fail"
                    evidence = (
                        f"{len(failed)}/{len(unique)} probe(s) have failures. "
                        f"Critical/high findings detected."
                    )
                else:
                    status = "partial"
                    evidence = (
                        f"{len(failed)}/{len(unique)} probe(s) have low/medium failures."
                    )

        mappings.append(ComplianceMapping(
            control_id=ctrl_id,
            framework="SOC 2",
            name=ctrl_def["name"],
            description=ctrl_def["description"],
            status=status,
            findings=[{"probe": f.probe, "severity": f.severity,
                       "failure_rate": round(f.failure_rate * 100, 1)}
                      for f in unique if f.failed_attempts > 0],
            evidence_summary=evidence,
        ))

    return mappings


def map_findings_to_iso27001(findings: list[Finding]) -> list[ComplianceMapping]:
    """Map vulnerability findings to ISO 27001 controls.

    A.8.28 (Secure Coding) applies to all findings with failures.
    """
    failed = [f for f in findings if f.failed_attempts > 0]

    if not findings:
        status = "not_assessed"
        evidence = "No security testing performed."
    elif not failed:
        status = "pass"
        evidence = f"{len(findings)} probe(s) tested, all passed. Secure coding practices validated."
    else:
        status = "fail"
        evidence = (
            f"{len(failed)}/{len(findings)} probe(s) have failures. "
            f"Secure coding review required for AI/ML components."
        )

    ctrl = ISO27001_CONTROLS["A.8.28"]
    return [ComplianceMapping(
        control_id=ctrl["id"],
        framework="ISO 27001:2022",
        name=ctrl["name"],
        description=ctrl["description"],
        status=status,
        findings=[{"probe": f.probe, "severity": f.severity,
                   "failure_rate": round(f.failure_rate * 100, 1)}
                  for f in failed],
        evidence_summary=evidence,
    )]


def build_compliance_package(
    report: VulnerabilityReport,
    gate_history: Optional[list[dict]] = None,
    risk_trend: Optional[list[dict]] = None,
) -> dict:
    """Build a complete compliance evidence package.

    Parameters
    ----------
    report : VulnerabilityReport
        The vulnerability report to base compliance on.
    gate_history : list[dict], optional
        CI/CD gate verdicts (scan_id, gate_passed, risk_score, timestamp).
    risk_trend : list[dict], optional
        Risk scores over time (scan_id, risk_score, timestamp).

    Returns
    -------
    dict
        Complete compliance package with SOC 2 + ISO 27001 mappings,
        gate history, and risk trend.
    """
    soc2 = map_findings_to_soc2(report.findings)
    iso27001 = map_findings_to_iso27001(report.findings)

    return {
        "scan_id": report.scan_id,
        "tenant_id": report.tenant_id,
        "generated_at": report.generated_at,
        "risk_score": report.executive_summary.risk_score,
        "soc2_controls": [m.to_dict() for m in soc2],
        "iso27001_controls": [m.to_dict() for m in iso27001],
        "gate_history": gate_history or [],
        "risk_trend": risk_trend or [],
        "summary": {
            "soc2_pass": sum(1 for m in soc2 if m.status == "pass"),
            "soc2_fail": sum(1 for m in soc2 if m.status == "fail"),
            "soc2_partial": sum(1 for m in soc2 if m.status == "partial"),
            "soc2_not_assessed": sum(1 for m in soc2 if m.status == "not_assessed"),
            "iso27001_status": iso27001[0].status if iso27001 else "not_assessed",
        },
    }
