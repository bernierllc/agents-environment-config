"""Trusted replay of merge-with-main promote slices, on real git graphs served by a local bare remote.

replay-promote-slice.py (plan 2026-11-21-mvs-trusted-slice-replay, R2) replays git's own merge of a slice's
authorized parents, regenerates the declared outputs with the BASE's generator, and requires the head's tree.
check-main-source.sh (R3) admits a slice only when that holds and main's rules require up-to-date branches. The
network boundaries are the git remote, a real bare repo here, and the GitHub API, a stub `gh` that serves main's
rules; the generator is a real Node script run by the replay. Nothing we own is stubbed.
"""
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPLAY = ROOT / "scripts" / "replay-promote-slice.py"
GUARD = ROOT / "scripts" / "check-main-source.sh"
SLICE = "promote/2026-11-22-1"
CONFIG = json.dumps({"generator": {"entry": "gen/build.mjs", "outputs": ["out"]}})
# Reads docs/*.md from its working tree (git ls-files, so the replay's git env must work) and writes
# out/manifest.json, stamped with its run time like the downstream generator.
BUILD = """import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { item } from './lib.mjs';
const docs = execFileSync('git', ['ls-files', 'docs'], { encoding: 'utf8' }).split('\\n').filter(Boolean).sort();
const items = docs.map((d) => item(d, readFileSync(d, 'utf8')));
mkdirSync('out', { recursive: true });
writeFileSync('out/manifest.json', JSON.stringify({ items, updated_at: new Date().toISOString() }, null, 2) + '\\n');
"""
LIB = "export const item = (path, text) => [path, text.trim()];\n"


def manifest(docs, stamp="2026-11-22T10:00:00.000Z"):
    """What BUILD writes for these docs, with this timestamp (JSON.stringify(_, null, 2) matches json.dumps here)."""
    items = [[p, docs[p].decode().strip()] for p in sorted(docs)]
    return (json.dumps({"items": items, "updated_at": stamp}, indent=2) + "\n").encode()


@pytest.fixture
def env(tmp_path):
    return {
        **os.environ,
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    }


class Graph:
    """m0 (docs/a.md, the generator, its config, its manifest); staging s1 = m0 + docs/b.md; main m1 = m0 + docs/c.md.
    Both sides regenerate out/manifest.json, so git's own merge conflicts there and only there."""

    def __init__(self, tmp_path, env):
        self.tmp, self.env, self.n = tmp_path, env, 0
        self.origin, self.author = tmp_path / "origin.git", tmp_path / "author"
        self.git(None, "init", "-q", "--bare", str(self.origin))
        self.git(self.origin, "config", "uploadpack.allowAnySHA1InWant", "true")
        self.git(self.origin, "config", "receive.unpackLimit", "100000")
        self.git(None, "init", "-q", "--bare", str(self.author))
        self.base_files = {".github/slice-replay.json": CONFIG.encode(), "gen/build.mjs": BUILD.encode(),
                           "gen/lib.mjs": LIB.encode()}
        self.m0 = self.commit(self.files({"docs/a.md": b"alpha\n"}))
        self.s1 = self.commit(self.files({"docs/a.md": b"alpha\n", "docs/b.md": b"bravo\n"}), self.m0)
        self.m1 = self.commit(self.files({"docs/a.md": b"alpha\n", "docs/c.md": b"charlie\n"}), self.m0)
        self.push(self.s1, "staging")
        self.push(self.m1, "main")
        self.merged_docs = {"docs/a.md": b"alpha\n", "docs/b.md": b"bravo\n", "docs/c.md": b"charlie\n"}

    def git(self, cwd, *args, stdin=None, env=None):
        return subprocess.run(["git", *args], cwd=cwd or self.tmp, env=env or self.env, check=True, input=stdin,
                              capture_output=True).stdout.decode().strip()

    def files(self, docs, extra=None, stamp="2026-11-22T09:00:00.000Z"):
        return {**self.base_files, **docs, "out/manifest.json": manifest(docs, stamp), **(extra or {})}

    def tree(self, files):
        """files: path -> bytes, or ("link", target) for a symlink."""
        index = self.tmp / f"index{self.n}"
        self.n += 1
        e = {**self.env, "GIT_DIR": str(self.author), "GIT_INDEX_FILE": str(index)}
        for path, data in files.items():
            mode, blob = ("120000", data[1].encode()) if isinstance(data, tuple) else ("100644", data)
            oid = self.git(None, "hash-object", "-w", "--stdin", stdin=blob, env=e)
            self.git(None, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}", env=e)
        return self.git(None, "write-tree", env=e)

    def commit(self, files, *parents):
        self.n += 1
        args = [x for p in parents for x in ("-p", p)]
        return self.git(self.author, "commit-tree", self.tree(files), *args, "-m", f"c{self.n}")

    def push(self, sha, branch):
        self.git(self.author, "push", "-q", "-f", str(self.origin), f"{sha}:refs/heads/{branch}")

    def slice(self, files, first=None, second=None):
        head = self.commit(files, first or self.s1, second or self.m1)
        self.push(head, SLICE)
        return head

    def good_files(self, stamp="2026-11-22T11:11:11.111Z", **over):
        return {**self.files(self.merged_docs, stamp=stamp), **over}

    def run(self, script, head, base=None, **extra_env):
        e = {**self.env, "HEAD_SHA": head, "BASE_SHA": base or self.m1, "HEAD_REF": SLICE,
             "HEAD_REPO": "my-org/my-repo", "REPO": "my-org/my-repo",
             "GITHUB_SERVER_URL": f"file://{self.origin.parent}", "GITHUB_REPOSITORY": self.origin.name,
             **extra_env}
        cmd = ["python3", "-I", str(script)] if script.suffix == ".py" else ["bash", str(script)]
        p = subprocess.run(cmd, cwd=self.tmp, env=e, capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr


@pytest.fixture
def g(tmp_path, env):
    if not shutil.which("node"):
        pytest.fail("node is required: the replay runs the base's Node generator for real")
    return Graph(tmp_path, env)


def rule(strict, checks=({"context": "PRs into main must come from staging"},)):
    return {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": strict,
                                                              "required_status_checks": list(checks)}}


