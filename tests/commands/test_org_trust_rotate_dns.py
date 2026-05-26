"""Command-level tests for dns_anchor enrollment and trust-rotate (Phase 2b).

The well-known pubkey fetch is monkeypatched (``org._pubkey_fetcher``) so the
tests never touch the network. The served key lives in a mutable holder so a
rotation can be simulated mid-test.
"""

import base64
import dataclasses
from pathlib import Path

import pytest

nacl_signing = pytest.importorskip("nacl.signing")
import typer  # noqa: E402

import aec.commands.org as org_cmd  # noqa: E402
from aec.commands.org import enroll_cmd, status_cmd, trust_rotate_cmd  # noqa: E402
from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.paths import OrgPaths  # noqa: E402
from aec.lib.org_config.state import read_state, write_state  # noqa: E402

CONFIG_TEXT = """---
schema_version: "1.0"
org_id: "acme"
org_name: "Acme"
config_version: "1.0.0"
trust:
  mode: "dns_anchor"
  dns_domain: "acme.example"
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


def _write_signed_config(directory: Path, signing_key) -> Path:
    cfg = directory / "acme.yaml"
    cfg.write_text(CONFIG_TEXT, encoding="utf-8")
    sig = signing_key.sign(CONFIG_TEXT.encode("utf-8")).signature
    cfg.with_name("acme.yaml.sig").write_bytes(sig)
    return cfg


def _install_fetcher(monkeypatch, holder):
    def fake_fetcher(url):
        assert url == "https://acme.example/.well-known/aec-pubkey"
        return base64.b64encode(bytes(holder["key"].verify_key))

    monkeypatch.setattr(org_cmd, "_pubkey_fetcher", fake_fetcher)


def test_enroll_dns_anchor_succeeds_and_pins_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    _install_fetcher(monkeypatch, {"key": key})
    cfg = _write_signed_config(tmp_path, key)

    enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)

    state = read_state(OrgPaths(home_dir=tmp_path), "acme")
    assert state is not None
    assert state.trust_mode == "dns_anchor"
    assert state.pubkey_source == "dns_anchor"
    assert state.pubkey_fingerprint == fingerprint(bytes(key.verify_key))


def test_enroll_dns_anchor_tampered_config_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    _install_fetcher(monkeypatch, {"key": key})
    cfg = _write_signed_config(tmp_path, key)
    cfg.write_text(cfg.read_text() + "# tampered\n", encoding="utf-8")

    with pytest.raises(typer.Exit) as exc:
        enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)
    assert exc.value.exit_code == 10


def test_enroll_dns_anchor_missing_signature_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    _install_fetcher(monkeypatch, {"key": key})
    cfg = _write_signed_config(tmp_path, key)
    cfg.with_name("acme.yaml.sig").unlink()

    with pytest.raises(typer.Exit) as exc:
        enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)
    assert exc.value.exit_code == 10


def test_reenroll_with_rotated_domain_key_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key1 = nacl_signing.SigningKey.generate()
    holder = {"key": key1}
    _install_fetcher(monkeypatch, holder)
    cfg = _write_signed_config(tmp_path, key1)
    enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)

    # Domain now publishes a different key (and the sidecar is re-signed by it),
    # but the change was not acknowledged via trust-rotate -> blocked.
    key2 = nacl_signing.SigningKey.generate()
    holder["key"] = key2
    cfg.with_name("acme.yaml.sig").write_bytes(key2.sign(CONFIG_TEXT.encode("utf-8")).signature)

    with pytest.raises(typer.Exit) as exc:
        enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)
    assert exc.value.exit_code == 10


def test_trust_rotate_dns_updates_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key1 = nacl_signing.SigningKey.generate()
    holder = {"key": key1}
    _install_fetcher(monkeypatch, holder)
    cfg = _write_signed_config(tmp_path, key1)
    enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)

    # Rotate: domain serves key2, enrolled sidecar re-signed by key2. trust-rotate
    # reads the config + sidecar from the orgs dir, not the original source path.
    key2 = nacl_signing.SigningKey.generate()
    holder["key"] = key2
    paths = OrgPaths(home_dir=tmp_path)
    paths.config_for("acme").with_name("acme.yaml.sig").write_bytes(
        key2.sign(CONFIG_TEXT.encode("utf-8")).signature
    )

    trust_rotate_cmd(org_id="acme", signature=None, yes=True)

    state = read_state(paths, "acme")
    assert state.pubkey_fingerprint == fingerprint(bytes(key2.verify_key))
    assert state.pubkey_source == "dns_anchor"


def test_status_surfaces_locked_rotation(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    _install_fetcher(monkeypatch, {"key": key})
    cfg = _write_signed_config(tmp_path, key)
    enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)

    paths = OrgPaths(home_dir=tmp_path)
    st = read_state(paths, "acme")
    write_state(
        paths,
        dataclasses.replace(
            st,
            key_rotation_pending={
                "detected_at": "2026-01-01T00:00:00Z",
                "new_fingerprint": "SHA256:newkey",
                "old_fingerprint": st.pubkey_fingerprint,
            },
        ),
    )

    status_cmd(org_id="acme")
    out = capsys.readouterr().out
    assert "LOCKED" in out
