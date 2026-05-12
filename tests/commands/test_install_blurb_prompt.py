"""After a successful install, AEC offers the agent-blurb feature unless declined."""


def test_install_offers_blurb_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# c\n")
    from aec.commands.install_cmd import maybe_offer_blurb
    from aec.lib.agent_blurb.config import load_config
    maybe_offer_blurb(root=tmp_path, accept=True)
    assert load_config(scope="project", root=tmp_path) is not None


def test_install_skips_blurb_when_declined(tmp_path):
    from aec.commands.install_cmd import maybe_offer_blurb
    from aec.lib.agent_blurb.decline import record_decline
    from aec.lib.agent_blurb.config import load_config
    record_decline(scope="project", aec_version="2.37.4", root=tmp_path)
    maybe_offer_blurb(root=tmp_path, accept=False)
    assert load_config(scope="project", root=tmp_path) is None
