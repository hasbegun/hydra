"""
Tests for REST target support in ScanConfigRequest schema and ScanManager._build_command.

Covers:
  T1.1 - Schema accepts REST fields
  T1.2 - REST fields are optional (Ollama config validates, REST fields are None)
  T1.3 - _build_command passes REST config via --generator_options for rest targets
  T1.4 - _build_command omits REST generator_options when absent or for non-rest targets
  T1.5 - Existing tests still pass (run separately via make test-local)
"""
import json
import sys
import os
import pytest

# Add backend root to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "services", "garak_service")
)

from models.schemas import ScanConfigRequest, GeneratorType


# ---------------------------------------------------------------------------
# T1.1: Schema accepts REST fields
# ---------------------------------------------------------------------------

class TestRestSchemaAcceptance:
    """T1.1: ScanConfigRequest accepts all REST-specific fields."""

    def test_rest_target_with_all_fields(self):
        config = ScanConfigRequest(
            target_type="rest",
            target_name="my-chatbot",
            rest_endpoint="https://api.example.com/chat",
            rest_headers={"Authorization": "Bearer sk-abc123"},
            rest_body_template='{"message": "$INPUT"}',
            rest_response_json_field="response.text",
        )
        assert config.target_type == "rest"
        assert config.target_name == "my-chatbot"
        assert config.rest_endpoint == "https://api.example.com/chat"
        assert config.rest_headers == {"Authorization": "Bearer sk-abc123"}
        assert config.rest_body_template == '{"message": "$INPUT"}'
        assert config.rest_response_json_field == "response.text"

    def test_rest_endpoint_various_urls(self):
        """REST endpoint accepts various URL formats."""
        urls = [
            "http://localhost:3030/api/v1/chat",
            "https://api.openai.com/v1/chat/completions",
            "http://host.docker.internal:8080/v1/chat",
            "https://myinstance.openai.azure.com/openai/deployments/gpt-4/chat/completions",
        ]
        for url in urls:
            config = ScanConfigRequest(
                target_type="rest",
                target_name="test",
                rest_endpoint=url,
            )
            assert config.rest_endpoint == url

    def test_rest_headers_multiple_entries(self):
        """REST headers accepts multiple key-value pairs."""
        headers = {
            "Authorization": "Bearer sk-abc123",
            "Content-Type": "application/json",
            "X-Custom-Header": "custom-value",
        }
        config = ScanConfigRequest(
            target_type="rest",
            target_name="test",
            rest_headers=headers,
        )
        assert config.rest_headers == headers

    def test_rest_body_template_openai_format(self):
        """REST body template accepts OpenAI-compatible format."""
        template = '{"model":"gpt-4","messages":[{"role":"user","content":"$INPUT"}],"stream":false}'
        config = ScanConfigRequest(
            target_type="rest",
            target_name="test",
            rest_body_template=template,
        )
        assert config.rest_body_template == template

    def test_rest_response_json_field_nested_path(self):
        """REST response field accepts nested JSON paths."""
        paths = [
            "choices[0].message.content",
            "response.text",
            "data.reply",
            "result",
        ]
        for path in paths:
            config = ScanConfigRequest(
                target_type="rest",
                target_name="test",
                rest_response_json_field=path,
            )
            assert config.rest_response_json_field == path

    def test_serialization_roundtrip(self):
        """REST fields survive model_dump -> ScanConfigRequest roundtrip."""
        config = ScanConfigRequest(
            target_type="rest",
            target_name="my-chatbot",
            rest_endpoint="https://api.example.com/chat",
            rest_headers={"Authorization": "Bearer tok"},
            rest_body_template='{"msg": "$INPUT"}',
            rest_response_json_field="choices[0].message.content",
        )
        data = config.model_dump()
        assert data["rest_endpoint"] == "https://api.example.com/chat"
        assert data["rest_headers"] == {"Authorization": "Bearer tok"}
        assert data["rest_body_template"] == '{"msg": "$INPUT"}'
        assert data["rest_response_json_field"] == "choices[0].message.content"

        restored = ScanConfigRequest(**data)
        assert restored.rest_endpoint == config.rest_endpoint
        assert restored.rest_headers == config.rest_headers
        assert restored.rest_body_template == config.rest_body_template
        assert restored.rest_response_json_field == config.rest_response_json_field


# ---------------------------------------------------------------------------
# T1.2: REST fields are optional (backward compatibility)
# ---------------------------------------------------------------------------