def gh_path(tmp_path, rules=(rule(True),), fail=False, pages=None, raw=None):
    """PATH with a `gh` that answers only GET rules/branches/main, logging every call to tmp_path/gh.log.

    The reply is what `gh api --paginate --slurp` prints: one array per page (one page of `rules` by default)."""
    bindir, log = tmp_path / "bin", tmp_path / "gh.log"
    bindir.mkdir(exist_ok=True)
    body = raw if raw is not None else json.dumps([list(p) for p in (pages or (rules,))])
    (tmp_path / "rules.json").write_bytes(body if isinstance(body, bytes) else body.encode())
    reply = "exit 4" if fail else f"cat {tmp_path / 'rules.json'}"
    (bindir / "gh").write_text(f'#!/bin/sh\necho "$@" >> {log}\n'
                               f'case "$*" in *rules/branches/main*) {reply} ;; *) exit 98 ;; esac\n')
    (bindir / "gh").chmod(0o755)
    return f"{bindir}{os.pathsep}{os.environ['PATH']}"


def holds(out):
    line = [x for x in out.splitlines() if x.startswith("slice replay holds:")]
    return line[0] if line else None


def test_a_slice_equal_to_the_replayed_merge_holds(g):
    head = g.slice(g.good_files())
    code, out = g.run(REPLAY, head)
    assert code == 0, out
    line = holds(out)
    gen_tree = g.git(g.author, "rev-parse", f"{g.m1}:gen")
    assert f"head={head} staging={g.s1} base={g.m1} " in line and f"generator={gen_tree}" in line, out


def test_the_guard_admits_a_slice_whose_replay_holds_while_main_requires_up_to_date_branches(g, tmp_path):
    head = g.slice(g.good_files())
    code, out = g.run(GUARD, head, PATH=gh_path(tmp_path))
    assert code == 0, out
    assert holds(out) and "allowed" in out, out
    assert (tmp_path / "gh.log").read_text().split() == ["api", "--paginate", "--slurp",
                                                         "repos/my-org/my-repo/rules/branches/main?per_page=100"]


def test_the_guard_reads_mains_strict_rule_from_any_page_of_the_rules_reply(g, tmp_path):
    other = {"type": "deletion"}
    code, out = g.run(GUARD, g.slice(g.good_files()), PATH=gh_path(tmp_path, pages=((other,) * 100, (rule(True),))))
    assert code == 0 and "allowed" in out, out


@pytest.mark.parametrize("rules,fail", [((rule(False),), False), ((), False), ((rule(True),), True),
                                        ((rule(True, checks=()),), False)],
                         ids=["not-strict", "no-status-check-rule", "rules-unreadable", "strict-without-checks"])
def test_the_guard_rejects_a_slice_whose_replay_holds_unless_main_requires_up_to_date_branches(g, tmp_path, rules,
                                                                                              fail):
    # Without strict checks main can move after the event, so the merge that lands is not the one replayed.
    code, out = g.run(GUARD, g.slice(g.good_files()), PATH=gh_path(tmp_path, rules, fail))
    assert code == 1, out
    assert holds(out) and "rejected" in out and "allowed" not in out, out


