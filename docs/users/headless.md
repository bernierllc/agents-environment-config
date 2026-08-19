# Headless AEC (running it from an agent)

Every prompt AEC can ask has a stable ID, is listed in a catalog you can read
before you run anything, and can be answered from a file, an environment
variable, or an org overlay. Nothing changes for a human at a keyboard — the
same command run interactively still asks the same questions in the same order.

The three moving parts:

1. **Discover** what a command will ask — `aec prompts list`
2. **Answer** it — `--answers file.json`, `AEC_ANSWERS`, or `AEC_ANSWER_<ID>`
3. **Fail loudly** when an answer is missing — `--non-interactive`

## 1. Discover the prompts

```bash
aec prompts list                      # every prompt, grouped by command
aec prompts list --command setup   # substring match on the command name
aec prompts list --json               # machine-readable
```

Each entry carries the prompt ID, its type (`yes_no`, `string`, `int`,
`enum[...]`), its default, its choices where it has them, and the environment
variable that answers it:

```
aec repo setup

  repo.discover.scan  (yes_no, default=True)
      Scan the project for files matching items in the AEC catalog.
      env: AEC_ANSWER_REPO_DISCOVER_SCAN
```

Some prompts are **dynamic families** — one prompt per installed skill, per
optional rule, per agent. Those are listed by prefix (e.g.
`skills.install.overwrite.<name>`); `aec prompts list` expands them against
what is actually installed on this machine.

## 2. Write the answers

Start from a skeleton rather than typing IDs by hand:

```bash
aec prompts template --command setup > answers.json
```

```json
{
  "repo.discover.scan": true,
  "repo.git.commit_strategy": "1",
  "setup.track_current_repo": true
}
```

Values are written the way a person would answer: booleans for `yes_no`,
strings for enums and free text, numbers for `int`. `null` means "no default —
you must fill this in."

Validate before you run anything with side effects:

```bash
aec prompts check answers.json
```

It exits non-zero and names every bad value:

```
✗ 1 problem(s) in answers.json:
  setup.track_current_repo: 'maybe' is not a valid yes_no
```

## 3. Run the command

```bash
aec --answers answers.json --non-interactive setup
```

`--answers`, `--non-interactive`, and `--defaults` are **global** options: they
belong before the subcommand, not after it. `aec setup --answers ...` is a
parse error.

Three ways to supply answers, highest precedence last:

| Source | How |
|---|---|
| Answers file | `aec --answers answers.json <command>` or `AEC_ANSWERS=/path/answers.json` |
| Single answer | `AEC_ANSWER_REPO_DISCOVER_SCAN=y aec setup` |
| Org overlay | enrolled via `aec org enroll` — wins over both of the above |

`--non-interactive` is what makes a run safe to automate: a prompt with no
answer **fails with the missing ID** instead of hanging on stdin or silently
picking something. The error names the exact ID to add to your answers file.

`--defaults` (or `AEC_USE_DEFAULTS=1`) accepts the declared default for any
prompt you did not answer. Use it for a first pass; use `--non-interactive`
alone when you want every decision to be explicit.

## `aec test schedule` without a REPL

`aec test schedule` normally drops into a `schedule>` REPL. The same verbs run
headlessly, one `--do` per command:

```bash
aec test schedule --list                       # print the schedule, change nothing
aec test schedule --do merge \
                  --do "n e2e :: npm run e2e" \
                  --do "+ unit" \
                  --do "o unit,e2e"
```

| Verb | Effect |
|---|---|
| `merge` | Pull newly detected suites into `.aec.json` |
| `+ NAME` | Schedule an existing suite |
| `n NAME :: COMMAND` | Define a suite and schedule it |
| `r N` | Unschedule position N |
| `o A,B,C` | Replace the run order |
| `mv FROM TO` | Move one scheduled item |

A failing verb aborts the whole run **before** anything is written, so a
half-applied schedule never lands in `.aec.json`.

## Keeping the catalog honest

The catalog is generated from the same IDs the callsites use, and a test walks
the source to assert the two sets match in both directions. A prompt that is
asked but not catalogued — or catalogued but never asked — fails CI. What
`aec prompts list` shows you is what the command will actually ask.
