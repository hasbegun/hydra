#!/usr/bin/env python3
"""
Hydra CLI Scan Tool

A command-line tool for running LLM vulnerability scans via the Hydra backend
API.  Supports YAML scan plans, ad-hoc scans, result comparison, and
automation-friendly output.

Usage:
    hydra_scan.py run --plan <path.yaml>        Run a YAML scan plan
    hydra_scan.py scan --model llama3.2         Ad-hoc scan
    hydra_scan.py health                        Check service health
    hydra_scan.py --help                        Full help
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

try:
    import websocket as ws_module
except ImportError:
    ws_module = None

from plan_loader import (
    load_plan,
    plan_to_scan_configs,
    validate_plan,
    PLAN_DEFAULTS,
    VALID_PRESETS,
)
from comparator import (
    compare_results,
    check_regression,
    extract_counts,
    find_previous_result,
    print_comparison,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BACKEND_URL = os.environ.get("HYDRA_BACKEND_URL", "http://localhost:8888")
DEFAULT_OUTPUT_DIR = "./hydra_reports"
POLL_INTERVAL_SECONDS = 3
WS_TIMEOUT_SECONDS = 5


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class HydraClient:
    """Thin HTTP client for the Hydra backend API."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        try:
            resp = self._session.request(method, self._url(path), **kwargs)
            resp.raise_for_status()
            return resp
        except requests.ConnectionError:
            _error(
                f"Cannot connect to backend at {self.base_url}. "
                "Is the Docker stack running? (make hydra-dev)"
            )
        except requests.HTTPError as exc:
            body = ""
            if exc.response is not None:
                try:
                    body = exc.response.json().get("detail", exc.response.text)
                except Exception:
                    body = exc.response.text
            _error(f"API error ({exc.response.status_code}): {body}")

    # --- Health ---
    def health(self) -> dict:
        return self._request("GET", "/health").json()

    # --- Scan lifecycle ---
    def start_scan(self, config: dict) -> dict:
        return self._request("POST", "/api/v1/scan/start", json=config).json()

    def scan_status(self, scan_id: str) -> dict:
        return self._request("GET", f"/api/v1/scan/{scan_id}/status").json()

    def scan_results(self, scan_id: str) -> dict:
        return self._request("GET", f"/api/v1/scan/{scan_id}/results").json()

    def scan_report_html(self, scan_id: str) -> bytes:
        return self._request("GET", f"/api/v1/scan/{scan_id}/report/html").content

    # --- Discovery ---
    def list_probes(self) -> dict:
        return self._request("GET", "/api/v1/plugins/probes").json()

    def list_models(self) -> dict:
        return self._request("GET", "/api/v1/generators").json()

    def get_preset(self, name: str) -> dict:
        return self._request("GET", f"/api/v1/config/presets/{name}").json()

    # --- History ---
    def scan_history(self, page: int = 1, page_size: int = 20) -> dict:
        return self._request(
            "GET", "/api/v1/scan/history",
            params={"page": page, "page_size": page_size},
        ).json()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(msg: str, exit_code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(exit_code)


def _info(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg)


def _ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Auth token resolution
# ---------------------------------------------------------------------------

def _resolve_auth_token(auth_cfg: dict, quiet: bool = False) -> Optional[str]:
    """Resolve an auth token from environment or refresh command.

    Returns the token string, or None if auth is not configured.
    """
    auth_type = auth_cfg.get("type", "none")
    if auth_type == "none":
        return None

    token_env = auth_cfg.get("token_env")
    refresh_cmd = auth_cfg.get("refresh_command")

    # Try refresh command first (gets a fresh token)
    if refresh_cmd:
        try:
            result = subprocess.run(
                refresh_cmd, shell=True, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                token = result.stdout.strip()
                _info(f"  Auth: refreshed token via '{refresh_cmd}'", quiet)
                return token
            else:
                _info(f"  Auth: refresh command failed (exit {result.returncode}), "
                      "falling back to env var", quiet)
        except subprocess.TimeoutExpired:
            _info("  Auth: refresh command timed out, falling back to env var", quiet)
        except Exception as exc:
            _info(f"  Auth: refresh command error: {exc}, falling back to env var", quiet)

    # Fall back to env var
    if token_env:
        token = os.environ.get(token_env)
        if token:
            _info(f"  Auth: using token from ${token_env}", quiet)
            return token
        _error(
            f"Auth token env var '{token_env}' is not set. "
            f"Export it before running: export {token_env}=\"your-token\""
        )

    _error(f"Auth type '{auth_type}' requires 'token_env' or 'refresh_command'")
    return None  # unreachable, _error exits


def _inject_auth_headers(scan_config: dict, auth_cfg: dict, token: str) -> None:
    """Inject the auth token into the scan config's REST headers."""
    header_name = auth_cfg.get("token_header", "Authorization")
    token_prefix = auth_cfg.get("token_prefix", "Bearer ")

    if "rest_headers" not in scan_config:
        scan_config["rest_headers"] = {}
    scan_config["rest_headers"][header_name] = f"{token_prefix}{token}"


# ---------------------------------------------------------------------------
# Progress monitoring
# ---------------------------------------------------------------------------

_TERMINAL_STATES = frozenset(("completed", "failed", "cancelled"))
_BAR_WIDTH = 20


def _render_progress_line(data: dict) -> None:
    """Render a single progress bar line to the terminal (in-place)."""
    progress = data.get("progress", 0)
    probe = data.get("current_probe", "")
    passed = data.get("passed", 0)
    failed = data.get("failed", 0)

    filled = int(_BAR_WIDTH * progress / 100)
    bar = "#" * filled + "-" * (_BAR_WIDTH - filled)
    line = f"\r[{bar}] {progress:.1f}%"
    if probe:
        line += f" | Probe: {probe}"
    line += f" | Pass: {passed} | Fail: {failed}"
    print(line, end="", flush=True)


def _monitor_progress_ws(client: HydraClient, scan_id: str, quiet: bool = False) -> dict:
    """Monitor scan progress via WebSocket, falling back to REST polling."""
    if ws_module is not None and not quiet:
        try:
            return _monitor_ws(client, scan_id)
        except Exception:
            pass  # fall through to REST polling

    return _monitor_rest(client, scan_id, quiet)


def _monitor_ws(client: HydraClient, scan_id: str) -> dict:
    """WebSocket progress monitoring."""
    ws_url = client.base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/v1/scan/{scan_id}/progress"

    final_status = None

    def on_message(ws_app, message):
        nonlocal final_status
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        if data.get("status", "") in _TERMINAL_STATES:
            final_status = data
            ws_app.close()
            return

        _render_progress_line(data)

    def on_error(ws_app, error):
        nonlocal final_status
        ws_app.close()

    def on_close(ws_app, close_status_code, close_msg):
        print()  # newline after progress bar

    app = ws_module.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    app.run_forever(ping_interval=10, ping_timeout=WS_TIMEOUT_SECONDS)

    if final_status:
        return final_status

    # If WS closed without final status, poll once more
    return client.scan_status(scan_id)


def _monitor_rest(client: HydraClient, scan_id: str, quiet: bool = False) -> dict:
    """REST polling fallback for progress monitoring."""
    while True:
        status = client.scan_status(scan_id)

        if not quiet:
            _render_progress_line(status)

        if status.get("status", "") in _TERMINAL_STATES:
            if not quiet:
                print()  # newline
            return status

        time.sleep(POLL_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Report saving
# ---------------------------------------------------------------------------

def _sanitize_filename(name: str) -> str:
    """Sanitize a string for safe use in filenames.

    Removes path separators and other characters that could escape the
    output directory or cause filesystem issues.
    """
    # Replace path separators and null bytes
    safe = name.replace("/", "_").replace("\\", "_").replace("\0", "")
    # Replace other problematic characters
    safe = re.sub(r'[<>:"|?*]', "_", safe)
    # Collapse runs of underscores
    safe = re.sub(r"_+", "_", safe).strip("_.")
    return safe or "unnamed"


def _save_reports(
    client: HydraClient,
    scan_id: str,
    target_name: str,
    output_cfg: dict,
) -> Dict[str, str]:
    """Download and save scan reports.  Returns paths dict."""
    out_dir = _ensure_dir(output_cfg.get("directory", DEFAULT_OUTPUT_DIR))
    pattern = output_cfg.get("filename_pattern", "{name}_{date}")
    ts_fmt = output_cfg.get("timestamp_format", "%Y-%m-%d")
    formats = output_cfg.get("formats", ["json", "html"])
    now = datetime.datetime.now()

    safe_name = _sanitize_filename(target_name)
    try:
        basename = pattern.format(
            name=safe_name,
            date=now.strftime(ts_fmt),
            time=now.strftime("%H%M%S"),
            plan="",
            preset="",
        )
    except KeyError:
        basename = f"{safe_name}_{now.strftime(ts_fmt)}"

    paths: Dict[str, str] = {}

    # JSON results
    if "json" in formats:
        results = client.scan_results(scan_id)
        json_path = out_dir / f"{basename}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        paths["json"] = str(json_path)

    # HTML report
    if "html" in formats:
        try:
            html = client.scan_report_html(scan_id)
            html_path = out_dir / f"{basename}.html"
            with open(html_path, "wb") as f:
                f.write(html)
            paths["html"] = str(html_path)
        except SystemExit:
            pass  # HTML may not be available; skip silently

    return paths


# ---------------------------------------------------------------------------
# Terminal summary
# ---------------------------------------------------------------------------

def _print_summary(result: dict, target_name: str, paths: Dict[str, str]) -> None:
    """Print a compact scan summary to stdout."""
    status = result.get("status", "unknown")
    passed, failed, total, pass_rate = extract_counts(result)

    print()
    print("=" * 60)
    print(f"  SCAN COMPLETE: {target_name}")
    print("=" * 60)
    print(f"  Status:     {status}")
    print(f"  Total:      {total} tests")
    print(f"  Passed:     {passed}")
    print(f"  Failed:     {failed}")
    print(f"  Pass Rate:  {pass_rate:.1f}%")
    if paths.get("json"):
        print(f"  JSON:       {paths['json']}")
    if paths.get("html"):
        print(f"  HTML:       {paths['html']}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Subcommand: run (plan-based scanning)
# ---------------------------------------------------------------------------

def _load_and_validate_plan(path: str) -> Optional[dict]:
    """Load and validate a YAML scan plan, printing errors on failure.

    Returns the parsed plan dict, or calls ``_error()`` / returns 1 on failure.
    On validation errors, prints them to stderr and returns None.
    """
    try:
        plan = load_plan(path)
    except FileNotFoundError as exc:
        _error(str(exc))
    except ValueError as exc:
        _error(str(exc))

    errors = validate_plan(plan)
    if errors:
        print("Scan plan validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return None

    return plan


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a YAML scan plan."""
    plan = _load_and_validate_plan(args.plan)
    if plan is None:
        return 1

    plan_name = plan.get("name", "unnamed")
    targets = plan.get("targets", [])
    output_cfg = plan.get("output", PLAN_DEFAULTS["output"])
    compare_cfg = plan.get("compare", PLAN_DEFAULTS["compare"])
    auto_cfg = plan.get("automation", PLAN_DEFAULTS["automation"])
    quiet = auto_cfg.get("quiet", False)

    # Dry run mode
    if args.dry_run:
        return _dry_run(plan)

    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)
    scan_configs = plan_to_scan_configs(plan)

    # Resolve auth token (if configured)
    auth_cfg = plan.get("auth", {})
    auth_token = None
    if auth_cfg.get("type", "none") != "none":
        auth_token = _resolve_auth_token(auth_cfg, quiet)

    _info(f"Plan: {plan_name} ({len(targets)} target(s))", quiet)

    all_results: List[Dict[str, Any]] = []
    exit_code = 0

    for i, (target, scan_config) in enumerate(zip(targets, scan_configs)):
        target_name = target.get("name", f"target-{i}")
        target_type = target.get("type", "unknown")

        _info(f"\n--- Target {i+1}/{len(targets)}: {target_name} ({target_type}) ---", quiet)

        # Inject auth token into REST headers (if configured)
        if auth_token and target_type == "rest":
            _inject_auth_headers(scan_config, auth_cfg, auth_token)

        # Fetch and merge preset if specified
        preset = target.get("preset") or plan.get("defaults", {}).get("preset")
        if preset:
            try:
                preset_data = client.get_preset(preset)
                preset_config = preset_data.get("config", {})
                # Preset probes override default "all" only if not explicitly set
                if scan_config.get("probes") == ["all"] and preset_config.get("probes"):
                    scan_config["probes"] = preset_config["probes"]
                # Merge other preset settings that weren't explicitly set
                for key in ("generations", "parallel_attempts", "parallel_requests"):
                    if key not in target and key not in plan.get("defaults", {}) and key in preset_config:
                        scan_config[key] = preset_config[key]
            except SystemExit:
                _info(f"  Warning: preset '{preset}' not available, using defaults", quiet)

        # Start scan
        try:
            resp = client.start_scan(scan_config)
        except SystemExit:
            print(f"  Failed to start scan for {target_name}", file=sys.stderr)
            exit_code = 1
            continue

        scan_id = resp.get("scan_id")
        _info(f"  Scan started: {scan_id}", quiet)

        # Monitor progress
        final_status = _monitor_progress_ws(client, scan_id, quiet)

        status = final_status.get("status", "unknown")
        if status == "failed":
            error_msg = final_status.get("error_message", "Unknown error")
            print(f"  Scan failed: {error_msg}", file=sys.stderr)
            exit_code = 1
            continue

        # Save reports
        paths = _save_reports(client, scan_id, target_name, output_cfg)

        # Get full results
        try:
            result = client.scan_results(scan_id)
        except SystemExit:
            result = final_status

        if not quiet:
            _print_summary(result, target_name, paths)

        # Comparison
        if compare_cfg.get("enabled") and paths.get("json"):
            baseline_dir = compare_cfg.get("baseline_dir", output_cfg.get("directory", DEFAULT_OUTPUT_DIR))
            prev = find_previous_result(target_name, baseline_dir, paths["json"])
            if prev:
                try:
                    comp = compare_results(paths["json"], str(prev), target_name)
                    threshold = compare_cfg.get("regression_threshold", 5.0)
                    if not quiet:
                        print_comparison(comp, threshold)
                    if compare_cfg.get("fail_on_regression") and check_regression(comp, threshold):
                        exit_code = 1
                except Exception as exc:
                    _info(f"  Comparison error: {exc}", quiet)
            else:
                _info("  No previous result found for comparison.", quiet)

        # Build result record for JSON stdout
        passed, failed, total, pass_rate = extract_counts(result)

        target_result = {
            "name": target_name,
            "type": target_type,
            "status": status,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 1),
            "reports": paths,
        }
        if target_type == "ollama":
            target_result["model"] = target.get("model")

        all_results.append(target_result)

        # Check exit code policy per-target
        policy = auto_cfg.get("exit_code_policy", "any_fail")
        if policy == "any_fail" and failed > 0:
            exit_code = 1
        elif policy == "threshold":
            min_rate = auto_cfg.get("min_pass_rate", 80.0)
            if pass_rate < min_rate:
                exit_code = 1

    # JSON stdout for automation
    if auto_cfg.get("json_stdout"):
        json_summary = {
            "plan": plan_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "targets": all_results,
            "overall_pass": exit_code == 0,
            "exit_code": exit_code,
        }
        print(json.dumps(json_summary, indent=2))

    return exit_code


def _dry_run(plan: dict) -> int:
    """Print what would run without starting any scans."""
    print("=" * 60)
    print("  DRY RUN — No scans will be started")
    print("=" * 60)
    print(f"  Plan:    {plan.get('name', 'unnamed')}")
    if plan.get("description"):
        print(f"  Desc:    {plan['description']}")
    print(f"  Targets: {len(plan.get('targets', []))}")
    print()

    auth_cfg = plan.get("auth", {})
    auth_type = auth_cfg.get("type", "none")
    if auth_type != "none":
        token_env = auth_cfg.get("token_env", "")
        token_set = "SET" if os.environ.get(token_env) else "NOT SET"
        print(f"  Auth:    {auth_type} (token from ${token_env} — {token_set})")
        if auth_cfg.get("refresh_command"):
            print(f"  Refresh: {auth_cfg['refresh_command']}")
        print()

    defaults = plan.get("defaults", {})
    if defaults:
        print("  Global Defaults:")
        for k, v in defaults.items():
            print(f"    {k}: {v}")
        print()

    scan_configs = plan_to_scan_configs(plan)
    for i, (target, config) in enumerate(zip(plan.get("targets", []), scan_configs)):
        print(f"  Target {i+1}: {target.get('name', 'unnamed')}")
        print(f"    Type:       {target.get('type')}")
        if target.get("type") == "ollama":
            print(f"    Model:      {target.get('model')}")
        elif target.get("type") == "rest":
            print(f"    Endpoint:   {target.get('endpoint')}")
        print(f"    Probes:     {config.get('probes', ['all'])}")
        print(f"    Gens:       {config.get('generations', 5)}")
        if target.get("preset") or defaults.get("preset"):
            print(f"    Preset:     {target.get('preset') or defaults.get('preset')}")
        print()

    output_cfg = plan.get("output", {})
    print(f"  Output:  {output_cfg.get('directory', DEFAULT_OUTPUT_DIR)}")
    print(f"  Formats: {output_cfg.get('formats', ['json', 'html'])}")

    compare_cfg = plan.get("compare", {})
    if compare_cfg.get("enabled"):
        print(f"  Compare: enabled (threshold: {compare_cfg.get('regression_threshold', 5.0)}%)")

    auto_cfg = plan.get("automation", {})
    print(f"  Policy:  {auto_cfg.get('exit_code_policy', 'any_fail')}")
    print("=" * 60)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: scan (ad-hoc)
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    """Run an ad-hoc single-target scan."""
    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)

    config: Dict[str, Any] = {
        "target_type": args.target_type or "ollama",
        "target_name": args.model or "unknown",
    }

    # Only set scan params when explicitly provided by the user, so preset
    # values can fill in the gaps.  argparse defaults are None for these.
    if args.generations is not None:
        config["generations"] = args.generations
    if args.eval_threshold is not None:
        config["eval_threshold"] = args.eval_threshold

    if args.probes:
        config["probes"] = args.probes.split(",")

    # REST fields
    if args.rest_endpoint:
        config["rest_endpoint"] = args.rest_endpoint
    if args.rest_body_template:
        config["rest_body_template"] = args.rest_body_template
    if args.rest_response_field:
        config["rest_response_json_field"] = args.rest_response_field
    if args.rest_headers:
        try:
            config["rest_headers"] = json.loads(args.rest_headers)
        except json.JSONDecodeError:
            _error("--rest-headers must be valid JSON")

    # Inject auth token for REST targets
    if args.auth_token:
        if "rest_headers" not in config:
            config["rest_headers"] = {}
        config["rest_headers"]["Authorization"] = f"Bearer {args.auth_token}"

    # Fetch preset — fills in keys not already set by the user
    if args.preset:
        try:
            preset_data = client.get_preset(args.preset)
            preset_config = preset_data.get("config", {})
            if "probes" not in config and preset_config.get("probes"):
                config["probes"] = preset_config["probes"]
            for key in ("generations", "eval_threshold", "parallel_attempts", "parallel_requests"):
                if key in preset_config and key not in config:
                    config[key] = preset_config[key]
        except SystemExit:
            _info(f"Warning: preset '{args.preset}' not available")

    # Apply scan defaults for anything still missing
    config.setdefault("generations", 5)
    config.setdefault("eval_threshold", 0.5)

    target_name = args.model or args.rest_endpoint or "target"

    # Start
    resp = client.start_scan(config)
    scan_id = resp.get("scan_id")
    print(f"Scan started: {scan_id}")

    # Monitor
    final_status = _monitor_progress_ws(client, scan_id)

    status = final_status.get("status", "unknown")
    if status == "failed":
        _error(f"Scan failed: {final_status.get('error_message', 'Unknown')}")

    # Save reports
    output_cfg = {"directory": args.output_dir or DEFAULT_OUTPUT_DIR, "formats": ["json", "html"]}
    paths = _save_reports(client, scan_id, target_name, output_cfg)

    result = client.scan_results(scan_id)
    _print_summary(result, target_name, paths)

    _, failed, _, _ = extract_counts(result)
    return 1 if failed > 0 else 0


# ---------------------------------------------------------------------------
# Subcommand: validate
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a YAML scan plan."""
    plan = _load_and_validate_plan(args.plan)
    if plan is None:
        return 1

    print(f"Plan is valid: {plan.get('name', 'unnamed')} ({len(plan.get('targets', []))} targets)")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------

STARTER_TEMPLATE = """\
# Hydra Scan Plan
# Generated by: hydra_scan.py init
# Docs: cli/README.md

name: "my-scan-plan"
description: "Describe your scan plan here"

defaults:
  preset: fast            # fast | default | full | owasp
  generations: 5

targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
    # preset: default     # Override global preset for this target
    # probes:             # Override probes for this target
    #   - dan
    #   - encoding

  # Uncomment to add a REST target:
  # - name: "my-api"
  #   type: rest
  #   endpoint: "http://host.docker.internal:8080/v1/chat/completions"
  #   headers:
  #     Authorization: "Bearer ${{API_KEY}}"
  #   body_template: '{{"model":"gpt-4","messages":[{{"role":"user","content":"$INPUT"}}]}}'
  #   response_field: "$.choices[0].message.content"

output:
  directory: "./hydra_reports"
  filename_pattern: "{{name}}_{{date}}"

# compare:
#   enabled: true
#   regression_threshold: 5.0

# automation:
#   exit_code_policy: threshold
#   min_pass_rate: 80.0
"""


def cmd_init(args: argparse.Namespace) -> int:
    """Generate a starter scan plan template."""
    plan_path = Path(args.plan)
    if plan_path.exists() and not args.force:
        _error(f"File already exists: {plan_path}. Use --force to overwrite.")

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(STARTER_TEMPLATE)
    print(f"Starter plan created: {plan_path}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: compare
# ---------------------------------------------------------------------------

def cmd_compare(args: argparse.Namespace) -> int:
    """Compare the two most recent results for a target."""
    baseline_dir = args.dir or DEFAULT_OUTPUT_DIR
    target_name = args.target

    # Find the two most recent results
    base = Path(baseline_dir)
    if not base.is_dir():
        _error(f"Directory not found: {baseline_dir}")

    candidates = sorted(
        [f for f in base.glob("*.json") if re.search(re.escape(target_name), f.stem)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if len(candidates) < 2:
        _error(f"Need at least 2 result files for '{target_name}' in {baseline_dir}")

    current_path = str(candidates[0])
    previous_path = str(candidates[1])

    comp = compare_results(current_path, previous_path, target_name)
    threshold = args.threshold or 5.0
    print_comparison(comp, threshold)

    if check_regression(comp, threshold):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Subcommand: health
# ---------------------------------------------------------------------------

def cmd_health(args: argparse.Namespace) -> int:
    """Check health of backend and related services."""
    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)
    try:
        data = client.health()
        print(f"Backend:  healthy")
        if "garak_installed" in data:
            garak_status = "installed" if data["garak_installed"] else "NOT installed"
            print(f"Garak:    {garak_status}")
        if "garak_version" in data:
            print(f"Version:  {data['garak_version']}")
        return 0
    except SystemExit:
        return 1


# ---------------------------------------------------------------------------
# Subcommand: probes
# ---------------------------------------------------------------------------

def cmd_probes(args: argparse.Namespace) -> int:
    """List available probes."""
    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)
    data = client.list_probes()
    plugins = data.get("plugins", [])
    print(f"Available probes ({data.get('total_count', len(plugins))}):")
    for p in plugins:
        desc = p.get("description", "")
        if desc and len(desc) > 60:
            desc = desc[:57] + "..."
        print(f"  {p.get('full_name', p.get('name', '')):<40s} {desc}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: models
# ---------------------------------------------------------------------------

def cmd_models(args: argparse.Namespace) -> int:
    """List available Ollama models."""
    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)
    data = client.list_models()
    models = data.get("generators", data.get("models", []))
    if isinstance(models, list):
        print(f"Available models ({len(models)}):")
        for m in models:
            if isinstance(m, dict):
                print(f"  {m.get('name', m.get('model', str(m)))}")
            else:
                print(f"  {m}")
    else:
        print(json.dumps(data, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: history
# ---------------------------------------------------------------------------

def cmd_history(args: argparse.Namespace) -> int:
    """View past scan history."""
    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)
    data = client.scan_history(page=args.page, page_size=args.page_size)
    scans = data.get("scans", [])
    pagination = data.get("pagination", {})

    print(f"Scan History (page {pagination.get('page', 1)}/{pagination.get('total_pages', 1)}, "
          f"total: {data.get('total_count', len(scans))})")
    print("-" * 80)
    print(f"{'Scan ID':<38s} {'Status':<12s} {'Target':<20s} {'Pass/Fail':<12s}")
    print("-" * 80)
    for s in scans:
        scan_id = s.get("scan_id", "")[:36]
        status = s.get("status", "")
        target = (s.get("target_name") or s.get("target_type") or "-")[:18]
        passed = s.get("passed", 0) or 0
        failed = s.get("failed", 0) or 0
        print(f"  {scan_id:<36s} {status:<12s} {target:<20s} {passed}/{failed}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    """Download reports for a past scan."""
    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)
    scan_id = args.scan_id
    output_cfg = {"directory": args.output_dir or DEFAULT_OUTPUT_DIR, "formats": ["json", "html"]}
    paths = _save_reports(client, scan_id, scan_id[:8], output_cfg)
    for fmt, path in paths.items():
        print(f"  {fmt.upper()}: {path}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    """Check status of a running scan."""
    client = HydraClient(args.backend_url or DEFAULT_BACKEND_URL)
    data = client.scan_status(args.scan_id)
    print(f"Scan:     {data.get('scan_id')}")
    print(f"Status:   {data.get('status')}")
    print(f"Progress: {data.get('progress', 0):.1f}%")
    if data.get("current_probe"):
        print(f"Probe:    {data['current_probe']}")
    print(f"Passed:   {data.get('passed', 0)}")
    print(f"Failed:   {data.get('failed', 0)}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: start-services / stop-services
# ---------------------------------------------------------------------------

def cmd_start_services(args: argparse.Namespace) -> int:
    """Start the Docker stack."""
    compose_dir = args.compose_dir or os.path.join(os.path.dirname(__file__), "..", "backend")
    cmd = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "up", "-d"]
    print(f"Starting Docker stack in {compose_dir}...")
    result = subprocess.run(cmd, cwd=compose_dir)
    return result.returncode


def cmd_stop_services(args: argparse.Namespace) -> int:
    """Stop the Docker stack."""
    compose_dir = args.compose_dir or os.path.join(os.path.dirname(__file__), "..", "backend")
    cmd = ["docker", "compose", "down"]
    print(f"Stopping Docker stack in {compose_dir}...")
    result = subprocess.run(cmd, cwd=compose_dir)
    return result.returncode


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hydra_scan",
        description="Hydra CLI - LLM vulnerability scanning tool",
    )
    parser.add_argument(
        "--backend-url",
        default=None,
        help=f"Backend API URL (default: {DEFAULT_BACKEND_URL})",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- run ---
    p_run = sub.add_parser("run", help="Run a YAML scan plan")
    p_run.add_argument("--plan", required=True, help="Path to YAML scan plan file")
    p_run.add_argument("--dry-run", action="store_true", help="Show what would run without scanning")
    p_run.add_argument("--output-dir", default=None, help="Override output directory")
    p_run.set_defaults(func=cmd_run)

    # --- scan ---
    p_scan = sub.add_parser("scan", help="Run an ad-hoc scan")
    p_scan.add_argument("--model", default=None, help="Ollama model name")
    p_scan.add_argument("--target-type", default=None, help="Target type (ollama, rest)")
    p_scan.add_argument("--preset", default=None, choices=list(VALID_PRESETS), help="Config preset")
    p_scan.add_argument("--probes", default=None, help="Comma-separated probe names")
    p_scan.add_argument("--generations", type=int, default=None, help="Generations per probe (default: 5, or from preset)")
    p_scan.add_argument("--eval-threshold", type=float, default=None, help="Eval threshold (default: 0.5, or from preset)")
    p_scan.add_argument("--rest-endpoint", default=None, help="REST API endpoint URL")
    p_scan.add_argument("--rest-body-template", default=None, help="REST body template (JSON, $INPUT placeholder)")
    p_scan.add_argument("--rest-response-field", default=None, help="JSON path for REST response extraction")
    p_scan.add_argument("--rest-headers", default=None, help="REST headers (JSON string)")
    p_scan.add_argument("--output-dir", default=None, help="Output directory")
    p_scan.add_argument("--auth-token", default=None, help="Bearer token for authenticated REST endpoints (e.g. Okta)")
    p_scan.set_defaults(func=cmd_scan)

    # --- validate ---
    p_val = sub.add_parser("validate", help="Validate a YAML scan plan")
    p_val.add_argument("--plan", required=True, help="Path to YAML scan plan file")
    p_val.set_defaults(func=cmd_validate)

    # --- init ---
    p_init = sub.add_parser("init", help="Generate a starter scan plan template")
    p_init.add_argument("--plan", required=True, help="Output path for the plan file")
    p_init.add_argument("--force", action="store_true", help="Overwrite if file exists")
    p_init.set_defaults(func=cmd_init)

    # --- compare ---
    p_cmp = sub.add_parser("compare", help="Compare recent scan results for a target")
    p_cmp.add_argument("--target", required=True, help="Target name to compare")
    p_cmp.add_argument("--dir", default=None, help="Directory containing result JSONs")
    p_cmp.add_argument("--threshold", type=float, default=5.0, help="Regression threshold (%)")
    p_cmp.set_defaults(func=cmd_compare)

    # --- health ---
    p_health = sub.add_parser("health", help="Check backend health")
    p_health.set_defaults(func=cmd_health)

    # --- probes ---
    p_probes = sub.add_parser("probes", help="List available probes")
    p_probes.set_defaults(func=cmd_probes)

    # --- models ---
    p_models = sub.add_parser("models", help="List available Ollama models")
    p_models.set_defaults(func=cmd_models)

    # --- history ---
    p_hist = sub.add_parser("history", help="View scan history")
    p_hist.add_argument("--page", type=int, default=1, help="Page number")
    p_hist.add_argument("--page-size", type=int, default=20, help="Results per page")
    p_hist.set_defaults(func=cmd_history)

    # --- report ---
    p_rep = sub.add_parser("report", help="Download reports for a past scan")
    p_rep.add_argument("scan_id", help="Scan ID")
    p_rep.add_argument("--output-dir", default=None, help="Output directory")
    p_rep.set_defaults(func=cmd_report)

    # --- status ---
    p_stat = sub.add_parser("status", help="Check running scan status")
    p_stat.add_argument("scan_id", help="Scan ID")
    p_stat.set_defaults(func=cmd_status)

    # --- start-services ---
    p_start = sub.add_parser("start-services", help="Start Docker stack")
    p_start.add_argument("--compose-dir", default=None, help="Path to docker-compose directory")
    p_start.set_defaults(func=cmd_start_services)

    # --- stop-services ---
    p_stop = sub.add_parser("stop-services", help="Stop Docker stack")
    p_stop.add_argument("--compose-dir", default=None, help="Path to docker-compose directory")
    p_stop.set_defaults(func=cmd_stop_services)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
