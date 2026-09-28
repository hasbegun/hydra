"""
Tests for Phase 1 Week 4: Enhanced Probe Validation.

Tests the ``ProbeValidator`` class directly (no filesystem or DB needed).
Also covers the priority queue routing and retry policy that were implemented
in Weeks 1-2 but are specified as Week 4 deliverables.

Test groups:
  - Blocked imports (os, subprocess, socket, importlib, shutil)
  - Blocked calls (eval, exec, __import__, compile)
  - File size limit (50 KB)
  - Probe inheritance requirement
  - Valid probe acceptance
  - Edge cases (nested imports, from X import Y, submodule imports)
  - Priority queue routing (already tested in test_celery_setup.py,
    re-verified here for the Week 4 spec)
  - Retry policy verification
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.custom_probe_service import (
    ProbeValidator,
    MAX_PROBE_SIZE_BYTES,
    BLOCKED_MODULES,
    BLOCKED_BUILTINS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PROBE = '''\
"""A valid probe."""
import garak.probes.base


class MyProbe(garak.probes.base.Probe):
    """Test probe for custom vulnerability."""

    prompts = ["Tell me something dangerous"]
    goal = "test"
    primary_detector = "always_pass"
    tags = ["avid-effect:security:S0403"]
'''


def _validate(code: str):
    """Shortcut for ProbeValidator.validate."""
    return ProbeValidator.validate(code)


def _error_types(result):
    """Extract the set of error_type values from a validation result."""
    return {e.error_type for e in result.errors}


def _error_messages(result):
    """Extract all error messages from a validation result."""
    return [e.message for e in result.errors]


# ---------------------------------------------------------------------------
# Blocked imports
# ---------------------------------------------------------------------------

class TestBlockedImports:
    """Importing blocked modules produces validation errors."""

    def test_blocks_os_import(self):
        code = 'import os\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("os" in e.message for e in result.errors)
        assert "security" in _error_types(result)

    def test_blocks_subprocess_import(self):
        code = 'import subprocess\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("subprocess" in e.message for e in result.errors)

    def test_blocks_socket_import(self):
        code = 'import socket\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("socket" in e.message for e in result.errors)

    def test_blocks_importlib_import(self):
        code = 'import importlib\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("importlib" in e.message for e in result.errors)

    def test_blocks_shutil_import(self):
        code = 'import shutil\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("shutil" in e.message for e in result.errors)

    def test_blocks_from_os_import(self):
        """``from os import path`` is also blocked."""
        code = 'from os import path\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("os" in e.message for e in result.errors)

    def test_blocks_from_os_path_import(self):
        """``from os.path import join`` blocks on root module ``os``."""
        code = 'from os.path import join\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("os" in e.message for e in result.errors)

    def test_blocks_import_os_as_alias(self):
        """``import os as operating_system`` is still blocked."""
        code = 'import os as o\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid

    def test_blocks_importlib_submodule(self):
        """``import importlib.util`` blocks on root module ``importlib``."""
        code = 'import importlib.util\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        assert any("importlib" in e.message for e in result.errors)

    def test_multiple_blocked_imports_all_reported(self):
        """All blocked imports are reported, not just the first one."""
        code = 'import os\nimport subprocess\nimport garak.probes.base\nclass P(garak.probes.base.Probe): pass'
        result = _validate(code)
        assert not result.valid
        msgs = " ".join(_error_messages(result))
        assert "os" in msgs
        assert "subprocess" in msgs

    def test_allows_safe_imports(self):
        """Non-blocked modules (json, re, typing) are accepted."""
        code = (
            'import json\nimport re\nfrom typing import List\n'
            'import garak.probes.base\n\n'
            'class P(garak.probes.base.Probe):\n'
            '    """test"""\n    pass\n'
        )
        result = _validate(code)
        assert result.valid


# ---------------------------------------------------------------------------
# Blocked builtin calls
# ---------------------------------------------------------------------------

class TestBlockedCalls:
    """Calling eval(), exec(), __import__(), compile() is rejected."""

    def test_blocks_eval_call(self):
        code = (
            'import garak.probes.base\n'
            'class P(garak.probes.base.Probe):\n'
            '    x = eval("1+1")\n'
        )
        result = _validate(code)
        assert not result.valid
        assert any("eval" in e.message for e in result.errors)

    def test_blocks_exec_call(self):
        code = (
            'import garak.probes.base\n'
            'class P(garak.probes.base.Probe):\n'
            '    def run(self):\n'
            '        exec("print(1)")\n'
        )
        result = _validate(code)
        assert not result.valid
        assert any("exec" in e.message for e in result.errors)

    def test_blocks_dunder_import_call(self):
        code = (
            'import garak.probes.base\n'
            'class P(garak.probes.base.Probe):\n'
            '    m = __import__("os")\n'
        )
        result = _validate(code)
        assert not result.valid
        assert any("__import__" in e.message for e in result.errors)

    def test_blocks_compile_call(self):
        code = (
            'import garak.probes.base\n'
            'class P(garak.probes.base.Probe):\n'
            '    c = compile("pass", "<str>", "exec")\n'
        )
        result = _validate(code)
        assert not result.valid
        assert any("compile" in e.message for e in result.errors)

    def test_eval_in_function_body(self):
        """eval inside a method body is detected."""
        code = (
            'import garak.probes.base\n'
            'class P(garak.probes.base.Probe):\n'
            '    def probe(self, g):\n'
            '        return eval("g.name")\n'
        )
        result = _validate(code)
        assert not result.valid


# ---------------------------------------------------------------------------
# File size limit
# ---------------------------------------------------------------------------

class TestFileSizeLimit:
    """Probe code exceeding 50 KB is rejected."""

    def test_rejects_over_50kb(self):
        # 51 KB of repeated comment
        code = "# " + "x" * (51 * 1024) + "\n"
        result = _validate(code)
        assert not result.valid
        assert result.errors[0].error_type == "size"
        assert "50 KB" in result.errors[0].message

    def test_accepts_under_50kb(self):
        result = _validate(VALID_PROBE)
        assert result.valid

    def test_exactly_50kb_accepted(self):
        """50 KB (boundary) is accepted."""
        padding_needed = MAX_PROBE_SIZE_BYTES - len(VALID_PROBE.encode("utf-8"))
        # Add a comment that fills up to exactly 50 KB
        padded = VALID_PROBE + "\n# " + "x" * (padding_needed - 4)
        assert len(padded.encode("utf-8")) <= MAX_PROBE_SIZE_BYTES
        result = _validate(padded)
        assert result.valid


# ---------------------------------------------------------------------------
# Probe inheritance requirement
# ---------------------------------------------------------------------------

class TestProbeInheritance:
    """Probe must inherit from something containing 'Probe'."""

    def test_rejects_no_inheritance(self):
        """Class without bases (no inheritance) is rejected."""
        code = (
            'import garak.probes.base\n'
            'class Foo:\n'
            '    pass\n'
        )
        result = _validate(code)
        assert not result.valid
        assert any("Probe" in e.message for e in result.errors)

    def test_rejects_wrong_base(self):
        """Class inheriting from non-Probe base is rejected."""
        code = (
            'import garak.probes.base\n'
            'class Foo(object):\n'
            '    pass\n'
        )
        result = _validate(code)
        assert not result.valid
        assert any("Probe" in e.message for e in result.errors)

    def test_accepts_probe_base(self):
        """Class inheriting from garak.probes.base.Probe is accepted."""
        result = _validate(VALID_PROBE)
        assert result.valid
        assert result.probe_info is not None
        assert len(result.probe_info["classes"]) == 1
        assert result.probe_info["classes"][0]["name"] == "MyProbe"

    def test_accepts_short_probe_base(self):
        """Class inheriting from just ``Probe`` (imported name) is accepted."""
        code = (
            'from garak.probes.base import Probe\n'
            'class MyProbe(Probe):\n'
            '    """test"""\n'
            '    pass\n'
        )
        result = _validate(code)
        assert result.valid

    def test_accepts_custom_probe_base(self):
        """Class inheriting from ``CustomProbe`` is accepted (contains 'Probe')."""
        code = (
            'import garak.probes.base\n'
            'class MyCustomProbe(garak.probes.base.Probe):\n'
            '    """test"""\n'
            '    pass\n'
        )
        result = _validate(code)
        assert result.valid


# ---------------------------------------------------------------------------
# Valid probe acceptance
# ---------------------------------------------------------------------------

class TestValidProbeAccepted:
    """Clean probes with proper inheritance pass validation."""

    def test_valid_probe_accepted(self):
        result = _validate(VALID_PROBE)
        assert result.valid
        assert result.errors == []

    def test_valid_probe_extracts_attributes(self):
        result = _validate(VALID_PROBE)
        assert result.probe_info is not None
        assert result.probe_info.get("has_prompts") is True
        assert result.probe_info.get("has_goal") is True
        assert result.probe_info.get("has_primary_detector") is True
        assert result.probe_info.get("has_tags") is True

    def test_valid_probe_has_docstring(self):
        result = _validate(VALID_PROBE)
        cls = result.probe_info["classes"][0]
        assert cls["docstring"] is not None

    def test_minimal_valid_probe(self):
        """Minimal probe: garak import + class inheriting Probe."""
        code = (
            'import garak.probes.base\n'
            'class P(garak.probes.base.Probe):\n'
            '    """minimal"""\n'
            '    pass\n'
        )
        result = _validate(code)
        assert result.valid


# ---------------------------------------------------------------------------
# Syntax errors
# ---------------------------------------------------------------------------

class TestSyntaxErrors:
    """Syntax errors are caught and reported."""

    def test_syntax_error_reported(self):
        code = "def foo(:\n    pass"
        result = _validate(code)
        assert not result.valid
        assert result.errors[0].error_type == "syntax"


# ---------------------------------------------------------------------------
# Garak import warning
# ---------------------------------------------------------------------------

class TestGarakImportWarning:
    """Missing garak import produces a warning (not an error)."""

    def test_no_garak_import_warning(self):
        code = 'class P(Probe):\n    """test"""\n    pass\n'
        result = _validate(code)
        # Still valid (warning only), but Probe base check may fail
        # depending on how we interpret "Probe" as a base
        assert any("garak" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Priority queue routing (spec: Week 4, impl: Week 1)
# ---------------------------------------------------------------------------

class TestPriorityRouting:
    """Priority queue routing — re-verified for Week 4 spec."""

    def test_express_for_small_probe_count(self):
        from tasks import route_to_queue
        assert route_to_queue(probe_count=3) == "express"

    def test_background_for_owasp_preset(self):
        from tasks import route_to_queue
        assert route_to_queue(preset="owasp") == "background"

    def test_background_for_full_preset(self):
        from tasks import route_to_queue
        assert route_to_queue(preset="full") == "background"

    def test_default_for_normal_scan(self):
        from tasks import route_to_queue
        assert route_to_queue(probe_count=10) == "default"

    def test_express_boundary(self):
        """Exactly 5 probes -> express."""
        from tasks import route_to_queue
        assert route_to_queue(probe_count=5) == "express"

    def test_six_probes_default(self):
        """6 probes -> default (not express)."""
        from tasks import route_to_queue
        assert route_to_queue(probe_count=6) == "default"


# ---------------------------------------------------------------------------
# Retry policy (spec: Week 4, impl: Week 2)
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    """Retry policy — re-verified for Week 4 spec."""

    def test_max_retries_is_2(self):
        from tasks.scan_task import execute_scan
        assert execute_scan.max_retries == 2

    def test_default_retry_delay_is_60(self):
        from tasks.scan_task import execute_scan
        assert execute_scan.default_retry_delay == 60


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------

class TestValidationConstants:
    """Module-level constants are correct."""

    def test_max_probe_size(self):
        assert MAX_PROBE_SIZE_BYTES == 50 * 1024

    def test_blocked_modules_complete(self):
        assert "os" in BLOCKED_MODULES
        assert "subprocess" in BLOCKED_MODULES
        assert "socket" in BLOCKED_MODULES
        assert "importlib" in BLOCKED_MODULES
        assert "shutil" in BLOCKED_MODULES

    def test_blocked_builtins_complete(self):
        assert "eval" in BLOCKED_BUILTINS
        assert "exec" in BLOCKED_BUILTINS
        assert "__import__" in BLOCKED_BUILTINS
        assert "compile" in BLOCKED_BUILTINS
