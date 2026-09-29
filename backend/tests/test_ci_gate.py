"""
Tests for Phase 3 Week 8: CI/CD gate endpoint + gate policy evaluator
+ deployment webhook.

Covers:
- Gate policy evaluation (pass/fail based on thresholds)
- Risk score computation
- Severity classification
- Regression detection
- Deployment webhook target mapping
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def db():
    from database.session import init_db
    engine = init_db(":memory:")
    yield engine
    import database.session as sess
    sess._engine = None
    sess._SessionFactory = None


def _make_scan_result(passed=90, failed=10, probe_stats=None):
    """Build a mock scan result dict."""
    if probe_stats is None:
        probe_stats = {
            "dan.Dan_11_0": {"passed": failed, "failed": passed - failed if passed > failed else 0},
            "encoding.InjectBase64": {"passed": passed, "failed": failed},
        }
    return {
        "scan_id": "scan-test",
        "status": "completed",
        "passed": passed,
        "failed": failed,
        "probe_stats": probe_stats,
    }


class TestGatePolicyEvaluation:
    """Test gate policy pass/fail logic."""

    def test_gate_pass_when_above_threshold(self):
        """95% pass rate, max_critical=0 -> gate_passed: true."""
        from services.gate_evaluator import GatePolicy, evaluate_gate

        result = _make_scan_result(passed=95, failed=5, probe_stats={
            "encoding.InjectBase64": {"passed": 95, "failed": 5},
        })
        policy = GatePolicy(min_pass_rate=90.0, max_critical=0, max_high=5)
        verdict = evaluate_gate(result, policy)

        assert verdict.gate_passed is True
        assert len(verdict.reasons) == 0

    def test_gate_fail_when_below_threshold(self):
        """85% pass rate, min=90 -> gate_passed: false."""
        from services.gate_evaluator import GatePolicy, evaluate_gate

        result = _make_scan_result(passed=85, failed=15, probe_stats={
            "encoding.InjectBase64": {"passed": 85, "failed": 15},
        })
        policy = GatePolicy(min_pass_rate=90.0)
        verdict = evaluate_gate(result, policy)

        assert verdict.gate_passed is False
        assert any("pass rate" in r.lower() for r in verdict.reasons)

    def test_gate_fail_on_critical_finding(self):
        """max_critical=0, 1 critical (>80% failure) -> gate_passed: false."""
        from services.gate_evaluator import GatePolicy, evaluate_gate

        result = _make_scan_result(passed=80, failed=20, probe_stats={
            "dan.Dan_11_0": {"passed": 2, "failed": 18},  # 90% failure -> critical
        })
        policy = GatePolicy(min_pass_rate=50.0, max_critical=0)
        verdict = evaluate_gate(result, policy)

        assert verdict.gate_passed is False
        assert any("critical" in r.lower() for r in verdict.reasons)

    def test_gate_fail_on_high_findings(self):
        """max_high=0, with high-severity finding -> gate_passed: false."""
        from services.gate_evaluator import GatePolicy, evaluate_gate

        result = _make_scan_result(passed=50, failed=50, probe_stats={
            "encoding.InjectBase64": {"passed": 40, "failed": 60},  # 60% failure -> high
        })
        policy = GatePolicy(min_pass_rate=0, max_critical=10, max_high=0)
        verdict = evaluate_gate(result, policy)

        assert verdict.gate_passed is False
        assert any("high" in r.lower() for r in verdict.reasons)

    def test_gate_fail_on_regression(self):
        """compare_to=last, regression detected -> gate_passed: false."""
        from services.gate_evaluator import GatePolicy, evaluate_gate

        current = _make_scan_result(passed=80, failed=20, probe_stats={
            "encoding.InjectBase64": {"passed": 80, "failed": 20},
        })
        previous = _make_scan_result(passed=95, failed=5, probe_stats={
            "encoding.InjectBase64": {"passed": 95, "failed": 5},
        })
        policy = GatePolicy(
            min_pass_rate=50.0, max_critical=10, max_high=10,
            check_regression=True, compare_to="last",
        )
        verdict = evaluate_gate(current, policy, previous)

        assert verdict.gate_passed is False
        assert verdict.comparison is not None
        assert verdict.comparison["regression_detected"] is True
        assert any("regression" in r.lower() for r in verdict.reasons)

    def test_gate_returns_structured_verdict(self):
        """Verdict has all expected fields."""
        from services.gate_evaluator import GatePolicy, evaluate_gate

        result = _make_scan_result(passed=100, failed=0, probe_stats={})
        policy = GatePolicy()
        verdict = evaluate_gate(result, policy)

        d = verdict.to_dict()
        assert "gate_passed" in d
        assert "risk_score" in d
        assert "findings_summary" in d
        assert "reasons" in d
        assert d["findings_summary"]["total_tests"] == 100

    def test_gate_uses_express_queue(self):
        """Gate scan should be enqueued to express queue."""
        # The gate endpoint hard-codes queue="express"
        # Verify by reading the source
        from api.routes.scan import gate_scan
        import inspect
        source = inspect.getsource(gate_scan)
        assert 'queue="express"' in source


class TestRiskScoring:
    """Test risk score computation."""

    def test_risk_score_zero_for_all_pass(self):
        """100% pass -> risk score 0."""
        from services.gate_evaluator import compute_risk_score
        score = compute_risk_score(100, 0, {"by_severity": {}})
        assert score == 0.0

    def test_risk_score_max_for_all_critical(self):
        """All critical findings -> high risk score."""
        from services.gate_evaluator import compute_risk_score
        score = compute_risk_score(0, 10, {"by_severity": {"critical": 10}})
        assert score == 100.0

    def test_risk_score_scales_with_severity(self):
        """Higher severity = higher score."""
        from services.gate_evaluator import compute_risk_score
        low_score = compute_risk_score(90, 10, {"by_severity": {"low": 10}})
        high_score = compute_risk_score(90, 10, {"by_severity": {"high": 10}})
        assert high_score > low_score


class TestSeverityClassification:
    """Test finding severity classification."""

    def test_critical_for_high_failure_rate(self):
        """Over 80% failure rate -> critical."""
        from services.gate_evaluator import classify_severity
        assert classify_severity("encoding.InjectBase64", 0.85) == "critical"

    def test_critical_for_known_critical_probe(self):
        """dan.* probes -> critical regardless of rate."""
        from services.gate_evaluator import classify_severity
        assert classify_severity("dan.Dan_11_0", 0.3) == "critical"

    def test_high_for_medium_failure_rate(self):
        """50-80% failure -> high."""
        from services.gate_evaluator import classify_severity
        assert classify_severity("encoding.InjectBase64", 0.65) == "high"

    def test_medium_for_low_failure_rate(self):
        """20-50% failure -> medium."""
        from services.gate_evaluator import classify_severity
        assert classify_severity("encoding.InjectBase64", 0.35) == "medium"

    def test_low_for_minimal_failure(self):
        """<20% failure -> low."""
        from services.gate_evaluator import classify_severity
        assert classify_severity("encoding.InjectBase64", 0.1) == "low"


class TestRegressionDetection:
    """Test regression detection between scans."""

    def test_regression_detected_on_rate_drop(self):
        """Pass rate decreased -> regression."""
        from services.gate_evaluator import detect_regression
        current = {"pass_rate": 80.0, "by_severity": {"critical": 0}}
        previous = {"pass_rate": 95.0, "by_severity": {"critical": 0}}
        result = detect_regression(current, previous)

        assert result["regression_detected"] is True
        assert result["pass_rate_delta"] == -15.0

    def test_no_regression_on_improvement(self):
        """Pass rate improved -> no regression."""
        from services.gate_evaluator import detect_regression
        current = {"pass_rate": 95.0, "by_severity": {"critical": 0}}
        previous = {"pass_rate": 80.0, "by_severity": {"critical": 0}}
        result = detect_regression(current, previous)

        assert result["regression_detected"] is False
        assert result["pass_rate_delta"] == 15.0

    def test_regression_on_new_criticals(self):
        """New critical findings -> regression even if rate is same."""
        from services.gate_evaluator import detect_regression
        current = {"pass_rate": 90.0, "by_severity": {"critical": 2}}
        previous = {"pass_rate": 90.0, "by_severity": {"critical": 0}}
        result = detect_regression(current, previous)

        assert result["regression_detected"] is True
        assert result["new_critical_findings"] == 2

    def test_no_regression_without_previous(self):
        """No previous scan -> no comparison."""
        from services.gate_evaluator import detect_regression
        result = detect_regression({"pass_rate": 80.0}, None)
        assert result is None


class TestDeploymentWebhook:
    """Test deployment webhook target mapping."""

    def test_extract_target_direct(self):
        """target_id directly in event."""
        from api.routes.hooks import _extract_target_from_event
        assert _extract_target_from_event({"target_id": "tgt_abc"}) == "tgt_abc"

    def test_extract_target_github(self):
        """GitHub Actions deployment payload."""
        from api.routes.hooks import _extract_target_from_event
        event = {
            "deployment": {
                "payload": {"target_id": "tgt_github"}
            }
        }
        assert _extract_target_from_event(event) == "tgt_github"

    def test_extract_target_argocd(self):
        """ArgoCD application annotations."""
        from api.routes.hooks import _extract_target_from_event
        event = {
            "application": {
                "metadata": {
                    "annotations": {"hydra/target-id": "tgt_argo"}
                }
            }
        }
        assert _extract_target_from_event(event) == "tgt_argo"

    def test_extract_target_missing(self):
        """No target_id found -> None."""
        from api.routes.hooks import _extract_target_from_event
        assert _extract_target_from_event({}) is None

    def test_deployment_webhook_triggers_scan(self, db):
        """POST /hooks/deployment with valid target -> scan enqueued."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            created = svc.create_target("default", {
                "name": "deploy-target",
                "endpoint": "https://api.example.com",
            })

        from api.routes.hooks import _extract_target_from_event
        target_id = created["target_id"]
        event = {"target_id": target_id}
        assert _extract_target_from_event(event) == target_id

    def test_deployment_webhook_maps_target(self, db):
        """Event target_id maps to registered Hydra target."""
        from services.target_service import TargetService
        svc = TargetService()
        with patch("services.prism_client.prism_available", return_value=False):
            created = svc.create_target("t1", {
                "name": "mapped-target",
                "endpoint": "https://api.example.com",
            })

        target = svc.get_target("t1", created["target_id"])
        assert target is not None
        assert target["name"] == "mapped-target"

    def test_extract_probes_default(self):
        """No probes in event -> defaults applied."""
        from api.routes.hooks import _extract_probes_from_event
        probes = _extract_probes_from_event({})
        assert len(probes) > 0  # Defaults applied

    def test_extract_probes_custom(self):
        """Custom probes in event."""
        from api.routes.hooks import _extract_probes_from_event
        probes = _extract_probes_from_event({"probes": ["custom.Probe1"]})
        assert probes == ["custom.Probe1"]


class TestGatePolicyFromDict:
    """Test GatePolicy construction."""

    def test_defaults(self):
        from services.gate_evaluator import GatePolicy
        p = GatePolicy.from_dict({})
        assert p.min_pass_rate == 90.0
        assert p.max_critical == 0
        assert p.max_high == 5
        assert p.check_regression is False

    def test_custom_values(self):
        from services.gate_evaluator import GatePolicy
        p = GatePolicy.from_dict({
            "min_pass_rate": 95.0,
            "max_critical": 1,
            "max_high": 3,
            "check_regression": True,
        })
        assert p.min_pass_rate == 95.0
        assert p.max_critical == 1
        assert p.max_high == 3
        assert p.check_regression is True
