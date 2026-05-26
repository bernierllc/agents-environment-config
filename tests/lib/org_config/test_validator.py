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


def test_rejects_unknown_trust_mode():
    fm, body = _load("valid-minimal.yaml")
    fm["trust"]["mode"] = "xyzzy"
    with pytest.raises(OrgConfigValidationError, match="trust.mode"):
        validate_org_config(fm, body)


def test_accepts_pinned_key_with_inline_pubkey():
    fm, body = _load("valid-minimal.yaml")
    fm["trust"] = {"mode": "pinned_key", "pubkey": "AAAA"}
    cfg = validate_org_config(fm, body)
    assert cfg.trust_mode == "pinned_key"
    assert cfg.trust_pubkey == "AAAA"


def test_pinned_key_requires_pubkey():
    fm, body = _load("valid-minimal.yaml")
    fm["trust"] = {"mode": "pinned_key"}
    with pytest.raises(OrgConfigValidationError, match="pubkey"):
        validate_org_config(fm, body)


def test_dns_anchor_requires_dns_domain():
    fm, body = _load("valid-minimal.yaml")
    fm["trust"] = {"mode": "dns_anchor"}
    with pytest.raises(OrgConfigValidationError, match="dns_domain"):
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


def test_accepts_projects_overlay():
    fm, body = _load("valid-minimal.yaml")
    body["projects"] = [
        {
            "match": {"git_remote": "github.com:acme/*"},
            "profile": {
                "items": {
                    "skills": {"repo-skill": {"source": "aec.default.skills", "stance": "required"}}
                },
                "prompts": {"setup.track_current_repo": True},
            },
        }
    ]
    cfg = validate_org_config(fm, body)
    assert len(cfg.projects) == 1
    overlay = cfg.projects[0]
    assert overlay.match.git_remote == "github.com:acme/*"
    assert overlay.profile.items["skills"]["repo-skill"].stance.value == "required"
    assert overlay.profile.prompts["setup.track_current_repo"] is True


def test_accepts_projects_directory_match():
    fm, body = _load("valid-minimal.yaml")
    body["projects"] = [{"match": {"directory": "~/work/acme/*"}, "profile": {}}]
    cfg = validate_org_config(fm, body)
    assert cfg.projects[0].match.directory == "~/work/acme/*"


def test_rejects_project_match_without_selector():
    fm, body = _load("valid-minimal.yaml")
    body["projects"] = [{"match": {}, "profile": {}}]
    with pytest.raises(OrgConfigValidationError, match="git_remote or directory"):
        validate_org_config(fm, body)


def test_rejects_project_profile_unknown_source():
    fm, body = _load("valid-minimal.yaml")
    body["projects"] = [
        {
            "match": {"git_remote": "*"},
            "profile": {"items": {"skills": {"x": {"source": "nope", "stance": "required"}}}},
        }
    ]
    with pytest.raises(OrgConfigValidationError, match="source"):
        validate_org_config(fm, body)


def test_rejects_project_profile_preferences_v1():
    fm, body = _load("valid-minimal.yaml")
    body["projects"] = [
        {"match": {"git_remote": "*"}, "profile": {"preferences": {"hook_mode": "auto"}}}
    ]
    with pytest.raises(OrgConfigValidationError, match="preferences"):
        validate_org_config(fm, body)


def test_rejects_project_profile_prompt_outside_allow_list():
    fm, body = _load("valid-minimal.yaml")
    body["projects"] = [
        {"match": {"git_remote": "*"}, "profile": {"prompts": {"definitely_not_a_prompt": True}}}
    ]
    with pytest.raises(OrgConfigValidationError, match="prompts"):
        validate_org_config(fm, body)


def _full_minimal_with_install(actions):
    fm, body = _load("valid-minimal.yaml")
    body["install"] = {"enrollment_script": actions}
    return fm, body


def test_accepts_enrollment_script_run_doctor():
    fm, body = _full_minimal_with_install([{"action": "run_doctor"}])
    cfg = validate_org_config(fm, body)
    assert cfg.enrollment_script == [{"action": "run_doctor"}]


def test_accepts_install_items_with_types_and_sources():
    fm, body = _full_minimal_with_install(
        [{"action": "install_items", "types": ["skills", "rules"], "sources": ["aec.default.skills"]}]
    )
    cfg = validate_org_config(fm, body)
    assert cfg.enrollment_script[0]["types"] == ["skills", "rules"]


