"""Org-config Phase 2: custom sources install.

Real git against local bare repos reached through https URLs that a test-only
git config rewrites (``url.<file-url>.insteadOf``), and a real ``~/.aec`` under
``tmp_path``. Nothing AEC owns is mocked.
"""
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import aec.commands.org as org_cmd
from aec.cli import app
from aec.lib.org_config import git_source
from aec.lib.org_config.errors import OrgConfigFetchError, OrgConfigValidationError
from aec.lib.org_config.parser import parse_org_config_text
from aec.lib.org_config.paths import OrgPaths
from aec.lib.org_config.state import read_state
from aec.lib.org_config.validator import validate_org_config

runner = CliRunner()

CONFIG_URL = "https://git.example.test/example-org/org-config.git"
SOURCE_URL = "https://git.example.test/example-org/team-catalog.git"

CONFIG = """---
schema_version: "1.0"
org_id: "example-org"
org_name: "Example Org"
config_version: "{version}"
trust:
  mode: "{trust_mode}"
{trust_extra}---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom:
    - id: "team-rules"
      url: "{url}"
{pin}      contributes: ["rules"]

install:
  mode: "managed"

items:
  skills: {{}}
  rules:
    "example-rule":
      source: "team-rules"
      stance: required
  agents: {{}}
  mcps: {{}}
"""

RULE = """---
name: example-rule
version: "{version}"
description: An example rule
---

# Example rule {version}
"""


def _config(*, pin, version="1.0.0", trust_mode="unsigned", trust_extra="", url=SOURCE_URL):
    return CONFIG.format(
        version=version, trust_mode=trust_mode, trust_extra=trust_extra, url=url, pin=pin
    )


def _validate(text):
    frontmatter, body = parse_org_config_text(text)
    return validate_org_config(frontmatter, body)


