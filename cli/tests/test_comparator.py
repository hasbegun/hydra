"""
Tests for cli/comparator.py — result comparison engine.

Covers T3.1-T3.5 from the test plan.
"""
import json
import os
import sys
import time
from io import StringIO
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from comparator import (
    ComparisonResult,
    ProbeComparison,
    check_regression,
    compare_results,
    extract_counts,
    find_previous_result,
    print_comparison,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_result(path: Path, data: dict) -> str:
    """Write a JSON result file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return str(path)


def _make_result(passed: int, failed: int, probes: dict = None) -> dict:
    """Build a minimal scan result dict."""
    result = {
        "status": "completed",
        "passed": passed,
        "failed": failed,
        "summary": {"passed": passed, "failed": failed},
    }
    if probes:
        result["digest"] = probes
    return result


# ---------------------------------------------------------------------------
# T3.1: Find previous result
# ---------------------------------------------------------------------------

class TestFindPreviousResult:
    def test_finds_most_recent(self, tmp_path):
        # Create two result files with different mtimes
        old = tmp_path / "llama3.2_2026-01-06.json"
        new = tmp_path / "llama3.2_2026-01-13.json"
        _write_result(old, _make_result(40, 5))
        time.sleep(0.05)
        _write_result(new, _make_result(42, 3))

        # Exclude the "current" file (new), should find old
        result = find_previous_result("llama3.2", str(tmp_path), str(new))
        assert result is not None
        assert result.name == "llama3.2_2026-01-06.json"

    def test_finds_without_exclusion(self, tmp_path):
        f1 = tmp_path / "llama3.2_2026-01-06.json"
        _write_result(f1, _make_result(40, 5))
        result = find_previous_result("llama3.2", str(tmp_path))
        assert result is not None
        assert result.name == "llama3.2_2026-01-06.json"

    def test_only_matches_target_name(self, tmp_path):
        _write_result(tmp_path / "mistral_2026-01-06.json", _make_result(40, 5))
        result = find_previous_result("llama3.2", str(tmp_path))
        assert result is None


# ---------------------------------------------------------------------------
# T3.2: No previous result
# ---------------------------------------------------------------------------

class TestNoPreviousResult:
    def test_empty_directory(self, tmp_path):
        result = find_previous_result("llama3.2", str(tmp_path))
        assert result is None

    def test_nonexistent_directory(self):
        result = find_previous_result("llama3.2", "/nonexistent/path")
        assert result is None

    def test_only_current_file(self, tmp_path):
        current = tmp_path / "llama3.2_2026-01-13.json"
        _write_result(current, _make_result(42, 3))
        result = find_previous_result("llama3.2", str(tmp_path), str(current))
        assert result is None


# ---------------------------------------------------------------------------
# T3.3: Compare improved
# ---------------------------------------------------------------------------

class TestCompareImproved:
    def test_overall_improvement(self, tmp_path):
        prev = _write_result(
            tmp_path / "llama3.2_2026-01-06.json",
            _make_result(80, 20, {
                "dan.Dan_11_0": {"passed": 8, "failed": 2},
            }),
        )
        curr = _write_result(
            tmp_path / "llama3.2_2026-01-13.json",
            _make_result(90, 10, {
                "dan.Dan_11_0": {"passed": 9, "failed": 1},
            }),
        )

        comp = compare_results(curr, prev, "llama3.2")
        assert comp.overall_delta > 0
        assert comp.overall_label == "IMPROVED"
        assert comp.current_pass_rate > comp.previous_pass_rate

    def test_per_probe_improvement(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(70, 30, {
                "dan.Dan_11_0": {"passed": 7, "failed": 3},
                "encoding.Base64": {"passed": 8, "failed": 2},
            }),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(85, 15, {
                "dan.Dan_11_0": {"passed": 9, "failed": 1},
                "encoding.Base64": {"passed": 9, "failed": 1},
            }),
        )

        comp = compare_results(curr, prev, "target")
        for pc in comp.probe_comparisons:
            assert pc.delta > 0
            assert pc.label == "IMPROVED"


# ---------------------------------------------------------------------------
# T3.4: Compare regression
# ---------------------------------------------------------------------------

class TestCompareRegression:
    def test_overall_regression(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(92, 8),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(75, 25),
        )

        comp = compare_results(curr, prev, "target")
        assert comp.overall_delta < 0
        assert comp.overall_label == "REGRESSION"

    def test_per_probe_regression_flagged(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(90, 10, {
                "dan.Dan_11_0": {"passed": 9, "failed": 1},
            }),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(70, 30, {
                "dan.Dan_11_0": {"passed": 5, "failed": 5},
            }),
        )

        comp = compare_results(curr, prev, "target")
        assert len(comp.regressions) > 0
        assert comp.regressions[0].probe_name == "dan.Dan_11_0"
        assert comp.regressions[0].is_regression


# ---------------------------------------------------------------------------
# T3.5: Threshold check
# ---------------------------------------------------------------------------

class TestThresholdCheck:
    def test_regression_below_threshold_ok(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(90, 10),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(87, 13),
        )
        comp = compare_results(curr, prev, "target")
        # Delta is -3%, threshold 5% -> should NOT trigger
        assert not check_regression(comp, 5.0)

    def test_regression_above_threshold_triggers(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(90, 10),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(80, 20),
        )
        comp = compare_results(curr, prev, "target")
        # Delta is -10%, threshold 5% -> SHOULD trigger
        assert check_regression(comp, 5.0)

    def test_improvement_never_triggers(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(80, 20),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(95, 5),
        )
        comp = compare_results(curr, prev, "target")
        assert not check_regression(comp, 0.0)

    def test_per_probe_regression_triggers(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(90, 10, {
                "dan.Dan_11_0": {"passed": 9, "failed": 1},
                "encoding.Base64": {"passed": 9, "failed": 1},
            }),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(85, 15, {
                "dan.Dan_11_0": {"passed": 5, "failed": 5},
                "encoding.Base64": {"passed": 10, "failed": 0},
            }),
        )
        comp = compare_results(curr, prev, "target")
        # dan dropped 40%, threshold 5% -> triggers
        assert check_regression(comp, 5.0)


# ---------------------------------------------------------------------------
# print_comparison output
# ---------------------------------------------------------------------------

class TestPrintComparison:
    def test_output_contains_key_info(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(80, 20, {"dan": {"passed": 8, "failed": 2}}),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(90, 10, {"dan": {"passed": 9, "failed": 1}}),
        )
        comp = compare_results(curr, prev, "my-target")

        buf = StringIO()
        print_comparison(comp, threshold=5.0, file=buf)
        output = buf.getvalue()

        assert "my-target" in output
        assert "COMPARISON" in output
        assert "No regressions" in output

    def test_regression_output(self, tmp_path):
        prev = _write_result(
            tmp_path / "t_2026-01-06.json",
            _make_result(90, 10, {"dan": {"passed": 9, "failed": 1}}),
        )
        curr = _write_result(
            tmp_path / "t_2026-01-13.json",
            _make_result(60, 40, {"dan": {"passed": 4, "failed": 6}}),
        )
        comp = compare_results(curr, prev, "my-target")

        buf = StringIO()
        print_comparison(comp, threshold=5.0, file=buf)
        output = buf.getvalue()

        assert "REGRESSION" in output


# ---------------------------------------------------------------------------
# Data class properties
# ---------------------------------------------------------------------------

class TestDataClasses:
    def test_probe_comparison_delta(self):
        pc = ProbeComparison("dan", previous_rate=80.0, current_rate=90.0)
        assert pc.delta == 10.0
        assert not pc.is_regression
        assert pc.label == "IMPROVED"

    def test_probe_comparison_regression(self):
        pc = ProbeComparison("dan", previous_rate=90.0, current_rate=80.0)
        assert pc.delta == -10.0
        assert pc.is_regression
        assert pc.label == "REGRESSION"

    def test_probe_comparison_unchanged(self):
        pc = ProbeComparison("dan", previous_rate=85.0, current_rate=85.0)
        assert pc.delta == 0.0
        assert not pc.is_regression
        assert pc.label == "UNCHANGED"

    def test_comparison_result_regressions(self):
        comp = ComparisonResult(
            target_name="t",
            current_date="2026-01-13",
            previous_date="2026-01-06",
            current_pass_rate=80.0,
            previous_pass_rate=90.0,
            probe_comparisons=[
                ProbeComparison("dan", 90.0, 70.0),
                ProbeComparison("enc", 85.0, 95.0),
            ],
        )
        assert len(comp.regressions) == 1
        assert comp.regressions[0].probe_name == "dan"
        assert comp.overall_delta == -10.0
        assert comp.overall_label == "REGRESSION"


# ---------------------------------------------------------------------------
# extract_counts — shared result extraction
# ---------------------------------------------------------------------------

class TestExtractCounts:
    """Tests for the canonical extract_counts function."""

    def test_from_results_nested(self):
        result = {
            "results": {"passed": 8, "failed": 2},
            "summary": {"total_tests": 10, "pass_rate": 80.0},
        }
        p, f, t, r = extract_counts(result)
        assert (p, f, t) == (8, 2, 10)
        assert r == 80.0

    def test_from_top_level(self):
        result = {"passed": 5, "failed": 3}
        p, f, t, r = extract_counts(result)
        assert (p, f, t) == (5, 3, 8)
        assert abs(r - 62.5) < 0.1

    def test_empty_result(self):
        p, f, t, r = extract_counts({})
        assert (p, f, t, r) == (0, 0, 0, 0.0)

    def test_none_sub_objects(self):
        p, f, t, r = extract_counts({"results": None, "summary": None})
        assert (p, f, t, r) == (0, 0, 0, 0.0)

    def test_summary_pass_rate_takes_precedence(self):
        result = {
            "results": {"passed": 9, "failed": 1},
            "summary": {"total_tests": 10, "pass_rate": 90.0},
        }
        _, _, _, r = extract_counts(result)
        assert r == 90.0

    def test_direct_pass_rate_field(self):
        result = {"pass_rate": 75.0}
        _, _, _, r = extract_counts(result)
        assert r == 75.0

    def test_results_preferred_over_top_level(self):
        """results.passed takes precedence over top-level passed."""
        result = {
            "passed": 100,
            "failed": 0,
            "results": {"passed": 3, "failed": 7},
        }
        p, f, _, _ = extract_counts(result)
        assert (p, f) == (3, 7)
