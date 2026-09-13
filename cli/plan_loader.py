"""
YAML Scan Plan loader, validator, and config builder.

Reads a scan plan YAML file, validates its schema, resolves environment
variable placeholders, merges per-target overrides with global defaults,
and produces a list of scan config dicts ready to POST to the backend API.
"""
import copy
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TARGET_TYPES = {"ollama", "rest"}

VALID_EXIT_CODE_POLICIES = {"never", "any_fail", "threshold"}

VALID_OUTPUT_FORMATS = {"json", "html", "summary"}

VALID_PRESETS = {"fast", "default", "full", "owasp"}

# Fields that can appear at the target level to override defaults
TARGET_OVERRIDE_FIELDS = {
    "preset",
    "probes",
    "exclude_probes",
    "generations",
    "eval_threshold",
    "parallel_attempts",
    "parallel_requests",
    "timeout_per_probe",
    "continue_on_error",
    "seed",
    "verbose",
}

# Environment variable pattern: ${VAR_NAME}
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Default values applied when the plan omits them
PLAN_DEFAULTS = {
    "output": {
        "directory": "./hydra_reports",
        "formats": ["json", "html"],
        "filename_pattern": "{name}_{date}",
        "timestamp_format": "%Y-%m-%d",
    },
    "compare": {
        "enabled": False,
        "baseline_dir": "./hydra_reports",
        "fail_on_regression": False,
        "regression_threshold": 5.0,
    },
    "automation": {
        "exit_code_policy": "any_fail",
        "min_pass_rate": 80.0,
        "quiet": False,
        "json_stdout": False,
    },
}

SCAN_DEFAULTS = {
    "generations": 5,
    "eval_threshold": 0.5,
    "continue_on_error": False,
    "verbose": 0,
}


# ---------------------------------------------------------------------------
# Environment variable resolution
# ---------------------------------------------------------------------------

def resolve_env_vars(value: Any) -> Any:
    """Recursively substitute ${VAR_NAME} placeholders from os.environ.

    Raises ``ValueError`` with a descriptive message when a referenced
    variable is not set, so the user can fix it before any scan starts.
    """
    if isinstance(value, str):
        unresolved: list[str] = []

        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is None:
                unresolved.append(var_name)
                return match.group(0)  # leave placeholder intact for error msg
            return env_val

        result = _ENV_VAR_PATTERN.sub(_replace, value)
        if unresolved:
            raise ValueError(
                f"Unset environment variable(s): {', '.join(unresolved)}. "
                "Set them before running the scan plan."
            )
        return result

    if isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}

    if isinstance(value, list):
        return [resolve_env_vars(item) for item in value]

    return value


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_plan(plan: dict) -> List[str]:
    """Return a list of human-readable validation error strings.

    An empty list means the plan is valid.
    """
    errors: list[str] = []

    # Required top-level fields
    if not plan.get("name"):
        errors.append("Missing required field: 'name'")

    targets = plan.get("targets")
    if not targets:
        errors.append("Missing required field: 'targets' (must be a non-empty list)")
        return errors  # no point checking further

    if not isinstance(targets, list):
        errors.append("'targets' must be a list")
        return errors

    # Validate defaults section
    defaults = plan.get("defaults", {})
    if defaults:
        _validate_scan_params(defaults, "defaults", errors)

    # Validate each target
    for i, target in enumerate(targets):
        label = f"targets[{i}]"
        if not target.get("name"):
            errors.append(f"{label}: missing required field 'name'")

        target_type = target.get("type")
        if not target_type:
            errors.append(f"{label}: missing required field 'type'")
        elif target_type not in VALID_TARGET_TYPES:
            errors.append(
                f"{label}: unknown target type '{target_type}' "
                f"(valid: {', '.join(sorted(VALID_TARGET_TYPES))})"
            )

        # Type-specific validation
        if target_type == "ollama":
            if not target.get("model"):
                errors.append(f"{label}: ollama target requires 'model' field")

        if target_type == "rest":
            if not target.get("endpoint"):
                errors.append(f"{label}: rest target requires 'endpoint' field")
            if not target.get("body_template"):
                errors.append(f"{label}: rest target requires 'body_template' field")
            if not target.get("response_field"):
                errors.append(f"{label}: rest target requires 'response_field' field")

        # Validate per-target scan params
        _validate_scan_params(target, label, errors)

    # Validate output section
    output = plan.get("output", {})
    if output:
        fmt = output.get("formats")
        if fmt is not None:
            if not isinstance(fmt, list):
                errors.append("output.formats must be a list")
            else:
                for f in fmt:
                    if f not in VALID_OUTPUT_FORMATS:
                        errors.append(
                            f"output.formats: unknown format '{f}' "
                            f"(valid: {', '.join(sorted(VALID_OUTPUT_FORMATS))})"
                        )

    # Validate automation section
    automation = plan.get("automation", {})
    if automation:
        policy = automation.get("exit_code_policy")
        if policy is not None and policy not in VALID_EXIT_CODE_POLICIES:
            errors.append(
                f"automation.exit_code_policy: unknown policy '{policy}' "
                f"(valid: {', '.join(sorted(VALID_EXIT_CODE_POLICIES))})"
            )

    return errors


