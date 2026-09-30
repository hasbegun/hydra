"""
Phase 4 Week 12 — Compliance evidence tests.

Tests SOC 2 + ISO 27001 mapping, evidence PDF generation,
and the campaign evidence endpoint.
"""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.report_schemas import (
    VulnerabilityReport, ExecutiveSummary, Finding, OWASPCategory,
)
from services.compliance_mapper import (
    map_findings_to_soc2,
    map_findings_to_iso27001,
    build_compliance_package,
    SOC2_CONTROLS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(
    probe: str, severity: str = "high",
    total: int = 10, failed: int = 5,
    owasp: list[str] | None = None,
) -> Finding:
    rate = failed / total if total > 0 else 0.0
    return Finding(
        probe=probe,
        severity=severity,
        total_attempts=total,
        failed_attempts=failed,
        failure_rate=rate,
        owasp_llm=owasp or [],
    )


def _make_report(findings: list[Finding], risk_score: float = 50.0) -> VulnerabilityReport:
    return VulnerabilityReport(
        scan_id="scan-compliance-001",
        tenant_id="t1",
        generated_at="2024-06-01T00:00:00Z",
        executive_summary=ExecutiveSummary(risk_score=risk_score),
        findings=findings,
        compliance=[],
    )


# ===================================================================
# SOC 2 Mapping
# ===================================================================

class TestSOC2Mapping:
    def test_maps_owasp_llm01_to_cc71(self):
        """Finding with OWASP LLM01 → CC7.1 control."""
        findings = [_finding("dan.Dan_11_0", severity="critical", owasp=["LLM01"])]
        mappings = map_findings_to_soc2(findings)
        cc71 = next(m for m in mappings if m.control_id == "CC7.1")
        assert cc71.status == "fail"
        assert len(cc71.findings) == 1
        assert cc71.findings[0]["probe"] == "dan.Dan_11_0"

    def test_maps_owasp_llm06_to_cc61(self):
        """Finding with OWASP LLM06 → CC6.1 control."""
        findings = [_finding("apikey.IsApiKey", severity="medium", owasp=["LLM06"])]
        mappings = map_findings_to_soc2(findings)
        cc61 = next(m for m in mappings if m.control_id == "CC6.1")
        # medium severity only → partial
        assert cc61.status == "partial"

    def test_control_pass_when_all_probes_pass(self):
        """SOC 2 control is 'pass' when all mapped probes passed."""
        findings = [_finding("dan.Dan_11_0", severity="low", failed=0, owasp=["LLM01"])]
        mappings = map_findings_to_soc2(findings)
        cc71 = next(m for m in mappings if m.control_id == "CC7.1")
        assert cc71.status == "pass"

    def test_not_assessed_when_no_probes(self):
        """Control is 'not_assessed' when no mapped probes tested."""
        findings = [_finding("dan.Dan_11_0", owasp=["LLM01"])]
        mappings = map_findings_to_soc2(findings)
        # CC8.1 maps to LLM05, which isn't tested
        cc81 = next(m for m in mappings if m.control_id == "CC8.1")
        assert cc81.status == "not_assessed"

    def test_all_six_soc2_controls_present(self):
        """All 6 SOC 2 controls are always in the output."""
        findings = [_finding("dan.Dan_11_0", owasp=["LLM01"])]
        mappings = map_findings_to_soc2(findings)
        assert len(mappings) == 6
        ids = {m.control_id for m in mappings}
        assert ids == {"CC6.1", "CC6.6", "CC7.1", "CC7.2", "CC8.1", "CC9.2"}

    def test_multiple_findings_per_control(self):
        """Multiple probes can contribute to the same control."""
        findings = [
            _finding("dan.Dan_11_0", severity="critical", owasp=["LLM01"]),
            _finding("continuation.ContinueSlur", severity="high", owasp=["LLM01"]),
        ]
        mappings = map_findings_to_soc2(findings)
        cc71 = next(m for m in mappings if m.control_id == "CC7.1")
        assert cc71.status == "fail"
        assert len(cc71.findings) == 2


# ===================================================================
# ISO 27001 Mapping
# ===================================================================

class TestISO27001Mapping:
    def test_maps_any_failed_finding_to_a828(self):
        """Any finding with failures → A.8.28 fail."""
        findings = [_finding("dan.Dan_11_0", owasp=["LLM01"])]
        mappings = map_findings_to_iso27001(findings)
        assert len(mappings) == 1
        assert mappings[0].control_id == "A.8.28"
        assert mappings[0].status == "fail"
        assert mappings[0].framework == "ISO 27001:2022"

    def test_pass_when_all_probes_pass(self):
        """A.8.28 passes when all probes pass."""
        findings = [_finding("dan.Dan_11_0", failed=0)]
        mappings = map_findings_to_iso27001(findings)
        assert mappings[0].status == "pass"

    def test_not_assessed_when_no_findings(self):
        """No findings at all → not_assessed."""
        mappings = map_findings_to_iso27001([])
        assert mappings[0].status == "not_assessed"


# ===================================================================
# Full Compliance Package
# ===================================================================

class TestCompliancePackage:
    def test_builds_complete_package(self):
        """Package has all required sections."""
        findings = [
            _finding("dan.Dan_11_0", severity="critical", owasp=["LLM01"]),
            _finding("encoding.InjectBase64", severity="high", owasp=["LLM01"]),
        ]
        report = _make_report(findings, risk_score=65.0)
        package = build_compliance_package(report)

        assert package["scan_id"] == "scan-compliance-001"
        assert package["risk_score"] == 65.0
        assert len(package["soc2_controls"]) == 6
        assert len(package["iso27001_controls"]) == 1
        assert "summary" in package
        assert package["summary"]["iso27001_status"] == "fail"

    def test_includes_gate_history(self):
        """Gate history included when provided."""
        report = _make_report([], risk_score=10.0)
        gate_history = [
            {"scan_id": "gate-1", "gate_passed": True, "risk_score": 10.0, "timestamp": "2024-06-01"},
            {"scan_id": "gate-2", "gate_passed": False, "risk_score": 80.0, "timestamp": "2024-06-02"},
        ]
        package = build_compliance_package(report, gate_history=gate_history)
        assert len(package["gate_history"]) == 2
        assert package["gate_history"][0]["gate_passed"] is True
        assert package["gate_history"][1]["gate_passed"] is False

    def test_includes_risk_trend(self):
        """Risk trend included when provided."""
        report = _make_report([], risk_score=30.0)
        risk_trend = [
            {"scan_id": "s1", "risk_score": 80.0, "timestamp": "2024-03-01"},
            {"scan_id": "s2", "risk_score": 50.0, "timestamp": "2024-06-01"},
            {"scan_id": "s3", "risk_score": 30.0, "timestamp": "2024-09-01"},
        ]
        package = build_compliance_package(report, risk_trend=risk_trend)
        assert len(package["risk_trend"]) == 3


# ===================================================================
# Evidence HTML Template
# ===================================================================

class TestEvidenceTemplate:
    def test_evidence_pdf_contains_control_sections(self):
        """Evidence HTML has SOC 2 control headings."""
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        findings = [_finding("dan.Dan_11_0", severity="critical", owasp=["LLM01"])]
        report = _make_report(findings)
        package = build_compliance_package(report)

        templates_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
        template = env.get_template("evidence_report.html")
        html = template.render(package=package, branding={}, css="")

        assert "CC7.1" in html
        assert "Detection and Monitoring" in html
        assert "SOC 2 Control Assessment" in html
        assert "ISO 27001" in html
        assert "A.8.28" in html

    def test_evidence_pdf_contains_gate_history(self):
        """Evidence HTML includes gate verdicts table."""
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        report = _make_report([])
        gate_history = [
            {"scan_id": "gate-1", "gate_passed": True, "risk_score": 15.0, "timestamp": "2024-06-01"},
        ]
        package = build_compliance_package(report, gate_history=gate_history)

        templates_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
        template = env.get_template("evidence_report.html")
        html = template.render(package=package, branding={}, css="")

        assert "CI/CD Gate History" in html
        assert "gate-1" in html
        assert "PASS" in html

    def test_evidence_pdf_contains_trend(self):
        """Evidence HTML includes risk score trend table."""
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        report = _make_report([])
        risk_trend = [
            {"scan_id": "s1", "risk_score": 80.0, "timestamp": "2024-03-01"},
            {"scan_id": "s2", "risk_score": 30.0, "timestamp": "2024-09-01"},
        ]
        package = build_compliance_package(report, risk_trend=risk_trend)

        templates_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
        template = env.get_template("evidence_report.html")
        html = template.render(package=package, branding={}, css="")

        assert "Risk Score Trend" in html
        assert "80.0" in html
        assert "30.0" in html


# ===================================================================
# Evidence Endpoint
# ===================================================================

class TestEvidenceEndpoint:
    def test_evidence_endpoint_returns_response(self):
        """GET /campaigns/{id}/evidence → response with attachment."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t1"

        mock_svc = MagicMock()
        mock_svc.get_campaign.return_value = {"id": "camp-1", "name": "Test"}
        mock_svc.list_runs.return_value = [
            {"run_id": "run-1", "scan_ids": ["scan-ev-1"]},
        ]

        findings = [_finding("dan.Dan_11_0", severity="critical", owasp=["LLM01"])]
        report = _make_report(findings)

        with patch("api.routes.campaigns.get_tenant", return_value=mock_tenant), \
             patch("api.routes.campaigns.get_campaign_service", return_value=mock_svc), \
             patch("api.routes.campaigns.load_report_from_prism", return_value=report):

            from api.routes.campaigns import router
            app = FastAPI()
            app.include_router(router, prefix="/api/v1/campaigns")
            client = TestClient(app)

            resp = client.get("/api/v1/campaigns/camp-1/evidence")
            assert resp.status_code == 200
            assert "attachment" in resp.headers.get("content-disposition", "")
            content = resp.content.decode("utf-8")
            assert "SOC 2" in content
            assert "CC7.1" in content

    def test_evidence_scoped_to_tenant(self):
        """Tenant A cannot access Tenant B's campaign evidence."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "tenant-A"

        mock_svc = MagicMock()
        mock_svc.get_campaign.return_value = None  # Not found for this tenant

        with patch("api.routes.campaigns.get_tenant", return_value=mock_tenant), \
             patch("api.routes.campaigns.get_campaign_service", return_value=mock_svc):

            from api.routes.campaigns import router
            app = FastAPI()
            app.include_router(router, prefix="/api/v1/campaigns")
            client = TestClient(app)

            resp = client.get("/api/v1/campaigns/other-camp/evidence")
            assert resp.status_code == 404

    def test_evidence_requires_runs(self):
        """Evidence requires at least one campaign run."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t1"

        mock_svc = MagicMock()
        mock_svc.get_campaign.return_value = {"id": "camp-1"}
        mock_svc.list_runs.return_value = []

        with patch("api.routes.campaigns.get_tenant", return_value=mock_tenant), \
             patch("api.routes.campaigns.get_campaign_service", return_value=mock_svc):

            from api.routes.campaigns import router
            app = FastAPI()
            app.include_router(router, prefix="/api/v1/campaigns")
            client = TestClient(app)

            resp = client.get("/api/v1/campaigns/camp-1/evidence")
            assert resp.status_code == 400
