"""
Result comparison engine for Hydra CLI scan results.

Compares current scan results with previous runs to detect regressions
and improvements in pass rates, both overall and per-probe.
"""
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

def _extract_pass_rate(result: dict) -> float:
    """Extract overall pass rate from a scan result JSON.

    Looks for common result structures from the backend API.
    """
    # Direct pass_rate field
    if "pass_rate" in result:
        return float(result["pass_rate"])

    # From summary
    summary = result.get("summary", {})
    if summary and "pass_rate" in summary:
        return float(summary["pass_rate"])

    # Calculate from passed/failed counts
    passed = 0
    failed = 0

    if "passed" in result and "failed" in result:
        passed = result["passed"]
        failed = result["failed"]
    elif summary:
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)

    total = passed + failed
    if total == 0:
        return 0.0
    return (passed / total) * 100.0


def _extract_probe_rates(result: dict) -> Dict[str, float]:
    """Extract per-probe pass rates from a scan result JSON.

    Returns a dict mapping probe name to pass rate percentage.
    """
    rates: Dict[str, float] = {}

    # Check digest (from garak report)
    digest = result.get("digest", {})
    if digest:
        for probe_name, probe_data in digest.items():
            if isinstance(probe_data, dict):
                passed = probe_data.get("passed", 0)
                failed = probe_data.get("failed", 0)
                total = passed + failed
                if total > 0:
                    rates[probe_name] = (passed / total) * 100.0

    # Check results.probes (alternative structure)
    results = result.get("results", {})
    if isinstance(results, dict):
        probes = results.get("probes", {})
        if isinstance(probes, dict):
            for probe_name, probe_data in probes.items():
                if isinstance(probe_data, dict) and probe_name not in rates:
                    passed = probe_data.get("passed", 0)
                    failed = probe_data.get("failed", 0)
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

    import datetime
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

    current_rate = _extract_pass_rate(current)
    previous_rate = _extract_pass_rate(previous)

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
