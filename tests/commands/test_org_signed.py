"""Command-level tests for pinned_key enrollment and trust-rotate (Phase 2a).

These call the command callbacks directly (catching ``typer.Exit``) so they
exercise the real wiring without the typer ``CliRunner`` introspection path.
"""

import base64
from pathlib import Path

import pytest

nacl_signing = pytest.importorskip("nacl.signing")
import typer  # noqa: E402

from aec.commands.org import enroll_cmd, trust_rotate_cmd  # noqa: E402
from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.paths import OrgPaths  # noqa: E402
from aec.lib.org_config.state import read_state  # noqa: E402

CONFIG_TEMPLATE = """---
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


def _write_signed_config(directory: Path, signing_key) -> Path:
    pubkey_raw = bytes(signing_key.verify_key)
    text = CONFIG_TEMPLATE.format(pubkey=base64.b64encode(pubkey_raw).decode())
    cfg = directory / "acme.yaml"
    cfg.write_text(text, encoding="utf-8")
    sig = signing_key.sign(text.encode("utf-8")).signature
    cfg.with_name("acme.yaml.sig").write_bytes(sig)
    return cfg


def test_enroll_pinned_key_succeeds_and_pins_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    cfg = _write_signed_config(tmp_path, key)

    enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)

    state = read_state(OrgPaths(home_dir=tmp_path), "acme")
    assert state is not None
    assert state.trust_mode == "pinned_key"
    assert state.pubkey_fingerprint == fingerprint(bytes(key.verify_key))


def test_enroll_pinned_key_tampered_config_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    cfg = _write_signed_config(tmp_path, key)
    # Tamper after signing: append a byte the signature does not cover.
    cfg.write_text(cfg.read_text() + "# tampered\n", encoding="utf-8")

    with pytest.raises(typer.Exit) as exc:
        enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)
    assert exc.value.exit_code == 10


def test_enroll_pinned_key_missing_signature_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = nacl_signing.SigningKey.generate()
    cfg = _write_signed_config(tmp_path, key)
    cfg.with_name("acme.yaml.sig").unlink()

    with pytest.raises(typer.Exit) as exc:
        enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)
    assert exc.value.exit_code == 10


def test_trust_rotate_updates_pinned_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key1 = nacl_signing.SigningKey.generate()
    cfg = _write_signed_config(tmp_path, key1)
    enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)

    # Org rotates to a new key: rewrite the enrolled config + signature in place.
    key2 = nacl_signing.SigningKey.generate()
    paths = OrgPaths(home_dir=tmp_path)
    enrolled = paths.config_for("acme")
    new_text = CONFIG_TEMPLATE.format(pubkey=base64.b64encode(bytes(key2.verify_key)).decode())
    enrolled.write_text(new_text, encoding="utf-8")
    paths.config_for("acme").with_name("acme.yaml.sig").write_bytes(
        key2.sign(new_text.encode("utf-8")).signature
    )

    trust_rotate_cmd(org_id="acme", signature=None, yes=True)

    state = read_state(paths, "acme")
    assert state.pubkey_fingerprint == fingerprint(bytes(key2.verify_key))


def test_enroll_pinned_key_rotation_without_ack_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key1 = nacl_signing.SigningKey.generate()
    cfg = _write_signed_config(tmp_path, key1)
    enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)

    # A different key arrives without going through trust-rotate -> blocked.
    key2 = nacl_signing.SigningKey.generate()
    new_text = CONFIG_TEMPLATE.format(pubkey=base64.b64encode(bytes(key2.verify_key)).decode())
    cfg.write_text(new_text, encoding="utf-8")
    cfg.with_name("acme.yaml.sig").write_bytes(key2.sign(new_text.encode("utf-8")).signature)

    with pytest.raises(typer.Exit) as exc:
        enroll_cmd(source=str(cfg), allow_unsigned=False, signature=None, trust_fingerprint=True, yes=True)
    assert exc.value.exit_code == 10
