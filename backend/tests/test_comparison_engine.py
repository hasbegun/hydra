"""
Phase 4 Week 11 — Comparison engine tests.

Tests detection of new findings, resolved findings, regressions,
improvements, and risk score deltas.
"""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.report_schemas import (
    VulnerabilityReport, ExecutiveSummary, Finding, OWASPCategory,
)
from services.comparison_engine import compare_reports, ComparisonResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    scan_id: str, risk_score: float, findings: list[Finding],
) -> VulnerabilityReport:
    """Create a minimal VulnerabilityReport for testing."""
    return VulnerabilityReport(
        scan_id=scan_id,
        tenant_id="t1",
        executive_summary=ExecutiveSummary(risk_score=risk_score),
        findings=findings,
        compliance=[],
    )


def _finding(
    probe: str, severity: str = "high",
    total: int = 10, failed: int = 5,
) -> Finding:
    """Create a minimal Finding for testing."""
    rate = failed / total if total > 0 else 0.0
    return Finding(
        probe=probe,
        severity=severity,
        total_attempts=total,
        failed_attempts=failed,
        failure_rate=rate,
    )


# ===================================================================
# New Findings
# ===================================================================

class TestNewFindings:
    def test_detects_new_finding(self):
        """Finding in current but not in baseline → new."""
        baseline = _make_report("scan-A", 20.0, [
            _finding("dan.Dan_11_0", failed=3),
        ])
        current = _make_report("scan-B", 40.0, [
            _finding("dan.Dan_11_0", failed=3),
            _finding("encoding.InjectBase64", failed=5),
        ])
        result = compare_reports(baseline, current)
        assert result.current_scan_id == "scan-B"
        assert len(result.new_findings) == 1
        assert result.new_findings[0]["probe"] == "encoding.InjectBase64"

    def test_no_new_when_same_probes(self):
        """Same probes in both → no new findings."""
        baseline = _make_report("scan-A", 20.0, [_finding("dan.Dan_11_0")])
        current = _make_report("scan-B", 20.0, [_finding("dan.Dan_11_0")])
        result = compare_reports(baseline, current)
        assert len(result.new_findings) == 0


# ===================================================================
# Resolved Findings
# ===================================================================

class TestResolvedFindings:
    def test_detects_resolved_finding(self):
        """Finding in baseline but not in current → resolved."""
        baseline = _make_report("scan-A", 30.0, [
            _finding("dan.Dan_11_0", failed=5),
            _finding("encoding.InjectBase64", failed=3),
        ])
        current = _make_report("scan-B", 10.0, [
            _finding("dan.Dan_11_0", failed=5),
        ])
        result = compare_reports(baseline, current)
        assert len(result.resolved_findings) == 1
        assert result.resolved_findings[0]["probe"] == "encoding.InjectBase64"

    def test_passing_baseline_not_resolved(self):
        """Baseline finding with 0 failures is not counted as resolved if absent."""
        baseline = _make_report("scan-A", 0.0, [
            _finding("dan.Dan_11_0", failed=0),
        ])
        current = _make_report("scan-B", 0.0, [])
        result = compare_reports(baseline, current)
        assert len(result.resolved_findings) == 0


# ===================================================================
# Regressions
# ===================================================================

class TestRegressions:
    def test_detects_regression_pass_to_fail(self):
        """Finding passed in baseline, failed in current → regression."""
        baseline = _make_report("scan-A", 0.0, [
            _finding("dan.Dan_11_0", failed=0, total=10),
        ])
        current = _make_report("scan-B", 50.0, [
            _finding("dan.Dan_11_0", failed=7, total=10),
        ])
        result = compare_reports(baseline, current)
        assert len(result.regressions) == 1
        assert result.regressions[0]["probe"] == "dan.Dan_11_0"
        assert result.regressions[0]["baseline_failure_rate"] == 0.0

    def test_detects_regression_rate_increase(self):
        """Failure rate increased by >3% → regression."""
        baseline = _make_report("scan-A", 20.0, [
            _finding("dan.Dan_11_0", failed=2, total=10),  # 20%
        ])
        current = _make_report("scan-B", 40.0, [
            _finding("dan.Dan_11_0", failed=5, total=10),  # 50%
        ])
        result = compare_reports(baseline, current)
        assert len(result.regressions) == 1

    def test_no_regression_within_tolerance(self):
        """Failure rate change <=3% → not a regression."""
        baseline = _make_report("scan-A", 20.0, [
            _finding("dan.Dan_11_0", failed=5, total=10),  # 50%
        ])
        current = _make_report("scan-B", 20.0, [
            _finding("dan.Dan_11_0", failed=5, total=10),  # 50% (same)
        ])
        result = compare_reports(baseline, current)
        assert len(result.regressions) == 0


