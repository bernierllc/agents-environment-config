"""Guard: nothing committed to AEC contains a specific person's paths or projects.

AEC is installed by anyone. A path like /Users/<someone>/projects/... in a
rule, command, script or module only works on that one machine, and tells
every other user's agents to run tools that do not exist. Examples must use
placeholders (/Users/me/, /home/user/, ~/projects/my-app). See "Product scope"
in AGENTINFO.md.

This is a heuristic, not a proof: it catches home-directory paths and the
project names under them. Personal names written without a path still need
review.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Every tracked file (docs and plans too: they are part of the product repo),
# except upstream content AEC vendors but does not author.
EXCLUDE = (
    "aec/templates/gitignore/",               # github/gitignore submodule
    "tests/test_no_maintainer_specifics.py",  # holds deliberately bad examples
)
PLACEHOLDERS = ("me", "you", "user", "username", "example", "name", "yourname", "runner",
                "test", "dev", "alice", "bob", "carol")
# Example project directories must be placeholders (or AEC-related public
# repos), not the names of someone's real projects.
PROJECT_PLACEHOLDERS = {
    "my-app", "my-api", "my-project", "my-plugin", "my-repo", "my-site", "my-events",
    "my-forms", "my-hub", "my-demo", "my-crm", "dashboard", "api-server", "mobile-app",
    "new-project", "test", "foo",
    "agents-environment-config", "claude-skills", "loadout",
}

SEP = r"[\\/]+"  # one or more separators: also matches escaped "\\" in source strings
HOME_PATH = re.compile(
    # /Users/<u>/, /home/<u>/, C:\Users\<u>\, C:/Users/<u>/ ...
    r"(?:(?:/(?:Users|home)/|\b[A-Za-z]:" + SEP + r"Users" + SEP + r")"
    # the username ends at a separator or at the end of the path
    r"(?P<user>[A-Za-z][\w.-]*)(?:" + SEP + r"|(?![\w.-]))"
    # ... or ~/
    r"|(?<![\w.])~" + SEP + r")"
    # ... optionally followed by <project root>/<name>, any case (AEC's
    # Windows default is ~/Projects)
    r"(?:(?i:projects|src|code|repos|dev|workspace|git|github)" + SEP + r"(?P<project>[A-Za-z0-9._-]+))?"
)


def _flagged(match) -> str:
    user, project = match.group("user"), match.group("project")
    if user and user.lower() not in PLACEHOLDERS:
        return "personal home"
    if project and project not in PROJECT_PLACEHOLDERS:
        return "real project name"
    return ""


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
                why = _flagged(m)
                if why:
                    hits.append(f"{rel}:{n}: {why} {m.group(0)}")
    return hits


def test_scanner_finds_shipped_files():
    assert len(_shipped_files()) > 100


def test_no_personal_paths_or_project_names_in_tracked_files():
    hits = _findings()
    assert not hits, "maintainer-specific paths in tracked files:\n" + "\n".join(hits[:40])


BAD = [
    "/Users/realname/x/", "/home/realname/x/", "C:/Users/realname/x/",
    r"C:\Users\realname\x", r"C:\\Users\\realname\\x",
    "/Users/me/projects/secret-app/", "/home/user/projects/secret-app/",
    r"D:\Users\user\projects\secret-app", r"C:\Users\user\Projects\secret-app",
    "~/projects/secret-app", "~/Projects/secret-app",
    "/Users/realname", "/home/realname", r"C:\Users\realname", "cd /Users/realname && ls",
    "/Users/me/src/secret-app", "/home/user/code/secret-app", r"C:\Users\user\Repos\secret-app",
]
OK = [
    "/Users/me/projects/my-app/", "/home/user/", r"C:\Users\example\projects\my-api",
    r"C:\Users\user\Projects\my-app", "~/projects/my-app", "~/.claude/skills", "a~/b",
]


def test_pattern_covers_every_home_form():
    def flagged(text):
        return any(_flagged(m) for m in HOME_PATH.finditer(text))

    assert [t for t in BAD if not flagged(t)] == []
    assert [t for t in OK if flagged(t)] == []
