---
name: "feedback-loop"
description: "Use when a skill, agent, hook, plugin, AEC or the development process itself (tests, CI, planning, review, deploy) caused rework, a wrong default, a missed case or a needless pause, to log that friction to a local per-subject store; and when an item's run ends with its feedback due for review, or the user says \"review feedback\", \"what friction have we logged\", \"feedback status\", to walk the entries with the user and turn accepted ones into a PR, issue or plan file."
tags: ["skill"]
---


# Feedback loop

Every skill, agent, hook, plugin, AEC itself and the way a project's work runs can teach us
something each time it goes wrong. This skill is the one shared way to **capture** that friction
when it happens, **count** it per subject, and **turn it into a fix** with the user's consent.

All data stays on this machine. Nothing is sent anywhere unless the user says yes during a review.

## Subjects

Feedback is filed against a *subject*, written `kind:name`:

| kind | name | friction looks like | fix lands as |
|---|---|---|---|
| `skill` | skill name (`my-skill`) | the skill's instructions caused rework, a wrong default, a missed case, a needless question | PR to the skill's source repo |
| `agent` | agent name / file stem | the agent's prompt sent it the wrong way, missed a step, overstepped its role | PR to the agent's source repo |
| `hook` | `<owning-item>/<hook-id>` | the hook crashed, timed out, needed a missing tool, misread its input, blocked something it should not have | PR to the owning item's source repo |
| `plugin` | plugin name | a plugin command or tool misbehaved | issue or PR on the plugin's repo |
| `aec` | `aec` | the `aec` CLI failed, asked something it could have known, did the wrong thing | issue or PR on the AEC repo |
| `process` | project slug (`my-project`) + `--area` dev, test, ci, plan, review, deploy | flaky or slow CI, a test that missed a regression, a plan wrong about the code, a review loop that took three rounds, a deploy surprise | a plan file or issue in that project |

A hook that **correctly** blocks something is working, not friction. Log the hook only when the
hook itself is at fault.

## The store

`scripts/feedback.py` (Python 3, stdlib only) owns the store. Run it from this skill's
directory. Root: `$AGENT_FEEDBACK_HOME`, default `~/.agent-feedback/`.

```
config.json                              {"enabled": true, "opt_out": ["skill:foo"]}
subjects/<kind>/<name>/entries.jsonl     append-only, one entry per line (parallel-safe)
subjects/<kind>/<name>/state.json        last_review, reviewed_count, source_repo, resolutions
```

Never edit these files by hand; always go through the script.

Each line of `entries.jsonl` is one JSON object. Required: `id` (12 hex chars, unique within the
subject: random for live entries; imports use the first 12 hex chars of the sha256 of
`ts\nkind\nname\nsummary`, plus `\n<n>` for the n-th repeat of the same date and summary, so a
re-import adds nothing), `ts` (UTC, `YYYY-MM-DDTHH:MM:SSZ`), `kind`, `name`,
`severity`, `summary`, `reporter` (`agent`, `cli`, `hook` or `human`). Optional: `suggestion`,
`phase`, `area` (process only), `project`. A program that cannot run the script (a CLI capturing
its own crash) may append one such line itself, with a single `O_APPEND` write.

## Logging

```bash
python3 <this-skill>/scripts/feedback.py log skill:my-skill --severity medium \
  --summary "tier table sent a migration stage to the smallest model; one retry wasted" \
  --suggestion "mark data-integrity stages mid-tier minimum" --phase plan --project my-project
python3 <this-skill>/scripts/feedback.py log process:my-project --area ci --severity low \
  --summary "e2e job queued 14 min behind a docs-only run"
```

- **Severity:** `high` = wrong output or a blocked run; `medium` = rework or a wasted stage;
  `low` = an annoyance or a weak default.
- **Summary:** what happened, one line. **Suggestion:** the concrete change to the subject.
- Log **when it happens**, not at the end of the session: the context is gone by then.
- Never put credentials, customer data or personal data in a summary. The script refuses text
  that looks like a key.
- When logging is disabled or the subject is opted out, `log` does nothing and exits 0. Logging
  never fails the item that calls it; a caller that is a hook also ignores the exit code.

## When to offer a review

