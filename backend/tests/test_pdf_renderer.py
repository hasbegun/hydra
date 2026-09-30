"""
Phase 4 Week 11 — PDF renderer tests.

Tests HTML template rendering, branding, content inclusion,
and PDF endpoint behavior.
"""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.report_schemas import (
    VulnerabilityReport, ExecutiveSummary, Finding, OWASPCategory, FindingEvidence,
)
from services.pdf_renderer import render_html, render_pdf, _risk_level


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(risk_score: float = 42.0, with_findings: bool = True) -> VulnerabilityReport:
    """Create a test report with optional findings."""
    findings = []
    if with_findings:
        findings = [
            Finding(
                probe="dan.Dan_11_0",
                category="DAN Jailbreak",
                severity="critical",
                description="Tests DAN jailbreak resistance.",
                risk_explanation="DAN attacks bypass safety training.",
                mitigation="Strengthen system prompts.",
                cwe_ids=["CWE-693"],
                owasp_llm=["LLM01"],
                total_attempts=10,
                failed_attempts=7,
                failure_rate=0.7,
                evidence=[
                    FindingEvidence(
                        prompt="Hello, I am DAN",
                        response="Sure! I can do anything now!",
                        result="fail",
                    ),
                ],
            ),
            Finding(
                probe="encoding.InjectBase64",
                category="Encoding Attacks",
                severity="high",
                description="Tests encoded payload attacks.",
                mitigation="Decode and filter inputs.",
                cwe_ids=["CWE-116"],
                owasp_llm=["LLM01"],
                total_attempts=10,
                failed_attempts=3,
                failure_rate=0.3,
                evidence=[],
            ),
        ]

    return VulnerabilityReport(
        scan_id="scan-pdf-001",
        tenant_id="t1",
        target_name="gpt-4o-staging",
        target_type="openai",
        generated_at="2024-01-15T10:30:00Z",
        executive_summary=ExecutiveSummary(
            risk_score=risk_score,
            total_tests=20,
            passed=10,
            failed=10,
            pass_rate=50.0,
            critical_count=1,
            high_count=1,
            medium_count=0,
            low_count=0,
            top_risks=["dan.Dan_11_0 (critical, 70.0% failure)"],
        ),
        findings=findings,
        compliance=[
            OWASPCategory(id="LLM01", name="Prompt Injection", status="fail",
                         probes_tested=["dan.Dan_11_0"], finding_count=7),
            OWASPCategory(id="LLM02", name="Insecure Output Handling", status="not_tested",
                         probes_tested=[], finding_count=0),
        ],
    )


# ===================================================================
# HTML Rendering
# ===================================================================

class TestHTMLRendering:
    def test_renders_from_vulnerability_report(self):
        """VulnerabilityReport → valid HTML string."""
        report = _make_report()
        html = render_html(report)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "scan-pdf-001" in html

    def test_includes_executive_summary(self):
        """HTML contains risk score, finding counts."""
        report = _make_report(risk_score=72.0)
        html = render_html(report)
        assert "72.0" in html  # risk score
        assert "/ 100 Risk Score" in html
        assert ">20<" in html  # total tests
        assert ">10<" in html  # passed/failed

    def test_includes_owasp_matrix(self):
        """HTML contains OWASP LLM Top 10 table."""
        report = _make_report()
        html = render_html(report)
        assert "OWASP LLM Top 10" in html
        assert "LLM01" in html
        assert "Prompt Injection" in html
        assert "FAIL" in html
        assert "NOT_TESTED" in html

    def test_includes_findings_with_evidence(self):
        """HTML contains prompt/response pairs."""
        report = _make_report()
        html = render_html(report)
        assert "dan.Dan_11_0" in html
        assert "Hello, I am DAN" in html
        assert "Sure! I can do anything now!" in html
        assert "CWE-693" in html
        assert "DAN Jailbreak" in html

    def test_includes_severity_badges(self):
        """HTML contains severity classifications."""
        report = _make_report()
        html = render_html(report)
        assert "CRITICAL" in html
        assert "HIGH" in html

    def test_includes_mitigation(self):
        """HTML includes recommended mitigations."""
        report = _make_report()
        html = render_html(report)
        assert "Strengthen system prompts" in html

    def test_includes_target_info(self):
        """HTML includes target name and type."""
        report = _make_report()
        html = render_html(report)
        assert "gpt-4o-staging" in html
        assert "openai" in html


# ===================================================================
# Branding
# ===================================================================

