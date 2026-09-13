"""
Result comparison engine for Hydra CLI scan results.

Compares current scan results with previous runs to detect regressions
and improvements in pass rates, both overall and per-probe.
"""
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProbeComparison:
    """Pass-rate change for a single probe."""
    probe_name: str
    previous_rate: float
    current_rate: float

    @property
    def delta(self) -> float:
        return self.current_rate - self.previous_rate

    @property
    def is_regression(self) -> bool:
        return self.delta < 0

    @property
    def label(self) -> str:
        if self.delta > 0:
            return "IMPROVED"
        if self.delta < 0:
            return "REGRESSION"
        return "UNCHANGED"


@dataclass
class ComparisonResult:
    """Full comparison between two scan results for the same target."""
    target_name: str
    current_date: str
    previous_date: str
    current_pass_rate: float
    previous_pass_rate: float
    probe_comparisons: List[ProbeComparison] = field(default_factory=list)

    @property
    def overall_delta(self) -> float:
        return self.current_pass_rate - self.previous_pass_rate

    @property
    def overall_label(self) -> str:
        if self.overall_delta > 0:
            return "IMPROVED"
        if self.overall_delta < 0:
            return "REGRESSION"
        return "UNCHANGED"

    @property
    def regressions(self) -> List[ProbeComparison]:
        return [p for p in self.probe_comparisons if p.is_regression]


# ---------------------------------------------------------------------------
# Finding previous results
# ---------------------------------------------------------------------------

def find_previous_result(
    target_name: str,
    baseline_dir: str,
    current_file: Optional[str] = None,
) -> Optional[Path]:
    """Find the most recent JSON result file for a given target name.

    Scans ``baseline_dir`` for files whose name contains ``target_name``
    and ends with ``.json``.  If ``current_file`` is given, it is excluded
    from candidates so we don't compare a file with itself.

    Returns the path to the most recent previous result, or None.
    """
    baseline = Path(baseline_dir)
    if not baseline.is_dir():
        return None

    # Normalise for matching: replace spaces and special chars
    safe_name = re.escape(target_name)

    candidates: list[Path] = []
    for json_file in sorted(baseline.glob("*.json")):
        if current_file and json_file.name == Path(current_file).name:
            continue
        if re.search(safe_name, json_file.stem):
            candidates.append(json_file)

    if not candidates:
        return None

    # Sort by modification time descending, pick most recent
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


# ---------------------------------------------------------------------------
# Extracting pass rates from result JSON
# ---------------------------------------------------------------------------

def extract_counts(result: dict) -> tuple:
    """Extract passed/failed/total/pass_rate from a scan result dict.

    The backend API returns data in several possible locations:
    - ``result["results"]["passed"]`` / ``result["results"]["failed"]``
    - ``result["summary"]["total_tests"]`` / ``result["summary"]["pass_rate"]``
    - ``result["passed"]`` / ``result["failed"]`` (top-level fallback)

    Returns:
        (passed, failed, total, pass_rate) where pass_rate is a percentage.
    """
    results = result.get("results", {}) or {}
    summary = result.get("summary", {}) or {}

    passed = results.get("passed") if results.get("passed") is not None else result.get("passed")
    failed = results.get("failed") if results.get("failed") is not None else result.get("failed")

    if passed is None:
        passed = summary.get("passed", 0)
    if failed is None:
        failed = summary.get("failed", 0)

    passed = passed or 0
    failed = failed or 0

    total = summary.get("total_tests") or (passed + failed)

    if summary.get("pass_rate") is not None:
        pass_rate = float(summary["pass_rate"])
    elif result.get("pass_rate") is not None:
        pass_rate = float(result["pass_rate"])
    elif total > 0:
        pass_rate = (passed / total) * 100.0
    else:
        pass_rate = 0.0

    return passed, failed, total, pass_rate


def _extract_probe_rates(result: dict) -> Dict[str, float]:
    """Extract per-probe pass rates from a scan result JSON.

    Returns a dict mapping probe name to pass rate percentage.

    Handles the garak digest format::

        digest:
          dan:                           # probe group
            _summary: { score: ... }
            dan.Dan_11_0:                # specific probe
              _summary:
                probe_score: 0.0
                probe_counts:
                  detection_counts:
                    passed: 0
                    fails: 2
    """
    rates: Dict[str, float] = {}

    # Check digest (from garak report)
    # Supports two formats:
    #   Flat:   digest.probe_name.{passed, failed}
    #   Nested: digest.group.probe_name._summary.probe_counts.detection_counts
    digest = result.get("digest", {}) or {}
    for entry_name, entry_data in digest.items():
        if not isinstance(entry_data, dict):
            continue

        # Check if this entry is a flat probe (has passed/failed directly)
        if "passed" in entry_data or "failed" in entry_data or "fails" in entry_data:
            passed = entry_data.get("passed", 0)
            failed = entry_data.get("failed", entry_data.get("fails", 0))
            total = passed + failed
            if total > 0:
                rates[entry_name] = (passed / total) * 100.0
            continue

        # Otherwise treat as a probe group — iterate sub-entries
        for key, value in entry_data.items():
            if key == "_summary" or not isinstance(value, dict):
                continue

            probe_summary = value.get("_summary", {})
            if probe_summary:
                # Real garak format: _summary.probe_counts.detection_counts
                counts = probe_summary.get("probe_counts", {})
                det_counts = counts.get("detection_counts", {})
                passed = det_counts.get("passed", 0)
                failed = det_counts.get("fails", 0)
                total = passed + failed
                if total > 0:
                    rates[key] = (passed / total) * 100.0
                elif probe_summary.get("probe_score") is not None:
                    rates[key] = float(probe_summary["probe_score"]) * 100.0
            else:
                # Sub-entry with direct passed/failed
                passed = value.get("passed", 0)
                failed = value.get("failed", value.get("fails", 0))
                total = passed + failed
                if total > 0:
                    rates[key] = (passed / total) * 100.0

    # Check results.probes (alternative structure)
    results = result.get("results", {}) or {}
    if isinstance(results, dict):
        probes = results.get("probes", {})
        if isinstance(probes, dict):
            for probe_name, probe_data in probes.items():
                if isinstance(probe_data, dict) and probe_name not in rates:
                    passed = probe_data.get("passed", 0)
                    failed = probe_data.get("failed", probe_data.get("fails", 0))
                    total = passed + failed
                    if total > 0:
                        rates[probe_name] = (passed / total) * 100.0

    return rates


