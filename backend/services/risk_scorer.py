"""
Risk scoring engine for vulnerability reports.

Computes a 0-100 risk score using the formula:

    risk_score = Σ(severity_weight × failure_rate × probe_count) / max_possible × 100

Reuses ``SEVERITY_WEIGHTS`` and ``classify_severity`` from
``gate_evaluator`` to avoid duplication.
"""
import logging
from typing import Optional

from services.gate_evaluator import SEVERITY_WEIGHTS, classify_severity

logger = logging.getLogger(__name__)


def score_findings(findings: list) -> float:
    """Compute a 0-100 risk score from a list of Finding-like dicts.

    Each finding must have: ``probe``, ``total_attempts``, ``failed_attempts``,
    ``failure_rate``, ``severity``.

    Formula:
        weighted_sum = Σ(severity_weight × failure_rate × total_attempts)
        max_possible = Σ(max_weight × total_attempts)
        risk_score   = (weighted_sum / max_possible) × 100

    Returns 0 when there are no findings or all pass.
    """
    if not findings:
        return 0.0

    max_weight = SEVERITY_WEIGHTS["critical"]
    weighted_sum = 0.0
    total_attempts = 0

    for f in findings:
        attempts = f.get("total_attempts", 0)
        if attempts == 0:
            continue
        total_attempts += attempts
        failure_rate = f.get("failure_rate", 0.0)
        severity = f.get("severity", "info")
        weight = SEVERITY_WEIGHTS.get(severity, 0)
        weighted_sum += weight * failure_rate * attempts

    max_possible = total_attempts * max_weight
    if max_possible == 0:
        return 0.0

    return min(round((weighted_sum / max_possible) * 100, 1), 100.0)


def classify_finding_severity(
    probe_name: str, failure_rate: float, override: Optional[str] = None,
) -> str:
    """Classify a finding's severity.

    Delegates to ``gate_evaluator.classify_severity`` unless an explicit
    override is provided (e.g. from probe_knowledge).
    """
    if override and override in SEVERITY_WEIGHTS:
        # Knowledge-base severity should still be escalated for critical
        # failure rates.
        if failure_rate > 0.8 and SEVERITY_WEIGHTS.get(override, 0) < SEVERITY_WEIGHTS["critical"]:
            return "critical"
        return override
    return classify_severity(probe_name, failure_rate)