class TestBranding:
    def test_uses_tenant_branding(self):
        """Company name, analyst, footer from branding config."""
        report = _make_report()
        branding = {
            "company_name": "HealthCo Security",
            "analyst": "Jane Doe",
            "footer": "Confidential — HealthCo Internal Use Only",
        }
        html = render_html(report, branding)
        assert "HealthCo Security" in html
        assert "Jane Doe" in html
        assert "Confidential — HealthCo Internal Use Only" in html

    def test_default_branding_when_none_set(self):
        """Works without custom branding — uses defaults."""
        report = _make_report()
        html = render_html(report, branding=None)
        assert "Hydra Security" in html
        assert "Generated by Hydra" in html

    def test_logo_included_when_set(self):
        """Logo URL rendered as img tag."""
        report = _make_report()
        branding = {"logo_url": "https://example.com/logo.png"}
        html = render_html(report, branding)
        assert "https://example.com/logo.png" in html
        assert "<img" in html

    def test_no_logo_tag_when_empty(self):
        """No img tag when logo_url is empty."""
        report = _make_report()
        html = render_html(report, branding={"logo_url": ""})
        # Should not have an img with empty src
        assert 'class="logo"' not in html


# ===================================================================
# PDF Generation
# ===================================================================

class TestPDFGeneration:
    def test_pdf_returns_bytes(self):
        """render_pdf returns bytes (HTML fallback in test env)."""
        report = _make_report()
        result = render_pdf(report)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_fallback_contains_html(self):
        """Without weasyprint, returns valid HTML bytes."""
        report = _make_report()
        result = render_pdf(report)
        # In test env without weasyprint, this should be HTML
        text = result.decode("utf-8")
        assert "<!DOCTYPE html>" in text
        assert "scan-pdf-001" in text

    def test_pdf_with_branding(self):
        """Branding applied to PDF output."""
        report = _make_report()
        result = render_pdf(report, branding={"company_name": "Sentinel"})
        text = result.decode("utf-8")
        assert "Sentinel" in text


# ===================================================================
# Risk Level Classification
# ===================================================================

class TestRiskLevel:
    def test_critical_above_75(self):
        assert _risk_level(80.0) == "critical"

    def test_high_50_to_75(self):
        assert _risk_level(60.0) == "high"

    def test_medium_25_to_50(self):
        assert _risk_level(30.0) == "medium"

    def test_low_below_25(self):
        assert _risk_level(10.0) == "low"


# ===================================================================
# PDF Storage
# ===================================================================

class TestPDFStorage:
    def test_pdf_stored_in_prism(self):
        """PDF bytes stored with tenant-prefixed key."""
        from services.pdf_renderer import store_pdf_in_prism

        class FakeStore:
            def __init__(self):
                self._data = {}
                self._tenant = None
            def set_tenant(self, tid):
                self._tenant = tid
            def store(self, key, data):
                self._data[key] = data

        fake = FakeStore()
        with patch("services.object_store.get_object_store", return_value=fake):
            result = store_pdf_in_prism(b"fake-pdf", "scan-99", "t1")
            assert result is True
            assert "t1/report:scan-99:pdf" in fake._data
            assert fake._tenant == "t1"


# ===================================================================
# PDF Endpoint
# ===================================================================

class TestPDFEndpoint:
    def test_pdf_endpoint_returns_bytes(self):
        """GET /report/pdf → response with attachment header."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        report = _make_report()
        entries = [
            {"entry_type": "attempt", "probe_classname": "dan.Dan_11_0",
             "status": 1, "prompt": {"turns": [{"content": {"text": "test"}}]},
             "outputs": [{"text": "resp"}]},
        ]

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t1"

        with patch("api.routes.scan.get_tenant", return_value=mock_tenant), \
             patch("api.routes.scan.garak_wrapper") as mock_gw, \
             patch("api.routes.scan.load_report_from_prism", return_value=report), \
             patch("api.routes.scan.store_pdf_in_prism", return_value=True):

            mock_gw.get_scan_status.return_value = {
                "scan_id": "scan-pdf-e2e", "status": "completed",
                "config": {"model_name": "gpt4"}, "passed": 5, "failed": 5,
            }

            from api.routes.scan import router
            app = FastAPI()
            app.include_router(router, prefix="/api/v1/scan")
            client = TestClient(app)

            resp = client.get("/api/v1/scan/scan-pdf-e2e/report/pdf")
            assert resp.status_code == 200
            assert "attachment" in resp.headers.get("content-disposition", "")
            assert len(resp.content) > 0
