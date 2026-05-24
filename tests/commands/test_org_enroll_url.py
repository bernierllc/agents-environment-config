"""Command-level tests for enrolling org configs from https URLs (Phase 2c).

The remote fetch is monkeypatched (``org._url_fetcher``) so nothing touches
the network.
"""

import base64
from pathlib import Path

import pytest

nacl_signing = pytest.importorskip("nacl.signing")
import typer  # noqa: E402

import aec.commands.org as org_cmd  # noqa: E402
from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.errors import OrgConfigFetchError  # noqa: E402
from aec.lib.org_config.paths import OrgPaths  # noqa: E402
from aec.lib.org_config.state import read_state  # noqa: E402

UNSIGNED = """---
schema_version: "1.0"
org_id: "acme"
org_name: "Acme"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: { skills: keep, rules: keep, agents: keep, mcps: keep }
  custom: []

items:
  skills: {}
  rules: {}
  agents: {}
  mcps: {}
"""

PINNED_TEMPLATE = """---
schema_version: "1.0"
org_id: "acme"
org_name: "Acme"
config_version: "1.0.0"
trust:
  mode: "pinned_key"
  pubkey: "{pubkey}"
---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom: []

items:
  skills: {{}}
  rules: {{}}
  agents: {{}}
  mcps: {{}}
"""


def _make_fetcher(mapping):
    def fetcher(url):
        if url not in mapping:
            raise OrgConfigFetchError(f"404 {url}")
        return mapping[url]

    return fetcher


def test_enroll_unsigned_from_url(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    url = "https://acme.example/acme.yaml"
    monkeypatch.setattr(org_cmd, "_url_fetcher", _make_fetcher({url: UNSIGNED.encode()}))

    org_cmd.perform_enroll(url, allow_unsigned=True)

    state = read_state(OrgPaths(home_dir=tmp_path), "acme")
    assert state is not None
    assert state.source_of_record == "url"
    assert state.source_url == url


def test_enroll_pinned_key_from_url_with_sig_sibling(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    pubkey_b64 = base64.b64encode(bytes(key.verify_key)).decode()
    cfg_text = PINNED_TEMPLATE.format(pubkey=pubkey_b64)
    sig = key.sign(cfg_text.encode("utf-8")).signature
    url = "https://acme.example/acme.yaml"
    monkeypatch.setattr(
        org_cmd,
        "_url_fetcher",
        _make_fetcher({url: cfg_text.encode("utf-8"), url + ".sig": sig}),
    )

    org_cmd.perform_enroll(url, trust_fingerprint=True)

    state = read_state(OrgPaths(home_dir=tmp_path), "acme")
    assert state.source_of_record == "url"
    assert state.pubkey_fingerprint == fingerprint(bytes(key.verify_key))


def test_enroll_unsigned_url_without_allow_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    url = "https://acme.example/acme.yaml"
    monkeypatch.setattr(org_cmd, "_url_fetcher", _make_fetcher({url: UNSIGNED.encode()}))
    monkeypatch.setattr(typer, "confirm", lambda *a, **k: False)

    with pytest.raises(typer.Exit) as exc:
        org_cmd.perform_enroll(url, allow_unsigned=False)
    assert exc.value.exit_code == 10


def test_enroll_rejects_non_https_url(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with pytest.raises(typer.Exit) as exc:
        org_cmd.perform_enroll("http://acme.example/acme.yaml")
    assert exc.value.exit_code == 13


def test_enroll_url_fetch_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(org_cmd, "_url_fetcher", _make_fetcher({}))  # any URL 404s
    with pytest.raises(typer.Exit) as exc:
        org_cmd.perform_enroll("https://acme.example/missing.yaml", allow_unsigned=True)
    assert exc.value.exit_code == 13
