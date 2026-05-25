"""A blocked MCP is fully torn down: settings.json entry + manifest record."""

from pathlib import Path

from aec.lib.manifest_v2 import get_installed, load_manifest, record_mcp_install, save_manifest
from aec.lib.mcp_settings import get_settings_path, read_mcp_servers, write_mcp_server
from aec.lib.org_config.apply import apply_items
from aec.lib.org_config.effective import EffectivePolicy
from aec.lib.org_config.schema import ItemPolicy, Stance
from aec.lib.scope import Scope


def _policy(items):
    return EffectivePolicy(
        items=items,
        preferences={},
        prompts={},
        default_sources={},
        custom_sources=[],
        install_mode=None,
        held=(),
    )


def test_blocked_mcp_removed_from_settings_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aec_home = tmp_path / ".agents-environment-config"
    aec_home.mkdir()
    manifest_path = aec_home / "installed-manifest.json"

    # Pretend an MCP server is installed globally: manifest + settings.json entry.
    m = load_manifest(manifest_path)
    record_mcp_install(m, "global", "risky-mcp", "1.0.0", package="risky-pkg")
    save_manifest(m, manifest_path)

    settings_path = get_settings_path(Scope(is_global=True, repo_path=None))
    write_mcp_server(settings_path, "risky-mcp", {"command": "risky", "args": []})
    assert "risky-mcp" in read_mcp_servers(settings_path)

    pol = _policy(
        {"mcps/risky-mcp": ("acme", ItemPolicy(source="aec.default.mcps", stance=Stance("blocked")))}
    )

    _result, removed = apply_items(
        pol,
        "global",
        source_dirs={},
        available_by_type={},
        manifest_path=manifest_path,
    )

    assert removed == [("mcp", "risky-mcp")]
    # Settings entry gone...
    assert "risky-mcp" not in read_mcp_servers(settings_path)
    # ...and manifest record gone.
    assert "risky-mcp" not in get_installed(load_manifest(manifest_path), "global", "mcps")