STRICT = json.dumps(rule(True))


KEY = b'"strict_required_status_checks_policy"'
MALFORMED = {
    "null-page": f"[[{STRICT}], null]", "object-page": f"[{{}}, [{STRICT}]]", "non-object-rule": f"[[{STRICT}, 7]]",
    "unslurped": f"[{STRICT}]", "object-reply": f'{{"pages": [[{STRICT}]]}}', "empty": "",
    "list-parameters": f'[[{STRICT}, {{"type": "required_status_checks", "parameters": [1]}}]]',
    "error-object": f'[[{STRICT}, {{"message": "Not Found"}}]]',
    "nan": f'[[{STRICT}, {{"type": "x", "parameters": {{"n": NaN}}}}]]',
    "duplicate-key": b'[[{"type": "required_status_checks", "parameters": {' + KEY + b": false, " + KEY + b": true}}]]",
    "invalid-utf8": f'[[{STRICT}, {{"type": "x\udcff"}}]]'.encode("utf-8", "surrogateescape"),
    "nul-in-key": b'[[{"type": "required_status_checks", "parameters": {"strict_required_status_checks_po\x00licy": true}}]]',
    **{f"check-{k}": f"[[{STRICT}, {json.dumps(rule(False, checks=(c,)))}]]" for k, c in
       {"null": None, "number": 7, "no-context": {}, "null-context": {"context": None}, "empty-context": {"context": ""}}.items()},
    "checks-not-a-list": f'[[{STRICT}, {{"type": "required_status_checks", "parameters": {{"required_status_checks": {{}}}}}}]]',
}


@pytest.mark.parametrize("raw", MALFORMED.values(), ids=MALFORMED.keys())
def test_a_malformed_rules_reply_rejects_even_beside_a_strict_rule(g, tmp_path, raw):
    code, out = g.run(GUARD, g.slice(g.good_files()), PATH=gh_path(tmp_path, raw=raw))
    assert code == 1 and "allowed" not in out, out


def test_two_runs_give_the_identical_tuple_and_tree(g):
    head = g.slice(g.good_files())
    first, second = g.run(REPLAY, head), g.run(REPLAY, head)
    assert first[0] == second[0] == 0, first[1] + second[1]
    assert holds(first[1]) == holds(second[1])


@pytest.mark.parametrize("tamper", ["extra-file", "changed-doc", "hand-edited-manifest", "stale-manifest"])
def test_a_tampered_slice_fails_closed(g, tamper):
    files = g.good_files()
    if tamper == "extra-file":
        files["src/backdoor.js"] = b"evil\n"
    elif tamper == "changed-doc":
        files["docs/a.md"] = b"alpha, rewritten\n"
        files["out/manifest.json"] = manifest({**g.merged_docs, "docs/a.md": b"alpha, rewritten\n"})
    elif tamper == "hand-edited-manifest":
        files["out/manifest.json"] = manifest({**g.merged_docs, "docs/z.md": b"zulu\n"})
    else:
        files["out/manifest.json"] = manifest({"docs/a.md": b"alpha\n", "docs/b.md": b"bravo\n"})
    code, out = g.run(REPLAY, g.slice(files))
    assert code == 1 and "is not the replayed merge" in out and not holds(out), out


def test_a_timestamp_differs_only_where_the_generator_stamps_it(g):
    files = g.good_files()
    files["out/manifest.json"] = files["out/manifest.json"].replace(b'"updated_at"', b'"updated_at_"')
    code, out = g.run(REPLAY, g.slice(files))
    assert code == 1 and "is not the replayed merge" in out, out


def test_a_conflict_resolved_by_hand_outside_the_outputs_fails_closed(g):
    s = g.commit(g.files({"docs/a.md": b"alpha from staging\n"}), g.m0)
    m = g.commit(g.files({"docs/a.md": b"alpha from main\n"}), g.m0)
    g.push(s, "staging")
    g.push(m, "main")
    docs = {"docs/a.md": b"alpha, resolved\n"}
    head = g.slice(g.files(docs), s, m)
    code, out = g.run(REPLAY, head, m)
    assert code == 1 and 'resolve conflicts by hand: "docs/a.md"' in out, out


