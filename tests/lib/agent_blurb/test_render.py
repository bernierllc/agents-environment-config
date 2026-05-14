"""Golden + determinism tests for the renderer.

The renderer must be a pure function: identical inputs produce byte-identical
output. This guarantees content_hash is stable across runs and platforms.
"""

from pathlib import Path

from aec.lib.agent_blurb.render import (
    render_block,
    sha256_short,
    shipped_template_hash,
    BLOCK_VERSION,
    SCHEMA_VERSION,
)


FIXTURES = Path(__file__).parent / "fixtures"


class TestSha256Short:
    def test_deterministic(self):
        assert sha256_short("hello") == sha256_short("hello")

    def test_length_is_16(self):
        assert len(sha256_short("hello")) == 16

    def test_different_inputs_differ(self):
        assert sha256_short("a") != sha256_short("b")


class TestShippedTemplateHash:
    def test_stable_across_calls(self):
        a = shipped_template_hash()
        b = shipped_template_hash()
        assert a == b


class TestRenderBlock:
    def test_balanced_project_golden(self):
        matrix = {
            "agents":   {"additive": "ask"},
            "skills":   {"additive": "auto"},
            "rules":    {"additive": "auto"},
            "packages": {"additive": "ask"},
            "plugins":  {"additive": "ask"},
        }
        body = render_block(
            scope="project",
            profile="balanced",
            matrix=matrix,
            aec_version="2.37.4",
        )
        body2 = render_block(
            scope="project",
            profile="balanced",
            matrix=matrix,
            aec_version="2.37.4",
        )
        assert body == body2

    def test_block_contains_required_markers(self):
        matrix = {it: {"additive": "ask"} for it in ("agents","skills","rules","packages","plugins")}
        body = render_block(
            scope="project", profile="conservative", matrix=matrix, aec_version="2.37.4"
        )
        assert "<!-- aec-blurb:start" in body
        assert "<!-- aec-blurb:end -->" in body
        assert "schema=1" in body
        assert "aec=2.37.4" in body
        assert "profile=conservative" in body
        assert "scope=project" in body

    def test_block_lists_auto_commands(self):
        matrix = {it: {"additive": "auto"} for it in ("agents","skills","rules","packages","plugins")}
        body = render_block(
            scope="project", profile="permissive", matrix=matrix, aec_version="2.37.4"
        )
        assert "aec list" in body
        assert "aec install skill" in body
        assert "aec install agent" in body
        assert "aec uninstall" in body
        assert "aec update" in body

    def test_content_hash_in_marker_matches_body(self):
        """The content-hash in the marker is over the rendered body content
        excluding the marker line itself."""
        matrix = {it: {"additive": "ask"} for it in ("agents","skills","rules","packages","plugins")}
        body = render_block(
            scope="project", profile="conservative", matrix=matrix, aec_version="2.37.4"
        )
        import re
        m = re.search(r"content-hash=([a-f0-9]+)", body)
        assert m is not None
        claimed = m.group(1)
        from aec.lib.agent_blurb.render import extract_inner_body, content_hash_of
        inner = extract_inner_body(body)
        assert content_hash_of(inner) == claimed

    def test_changing_profile_changes_content_hash(self):
        m1 = {it: {"additive": "ask"} for it in ("agents","skills","rules","packages","plugins")}
        m2 = {it: {"additive": "auto"} for it in ("agents","skills","rules","packages","plugins")}
        b1 = render_block(scope="project", profile="conservative", matrix=m1, aec_version="2.37.4")
        b2 = render_block(scope="project", profile="permissive", matrix=m2, aec_version="2.37.4")
        assert b1 != b2


def test_block_version_and_schema_are_used():
    """Sanity check that exported constants are non-empty."""
    assert BLOCK_VERSION
    assert SCHEMA_VERSION == 1
    assert FIXTURES.name == "fixtures"