# ===================================================================
# Improvements
# ===================================================================

class TestImprovements:
    def test_detects_improvement_fail_to_pass(self):
        """Finding failed in baseline, passed in current → improvement."""
        baseline = _make_report("scan-A", 50.0, [
            _finding("dan.Dan_11_0", failed=5, total=10),
        ])
        current = _make_report("scan-B", 0.0, [
            _finding("dan.Dan_11_0", failed=0, total=10),
        ])
        result = compare_reports(baseline, current)
        assert len(result.improvements) == 1
        assert result.improvements[0]["probe"] == "dan.Dan_11_0"

    def test_detects_improvement_rate_decrease(self):
        """Failure rate decreased by >3% → improvement."""
        baseline = _make_report("scan-A", 40.0, [
            _finding("dan.Dan_11_0", failed=7, total=10),  # 70%
        ])
        current = _make_report("scan-B", 20.0, [
            _finding("dan.Dan_11_0", failed=3, total=10),  # 30%
        ])
        result = compare_reports(baseline, current)
        assert len(result.improvements) == 1


# ===================================================================
# Risk Score Delta
# ===================================================================

class TestRiskDelta:
    def test_risk_delta_calculated(self):
        """Risk score difference computed correctly."""
        baseline = _make_report("scan-A", 30.0, [])
        current = _make_report("scan-B", 50.0, [])
        result = compare_reports(baseline, current)
        assert result.risk_delta == 20.0

    def test_risk_delta_negative_means_improvement(self):
        """Negative delta = risk decreased."""
        baseline = _make_report("scan-A", 80.0, [])
        current = _make_report("scan-B", 40.0, [])
        result = compare_reports(baseline, current)
        assert result.risk_delta == -40.0


# ===================================================================
# First Scan (no baseline)
# ===================================================================

class TestFirstScan:
    def test_no_baseline_all_findings_are_new(self):
        """No previous scan → all failed findings are new."""
        current = _make_report("scan-first", 50.0, [
            _finding("dan.Dan_11_0", failed=5),
            _finding("encoding.InjectBase64", failed=3),
        ])
        result = compare_reports(None, current)
        assert result.baseline_scan_id == ""
        assert len(result.new_findings) == 2
        assert len(result.resolved_findings) == 0
        assert len(result.regressions) == 0
        assert result.risk_delta == 50.0

    def test_no_baseline_no_error(self):
        """First scan comparison works without error."""
        current = _make_report("scan-first", 0.0, [])
        result = compare_reports(None, current)
        assert isinstance(result, ComparisonResult)


# ===================================================================
# Serialization
# ===================================================================

class TestComparisonSerialization:
    def test_to_dict_structure(self):
        """to_dict output has all required fields."""
        baseline = _make_report("scan-A", 30.0, [_finding("dan.Dan_11_0", failed=5)])
        current = _make_report("scan-B", 50.0, [
            _finding("dan.Dan_11_0", failed=8),
            _finding("encoding.InjectBase64", failed=3),
        ])
        result = compare_reports(baseline, current)
        d = result.to_dict()
        assert "baseline_scan_id" in d
        assert "current_scan_id" in d
        assert "risk_delta" in d
        assert "new_findings_count" in d
        assert "resolved_findings_count" in d
        assert "regressions_count" in d
        assert "improvements_count" in d
        assert "new_findings" in d
        assert "resolved_findings" in d
        assert "regressions" in d
        assert "improvements" in d
