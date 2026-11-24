# Skill install scan: a blocking static security scan before any skill is placed

**Status:** planned. Scheduling pending.
**Urgency note (not a tier):** skills run inside full-access agents and `aec` places them with no content check.
**Source:** maintainer-approved request (2026-11-24): add
[NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector) (Apache-2.0, free) in `--no-llm` static mode as a blocking
pre-install check that fails loudly and names the finding.

**Incumbent (checked 2026-11-24): nothing in aec scans skill content.** Evidence:

- `git grep -i skillspector` over the repo finds no hit.
- `aec/lib/skills_manifest.py` `_scan_skill_paths` walks paths to hash and version a skill; it reads no content for risk.
- `aec/lib/filesystem.py` `check_install_paths` guards names, symlinked parents and the delete target. It checks where a
  skill lands, not what it says or runs.
- `aec/lib/org_config/trust.py` `verify_trust` proves who signed an org config. It says nothing about the content of the
  skills that config names.
- `nevar-security-review` (claude-skills) reviews a code change or repository. It runs when someone asks for a review, not at
  install time, so it cannot gate a placement.

The thing this plan wraps is SkillSpector's CLI. Its configuration surface was read before this plan (README, "Integrating
SkillSpector"): exit codes, `--fail-on-incomplete`, `--format json`, `--baseline`. The glue stays small: one module that runs it
and one call from the existing write chokepoint.

## Problem

1. `aec install skill <name>`, `aec skills install`, `aec skills update`, `aec upgrade` and the org apply flows copy a skill
   directory into an agent's skills folder and wire its hooks. The agents that load it run with full access. SkillSpector's own
   dataset reports 26.1% of a 31,132-skill analyzed subset with vulnerabilities and 5.2% as likely malicious; the catalog aec ships contains
   community content (`.claude/agents` is the agency-agents submodule, `.claude/skills` the claude-skills submodule).
2. There are two write paths. `place_installed_item` (`aec/lib/filesystem.py`) is documented as the one write chokepoint for
   install, upgrade, org apply and global migration. `aec skills install` and `aec skills update`
   (`aec/commands/skills.py` lines 171 and 322) skip it with their own `shutil.copytree`, so a gate added to the chokepoint
   alone would leave the `skills` subcommand ungated.
3. Nothing records that a scan happened, so a later `aec doctor` or a human cannot tell a scanned skill from an unscanned one.

## Root cause

Install trusts the source. The only checks are about paths and provenance of the config, never about the content that is about
to be executed by an agent. The second write path is a smaller instance of the same defect: behavior that belongs to one
component (placing a skill) lives in two.

## Correct fix

Each behavior lives in the component that owns it; callers call.

### 1. Scanner module: `aec/lib/skill_scan.py` (new, the only code that knows SkillSpector)

- `scan_skill_dir(src: Path, name: str) -> ScanResult` runs
  `skillspector scan --no-llm --format json --fail-on-incomplete -- <src>` (the shape SkillSpector documents for install gates)
  with an argument list, never a shell string, `cwd` set to a fresh empty temp directory (the skill is untrusted and must not
  be the interpreter's current directory), a minimal environment (no provider API keys, so a static scan cannot turn into an
  LLM scan by accident), and a timeout (default 120 s).
- Verdicts, all decided here and nowhere else:
  - exit 0 and JSON parsed: `passed`. The output says "static scan passed", never "safe" (SkillSpector states that a low
    static-only score is not a clean full scan).
  - exit 1: `blocked`. The message lists every `issues[]` entry as `<id> <category> <severity> <file>:<line>`, the
    `risk_assessment` score and recommendation, and the incomplete-analysis reason when that is the cause.
  - exit 2, timeout, a crash, unparsable JSON or a JSON shape that lacks `risk_assessment` or `issues`: `error`, which blocks
    (fail closed) and says it is a scanner failure, not a finding.
  - `skillspector` not found, or older than the minimum version this plan pins: `unavailable`, which blocks and prints the exact
    install command and the Python 3.12/3.13 requirement (SkillSpector's yara dependency has no wheels for newer interpreters,
    NVIDIA/SkillSpector issue 1008). aec never installs the scanner silently; it is third-party software.
- `~/.agents-environment-config/skill-scans.json` caches a verdict by `hash_skill_directory(src)` plus the scanner version, so
  an unchanged skill is not rescanned on every `aec upgrade`.

### 2. One call from the chokepoint: `place_installed_item`

- When `src` is a directory containing `SKILL.md`, `place_installed_item` calls `scan_skill_dir` **before** any delete or copy.
  A `blocked`, `error` or `unavailable` verdict raises one `SkillScanBlocked` error; the existing installed copy stays in
  place, so a bad update never removes a good install. Callers (`install_cmd.py:334`, `upgrade.py:277, 308, 632`, the org apply
  flows) do not re-check; they report the exception the way they already report `ValueError` from `check_install_paths`.
- `aec skills install` and `aec skills update` are changed to place through `place_installed_item` instead of their own
  `copytree`. This removes the second write path; the manifest handling they do after the copy is unchanged.
