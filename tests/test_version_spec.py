"""One version-pin evaluator for every source: parser, plan_apply on both sources, validator parity."""

import pytest

from aec.lib.apply_core import DesiredItem, plan_apply
from aec.lib.org_config.errors import OrgConfigValidationError
from aec.lib.org_config.validator import validate_org_config
from aec.lib.skills_manifest import parse_version_spec, version_satisfies

SATISFIES = [
    # (version, spec, expected)
    ("2.1.0", "", True),
    ("2.1.0", "latest", True),
    ("2.1.0", "2.1.0", True),
    ("2.1.1", "2.1.0", False),
    ("2.1.0", "==2.1.0", True),
    ("2.1.0", "==2.1", True),  # zero-padded
    ("2.1.0", "== 2.2.0", False),
    ("2.1.0", ">=2.0.0", True),
    ("2.0.0", ">=2.0.0", True),
    ("1.9.9", ">=2.0.0", False),
    ("2.0.0", ">2.0.0", False),
    ("2.0.1", ">2.0.0", True),
    ("2.0.0", "<=2.0.0", True),
    ("2.0.1", "<=2.0.0", False),
    ("1.9.9", "<2.0.0", True),
    ("2.1.0", "<2.0.0", False),
    ("1.4.5", "~=1.4.5", True),
    ("1.4.9", "~=1.4.5", True),
    ("1.5.0", "~=1.4.5", False),
    ("1.4.4", "~=1.4.5", False),
    ("2.9.0", "~=2.2", True),
    ("3.0.0", "~=2.2", False),
    ("2.5.0", ">=2.0.0, <3.0.0", True),
    ("3.0.0", ">=2.0.0, <3.0.0", False),
    ("1.0.0", ">=2.0.0,<3.0.0", False),
    ("2.5.0", " >=2.0 ,<3 ", True),
]

MALFORMED = ["^1.0", "1.x", "*", "~=2", "=2.0.0", ">=", ">=2.0.0,", ",", "2.0-rc1", "v2.0.0", "!=2.0", "2..0", None, 2.1]


@pytest.mark.parametrize("version,spec,expected", SATISFIES)
def test_version_satisfies(version, spec, expected):
    assert version_satisfies(version, spec) is expected


@pytest.mark.parametrize("spec", MALFORMED)
def test_malformed_pin_raises_naming_pin_and_syntax(spec):
    with pytest.raises(ValueError, match="invalid version pin") as exc:
        version_satisfies("1.0.0", spec)
    assert repr(spec) in str(exc.value) and "~=" in str(exc.value)


def test_unparseable_version_under_a_constraint_raises():
    with pytest.raises(ValueError, match="not a dotted-integer"):
        version_satisfies("2.0.0-beta", ">=1.0.0")
    assert version_satisfies("2.0.0-beta", "latest") is True  # no constraint, nothing to parse


# --- plan_apply: default catalog ("") and a custom source, same evaluator ---

CUSTOM = "example-org/team-skills"


def _plan(spec, *, source_id="", available="2.1.0", installed=None):
    key = (source_id, "skills") if source_id else "skills"
    avail = {key: {"my-skill": {"version": available}}}
    skills = {"my-skill": {"version": installed, "source": source_id}} if installed else {}
    manifest = {"global": {"skills": skills, "rules": {}, "agents": {}, "mcps": {}}, "repos": {}}
    item = DesiredItem("skill", "my-skill", "global", version_spec=spec, source_id=source_id)
    return plan_apply([item], manifest=manifest, available_by_type=avail)[0]


@pytest.mark.parametrize("source_id", ["", CUSTOM])
@pytest.mark.parametrize("spec", ["", "latest", "2.1.0", ">=2.0.0", "~=2.1", ">=2.0,<3"])
def test_matching_pin_installs(source_id, spec):
    entry = _plan(spec, source_id=source_id)
    assert entry.action == "install" and entry.to_version == "2.1.0"


@pytest.mark.parametrize("source_id", ["", CUSTOM])
@pytest.mark.parametrize("spec", ["2.0.0", "<2.0.0", "~=2.0.1", ">=3.0.0,<4"])
def test_mismatched_pin_is_unsatisfiable_never_ignored(source_id, spec):
    """A default-catalog pin used to be silently ignored; now it gates like a custom source."""
    entry = _plan(spec, source_id=source_id)
    assert entry.action == "unsatisfiable"
    assert "'my-skill'" in entry.reason and spec in entry.reason and "2.1.0" in entry.reason


@pytest.mark.parametrize("source_id", ["", CUSTOM])
def test_malformed_pin_is_unsatisfiable_naming_the_syntax(source_id):
    entry = _plan("^2.0", source_id=source_id)
    assert entry.action == "unsatisfiable"
    assert "invalid version pin '^2.0'" in entry.reason and "~=" in entry.reason


@pytest.mark.parametrize("source_id", ["", CUSTOM])
def test_installed_version_outside_the_pin_is_replaced(source_id):
    entry = _plan("<3.0.0", source_id=source_id, available="2.1.0", installed="3.0.0")
    assert (entry.action, entry.from_version, entry.to_version) == ("upgrade", "3.0.0", "2.1.0")


@pytest.mark.parametrize("source_id", ["", CUSTOM])
def test_installed_version_inside_the_pin_is_kept(source_id):
    assert _plan("~=2.1", source_id=source_id, installed="2.1.0").action == "noop"


# --- validator accepts exactly what the evaluator parses ---

def _validate_version(version, stance="required", source="aec.default.skills"):
    fm = {"schema_version": "1.0", "org_id": "x", "org_name": "X", "config_version": "1.0.0",
          "trust": {"mode": "unsigned"}}
    item = {"source": source, "stance": stance, "version": version}
    body = {"sources": {"default": {}, "custom": []},
            "items": {"skills": {"my-skill": item}, "rules": {}, "agents": {}, "mcps": {}}}
    return validate_org_config(fm, body)


# None is "no version" in an org config (absent key), so it is not a parity case.
@pytest.mark.parametrize("spec", [s for _, s, _ in SATISFIES] + [m for m in MALFORMED if m is not None])
def test_validator_parity_with_evaluator(spec):
    try:
        parse_version_spec(spec)
        parses = True
    except ValueError:
        parses = False
    if parses:
        assert _validate_version(spec).items["skills"]["my-skill"].version == spec
    else:
        with pytest.raises(OrgConfigValidationError) as exc:
            _validate_version(spec)
        assert exc.value.field_path == "items.skills.my-skill.version"


@pytest.mark.parametrize("spec", [">=2.0.0", "~=2.1", ">=1,<2", "latest", ""])
def test_pinned_stance_needs_one_exact_version(spec):
    with pytest.raises(OrgConfigValidationError, match="one exact version"):
        _validate_version(spec, stance="pinned")


@pytest.mark.parametrize("spec", ["2.1.0", "==2.1.0"])
def test_pinned_stance_accepts_an_exact_version(spec):
    assert _validate_version(spec, stance="pinned").items["skills"]["my-skill"].version == spec


def test_pinned_stance_without_a_version_is_rejected():
    with pytest.raises(OrgConfigValidationError, match="requires a version"):
        _validate_version(None, stance="pinned")