def _git(*args, cwd=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(work: Path, rel: str, content: str) -> str:
    path = work / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git("add", "-A", cwd=work)
    _git("commit", "-q", "-m", "update", cwd=work)
    _git("push", "-q", "--force", "origin", "HEAD:main", cwd=work)
    return _git("rev-parse", "HEAD", cwd=work)


@pytest.fixture
def repos(tmp_path, monkeypatch):
    """Two bare repos (org config, team catalog) behind https URLs; returns work clones."""
    lines = ["[user]\n\tname = Test\n\temail = test@example.test\n", '[protocol "file"]\n\tallow = always\n']
    works = {}
    for key, url in (("config", CONFIG_URL), ("source", SOURCE_URL)):
        bare = tmp_path / f"{key}.git"
        _git("init", "-q", "--bare", "-b", "main", str(bare))
        lines.append(f'[url "{bare.as_uri()}"]\n\tinsteadOf = {url}\n')
        works[key] = tmp_path / f"{key}-work"
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("".join(lines), encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, url in (("config", CONFIG_URL), ("source", SOURCE_URL)):
        _git("init", "-q", "-b", "main", str(works[key]))
        _git("remote", "add", "origin", str(tmp_path / f"{key}.git"), cwd=works[key])
    return works


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setattr(Path, "home", lambda: h)
    monkeypatch.setenv("HOME", str(h))
    return h


@pytest.fixture
def paths(home):
    return OrgPaths(home_dir=home)


def _enroll_local(tmp_path, text):
    src = tmp_path / "example-org.yaml"
    src.write_text(text, encoding="utf-8")
    result = runner.invoke(app, ["org", "enroll", str(src), "--allow-unsigned", "--yes"])
    assert result.exit_code == 0, result.output


def _manifest(home):
    return json.loads((home / ".agents-environment-config" / "installed-manifest.json").read_text())


def _push_rule(repos, version):
    return _commit(repos["source"], ".agent-rules/team/example-rule.md", RULE.format(version=version))


# --------------------------------------------------------------------------- #
#  validation                                                                  #
# --------------------------------------------------------------------------- #

SHA = "a" * 40


def test_commit_pin_makes_ref_optional():
    cfg = _validate(_config(pin=f'      commit: "{SHA}"\n'))
    (cs,) = cfg.custom_sources
    assert (cs.ref, cs.commit) == (None, SHA)


def test_ref_only_source_accepted_in_unsigned_org():
    cfg = _validate(_config(pin='      ref: "main"\n'))
    assert cfg.custom_sources[0].ref == "main"


@pytest.mark.parametrize(
    "pin, message",
    [
        ("", "ref or commit"),
        ('      commit: "abc123"\n', "40"),
        ('      ref: "--upload-pack=x"\n', "ref"),
    ],
)
def test_bad_pins_rejected(pin, message):
    with pytest.raises(OrgConfigValidationError, match=message):
        _validate(_config(pin=pin))


def test_source_url_validated():
    with pytest.raises(OrgConfigValidationError, match="url"):
        _validate(_config(pin='      ref: "main"\n', url="file:///tmp/x"))


def test_signed_org_requires_commit_pin():
    with pytest.raises(OrgConfigValidationError, match="commit"):
        _validate(
            _config(
                pin='      ref: "main"\n',
                trust_mode="pinned_key",
                trust_extra='  pubkey: "AAAA"\n',
            )
        )


def test_item_type_must_be_contributed_by_its_source():
    text = _config(pin='      ref: "main"\n').replace('contributes: ["rules"]', 'contributes: ["skills"]')
    with pytest.raises(OrgConfigValidationError, match="contribute"):
        _validate(text)


def test_reserved_source_id_rejected():
    text = _config(pin='      ref: "main"\n').replace('"team-rules"', '"aec.default.rules"')
    with pytest.raises(OrgConfigValidationError, match="reserved"):
        _validate(text)


def test_signed_org_without_commit_exits_validation_at_enroll(home, tmp_path):
    src = tmp_path / "example-org.yaml"
    src.write_text(
        _config(pin='      ref: "main"\n', trust_mode="pinned_key", trust_extra='  pubkey: "AAAA"\n'),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["org", "enroll", str(src), "--yes"])
    assert result.exit_code == org_cmd.EXIT_VALIDATION, result.output


# --------------------------------------------------------------------------- #
#  pinned fetch                                                                #
# --------------------------------------------------------------------------- #


def test_sync_source_installs_the_pin_not_the_ref_tip(repos, tmp_path):
    a = _push_rule(repos, "1.0.0")
    b = _push_rule(repos, "2.0.0")
    dest = tmp_path / "clone"
    assert git_source.sync_source(SOURCE_URL, "main", a, dest) == a
    assert "1.0.0" in (dest / ".agent-rules/team/example-rule.md").read_text()
    # Ref-only follows the tip; the same clone dir is reused.
    assert git_source.sync_source(SOURCE_URL, "main", None, dest) == b
    assert git_source.remote_commit(SOURCE_URL, "main") == b


def test_sync_source_names_an_unserved_pin(repos, tmp_path):
    _push_rule(repos, "1.0.0")
    with pytest.raises(OrgConfigFetchError, match="pinned commit"):
        git_source.sync_source(SOURCE_URL, None, "0" * 40, tmp_path / "clone")


# --------------------------------------------------------------------------- #
#  apply                                                                       #
# --------------------------------------------------------------------------- #


def test_apply_installs_from_custom_source_with_provenance(repos, home, paths, tmp_path):
    a = _push_rule(repos, "1.0.0")
    _push_rule(repos, "2.0.0")  # the ref moved past the pin
    _enroll_local(tmp_path, _config(pin=f'      commit: "{a}"\n'))

    result = runner.invoke(app, ["org", "apply", "--yes"])
    assert result.exit_code == 0, result.output

    record = _manifest(home)["global"]["rules"]["example-rule"]
    assert record["version"] == "1.0.0"
    assert record["source"] == "example-org/team-rules"
    clone = paths.org_dir_for("example-org") / "sources" / "team-rules"
    assert _git("rev-parse", "HEAD", cwd=clone) == a
    installed = list((home / ".agent-tools" / "rules").rglob("example-rule*"))
    assert installed and "Example rule 1.0.0" in installed[0].read_text()
    assert read_state(paths, "example-org").source_commits == {"team-rules": a}


def test_unserved_pin_applies_nothing(repos, home, paths, tmp_path):
    _push_rule(repos, "1.0.0")
    _enroll_local(tmp_path, _config(pin=f'      commit: "{"0" * 40}"\n'))

    result = runner.invoke(app, ["org", "apply", "--yes"])
    assert result.exit_code != 0
    assert "team-rules" in result.output and "pinned commit" in result.output
    manifest_file = home / ".agents-environment-config" / "installed-manifest.json"
    assert not manifest_file.exists() or "example-rule" not in _manifest(home)["global"]["rules"]
    assert not (home / ".agent-tools" / "rules").exists() or not list(
        (home / ".agent-tools" / "rules").rglob("example-rule*")
    )


def test_outdated_and_upgrade_resolve_against_the_items_source(repos, home, paths, tmp_path):
    a = _push_rule(repos, "1.0.0")
    _enroll_local(tmp_path, _config(pin=f'      commit: "{a}"\n'))
    assert runner.invoke(app, ["org", "apply", "--yes"]).exit_code == 0

    # The source clone moves to a newer version (as a later apply/refresh would).
    b = _push_rule(repos, "1.1.0")
    git_source.sync_source(SOURCE_URL, None, b, paths.org_dir_for("example-org") / "sources" / "team-rules")

    out = runner.invoke(app, ["outdated"])
    assert out.exit_code == 0, out.output
    assert "example-rule" in out.output and "1.1.0" in out.output

    up = runner.invoke(app, ["upgrade", "--yes"])
    assert up.exit_code == 0, up.output
    record = _manifest(home)["global"]["rules"]["example-rule"]
    assert record["version"] == "1.1.0"
    assert record["source"] == "example-org/team-rules"


# --------------------------------------------------------------------------- #
#  refresh: a ref-only source that moves goes to review                        #
# --------------------------------------------------------------------------- #


def test_moved_ref_only_source_goes_to_pending_review(repos, home, paths):
    a = _push_rule(repos, "1.0.0")
    _commit(repos["config"], "org/example-org.yaml", _config(pin='      ref: "main"\n'))
    result = runner.invoke(
        app,
        ["org", "enroll", f"git+{CONFIG_URL}#main:org/example-org.yaml", "--allow-unsigned", "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["org", "apply", "--yes"]).exit_code == 0
    assert read_state(paths, "example-org").source_commits == {"team-rules": a}

    # Unchanged YAML and unchanged source: nothing to review.
    assert org_cmd.refresh_remote_orgs(paths) == [("example-org", "unchanged")]

    b = _push_rule(repos, "1.1.0")
    assert org_cmd.refresh_remote_orgs(paths) == [("example-org", "pending review")]
    pending = read_state(paths, "example-org").pending
    assert pending["kind"] == "review" and pending["sources"] == {"team-rules": b}
    # Not installed until reviewed.
    assert _manifest(home)["global"]["rules"]["example-rule"]["version"] == "1.0.0"

    result = runner.invoke(app, ["org", "apply", "--yes"])
    assert result.exit_code == 0, result.output
    st = read_state(paths, "example-org")
    assert st.pending is None and st.source_commits == {"team-rules": b}
    assert _manifest(home)["global"]["rules"]["example-rule"]["version"] == "1.1.0"


def test_signed_org_source_without_commit_is_verify_failed_at_refresh(repos, home, paths):
    """A refresh that fetches a signed config whose source lost its pin never applies it."""
    _commit(repos["config"], "org/example-org.yaml", _config(pin='      ref: "main"\n'))
    assert runner.invoke(
        app,
        ["org", "enroll", f"git+{CONFIG_URL}#main:org/example-org.yaml", "--allow-unsigned", "--yes"],
    ).exit_code == 0
    _commit(
        repos["config"],
        "org/example-org.yaml",
        _config(pin='      ref: "main"\n', version="1.1.0", trust_mode="pinned_key", trust_extra='  pubkey: "AAAA"\n'),
    )
    ((_org_id, status),) = org_cmd.refresh_remote_orgs(paths)
    assert status.startswith("verify_failed") and "commit" in status
    assert read_state(paths, "example-org").pending["kind"] == "verify_failed"