def _validate_scan_params(section: dict, label: str, errors: list[str]) -> None:
    """Validate scan parameter fields within a section."""
    preset = section.get("preset")
    if preset is not None and preset not in VALID_PRESETS:
        errors.append(
            f"{label}.preset: unknown preset '{preset}' "
            f"(valid: {', '.join(sorted(VALID_PRESETS))})"
        )

    generations = section.get("generations")
    if generations is not None:
        if not isinstance(generations, int) or generations < 1 or generations > 500:
            errors.append(f"{label}.generations: must be an integer between 1 and 500")

    threshold = section.get("eval_threshold")
    if threshold is not None:
        if not isinstance(threshold, (int, float)) or threshold < 0.0 or threshold > 1.0:
            errors.append(
                f"{label}.eval_threshold: must be a number between 0.0 and 1.0"
            )

    verbose = section.get("verbose")
    if verbose is not None:
        if not isinstance(verbose, int) or verbose < 0 or verbose > 3:
            errors.append(f"{label}.verbose: must be 0, 1, 2, or 3")


# ---------------------------------------------------------------------------
# Loading & merging
# ---------------------------------------------------------------------------

def load_plan(path: str) -> dict:
    """Read a YAML scan plan file and return the parsed dict.

    Resolves environment variable placeholders (``${VAR}``) and fills in
    top-level section defaults (output, compare, automation).

    Raises ``FileNotFoundError`` or ``yaml.YAMLError`` on I/O / parse errors
    and ``ValueError`` on unset environment variables.
    """
    plan_path = Path(path)
    if not plan_path.exists():
        raise FileNotFoundError(f"Scan plan not found: {path}")

    with open(plan_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if raw is None or not isinstance(raw, dict):
        raise ValueError(f"Scan plan is empty or not a valid YAML mapping: {path}")

    # Resolve env vars throughout the plan
    plan = resolve_env_vars(raw)

    # Apply section defaults for missing top-level keys
    for section, section_defaults in PLAN_DEFAULTS.items():
        if section not in plan:
            plan[section] = copy.deepcopy(section_defaults)
        else:
            for key, val in section_defaults.items():
                if key not in plan[section]:
                    plan[section][key] = copy.deepcopy(val)

    return plan


def merge_defaults(target: dict, defaults: dict) -> dict:
    """Merge global ``defaults`` into a per-target dict.

    Target-level values take precedence.  Only keys listed in
    ``TARGET_OVERRIDE_FIELDS`` are merged.
    """
    merged = dict(target)
    for field in TARGET_OVERRIDE_FIELDS:
        if field not in merged and field in defaults:
            merged[field] = copy.deepcopy(defaults[field])
    return merged


# ---------------------------------------------------------------------------
# Converting plan targets → API payloads
# ---------------------------------------------------------------------------

def target_to_scan_config(target: dict, defaults: dict) -> dict:
    """Convert a single plan target (merged with defaults) into a dict
    matching the backend ``ScanConfigRequest`` schema.

    Returns a dict ready to be POSTed to ``/api/v1/scan/start``.
    """
    merged = merge_defaults(target, defaults)

    config: Dict[str, Any] = {}

    # Target type mapping
    target_type = merged["type"]
    if target_type == "ollama":
        config["target_type"] = "ollama"
        config["target_name"] = merged["model"]
    elif target_type == "rest":
        config["target_type"] = "rest"
        config["target_name"] = merged.get("name", "rest-target")
        if merged.get("endpoint"):
            config["rest_endpoint"] = merged["endpoint"]
        if merged.get("headers"):
            config["rest_headers"] = merged["headers"]
        if merged.get("body_template"):
            config["rest_body_template"] = merged["body_template"].strip()
        if merged.get("response_field"):
            config["rest_response_json_field"] = merged["response_field"]

    # Pass-through generator_options (for advanced settings like request_timeout)
    if merged.get("generator_options"):
        config["generator_options"] = merged["generator_options"]

    # Scan parameters (from merged target + defaults)
    for field, default in SCAN_DEFAULTS.items():
        config[field] = merged.get(field, default)

    # Probes
    probes = merged.get("probes")
    if probes:
        config["probes"] = probes if isinstance(probes, list) else [probes]
    else:
        config["probes"] = ["all"]

    # Optional params
    for opt_field in (
        "exclude_probes",
        "seed",
        "parallel_requests",
        "parallel_attempts",
        "timeout_per_probe",
    ):
        val = merged.get(opt_field)
        if val is not None:
            config[opt_field] = val

    return config


def plan_to_scan_configs(plan: dict) -> List[dict]:
    """Convert all targets in a plan to a list of API-ready scan config dicts."""
    defaults = plan.get("defaults", {})
    targets = plan.get("targets", [])
    return [target_to_scan_config(t, defaults) for t in targets]