def test_accepts_set_pref_with_if_unset():
    fm, body = _full_minimal_with_install(
        [{"action": "set_pref", "key": "hook_mode", "value": "auto", "if_unset": True}]
    )
    cfg = validate_org_config(fm, body)
    assert cfg.enrollment_script[0]["if_unset"] is True


def test_accepts_set_hooks_policy():
    fm, body = _full_minimal_with_install([{"action": "set_hooks", "policy": "per-repo"}])
    cfg = validate_org_config(fm, body)
    assert cfg.enrollment_script[0]["policy"] == "per-repo"


def test_accepts_add_source_referencing_custom_source():
    fm, body = _load("valid-minimal.yaml")
    body["sources"] = {
        "default": {"skills": "keep", "rules": "keep", "agents": "keep", "mcps": "keep"},
        "custom": [
            {
                "id": "acme-skills",
                "url": "https://example.com/repo.git",
                "ref": "main",
                "contributes": ["skills"],
            }
        ],
    }
    body["install"] = {
        "enrollment_script": [{"action": "add_source", "source_id": "acme-skills"}]
    }
    cfg = validate_org_config(fm, body)
    assert cfg.enrollment_script[0]["source_id"] == "acme-skills"


def test_rejects_unknown_action_escape_hatch():
    fm, body = _full_minimal_with_install(
        [
            {"action": "run_doctor"},
            {"action": "set_hooks"},
            {"action": "install_items"},
            {"action": "run", "cmd": "rm -rf /"},
        ]
    )
    with pytest.raises(
        OrgConfigValidationError,
        match=r"enrollment_script\[3\]\.action 'run' is not a recognized action",
    ):
        validate_org_config(fm, body)


def test_rejects_add_source_unknown_source_id():
    fm, body = _full_minimal_with_install(
        [{"action": "add_source", "source_id": "nope"}]
    )
    with pytest.raises(OrgConfigValidationError, match="source_id"):
        validate_org_config(fm, body)


def test_rejects_set_pref_unknown_key():
    fm, body = _full_minimal_with_install(
        [{"action": "set_pref", "key": "definitely_not_allow_listed", "value": 1}]
    )
    with pytest.raises(OrgConfigValidationError, match="key"):
        validate_org_config(fm, body)


def test_rejects_install_items_unknown_type():
    fm, body = _full_minimal_with_install(
        [{"action": "install_items", "types": ["bogus"]}]
    )
    with pytest.raises(OrgConfigValidationError, match="types"):
        validate_org_config(fm, body)


def test_rejects_set_hooks_invalid_policy():
    fm, body = _full_minimal_with_install([{"action": "set_hooks", "policy": "off"}])
    with pytest.raises(OrgConfigValidationError, match="policy"):
        validate_org_config(fm, body)


def _item_with(**extra):
    policy = {"source": "aec.default.skills", "stance": "required"}
    policy.update(extra)
    return {"skills": {"timed": policy}, "rules": {}, "agents": {}, "mcps": {}}


def test_accepts_item_time_bounds():
    fm, body = _load("valid-minimal.yaml")
    body["items"] = _item_with(required_after="2026-06-01", expires_at="2026-12-01T00:00:00Z")
    cfg = validate_org_config(fm, body)
    pol = cfg.items["skills"]["timed"]
    assert pol.required_after == "2026-06-01"
    assert pol.expires_at == "2026-12-01T00:00:00Z"


def test_rejects_non_iso_required_after():
    fm, body = _load("valid-minimal.yaml")
    body["items"] = _item_with(required_after="not-a-date")
    with pytest.raises(OrgConfigValidationError, match="required_after"):
        validate_org_config(fm, body)


def test_rejects_non_iso_expires_at():
    fm, body = _load("valid-minimal.yaml")
    body["items"] = _item_with(expires_at="soon")
    with pytest.raises(OrgConfigValidationError, match="expires_at"):
        validate_org_config(fm, body)


def test_rejects_expiry_before_required_after():
    fm, body = _load("valid-minimal.yaml")
    body["items"] = _item_with(required_after="2026-12-01", expires_at="2026-06-01")
    with pytest.raises(OrgConfigValidationError, match="expires_at"):
        validate_org_config(fm, body)