@pytest.mark.parametrize("generator", [True, False])
def test_a_directory_rename_split_conflict_fails_closed(g, generator):
    # git exits 1 for a directory rename split but lists no unmerged file for it: only its message names the
    # directory. With a generator, the output conflict sits beside it and must not make the split look authorized.
    if not generator:
        del g.base_files[".github/slice-replay.json"]
    files = g.files if generator else (lambda docs: {**g.base_files, **docs})
    old = {"docs/old/a.md": b"alpha\n", "docs/old/b.md": b"bravo\n"}
    m0 = g.commit(files(old), g.m0)
    s = g.commit(files({"docs/one/a.md": b"alpha\n", "docs/two/b.md": b"bravo\n"}), m0)
    m = g.commit(files({**old, "docs/old/c.md": b"charlie\n"}), m0)
    g.push(s, "staging")
    g.push(m, "main")
    head = g.slice(files({"docs/one/a.md": b"alpha\n", "docs/two/b.md": b"bravo\n", "docs/old/c.md": b"charlie\n"}), s, m)
    code, out = g.run(REPLAY, head, m)
    assert code == 1 and not holds(out), out
    assert 'resolve conflicts by hand: "docs/old"' in out, out


def test_a_generator_failure_fails_closed(g):
    g.base_files["gen/build.mjs"] = b"process.exit(3);\n"
    m = g.commit(g.files({"docs/a.md": b"alpha\n", "docs/c.md": b"charlie\n"}), g.m0)
    g.push(m, "main")
    head = g.slice(g.good_files(), g.s1, m)
    code, out = g.run(REPLAY, head, m)
    assert code == 1 and "failed with exit 3" in out, out


def test_a_changed_generator_version_changes_the_tuple(g):
    code, out = g.run(REPLAY, g.slice(g.good_files()))
    assert code == 0, out
    before = holds(out)
    g.base_files["gen/lib.mjs"] = b"// v2\n" + LIB.encode()
    m2 = g.commit(g.files({"docs/a.md": b"alpha\n", "docs/c.md": b"charlie\n"}), g.m1)
    g.push(m2, "main")
    code, out = g.run(REPLAY, g.slice(g.good_files(), g.s1, m2), m2)
    assert code == 0, out
    after = holds(out)
    pick = lambda line, key: line.split(f"{key}=")[1].split()[0]  # noqa: E731
    assert pick(before, "generator") != pick(after, "generator")
    assert pick(before, "tool") == pick(after, "tool")


def test_a_malicious_generator_import_on_the_head_side_is_never_loaded(g):
    # Staging rewrites the generator's sibling import; the merged tree (and the head) carry it as data. The replay
    # runs the base's generator, so the rewritten import never runs.
    marker = g.tmp / "pwned"
    evil = f"import {{ writeFileSync }} from 'node:fs'; writeFileSync({json.dumps(str(marker))}, 'x');\n{LIB}"
    staging_files = g.files({"docs/a.md": b"alpha\n", "docs/b.md": b"bravo\n"}, {"gen/lib.mjs": evil.encode()})
    s = g.commit(staging_files, g.m0)
    g.push(s, "staging")
    head = g.slice(g.good_files(**{"gen/lib.mjs": evil.encode()}), s)
    code, out = g.run(REPLAY, head)
    assert code == 0, out
    assert not marker.exists()


def test_a_symlink_in_the_head_objects_is_never_followed(g):
    secret = g.tmp / "secret.txt"
    secret.write_text("SECRET-VALUE\n")
    link = ("link", str(secret))
    s = g.commit(g.files({"docs/a.md": b"alpha\n", "docs/b.md": b"bravo\n"}, {"docs/l.md": link}), g.m0)
    g.push(s, "staging")
    # The replay reads the link as a plain file holding its target path, so that is what the manifest holds.
    docs = {**g.merged_docs, "docs/l.md": str(secret).encode()}
    head = g.slice({**g.files(docs, stamp="2026-11-22T12:00:00.000Z"), "docs/l.md": link}, s)
    code, out = g.run(REPLAY, head)
    assert code == 0, out
    assert "SECRET-VALUE" not in out


def test_a_base_without_a_generator_replays_the_plain_merge(g):
    del g.base_files[".github/slice-replay.json"]
    s = g.commit({**g.base_files, "docs/b.md": b"bravo\n"}, g.m0)
    m = g.commit({**g.base_files, "docs/c.md": b"charlie\n"}, g.m0)
    g.push(s, "staging")
    g.push(m, "main")
    head = g.slice({**g.base_files, "docs/b.md": b"bravo\n", "docs/c.md": b"charlie\n"}, s, m)
    code, out = g.run(REPLAY, head, m)
    assert code == 0 and "generator=none" in holds(out), out
    tampered = g.slice({**g.base_files, "docs/b.md": b"bravo\n", "docs/c.md": b"changed\n"}, s, m)
    code, out = g.run(REPLAY, tampered, m)
    assert code == 1 and "is not the replayed merge" in out, out


