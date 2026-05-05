from pathlib import Path
import pytest

from aec.lib.org_config.parser import parse_org_config_text
from aec.lib.org_config.validator import validate_org_config
from aec.lib.org_config.errors import (
    OrgConfigValidationError,
    OrgConfigUnknownSchemaError,
)
from aec.lib.org_config.schema import OrgConfig, Stance


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return parse_org_config_text((FIXTURES / name).read_text())


def test_validates_minimal_config():
    fm, body = _load("valid-minimal.yaml")
    cfg = validate_org_config(fm, body)
    assert isinstance(cfg, OrgConfig)
    assert cfg.org_id == "minimal"
    assert cfg.trust_mode == "unsigned"


def test_validates_full_config_into_typed_items():
    fm, body = _load("valid-full.yaml")
    cfg = validate_org_config(fm, body)
    for type_name, items in cfg.items.items():
        for item_name, policy in items.items():
            assert isinstance(policy.stance, Stance), \
                f"{type_name}.{item_name} stance is not Stance enum"


def test_rejects_item_missing_source():
    fm, body = _load("invalid-no-source.yaml")
    with pytest.raises(OrgConfigValidationError, match="source"):
        validate_org_config(fm, body)


def test_rejects_item_with_unknown_source():
    fm, body = _load("invalid-unknown-source.yaml")
    with pytest.raises(OrgConfigValidationError, match="source"):
        validate_org_config(fm, body)


def test_rejects_unknown_stance():
    fm, body = _load("invalid-bad-stance.yaml")
    with pytest.raises(OrgConfigValidationError, match="stance"):
        validate_org_config(fm, body)


def test_rejects_unknown_future_schema():
    fm, body = _load("invalid-future-schema.yaml")
    with pytest.raises(OrgConfigUnknownSchemaError):
        validate_org_config(fm, body)


def test_rejects_non_unsigned_trust_in_phase_1():
    fm, body = _load("valid-minimal.yaml")
    fm["trust"]["mode"] = "dns_anchor"
    with pytest.raises(OrgConfigValidationError, match="trust"):
        validate_org_config(fm, body)


def test_rejects_install_preference_outside_allow_list():
    fm, body = _load("valid-minimal.yaml")
    body["install"] = {"preferences": {"definitely_not_allowed_key": "x"}}
    with pytest.raises(OrgConfigValidationError, match="install.preferences"):
        validate_org_config(fm, body)


def test_rejects_install_prompt_outside_allow_list():
    fm, body = _load("valid-minimal.yaml")
    body["install"] = {"prompts": {"definitely_not_a_real_prompt_id": True}}
    with pytest.raises(OrgConfigValidationError, match="install.prompts"):
        validate_org_config(fm, body)


def test_rejects_enrollment_script_in_phase_1():
    fm, body = _load("valid-minimal.yaml")
    body["install"] = {"enrollment_script": [{"action": "run_doctor"}]}
    with pytest.raises(OrgConfigValidationError, match="enrollment_script"):
        validate_org_config(fm, body)


def test_rejects_projects_block_in_phase_1():
    fm, body = _load("valid-minimal.yaml")
    body["projects"] = [{"match": {"git_remote": "*"}, "profile": {}}]
    with pytest.raises(OrgConfigValidationError, match="projects"):
        validate_org_config(fm, body)