def _extract_date_from_filename(filepath: Path) -> str:
    """Extract date string from a result filename.

    Expects format like ``target-name_2026-01-13.json``.
    Falls back to modification time if no date pattern found.
    """
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filepath.stem)
    if match:
        return match.group(1)

    mtime = filepath.stat().st_mtime
    return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def compare_results(
    current_path: str,
    previous_path: str,
    target_name: str,
) -> ComparisonResult:
    """Compare two JSON result files and produce a ComparisonResult.

    Args:
        current_path: Path to the current (new) result JSON.
        previous_path: Path to the previous (baseline) result JSON.
        target_name: Human-readable target label.

    Raises:
        FileNotFoundError: If either file doesn't exist.
        json.JSONDecodeError: If either file isn't valid JSON.
    """
    with open(current_path, "r", encoding="utf-8") as f:
        current = json.load(f)
    with open(previous_path, "r", encoding="utf-8") as f:
        previous = json.load(f)

    _, _, _, current_rate = extract_counts(current)
    _, _, _, previous_rate = extract_counts(previous)

    current_date = _extract_date_from_filename(Path(current_path))
    previous_date = _extract_date_from_filename(Path(previous_path))

    # Per-probe comparison
    current_probes = _extract_probe_rates(current)
    previous_probes = _extract_probe_rates(previous)

    probe_comparisons: list[ProbeComparison] = []
    all_probe_names = sorted(set(current_probes.keys()) | set(previous_probes.keys()))
    for probe_name in all_probe_names:
        if probe_name in current_probes and probe_name in previous_probes:
            probe_comparisons.append(ProbeComparison(
                probe_name=probe_name,
                previous_rate=previous_probes[probe_name],
                current_rate=current_probes[probe_name],
            ))

    return ComparisonResult(
        target_name=target_name,
        current_date=current_date,
        previous_date=previous_date,
        current_pass_rate=current_rate,
        previous_pass_rate=previous_rate,
        probe_comparisons=probe_comparisons,
    )


# ---------------------------------------------------------------------------
# Regression checking
# ---------------------------------------------------------------------------

def check_regression(result: ComparisonResult, threshold: float) -> bool:
    """Return True if any regression exceeds the threshold (percentage points).

    Checks both overall pass rate and individual probe regressions.
    """
    if result.overall_delta < -threshold:
        return True

    for pc in result.probe_comparisons:
        if pc.delta < -threshold:
            return True

    return False


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def print_comparison(
    result: ComparisonResult,
    threshold: float = 5.0,
    file=None,
) -> None:
    """Print a formatted comparison table to the terminal."""
    out = file or sys.stdout
    width = 60

    def _line(text: str = "") -> None:
        print(text, file=out)

    _line("=" * width)
    _line(f"  COMPARISON: {result.target_name} ({result.current_date} vs {result.previous_date})")
    _line("=" * width)

    # Overall
    overall_tag = f"[!! {result.overall_label}]" if result.overall_delta < -threshold else f"[{result.overall_label}]"
    _line(
        f"  Overall Pass Rate:  {result.previous_pass_rate:.1f}%  ->  "
        f"{result.current_pass_rate:.1f}%  ({result.overall_delta:+.1f}%)  {overall_tag}"
    )
    _line("-" * width)

    # Per-probe
    if result.probe_comparisons:
        _line("  PROBE CHANGES")
        _line("-" * width)
        for pc in result.probe_comparisons:
            tag = f"[!! REGRESSION]" if pc.delta < -threshold else f"[{pc.label}]"
            name_padded = pc.probe_name.ljust(25)
            _line(
                f"  {name_padded} {pc.previous_rate:.1f}% -> {pc.current_rate:.1f}%  "
                f"({pc.delta:+.1f}%)  {tag}"
            )
        _line("-" * width)

    # Summary
    regressions = [
        pc for pc in result.probe_comparisons if pc.delta < -threshold
    ]
    if regressions:
        for r in regressions:
            _line(
                f"  REGRESSION DETECTED: {r.probe_name} dropped {abs(r.delta):.1f}% "
                f"(threshold: {threshold:.1f}%)"
            )
    elif result.overall_delta < -threshold:
        _line(
            f"  REGRESSION DETECTED: Overall pass rate dropped {abs(result.overall_delta):.1f}% "
            f"(threshold: {threshold:.1f}%)"
        )
    else:
        _line("  No regressions detected.")

    _line("=" * width)
