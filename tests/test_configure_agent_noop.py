"""Rewriting an unchanged blurb must leave the file byte-identical."""

from aec.commands.configure_agent import _spliced
from aec.lib.agent_blurb.profile import expand_profile
from aec.lib.agent_blurb.render import render_block


def _block(version, profile="balanced"):
    return render_block("project", profile, expand_profile(profile), version)


def test_same_body_new_aec_version_is_not_rewritten():
    on_disk = "# mine\n\n" + _block("1.0.0")
    assert _spliced(on_disk, _block("2.0.0")) is None


def test_changed_body_is_rewritten():
    on_disk = "# mine\n\n" + _block("1.0.0", "balanced")
    out = _spliced(on_disk, _block("1.0.0", "conservative"))
    assert out is not None and "maintenance=ask" in out


def test_hand_edited_body_is_rewritten():
    on_disk = _block("1.0.0").replace("AEC", "HAND", 1)
    assert _spliced(on_disk, _block("1.0.0")) is not None


def test_balanced_auto_conservative_ask_for_update():
    assert "`aec update` — update installed items (maintenance=auto)" in _block("1")
    assert "`aec update` — update installed items (maintenance=ask)" in _block("1", "conservative")