@pytest.mark.parametrize("config", [
    "not json",
    json.dumps({"generator": {"entry": "../escape.mjs", "outputs": ["out"]}}),
    json.dumps({"generator": {"entry": "/abs/build.mjs", "outputs": ["out"]}}),
    json.dumps({"generator": {"entry": "gen/build.mjs", "outputs": ["gen"]}}),
    json.dumps({"generator": {"entry": "gen/build.mjs", "outputs": []}}),
], ids=["not-json", "dotdot-entry", "absolute-entry", "output-over-generator", "no-outputs"])
def test_a_bad_generator_config_fails_closed(g, config):
    g.base_files[".github/slice-replay.json"] = config.encode()
    m = g.commit(g.files({"docs/a.md": b"alpha\n", "docs/c.md": b"charlie\n"}), g.m0)
    g.push(m, "main")
    code, out = g.run(REPLAY, g.slice(g.good_files(), g.s1, m), m)
    assert code == 1 and ".github/slice-replay.json" in out, out


def test_failed_provenance_replays_nothing(g):
    head = g.slice(g.good_files(), g.s1, g.m0)  # an older main as second parent
    code, out = g.run(REPLAY, head)
    assert code == 1 and "stale" in out and "provenance does not hold" in out, out


def test_a_truncated_fetch_fails_closed(g):
    # The remote loses one blob the head needs (origin keeps pushed objects loose: receive.unpackLimit).
    head = g.slice(g.good_files())
    blob = g.git(g.author, "rev-parse", f"{head}:docs/b.md")
    loose = g.origin / "objects" / blob[:2] / blob[2:]
    assert loose.exists()
    loose.chmod(0o644)
    loose.unlink()
    code, out = g.run(REPLAY, head)
    assert code == 1 and not holds(out), out


def test_a_tampered_slice_is_rejected_before_any_api_call_even_with_up_to_date_rules(g, tmp_path):
    # The verdict on the head comes from git objects only; no check run (a forged 'Promote slice' one included) and
    # no API reply can admit a slice whose replay fails, so gh is never called for it.
    tampered = g.good_files(**{"src/backdoor.js": b"evil\n"})
    code, out = g.run(GUARD, g.slice(tampered), PATH=gh_path(tmp_path))
    assert code == 1 and "is not the replayed merge" in out and "rejected" in out, out
    assert not (tmp_path / "gh.log").exists()


def _replay_module():
    spec = importlib.util.spec_from_file_location("replay_promote_slice", REPLAY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TREE = "a" * 40


@pytest.mark.parametrize("raw, expected", [
    (f"{TREE}\0".encode(), (TREE, [], [])),
    (f"{TREE}\0out\0\0" "1\0out\0Auto-merging\0t\0" "1\0old\0CONFLICT (x)\0t\0".encode(),
     (TREE, ["out"], [("Auto-merging", ["out"]), ("CONFLICT (x)", ["old"])])),
])
def test_the_merge_tree_reply_parses(raw, expected):
    assert _replay_module().parse_merge_tree(raw) == expected


@pytest.mark.parametrize("raw", [
    f"{TREE}\0out\0\0" "1\0out\0CONFLICT (contents)\0text",  # last message not NUL-terminated
    f"{TREE}\0out\0\0" "1\0out\0CONFLICT (contents)\0",  # last message has no text field
    f"{TREE}\0out\0",  # conflicted paths with no terminating empty field
    f"{TREE}\0out\0\0",  # conflicted paths with every message cut off
    f"{TREE}\0\0" "+1\0a\0CONFLICT (x)\0t\0",  # signed count
    f"{TREE}\0\0" " 1\0a\0CONFLICT (x)\0t\0",  # padded count
    f"{TREE}\0\0" "\u0661\0a\0CONFLICT (x)\0t\0",  # non-ASCII digit
    f"{TREE}",  # tree not terminated
    f"{TREE}\0\0" "3\0a\0CONFLICT (x)\0",  # count runs past the reply
    f"{TREE}\0\0" "x\0a\0CONFLICT (x)\0t\0",  # count is not a number
    f"{TREE}\0\0" "1\0a\0CONFLICT (x)\0t\0\0junk\0",  # fields after the messages
])
def test_a_malformed_merge_tree_reply_fails_closed(raw):
    mod = _replay_module()
    with pytest.raises(mod.Reject):
        mod.parse_merge_tree(raw.encode())
