"""Scope detection for global uninstall: which repos also have a repo install.

A repo-scoped install overrides + is owned independently of the global one,
so global uninstall must surface every repo with its own copy and never reap
them without permission.
"""

import builtins

from aec.commands.uninstall import _prompt_repo_selection
from aec.lib.uninstall_scope import find_repos_with_install, resolve_repos_flag


def _manifest(repos):
    return {"manifestVersion": 2, "global": {}, "repos": repos}


class TestFindReposWithInstall:
    def test_empty_when_no_repos(self):
        assert find_repos_with_install(_manifest({}), "skills", "x") == []

    def test_finds_repo_with_the_item(self):
        m = _manifest({
            "/a": {"skills": {"x": {}}, "rules": {}, "agents": {}, "mcps": {}},
            "/b": {"skills": {"y": {}}, "rules": {}, "agents": {}, "mcps": {}},
        })
        assert find_repos_with_install(m, "skills", "x") == ["/a"]

    def test_sorted_when_multiple(self):
        m = _manifest({
            "/b": {"skills": {"x": {}}},
            "/a": {"skills": {"x": {}}},
        })
        assert find_repos_with_install(m, "skills", "x") == ["/a", "/b"]

    def test_ignores_other_item_types(self):
        m = _manifest({"/a": {"skills": {}, "agents": {"x": {}}}})
        assert find_repos_with_install(m, "skills", "x") == []


class TestResolveReposFlag:
    candidates = ["/a", "/b", "/c"]

    def test_none_selects_nothing(self):
        assert resolve_repos_flag(None, self.candidates) == []

    def test_none_word_selects_nothing(self):
        assert resolve_repos_flag("none", self.candidates) == []

    def test_all_selects_every_candidate(self):
        assert resolve_repos_flag("all", self.candidates) == ["/a", "/b", "/c"]

    def test_explicit_paths_intersect_candidates(self):
        assert resolve_repos_flag("/a,/c", self.candidates) == ["/a", "/c"]

    def test_unknown_paths_dropped(self):
        assert resolve_repos_flag("/a,/zzz", self.candidates) == ["/a"]


class TestPromptRepoSelection:
    def _answers(self, monkeypatch, replies):
        it = iter(replies)
        monkeypatch.setattr(builtins, "input", lambda *_: next(it))

    def test_all_selects_every_repo(self, monkeypatch):
        self._answers(monkeypatch, ["a"])
        assert _prompt_repo_selection("skill", "x", ["/a", "/b"]) == ["/a", "/b"]

    def test_default_only_global(self, monkeypatch):
        self._answers(monkeypatch, ["g"])
        assert _prompt_repo_selection("skill", "x", ["/a", "/b"]) == []

    def test_each_asks_per_repo(self, monkeypatch):
        self._answers(monkeypatch, ["e", "y", "n"])
        assert _prompt_repo_selection("skill", "x", ["/a", "/b"]) == ["/a"]

    def test_show_then_choose(self, monkeypatch):
        self._answers(monkeypatch, ["s", "a"])
        assert _prompt_repo_selection("skill", "x", ["/a"]) == ["/a"]
