"""Guard: nothing committed to AEC contains a specific person's home directory.

AEC is installed by anyone. A path like /Users/<someone>/projects/... in a
rule, command, script or module only works on that one machine, and tells
every other user's agents to run tools that do not exist. Examples must use
placeholders (/Users/me/, /home/user/, ~/). See "Product scope" in AGENTINFO.md.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
# Every tracked file (docs and plans too: they are part of the product repo),
# except upstream content AEC vendors but does not author.
EXCLUDE = ("aec/templates/gitignore/",)  # github/gitignore submodule
PLACEHOLDERS = ("me", "you", "user", "username", "example", "name", "yourname", "runner",
                "test", "dev", "alice", "bob")
HOME_PATH = re.compile(r"/(?:Users|home)/([A-Za-z][\w.-]*)/")


def _shipped_files():
    # -z keeps filenames with spaces intact.
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout.split("\0")
    return [f for f in out if f and not f.startswith(EXCLUDE) and (REPO / f).is_file()]


def test_scanner_finds_shipped_files():
    assert len(_shipped_files()) > 100


def test_no_personal_home_paths_in_tracked_files():
    hits = []
    for rel in _shipped_files():
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in HOME_PATH.finditer(line):
                if m.group(1).lower() not in PLACEHOLDERS:
                    hits.append(f"{rel}:{n}: {m.group(0)}")
    assert not hits, "personal home paths in tracked files:\n" + "\n".join(hits[:40])


# Example project directories must be placeholders (or AEC's own public repos),
# not the names of someone's real projects.
EXAMPLE_PROJECT = re.compile(r"/Users/example/projects/([A-Za-z0-9._-]+)")
EXAMPLE_PROJECT_OK = {"my-app", "my-api", "my-project", "my-plugin", "my-repo", "my-site",
                      "my-events", "my-forms", "my-hub", "my-demo", "my-crm",
                      "agents-environment-config", "claude-skills"}


def test_example_paths_use_placeholder_project_names():
    hits = []
    for rel in _shipped_files():
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in EXAMPLE_PROJECT.finditer(line):
                if m.group(1) not in EXAMPLE_PROJECT_OK:
                    hits.append(f"{rel}:{n}: {m.group(0)}")
    assert not hits, "example paths naming real projects:\n" + "\n".join(hits[:40])