At the end of an item's run (or when the user asks), check the subject:

```bash
python3 <this-skill>/scripts/feedback.py status skill:my-skill      # one subject
python3 <this-skill>/scripts/feedback.py status --due               # every subject past threshold
```

A subject is **due** when its open entries logged since its last review include **any high,
or ≥3 medium, or ≥5 total**. Only then make the offer. Never offer for a subject that is not due.

## The review conversation

1. Get the entries: `feedback.py review <subject>` (`--json` for structure). Keep its `through`
   value (`<N>`): it marks exactly the entries this review showed, so anything logged while the
   conversation runs stays pending for the next review.
2. Show them in this compact shape. Every line names the subject, because the entries come from
   **past** runs, not this conversation:

   ```
   <kind> <name> — feedback: <N> entries since <last review or "first review"> — review due (<reason>).
   Top <name> entries (from previous runs):
   - [high] <summary> → <proposed fix>
   - [medium] <summary> → <proposed fix>
   (<K> more low-severity entries, listed on request)
   Proposed changes to <name>: <file>: <one-line change> (one line per file)
   ```

3. Ask, verbatim with the subject filled in:

   > Friction in the **<name>** <kind> has been noted in previous runs. Would you like to review
   > it together and suggest a fix back to its source? (Y / N / Never)

- **Y:** walk the entries, draft the concrete changes, resolve the source (below), and open the
  PR or issue **only on explicit confirmation**. Record outcomes with `resolve`, then
  `mark-reviewed --through <N>`.
- **N:** `mark-reviewed --through <N>` so the same entries do not re-trigger; logging continues and the offer
  returns only when new entries hit the threshold.
- **Never:** confirm once ("Stop logging feedback for <name> and never ask again?"), then
  `feedback.py config --opt-out <subject>`.

## Resolving entries

```bash
feedback.py resolve <subject> <id> [<id> ...] --status folded --pr <url>   # fix is in a PR
feedback.py resolve <subject> <id> --status merged                          # that PR merged
feedback.py resolve <subject> <id> --status not-a-problem                   # not the subject's fault
feedback.py resolve <subject> <id> --status deferred                        # real, not now; stays open
feedback.py mark-reviewed <subject> --through <N> [--source-repo <owner/repo or path>]
```

`folded`, `merged` and `not-a-problem` close an entry; `deferred` keeps it open. The entries file
is never rewritten, so the history stays countable (`feedback.py report`).

## Folding a fix into the subject

- Each lesson lands in the section of the subject that **owns that concern**, stated at the
  highest generality that still prevents the recurrence.
- A lesson that only applies to one project's artifact does not go into a shared item: resolve
  it `not-a-problem` (or, for `process`, it belongs in that project).
- Never assume one host's behavior is universal; phrase harness quirks as "some harnesses" and
  give the portable alternative.
- **One PR per review, never one per entry.** Entries cluster in the same sections; per-entry PRs
  conflict and each needs its own version bump.
- Bump the item's `version` and follow its repo's release rules (manifests, changelogs) in the
  same commit. A lesson that also governs a sibling item lands in both.

## Finding the source

Resolve in order, then cache it with `mark-reviewed --source-repo`:

1. The current directory **is** the subject's source repo (the item is tracked in git here, not
   an installed copy).
2. The subject's frontmatter has `source:`; or `aec` is installed and `aec info <kind> <name>`
   reports where it came from.
3. Ask the user once.

For `process`, the source is the project itself: propose a plan file or an issue there instead
of a PR to a shared item. Use `feedback.py report process:<project>` to show trends by area and
month so the user can see which part of the work keeps costing time.

For `aec`, offer an issue on the AEC repository containing the summaries and suggestions only.
Create it only on explicit consent.

## Turning it on and off

```bash
feedback.py config                       # show
feedback.py config --disable             # stop all logging
feedback.py config --enable
feedback.py config --opt-out skill:foo   # silence one subject
feedback.py config --opt-in skill:foo
```

With AEC installed, `aec feedback enable|disable|opt-out|opt-in` runs these same commands.

## Adding feedback to an item

To build this loop into a skill, agent, hook or plugin you maintain, see
[references/adopting.md](references/adopting.md).
