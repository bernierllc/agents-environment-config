"""Tests for aec.lib.confine, the one check every repo writer goes through."""

from aec.lib.confine import escapes


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
