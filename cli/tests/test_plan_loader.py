"""
Tests for cli/plan_loader.py — YAML scan plan loading, validation, and conversion.

Covers T2.1-T2.8 from the test plan.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure cli/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plan_loader import (
    load_plan,
    merge_defaults,
    plan_to_scan_configs,
    resolve_env_vars,
    target_to_scan_config,
    validate_plan,
    PLAN_DEFAULTS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, content: str) -> str:
    """Write YAML content to a temp file and return its path."""
    p = tmp_path / "plan.yaml"
    p.write_text(content, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# T2.1: Minimal plan loads
# ---------------------------------------------------------------------------

class TestMinimalPlanLoads:
    def test_minimal_plan(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "quick-check"
targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
""")
        plan = load_plan(path)
        assert plan["name"] == "quick-check"
        assert len(plan["targets"]) == 1
        assert plan["targets"][0]["name"] == "llama3.2"
        assert plan["targets"][0]["type"] == "ollama"
        assert plan["targets"][0]["model"] == "llama3.2"

    def test_defaults_filled(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "t"
    type: ollama
    model: llama3.2
""")
        plan = load_plan(path)
        # Verify top-level sections have defaults
        assert plan["output"]["directory"] == "./hydra_reports"
        assert plan["output"]["formats"] == ["json", "html"]
        assert plan["compare"]["enabled"] is False
        assert plan["automation"]["exit_code_policy"] == "any_fail"


# ---------------------------------------------------------------------------
# T2.2: Full plan loads
# ---------------------------------------------------------------------------

class TestFullPlanLoads:
    def test_full_plan(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "full-plan"
description: "Full test plan"
version: "2.0"

defaults:
  preset: default
  generations: 10
  seed: 42

targets:
  - name: "llama3.2"
    type: ollama
    model: llama3.2
    preset: fast

  - name: "my-api"
    type: rest
    endpoint: "http://localhost:8080/chat"
    body_template: '{"msg": "$INPUT"}'
    response_field: "response.text"
    probes:
      - dan
      - encoding

output:
  directory: "./reports"
  formats:
    - json
    - html
    - summary
  filename_pattern: "{plan}_{name}_{date}"

compare:
  enabled: true
  baseline_dir: "./reports"
  fail_on_regression: true
  regression_threshold: 3.0

automation:
  exit_code_policy: threshold
  min_pass_rate: 90.0
  quiet: true
  json_stdout: true
""")
        plan = load_plan(path)
        assert plan["name"] == "full-plan"
        assert plan["description"] == "Full test plan"
        assert plan["version"] == "2.0"
        assert plan["defaults"]["preset"] == "default"
        assert plan["defaults"]["generations"] == 10
        assert plan["defaults"]["seed"] == 42
        assert len(plan["targets"]) == 2
        assert plan["targets"][0]["preset"] == "fast"
        assert plan["targets"][1]["type"] == "rest"
        assert plan["targets"][1]["probes"] == ["dan", "encoding"]
        assert plan["output"]["directory"] == "./reports"
        assert "summary" in plan["output"]["formats"]
        assert plan["compare"]["enabled"] is True
        assert plan["compare"]["fail_on_regression"] is True
        assert plan["compare"]["regression_threshold"] == 3.0
        assert plan["automation"]["exit_code_policy"] == "threshold"
        assert plan["automation"]["min_pass_rate"] == 90.0
        assert plan["automation"]["quiet"] is True
        assert plan["automation"]["json_stdout"] is True


# ---------------------------------------------------------------------------
# T2.3: Environment variable substitution
# ---------------------------------------------------------------------------

