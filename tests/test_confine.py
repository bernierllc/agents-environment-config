"""Tests for aec.lib.confine, the one check every repo writer goes through."""

import pytest

from aec.lib.confine import escapes, item_name_problem


def test_confined_paths_pass_including_ones_not_yet_created(tmp_path):
    (tmp_path / "a").mkdir()
    assert escapes(tmp_path, [tmp_path / "a" / "new.md", tmp_path / "b" / "c.md"]) == []


def test_dotdot_and_foreign_paths_are_outside(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    got = escapes(repo, [repo / ".." / "x.md", tmp_path / "y.md", repo])
    assert len(got) == 3 and all("is outside" in g for g in got)


def test_any_symlinked_component_is_refused_even_dangling(tmp_path):
    repo = tmp_path / "repo"
    (repo / "real").mkdir(parents=True)
    (repo / "dir").symlink_to(repo / "real", target_is_directory=True)  # even one pointing inside
    (repo / "gone.md").symlink_to(tmp_path / "missing.md")
    got = escapes(repo, [repo / "dir" / "f.md", repo / "gone.md"])
    assert [g.split()[-1] for g in got] == ["symlink", "symlink"]


@pytest.mark.parametrize(
    "plural, name",
    [
        ("rules", "../../x"), ("rules", "a/../../x"), ("rules", "/etc/x"), ("rules", "a//b"),
        ("rules", "a\\b"), ("rules", "."), ("rules", ".."), ("rules", ""), ("rules", "a/"),
        ("skills", "../../x"), ("skills", "a/b"), ("agents", "/etc/x"), ("mcps", "a/b"),
        ("rules", 7), ("rules", None),
    ],
)
def test_unsafe_item_names_are_rejected(plural, name):
    assert item_name_problem(plural, name) is not None


@pytest.mark.parametrize(
    "plural, name",
    [
        ("rules", "general/foo"), ("rules", "frameworks/database/connection-management"),
        ("rules", "foo"), ("skills", "secure-coding-v2"), ("agents", "reviewer"), ("mcps", "my.server_1"),
    ],
)
def test_safe_item_names_are_accepted(plural, name):
    assert item_name_problem(plural, name) is None


def _install(target, name, src, dst, tmp_path):
    from aec.commands.install_cmd import _install_single_item

    _install_single_item(
        item_type="rule", plural="rules", name=name, src=src, dst=dst, target_dir=target,
        scope_key="global", manifest_file=tmp_path / "manifest.json", item_info={"version": "1.0.0"},
    )


def test_install_refuses_a_name_that_leaves_target_dir(tmp_path):
    from aec.lib.filesystem import installed_dst_path

    target, victim = tmp_path / "rules", tmp_path / "victim.md"
    target.mkdir()
    victim.write_text("keep")
    src = tmp_path / "src.md"
    src.write_text("new")
    for name in ("../victim", "a/../../victim"):
        with pytest.raises(ValueError, match="is outside"):
            _install(target, name, src, installed_dst_path(target, name, src), tmp_path)
    assert victim.read_text() == "keep"


def test_install_refuses_a_symlinked_parent_that_escapes_target_dir(tmp_path):
    target, outside = tmp_path / "rules", tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    (outside / "victim.md").write_text("keep")
    (target / "general").symlink_to(outside, target_is_directory=True)
    src = tmp_path / "src.md"
    src.write_text("new")
    with pytest.raises(ValueError, match="symlink"):
        _install(target, "general/victim", src, target / "general" / "victim.md", tmp_path)
    assert (outside / "victim.md").read_text() == "keep"


def test_install_still_replaces_a_symlink_at_the_destination(tmp_path):
    target, elsewhere = tmp_path / "rules", tmp_path / "elsewhere.md"
    target.mkdir()
    elsewhere.write_text("not ours")
    (target / "foo.md").symlink_to(elsewhere)
    src = tmp_path / "src.md"
    src.write_text("new")
    _install(target, "foo", src, target / "foo.md", tmp_path)
    assert not (target / "foo.md").is_symlink() and (target / "foo.md").read_text() == "new"
    assert elsewhere.read_text() == "not ours"