class TestRestFieldsOptional:
    """T1.2: REST fields default to None; Ollama configs still validate."""

    def test_ollama_config_no_rest_fields(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2",
        )
        assert config.rest_endpoint is None
        assert config.rest_headers is None
        assert config.rest_body_template is None
        assert config.rest_response_json_field is None

    def test_openai_config_no_rest_fields(self):
        config = ScanConfigRequest(
            target_type="openai",
            target_name="gpt-3.5-turbo",
        )
        assert config.rest_endpoint is None
        assert config.rest_headers is None
        assert config.rest_body_template is None
        assert config.rest_response_json_field is None

    def test_rest_fields_none_omitted_in_json(self):
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2",
        )
        data = config.model_dump(exclude_none=True)
        assert "rest_endpoint" not in data
        assert "rest_headers" not in data
        assert "rest_body_template" not in data
        assert "rest_response_json_field" not in data

    def test_rest_type_without_rest_fields(self):
        """REST target type validates even without REST-specific fields.
        Validation of required REST fields is done at the CLI/API layer,
        not at the schema level, to keep backward compatibility."""
        config = ScanConfigRequest(
            target_type="rest",
            target_name="test",
        )
        assert config.rest_endpoint is None

    def test_partial_rest_fields(self):
        """Only some REST fields can be set."""
        config = ScanConfigRequest(
            target_type="rest",
            target_name="test",
            rest_endpoint="https://api.example.com/chat",
        )
        assert config.rest_endpoint == "https://api.example.com/chat"
        assert config.rest_headers is None
        assert config.rest_body_template is None
        assert config.rest_response_json_field is None


# ---------------------------------------------------------------------------
# GeneratorType enum includes REST
# ---------------------------------------------------------------------------

class TestGeneratorTypeRest:
    """GeneratorType enum includes REST value."""

    def test_rest_enum_value(self):
        assert GeneratorType.REST == "rest"
        assert GeneratorType.REST.value == "rest"

    def test_rest_in_enum_members(self):
        assert "REST" in GeneratorType.__members__

    def test_existing_enum_values_unchanged(self):
        assert GeneratorType.OPENAI == "openai"
        assert GeneratorType.OLLAMA if hasattr(GeneratorType, "OLLAMA") else True


# ---------------------------------------------------------------------------
# Helper: extract generator_options from command list
# ---------------------------------------------------------------------------

def _parse_generator_options(cmd: list[str]) -> dict:
    """Extract and parse the --generator_options JSON from a command list."""
    if "--generator_options" not in cmd:
        return {}
    idx = cmd.index("--generator_options")
    return json.loads(cmd[idx + 1])


# ---------------------------------------------------------------------------
# T1.3: _build_command passes REST config via --generator_options
# ---------------------------------------------------------------------------

class TestBuildCommandRestFlags:
    """T1.3: _build_command passes REST config through --generator_options."""

    def _build(self, config_overrides: dict) -> list[str]:
        from scan_manager import ScanManager

        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "rest", "target_name": "my-chatbot"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_rest_endpoint_mapped_to_uri(self):
        cmd = self._build({"rest_endpoint": "https://api.example.com/chat"})
        opts = _parse_generator_options(cmd)
        assert opts["rest"]["uri"] == "https://api.example.com/chat"

    def test_rest_headers_mapped(self):
        headers = {"Authorization": "Bearer sk-abc123", "X-Custom": "val"}
        cmd = self._build({"rest_headers": headers})
        opts = _parse_generator_options(cmd)
        assert opts["rest"]["headers"] == headers

    def test_rest_body_template_mapped_to_req_template(self):
        template = '{"model":"gpt-4","messages":[{"role":"user","content":"$INPUT"}]}'
        cmd = self._build({"rest_body_template": template})
        opts = _parse_generator_options(cmd)
        assert opts["rest"]["req_template"] == template

    def test_rest_response_json_field_mapped(self):
        field = "choices[0].message.content"
        cmd = self._build({"rest_response_json_field": field})
        opts = _parse_generator_options(cmd)
        assert opts["rest"]["response_json_field"] == field
        assert opts["rest"]["response_json"] is True

    def test_all_rest_fields_together(self):
        cmd = self._build({
            "rest_endpoint": "https://api.example.com/chat",
            "rest_headers": {"Authorization": "Bearer tok"},
            "rest_body_template": '{"msg": "$INPUT"}',
            "rest_response_json_field": "response.text",
        })
        opts = _parse_generator_options(cmd)
        rest = opts["rest"]
        assert rest["uri"] == "https://api.example.com/chat"
        assert rest["headers"] == {"Authorization": "Bearer tok"}
        assert rest["req_template"] == '{"msg": "$INPUT"}'
        assert rest["response_json_field"] == "response.text"
        assert rest["response_json"] is True

    def test_rest_flags_with_other_flags(self):
        """REST config works alongside standard flags like probes, generations."""
        cmd = self._build({
            "rest_endpoint": "https://api.example.com/chat",
            "rest_body_template": '{"msg": "$INPUT"}',
            "rest_response_json_field": "response.text",
            "probes": ["dan", "encoding"],
            "generations": 10,
            "continue_on_error": True,
        })
        opts = _parse_generator_options(cmd)
        assert "rest" in opts
        assert opts["rest"]["uri"] == "https://api.example.com/chat"
        assert "--probes" in cmd
        assert "--continue_on_error" in cmd

    def test_rest_generator_options_not_overwritten_by_user_opts(self):
        """User-provided generator_options for rest are preserved; rest_* fields
        fill in missing keys without overwriting."""
        cmd = self._build({
            "rest_endpoint": "https://api.example.com/chat",
            "rest_body_template": '{"msg": "$INPUT"}',
            "generator_options": {"rest": {"uri": "https://custom.url/v1", "max_tokens": 200}},
        })
        opts = _parse_generator_options(cmd)
        # User's uri takes precedence
        assert opts["rest"]["uri"] == "https://custom.url/v1"
        assert opts["rest"]["max_tokens"] == 200
        # rest_body_template fills in req_template since it wasn't in user opts
        assert opts["rest"]["req_template"] == '{"msg": "$INPUT"}'