class TestEnvVarSubstitution:
    def test_env_var_resolved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret-token-123")
        path = _write_yaml(tmp_path, """
name: "env-test"
targets:
  - name: "api"
    type: rest
    endpoint: "http://example.com/chat"
    headers:
      Authorization: "Bearer ${MY_TOKEN}"
    body_template: '{"msg": "$INPUT"}'
    response_field: "response.text"
""")
        plan = load_plan(path)
        assert plan["targets"][0]["headers"]["Authorization"] == "Bearer secret-token-123"

    def test_unset_env_var_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("UNSET_VAR_XYZ", raising=False)
        path = _write_yaml(tmp_path, """
name: "env-test"
targets:
  - name: "api"
    type: rest
    endpoint: "${UNSET_VAR_XYZ}"
    body_template: '{"msg": "$INPUT"}'
    response_field: "r"
""")
        with pytest.raises(ValueError, match="UNSET_VAR_XYZ"):
            load_plan(path)

    def test_multiple_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOST", "api.example.com")
        monkeypatch.setenv("PORT", "8080")
        path = _write_yaml(tmp_path, """
name: "multi-env"
targets:
  - name: "api"
    type: rest
    endpoint: "http://${HOST}:${PORT}/chat"
    body_template: '{"msg": "$INPUT"}'
    response_field: "r"
""")
        plan = load_plan(path)
        assert plan["targets"][0]["endpoint"] == "http://api.example.com:8080/chat"


# ---------------------------------------------------------------------------
# T2.4: Default merging
# ---------------------------------------------------------------------------

class TestDefaultMerging:
    def test_target_inherits_defaults(self):
        defaults = {"probes": ["dan", "encoding"], "generations": 10, "preset": "fast"}
        target = {"name": "t", "type": "ollama", "model": "llama3.2"}
        merged = merge_defaults(target, defaults)
        assert merged["probes"] == ["dan", "encoding"]
        assert merged["generations"] == 10
        assert merged["preset"] == "fast"

    def test_target_keeps_own_values(self):
        defaults = {"probes": ["dan"], "generations": 10}
        target = {"name": "t", "type": "ollama", "model": "m", "probes": ["encoding"], "generations": 20}
        merged = merge_defaults(target, defaults)
        assert merged["probes"] == ["encoding"]
        assert merged["generations"] == 20


# ---------------------------------------------------------------------------
# T2.5: Target override
# ---------------------------------------------------------------------------

class TestTargetOverride:
    def test_target_preset_overrides_default(self):
        defaults = {"preset": "fast"}
        target = {"name": "t", "type": "ollama", "model": "m", "preset": "owasp"}
        merged = merge_defaults(target, defaults)
        assert merged["preset"] == "owasp"


# ---------------------------------------------------------------------------
# T2.6: Invalid YAML rejected
# ---------------------------------------------------------------------------

