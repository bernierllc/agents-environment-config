from aec.lib.org_config.errors import (
    OrgConfigError,
    OrgConfigParseError,
    OrgConfigValidationError,
    OrgConfigTrustError,
    OrgConfigMultiOrgRejectedError,
    OrgConfigUnknownSchemaError,
)


def test_all_errors_subclass_org_config_error():
    for cls in (
        OrgConfigParseError,
        OrgConfigValidationError,
        OrgConfigTrustError,
        OrgConfigMultiOrgRejectedError,
        OrgConfigUnknownSchemaError,
    ):
        assert issubclass(cls, OrgConfigError)


def test_validation_error_carries_field_path():
    err = OrgConfigValidationError("bad stance", field_path="items.skills.foo.stance")
    assert err.field_path == "items.skills.foo.stance"
    assert "items.skills.foo.stance" in str(err)