- The verification-pipeline script copy (`install_cmd.py` near line 682) copies scripts from an already-installed skill into a
  repo. It is not a placement of a new skill and is out of scope; the plan records it so it is not mistaken for a gap.

### 3. Override, setting and record

- Policy setting `skill_scan: block | warn | off`, default `block`, in aec preferences; an org config can force `block`. `warn`
  and `off` print one line on every install saying the scan was weakened and by which setting. The default is the safe one for a
  first-time user; the people who need less choose it knowingly.
- A single skill can be accepted only with `--accept-scan-risk "<reason>"`. `--yes` never implies it (a test pins this, because
  agents run `aec` with `--yes`). The reason is written to the manifest item beside `scan: {verdict, scanner_version,
  content_hash, accepted_reason}`.
- Findings that are known false positives are accepted through SkillSpector's own `--baseline` file, not through code in aec.
  Where that file lives (catalog-committed or per user) is decided in step 3 below from measured results.

### 4. `aec doctor` and the catalog

- `aec doctor` reports each installed skill whose manifest item has no `scan` record, or whose recorded `content_hash` no longer
  matches the directory, and exits non-zero for it (the doctor exit-code contract is owned by
  `2026-11-21-stale-skills-fail-loudly.md`; this check uses it, it does not redefine it).
- A CI job in aec scans every skill in the catalog with the same module and fails on `blocked`, so the shipped catalog is
  certified once at merge, and a user's install of an unmodified catalog skill hits the cache. Path-filtered so it runs only
  when a skill directory or `aec/lib/skill_scan.py` changes.

## Sequencing (nothing blocks a user before the baseline exists)

1. **Measure first, no behavior change.** Install the scanner locally, run it over every skill in the catalog, record the
   findings count per skill and the false positives. Confirm in the scanner's own documentation and a packet capture or a
   network-denied run what `--no-llm` still sends: SkillSpector's README says SC4 sends the skill's declared dependency names
   and versions to api.osv.dev even in static mode and falls back to a bundled list when offline. The plan's user-facing text
   states this; if the scanner has no offline switch, the setting `skill_scan_osv: on | off` is added in step 2. Confirm
   whether a PyPI release exists and pin the install command to a tag or version, not a branch.
2. Build `skill_scan.py` with the fake-scanner unit tests and the real-scanner contract test (Tests below), behind
   `skill_scan: off` as the temporary default so nothing is gated yet.
3. Commit the baseline decided from step 1 and route `aec skills install/update` through the chokepoint.
4. Flip the default to `block`, add the doctor check and the catalog CI job, document it in the README and in `aec doctor` output.

## Not in scope

- **LLM-mode scanning.** It spends tokens and sends skill content to a model provider. It needs an explicit, separate maintainer
  decision; static mode needs none. Nothing in this plan reads an LLM provider key.
- **Agents, rules, MCP servers and plugins.** SkillSpector scans skills (Claude Code, Codex and MCP skills). Whether agents (the
  agency-agents submodule) and MCP servers should be gated the same way is a follow-up decision once step 1 shows how the scanner
  treats non-skill markdown; the chokepoint already takes a type, so adding one is a small change.
- Replacing `verify_trust` or the signing flow: it answers a different question (who published the config).

## Tests

Real runs wherever we own the code; mocks only for the third party, each with a validation test.

- **Contract test against the real scanner** (marker `requires_skillspector`, runs in the CI job that installs the pinned
  scanner): a clean fixture skill returns exit 0 and parses; a fixture with a known malicious pattern (a credential read piped to
  a network call, a prompt-injection instruction) returns exit 1 and the output names its `issues[].id`. The test also asserts
  the JSON keys `risk_assessment.score`, `risk_assessment.recommendation`, `issues[].id`, `issues[].location.file`.
- **Fake `skillspector` on PATH** for the paths a real scan cannot produce on demand: exit 2, a hang past the timeout, garbage
  output, JSON without `issues`, a binary below the pinned version, no binary. The fake emits the exact key set the contract test
  asserts, and a test fails if the two key sets differ.
- Gate behavior: a blocked update leaves the old installed copy byte-identical; `--yes` alone does not accept a block;
  `--accept-scan-risk` records the reason; `skill_scan: warn` installs and prints the warning; the cache skips a second scan of
  an unchanged skill and rescans after a one-byte edit.
- Writers enumerated (contract change coverage): one test per entry point (`aec install skill`, `aec skills install`,
  `aec skills update`, `aec upgrade`, org apply) that a blocked skill is not placed.

## Affected surfaces

`aec/lib/skill_scan.py` (new), `aec/lib/filesystem.py` (`place_installed_item`), `aec/commands/skills.py` (install, update),
`aec/commands/install_cmd.py`, `aec/commands/upgrade.py`, the org apply placement path (confirm in step 1 whether it reaches
`place_installed_item` directly or through `upgrade`), `aec/lib/skills_manifest.py` (the `scan` record), `aec/commands/doctor.py`,
aec preferences (`skill_scan`), CI config, README and the generated project instructions in `aec/lib/tracking.py`.

## Review notes for the author of this plan

- Open question for step 1: PyPI availability and the pinned version of SkillSpector.
- Spend: none. Static mode and the OSV lookup are free; no step uses an LLM key.
