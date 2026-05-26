"""Tests for per-project overlay matching (Phase 4a)."""
from __future__ import annotations

from aec.lib.org_config.projects import match_project, normalize_git_remote
from aec.lib.org_config.schema import ProjectMatch, ProjectOverlay, ProjectProfile


def _overlay(*, git_remote=None, directory=None, tag="p"):
    return ProjectOverlay(
        match=ProjectMatch(git_remote=git_remote, directory=directory),
        profile=ProjectProfile(items={"_tag": tag}, prompts={}),
    )


class TestNormalizeGitRemote:
    def test_scp_form(self):
        assert normalize_git_remote("git@github.com:acme/backend.git") == "github.com:acme/backend"

    def test_https_form_matches_scp(self):
        assert normalize_git_remote("https://github.com/acme/backend.git") == "github.com:acme/backend"

    def test_https_without_dot_git(self):
        assert normalize_git_remote("https://github.com/acme/backend") == "github.com:acme/backend"

    def test_ssh_url_form(self):
        assert normalize_git_remote("ssh://git@github.com/acme/backend.git") == "github.com:acme/backend"

    def test_trailing_slash_stripped(self):
        assert normalize_git_remote("https://github.com/acme/backend/") == "github.com:acme/backend"


class TestMatchProject:
    def test_no_overlays_returns_none(self):
        assert match_project([], repo_path="/x", git_remote="git@github.com:acme/x.git") is None

    def test_exact_remote_match(self):
        overlays = [_overlay(git_remote="github.com:acme/backend", tag="hit")]
        prof = match_project(overlays, repo_path="/x", git_remote="git@github.com:acme/backend.git")
        assert prof is not None and prof.items["_tag"] == "hit"

    def test_remote_glob_match(self):
        overlays = [_overlay(git_remote="github.com:acme/*", tag="hit")]
        prof = match_project(overlays, repo_path="/x", git_remote="https://github.com/acme/backend")
        assert prof is not None and prof.items["_tag"] == "hit"

    def test_remote_no_match_returns_none(self):
        overlays = [_overlay(git_remote="github.com:other/*")]
        assert match_project(overlays, repo_path="/x", git_remote="git@github.com:acme/x.git") is None

    def test_first_match_wins(self):
        overlays = [
            _overlay(git_remote="github.com:acme/*", tag="first"),
            _overlay(git_remote="github.com:acme/backend", tag="second"),
        ]
        prof = match_project(overlays, repo_path="/x", git_remote="git@github.com:acme/backend.git")
        assert prof.items["_tag"] == "first"

    def test_directory_glob_match(self):
        overlays = [_overlay(directory="~/work/acme/*", tag="dir")]
        prof = match_project(overlays, repo_path="~/work/acme/backend", git_remote=None)
        assert prof is not None and prof.items["_tag"] == "dir"

    def test_directory_no_match(self):
        overlays = [_overlay(directory="~/work/other/*")]
        assert match_project(overlays, repo_path="~/work/acme/backend", git_remote=None) is None

    def test_git_remote_preferred_but_directory_is_fallback(self):
        # Overlay specifies both; remote is unknown here, so directory decides.
        overlays = [_overlay(git_remote="github.com:acme/*", directory="~/work/acme/*", tag="both")]
        prof = match_project(overlays, repo_path="~/work/acme/backend", git_remote=None)
        assert prof is not None and prof.items["_tag"] == "both"
