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
EXCLUDE = (
    "aec/templates/gitignore/",               # github/gitignore submodule
    "tests/test_no_maintainer_specifics.py",  # holds deliberately bad examples
)
PLACEHOLDERS = ("me", "you", "user", "username", "example", "name", "yourname", "runner",
                "test", "dev", "alice", "bob", "carol")
# Example project directories must be placeholders (or AEC's own public repos),
# not the names of someone's real projects.
PROJECT_PLACEHOLDERS = {"my-app", "my-api", "my-project", "my-plugin", "my-repo", "my-site",
                        "my-events", "my-forms", "my-hub", "my-demo", "my-crm",
                        "agents-environment-config", "claude-skills"}

# A home directory on macOS/Linux (/Users/<u>/, /home/<u>/) or Windows
# (C:\Users\<u>\ or C:/Users/<u>/), optionally followed by projects/<name>.
HOME_PATH = re.compile(
    # [\\/]+ also matches escaped backslashes inside source strings ("C:\\\\Users").
    r"(?:/(?:Users|home)/|\b[A-Za-z]:[\\/]+Users[\\/]+)"
    r"(?P<user>[A-Za-z][\w.-]*)[\\/]+"
    r"(?:projects[\\/]+(?P<project>[A-Za-z0-9._-]+))?"
)


def _shipped_files():
    # -z keeps filenames with spaces intact.
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout.split("\0")
    return [f for f in out if f and not f.startswith(EXCLUDE) and (REPO / f).is_file()]


def _findings():
    hits = []
    for rel in _shipped_files():
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in HOME_PATH.finditer(line):
                if m.group("user").lower() not in PLACEHOLDERS:
                    hits.append(f"{rel}:{n}: personal home {m.group(0)}")
                elif m.group("project") and m.group("project") not in PROJECT_PLACEHOLDERS:
                    hits.append(f"{rel}:{n}: real project name {m.group(0)}")
    return hits


def test_scanner_finds_shipped_files():
    assert len(_shipped_files()) > 100


def test_no_personal_paths_or_project_names_in_tracked_files():
    hits = _findings()
    assert not hits, "maintainer-specific paths in tracked files:\n" + "\n".join(hits[:40])


def test_pattern_covers_every_home_form():
    bad = ["/Users/realname/x/", "/home/realname/x/", "C:\\Users\\realname\\x",
           "C:\\\\Users\\\\realname\\\\x",
           "C:/Users/realname/x/", "/Users/me/projects/secret-app/", "/home/user/projects/secret-app/",
           "D:\\Users\\user\\projects\\secret-app"]
    ok = ["/Users/me/projects/my-app/", "/home/user/", "C:\\Users\\example\\projects\\my-api"]
    def flagged(t):
        return any(m.group("user").lower() not in PLACEHOLDERS
                   or (m.group("project") and m.group("project") not in PROJECT_PLACEHOLDERS)
                   for m in HOME_PATH.finditer(t))
    assert all(flagged(t) for t in bad), [t for t in bad if not flagged(t)]
    assert not any(flagged(t) for t in ok), [t for t in ok if flagged(t)]