class TestInvalidYamlRejected:
    def test_missing_name(self, tmp_path):
        path = _write_yaml(tmp_path, """
targets:
  - name: "t"
    type: ollama
    model: m
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("name" in e.lower() for e in errors)

    def test_missing_targets(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("targets" in e.lower() for e in errors)

    def test_empty_targets(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets: []
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("targets" in e.lower() for e in errors)

    def test_target_missing_name(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - type: ollama
    model: m
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("name" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# T2.7: Unknown target type
# ---------------------------------------------------------------------------

class TestUnknownTargetType:
    def test_grpc_rejected(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "t"
    type: grpc
    model: m
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("grpc" in e for e in errors)

    def test_unknown_type_rejected(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "t"
    type: websocket
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("websocket" in e for e in errors)


# ---------------------------------------------------------------------------
# T2.8: REST missing fields
# ---------------------------------------------------------------------------

class TestRestMissingFields:
    def test_rest_without_endpoint(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "api"
    type: rest
    body_template: '{"msg": "$INPUT"}'
    response_field: "r"
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("endpoint" in e for e in errors)

    def test_rest_without_body_template(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "api"
    type: rest
    endpoint: "http://example.com/chat"
    response_field: "r"
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("body_template" in e for e in errors)

    def test_rest_without_response_field(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "api"
    type: rest
    endpoint: "http://example.com/chat"
    body_template: '{"msg": "$INPUT"}'
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("response_field" in e for e in errors)


# ---------------------------------------------------------------------------
# plan_to_scan_configs conversion
# ---------------------------------------------------------------------------

class TestPlanToScanConfigs:
    def test_ollama_target(self):
        plan = {
            "name": "test",
            "defaults": {"generations": 10},
            "targets": [
                {"name": "llama3.2", "type": "ollama", "model": "llama3.2"},
            ],
        }
        configs = plan_to_scan_configs(plan)
        assert len(configs) == 1
        cfg = configs[0]
        assert cfg["target_type"] == "ollama"
        assert cfg["target_name"] == "llama3.2"
        assert cfg["generations"] == 10
        assert cfg["probes"] == ["all"]

    def test_rest_target(self):
        plan = {
            "name": "test",
            "defaults": {},
            "targets": [
                {
                    "name": "my-api",
                    "type": "rest",
                    "endpoint": "http://example.com/chat",
                    "headers": {"Authorization": "Bearer tok"},
                    "body_template": '{"msg": "$INPUT"}',
                    "response_field": "response.text",
                    "probes": ["dan", "encoding"],
                },
            ],
        }
        configs = plan_to_scan_configs(plan)
        assert len(configs) == 1
        cfg = configs[0]
        assert cfg["target_type"] == "rest"
        assert cfg["target_name"] == "my-api"
        assert cfg["rest_endpoint"] == "http://example.com/chat"
        assert cfg["rest_headers"] == {"Authorization": "Bearer tok"}
        assert cfg["rest_body_template"] == '{"msg": "$INPUT"}'
        assert cfg["rest_response_json_field"] == "response.text"
        assert cfg["probes"] == ["dan", "encoding"]

    def test_multi_target(self):
        plan = {
            "name": "test",
            "defaults": {"preset": "fast"},
            "targets": [
                {"name": "t1", "type": "ollama", "model": "llama3.2"},
                {"name": "t2", "type": "ollama", "model": "mistral"},
                {"name": "t3", "type": "rest", "endpoint": "http://x", "body_template": "b", "response_field": "r"},
            ],
        }
        configs = plan_to_scan_configs(plan)
        assert len(configs) == 3
        assert configs[0]["target_name"] == "llama3.2"
        assert configs[1]["target_name"] == "mistral"
        assert configs[2]["target_type"] == "rest"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_plan("/nonexistent/path/plan.yaml")

    def test_empty_file(self, tmp_path):
        path = _write_yaml(tmp_path, "")
        with pytest.raises(ValueError, match="empty"):
            load_plan(path)

    def test_invalid_yaml_syntax(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("{{invalid yaml", encoding="utf-8")
        # yaml.safe_load may raise or return a string; either is caught
        with pytest.raises(Exception):
            plan = load_plan(str(p))
            if not isinstance(plan, dict):
                raise ValueError("not a dict")

    def test_resolve_env_no_vars(self):
        assert resolve_env_vars("plain string") == "plain string"
        assert resolve_env_vars(42) == 42
        assert resolve_env_vars(None) is None
        assert resolve_env_vars(["a", "b"]) == ["a", "b"]

    def test_invalid_preset_in_defaults(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
defaults:
  preset: nonexistent
targets:
  - name: "t"
    type: ollama
    model: m
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("preset" in e and "nonexistent" in e for e in errors)

    def test_invalid_generations(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "t"
    type: ollama
    model: m
    generations: 0
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("generations" in e for e in errors)

    def test_invalid_exit_code_policy(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "t"
    type: ollama
    model: m
automation:
  exit_code_policy: invalid
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("exit_code_policy" in e for e in errors)

    def test_invalid_output_format(self, tmp_path):
        path = _write_yaml(tmp_path, """
name: "test"
targets:
  - name: "t"
    type: ollama
    model: m
output:
  formats:
    - pdf
""")
        plan = load_plan(path)
        errors = validate_plan(plan)
        assert any("pdf" in e for e in errors)


# ---------------------------------------------------------------------------
# Generator options pass-through
# ---------------------------------------------------------------------------

class TestGeneratorOptions:
    """Tests for generator_options pass-through in plan_to_scan_configs."""

    def test_generator_options_from_rest_target(self):
        plan = {
            "name": "test",
            "targets": [
                {
                    "name": "api",
                    "type": "rest",
                    "endpoint": "http://example.com/chat",
                    "body_template": '{"msg": "$INPUT"}',
                    "response_field": "$.choices[0].message.content",
                    "generator_options": {
                        "rest": {"request_timeout": 120, "max_tokens": 200}
                    },
                },
            ],
        }
        configs = plan_to_scan_configs(plan)
        cfg = configs[0]
        assert cfg["generator_options"] == {
            "rest": {"request_timeout": 120, "max_tokens": 200}
        }

    def test_generator_options_from_ollama_target(self):
        plan = {
            "name": "test",
            "targets": [
                {
                    "name": "t",
                    "type": "ollama",
                    "model": "llama3.2",
                    "generator_options": {"ollama": {"num_ctx": 4096}},
                },
            ],
        }
        configs = plan_to_scan_configs(plan)
        cfg = configs[0]
        assert cfg["generator_options"] == {"ollama": {"num_ctx": 4096}}

    def test_no_generator_options(self):
        plan = {
            "name": "test",
            "targets": [
                {"name": "t", "type": "ollama", "model": "llama3.2"},
            ],
        }
        configs = plan_to_scan_configs(plan)
        cfg = configs[0]
        assert "generator_options" not in cfg


# ---------------------------------------------------------------------------
# Body template stripping
# ---------------------------------------------------------------------------

class TestBodyTemplateStrip:
    """Verify YAML block scalar trailing newlines are stripped."""

    def test_body_template_trailing_newline(self):
        plan = {
            "name": "test",
            "targets": [
                {
                    "name": "api",
                    "type": "rest",
                    "endpoint": "http://example.com/chat",
                    "body_template": '{"msg": "$INPUT"}\n',
                    "response_field": "r",
                },
            ],
        }
        configs = plan_to_scan_configs(plan)
        assert configs[0]["rest_body_template"] == '{"msg": "$INPUT"}'

    def test_body_template_multiline_yaml(self, tmp_path):
        yaml_content = """
name: "test"
targets:
  - name: "api"
    type: rest
    endpoint: "http://example.com/chat"
    body_template: |
      {"msg": "$INPUT"}
    response_field: "r"
"""
        path = _write_yaml(tmp_path, yaml_content)
        plan = load_plan(path)
        configs = plan_to_scan_configs(plan)
        assert configs[0]["rest_body_template"] == '{"msg": "$INPUT"}'

    def test_body_template_no_trailing_whitespace(self):
        plan = {
            "name": "test",
            "targets": [
                {
                    "name": "api",
                    "type": "rest",
                    "endpoint": "http://example.com/chat",
                    "body_template": '{"msg": "$INPUT"}',
                    "response_field": "r",
                },
            ],
        }
        configs = plan_to_scan_configs(plan)
        assert configs[0]["rest_body_template"] == '{"msg": "$INPUT"}'


# ===================================================================
# Auth section validation
# ===================================================================

class TestAuthValidation:
    """Test plan_loader validates the auth section correctly."""

    def _plan_with_auth(self, auth_cfg):
        return {
            "name": "auth-test",
            "targets": [{"name": "t", "type": "ollama", "model": "m"}],
            "auth": auth_cfg,
        }

    def test_valid_okta_auth(self):
        errors = validate_plan(self._plan_with_auth({"type": "okta", "token_env": "MY_TOKEN"}))
        assert errors == []

    def test_valid_bearer_auth(self):
        errors = validate_plan(self._plan_with_auth({"type": "bearer", "token_env": "TOK"}))
        assert errors == []

    def test_valid_none_auth(self):
        errors = validate_plan(self._plan_with_auth({"type": "none"}))
        assert errors == []

    def test_unknown_auth_type(self):
        errors = validate_plan(self._plan_with_auth({"type": "kerberos"}))
        assert any("unknown auth type" in e for e in errors)

    def test_okta_missing_token_env(self):
        errors = validate_plan(self._plan_with_auth({"type": "okta"}))
        assert any("token_env" in e for e in errors)

    def test_bearer_missing_token_env(self):
        errors = validate_plan(self._plan_with_auth({"type": "bearer"}))
        assert any("token_env" in e for e in errors)

    def test_cookie_does_not_require_token_env(self):
        errors = validate_plan(self._plan_with_auth({"type": "cookie"}))
        assert errors == []

    def test_no_auth_section_is_valid(self):
        plan = {"name": "t", "targets": [{"name": "t", "type": "ollama", "model": "m"}]}
        errors = validate_plan(plan)
        assert errors == []
