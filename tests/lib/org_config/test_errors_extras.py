"""Extra coverage for the `OrgConfigValidationError` constructor branches."""
from __future__ import annotations

from aec.lib.org_config.errors import OrgConfigValidationError


def test_validation_error_without_field_path_uses_bare_message():
    exc = OrgConfigValidationError("oops")
    assert str(exc) == "oops"
    assert exc.field_path is None


def test_validation_error_with_field_path_prefixes_message():
    exc = OrgConfigValidationError("missing", field_path="trust.mode")
    assert str(exc) == "trust.mode: missing"
    assert exc.field_path == "trust.mode"