# ---------------------------------------------------------------------------
# T1.4: _build_command omits REST generator_options when absent
# ---------------------------------------------------------------------------

class TestBuildCommandRestFlagsOmitted:
    """T1.4: _build_command does NOT include REST generator_options for Ollama configs."""

    def _build(self, config_overrides: dict) -> list[str]:
        from scan_manager import ScanManager

        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "ollama", "target_name": "llama3.2:3b"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_no_rest_opts_for_ollama(self):
        cmd = self._build({})
        opts = _parse_generator_options(cmd)
        assert "rest" not in opts

    def test_no_rest_opts_with_none_values(self):
        cmd = self._build({
            "rest_endpoint": None,
            "rest_headers": None,
            "rest_body_template": None,
            "rest_response_json_field": None,
        })
        opts = _parse_generator_options(cmd)
        assert "rest" not in opts

    def test_no_rest_opts_with_empty_string(self):
        cmd = self._build({
            "rest_endpoint": "",
            "rest_body_template": "",
            "rest_response_json_field": "",
        })
        opts = _parse_generator_options(cmd)
        assert "rest" not in opts

    def test_no_rest_opts_with_empty_headers(self):
        cmd = self._build({"rest_headers": {}})
        opts = _parse_generator_options(cmd)
        assert "rest" not in opts


# ---------------------------------------------------------------------------
# Schema -> command roundtrip integration test
# ---------------------------------------------------------------------------

class TestRestSchemaToCommandRoundtrip:
    """Validate schema -> dict -> _build_command pipeline for REST targets."""

    def _build(self, config_overrides: dict) -> list[str]:
        from scan_manager import ScanManager

        mgr = ScanManager.__new__(ScanManager)
        mgr.garak_path = "/usr/local/bin/garak"
        base = {"target_type": "rest", "target_name": "test"}
        base.update(config_overrides)
        return mgr._build_command(base)

    def test_full_rest_schema_to_command(self):
        """Full pipeline: schema validation -> model_dump -> _build_command."""
        config = ScanConfigRequest(
            target_type="rest",
            target_name="prod-chatbot",
            rest_endpoint="https://api.myapp.com/v1/chat/completions",
            rest_headers={
                "Authorization": "Bearer sk-abc123",
                "Content-Type": "application/json",
            },
            rest_body_template='{"model":"gpt-4","messages":[{"role":"user","content":"$INPUT"}],"stream":false}',
            rest_response_json_field="choices[0].message.content",
            probes=["dan", "encoding", "promptinject"],
            generations=15,
            eval_threshold=0.6,
            continue_on_error=True,
        )
        cmd = self._build(config.model_dump())

        # Verify target
        idx = cmd.index("--target_type")
        assert cmd[idx + 1] == "rest"
        idx = cmd.index("--target_name")
        assert cmd[idx + 1] == "prod-chatbot"

        # Verify REST config in generator_options
        opts = _parse_generator_options(cmd)
        rest = opts["rest"]
        assert rest["uri"] == "https://api.myapp.com/v1/chat/completions"
        assert rest["headers"]["Authorization"] == "Bearer sk-abc123"
        assert rest["headers"]["Content-Type"] == "application/json"
        assert "$INPUT" in rest["req_template"]
        assert rest["response_json_field"] == "choices[0].message.content"
        assert rest["response_json"] is True

        # Verify standard flags still work
        assert "--probes" in cmd
        assert "--continue_on_error" in cmd

        idx = cmd.index("--generations")
        assert cmd[idx + 1] == "15"

        idx = cmd.index("--eval_threshold")
        assert cmd[idx + 1] == "0.6"

    def test_ollama_schema_to_command_no_rest(self):
        """Ollama schema -> _build_command has no REST in generator_options."""
        config = ScanConfigRequest(
            target_type="ollama",
            target_name="llama3.2",
            probes=["dan"],
            generations=5,
        )
        cmd = self._build(config.model_dump())
        opts = _parse_generator_options(cmd)
        assert "rest" not in opts
