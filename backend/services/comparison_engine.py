"""
Comparison engine — diffs two ``VulnerabilityReport`` instances to
detect new findings, resolved findings, regressions, and risk score
deltas.

Used by:
  - ``GET /scan/{id}/report/comparison?compare_to={other_id}``
  - Webhook notification enhancement (include diff summary)
"""
import logging
from typing import Optional

from models.report_schemas import VulnerabilityReport, Finding

logger = logging.getLogger(__name__)


class ComparisonResult:
    """Result of comparing two vulnerability reports."""

    def __init__(
        self,
        baseline_scan_id: str,
        current_scan_id: str,
        risk_score_baseline: float,
        risk_score_current: float,
        new_findings: list[dict],
        resolved_findings: list[dict],
        regressions: list[dict],
        improvements: list[dict],
    ):
        self.baseline_scan_id = baseline_scan_id
        self.current_scan_id = current_scan_id
        self.risk_score_baseline = risk_score_baseline
        self.risk_score_current = risk_score_current
        self.risk_delta = round(risk_score_current - risk_score_baseline, 1)
        self.new_findings = new_findings
        self.resolved_findings = resolved_findings
        self.regressions = regressions
        self.improvements = improvements

    def to_dict(self) -> dict:
        return {
            "baseline_scan_id": self.baseline_scan_id,
            "current_scan_id": self.current_scan_id,
            "risk_score_baseline": self.risk_score_baseline,
            "risk_score_current": self.risk_score_current,
            "risk_delta": self.risk_delta,
            "new_findings_count": len(self.new_findings),
            "resolved_findings_count": len(self.resolved_findings),
            "regressions_count": len(self.regressions),
            "improvements_count": len(self.improvements),
            "new_findings": self.new_findings,
            "resolved_findings": self.resolved_findings,
            "regressions": self.regressions,
            "improvements": self.improvements,
        }


def _finding_key(f: Finding) -> str:
    """Unique key for a finding — the probe classname."""
    return f.probe


def _finding_summary(f: Finding) -> dict:
    """Compact summary of a finding for comparison output."""
    return {
        "probe": f.probe,
        "severity": f.severity,
        "failure_rate": round(f.failure_rate * 100, 1),
        "failed_attempts": f.failed_attempts,
        "total_attempts": f.total_attempts,
    }


def compare_reports(
    baseline: Optional[VulnerabilityReport],
    current: VulnerabilityReport,
) -> ComparisonResult:
    """Compare two vulnerability reports and produce a diff.

    Parameters
    ----------
    baseline : VulnerabilityReport or None
        The previous/baseline report. If None, all current findings are
        treated as new (first scan scenario).
    current : VulnerabilityReport
        The current report being compared.

    Returns
    -------
    ComparisonResult
        Contains new findings, resolved findings, regressions, and
        improvements with risk score delta.
    """
    if baseline is None:
        # First scan — everything is new, no regressions
        return ComparisonResult(
            baseline_scan_id="",
            current_scan_id=current.scan_id,
            risk_score_baseline=0.0,
            risk_score_current=current.executive_summary.risk_score,
            new_findings=[_finding_summary(f) for f in current.findings if f.failed_attempts > 0],
            resolved_findings=[],
            regressions=[],
            improvements=[],
        )

    # Build lookup maps by probe
    baseline_map: dict[str, Finding] = {_finding_key(f): f for f in baseline.findings}
    current_map: dict[str, Finding] = {_finding_key(f): f for f in current.findings}

    new_findings: list[dict] = []
    resolved_findings: list[dict] = []
    regressions: list[dict] = []
    improvements: list[dict] = []

    # Check current findings against baseline
    for key, cur_f in current_map.items():
        base_f = baseline_map.get(key)

        if base_f is None:
            # Finding exists in current but not in baseline → new
            if cur_f.failed_attempts > 0:
                new_findings.append(_finding_summary(cur_f))
        else:
            # Finding exists in both — check for regression/improvement
            base_rate = base_f.failure_rate
            cur_rate = cur_f.failure_rate

            if cur_f.failed_attempts > 0 and base_f.failed_attempts == 0:
                # Was passing, now failing → regression
                regressions.append({
                    **_finding_summary(cur_f),
                    "baseline_failure_rate": round(base_rate * 100, 1),
                })
            elif cur_rate > base_rate + 0.03:
                # Failure rate increased by >3% → regression
                regressions.append({
                    **_finding_summary(cur_f),
                    "baseline_failure_rate": round(base_rate * 100, 1),
                })
            elif cur_f.failed_attempts == 0 and base_f.failed_attempts > 0:
                # Was failing, now passing → improvement
                improvements.append({
                    **_finding_summary(cur_f),
                    "baseline_failure_rate": round(base_rate * 100, 1),
                })
            elif cur_rate < base_rate - 0.03:
                # Failure rate decreased by >3% → improvement
                improvements.append({
                    **_finding_summary(cur_f),
                    "baseline_failure_rate": round(base_rate * 100, 1),
                })

    # Check baseline findings not in current → resolved
    for key, base_f in baseline_map.items():
        if key not in current_map and base_f.failed_attempts > 0:
            resolved_findings.append(_finding_summary(base_f))

    return ComparisonResult(
        baseline_scan_id=baseline.scan_id,
        current_scan_id=current.scan_id,
        risk_score_baseline=baseline.executive_summary.risk_score,
        risk_score_current=current.executive_summary.risk_score,
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        regressions=regressions,
        improvements=improvements,
    )
