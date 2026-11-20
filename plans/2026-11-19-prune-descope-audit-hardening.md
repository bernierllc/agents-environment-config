# Harden the call audit in the prune quarantine tests

Status: planned; scheduling pending.

## Root cause and affected surfaces

`tests/test_prune_descope.py` (PR #165) claims to prove that
`scripts/prune-merged-worktrees.sh` mutates nothing except `git worktree move` into the quarantine
tree, `mkdir -p` of quarantine directories and `rm -f` of its own `mktemp` scratch files. It does so
with a black-box audit: PATH shims for the tools the script calls log every call, each call is matched
against a table of exact-argv templates with typed slots, and a content hash of git state is compared
before and after each run.

A black-box audit can only vouch for what it can see. Three reviews of head `64c4c19` (Codex,
high) found limits in what it sees. None is a defect in the script, which has no P0 or P1 across five
independent reviews; they are limits in how strong a claim the tests can make about future script edits.

1. **Slots validate spelling, not containment.** A scratch slot accepts any path the run's `mktemp`
   returned plus the fixed suffix. If that path is a symlink into `.git`, then `rm -f <link>/index` is accepted
   as `rm-one-scratch` and deletes the real index. The quarantine `worktree move` is likewise accepted when its
   timestamp directory is a symlink out of the quarantine root.
2. **Writers that are not shimmed are invisible.** Shell builtins and redirections (`: > "$HOME/../victim"`),
   `python3 -I -c 'os.unlink(...)'`, and absolute-path tool calls (`p=/usr; "$p/bin/git"`) pass the three
   bypass regexes and never reach a shim. Their target is outside every hashed tree.
3. **`_git_dir_state` hashes object files by size.** Same-length corruption of an existing loose object or pack
   leaves the snapshot unchanged.

Smaller gaps from review B (Sonnet, no P0 or P1): the move-back after a rescan hit
(`-C REPO worktree move <hold> <wt>`) matches no template and no audited state reaches it; `STAMP` uses `\d`, so
Unicode digits match (they still resolve under the quarantine root); `LOGGED` omits `python3`, `awk`, `sort`,
`sed`, `perl`, `lsof`, `gh`, `du` and `cmp`; no audited state runs `find -exec python3` over a venv.

## Correct fix

Make the claim in the tests match what they can prove, then close each gap at its owner:

1. **Containment.** A slot match also requires `os.path.realpath` of the argument to sit under the slot's
   root (scratch root, quarantine root) and refuses any symlink along the way. The fixture creates symlinked
   scratch and stamp directories as mutants that must be rejected.
2. **Bypass.** Replace the three regexes with a check that is not about spelling: run the script a second time under
   a sandbox that denies writes everywhere outside the allowed paths (macOS `sandbox-exec` profile, or a read-only
   bind mount on Linux CI), so a builtin or redirection that writes elsewhere fails the run. Keep the static test
   that the script never bypasses PATH shims as a fast first line.
3. **Object hashing.** Hash the content of every file under `.git/objects`, `info` and `pack`, not its size. Add a
   same-length corruption mutant.
4. Cover the move-back template and the venv `find -exec python3` call with audited states, or delete the code path
   if no state can reach it. Anchor `STAMP` with `[0-9]`. Add the unshimmed tools to `LOGGED` or to the sandbox
   deny list.

## Surfaces

`tests/test_prune_descope.py` only, plus the fixture helpers it owns. No change to `scripts/` unless item 4
deletes an unreachable path. Depends on PR #165 landing first.

## Priority

Medium. The script is report-only for purge and quarantine-only for mutation, so the residual risk is a future
script edit that mutates something and passes the audit.
