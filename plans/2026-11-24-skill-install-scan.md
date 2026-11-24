# Skill install scan: a blocking static security scan before any skill is placed

**Status:** planned. Scheduling pending.
**Urgency note (not a tier):** skills run inside full-access agents and `aec` places them with no content check.
**Source:** request (2026-11-24): add
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

- `scan_skill_dir(src: Path, name: str) -> ScanResult` first **stages** the skill: it copies `src` into a fresh temp directory
  with `symlinks=True` and the same ignore rules the placement uses, and **rejects any symlink and any file the placement
  would copy but the scan would not see** (dotfiles are the known case: the placement drops them today, the content hash
  skips them; step 1 measures what the scanner itself skips). It then runs
  `skillspector scan --no-llm --format json --fail-on-incomplete -- <staged>` (the shape SkillSpector documents for install
  gates) with an argument list, never a shell string, `cwd` set to a second empty temp directory (the skill is untrusted and
  must not be the interpreter's current directory), a minimal environment (no provider API keys, so a static scan cannot turn
  into an LLM scan by accident), and a timeout sized to the scanner's own deadline (step 1 measures it; a timeout shorter than
  the scanner's default would produce false `error` verdicts). The **staged bytes are what gets hashed, scanned and then
  copied into place**, so the scan and the install cannot see different content.
- Verdicts, all decided here and nowhere else. `passed` follows SkillSpector's documented gate recipe, not the exit code
  alone: exit 0 also covers `CAUTION` and a score of exactly 50, so one CRITICAL finding exits 0.
  - `passed` only when exit is 0, `execution_successful` is true, `metadata.llm_requested` is false,
    `analysis_completeness.is_complete` is true and `risk_assessment.recommendation` is `SAFE`. The output says "static scan
    passed", never "safe" (SkillSpector states that a low static-only score is not a clean full scan).
  - `blocked`: exit 1, or exit 0 with a recommendation other than `SAFE` (`CAUTION` blocks by default; accepting it is the
    explicit override below). The message lists every `issues[]` entry as `<id> <category> <severity> <file>:<line>`, the
    `risk_assessment` score and recommendation, and the incomplete-analysis reason when that is the cause.
  - exit 2, timeout, a crash, unparsable JSON or a JSON shape that lacks `risk_assessment` or `issues`: `error`, which blocks
    (fail closed) and says it is a scanner failure, not a finding.
  - `skillspector` not found, or older than the minimum version this plan pins: `unavailable`, which blocks and prints the exact
    install command and the Python 3.12/3.13 requirement (SkillSpector's yara dependency has no wheels for newer interpreters,
    NVIDIA/SkillSpector issue 1008). aec never installs the scanner silently; it is third-party software.
- `~/.agents-environment-config/skill-scans.json` caches a verdict keyed by a hash of the **staged** bytes (every file,
  including dotfiles and file modes, not `hash_skill_directory`, which skips dotfiles), the scanner version and whether the
  OSV lookup ran online or from the bundled fallback (SC4 depends on the network). Entries expire (default 7 days, so new
  advisories are picked up) and the file is written atomically with a content check on read; a corrupt or unreadable cache
  means "rescan", never "passed". Only `passed` is cached.

### 2. One call from the chokepoint: `place_installed_item`

- `place_installed_item` has no item-type parameter and returns nothing today, so this step adds the plumbing: an `item_type`
  argument, the `skill_scan` policy and an `accept_risk` reason in, and the scan record out for the manifest. Every caller is
  updated in the same change.
- When the item is a skill (`item_type == "skill"`, with a case-insensitive `SKILL.md` check as a second signal so a lowercase
  `skill.md` or a bundle directory is not skipped), `place_installed_item` calls `scan_skill_dir` **before** any delete or
  copy. A `blocked`, `error` or `unavailable` verdict raises one `SkillScanBlocked` error; the existing installed copy stays in
  place, so a bad update never removes a good install. Callers (`install_cmd.py:334`, `upgrade.py:277, 308, 632`, the org
  apply flows) do not re-check; they report the exception the way they already report `ValueError` from `check_install_paths`.
- **`migrate_item_to_global` loses data on a block today** (`aec/lib/global_install_prompt.py:141-147`): it deletes the per-repo
  copies and their manifest entries, then calls `place_installed_item`. A block raised there would arrive after the loss. The
  change places the global copy first and deletes the per-repo copies only after placement succeeds. A test pins that a
  blocked migration leaves every per-repo copy and manifest entry in place.
- **Org apply** runs with `yes=True` (`aec/lib/apply_core.py`) and handles errors per item. A `SkillScanBlocked` there must
  surface (a failed item in the apply report and a non-zero exit), never be swallowed, and org config can carry an
  accepted-risk entry per skill only through the same recorded `--accept-scan-risk` reason path.
- **Hook activation is a second way to run skill content.** `aec/lib/catalog_hooks.py` (`wire`, `refresh`) and
  `aec/lib/hooks/drift.py` `repair_repo` wire a skill's hooks from the catalog directory or the repo-local copy, not from the
  placed copy. Step 1 enumerates every such path; each one wires hooks only for a skill that has a passing (or accepted)
  scan record for the exact bytes it wires, and reports the missing record as the reason.
- `aec skills install` and `aec skills update` are changed to place through `place_installed_item` instead of their own
  `copytree`. This removes the second write path; the manifest handling they do after the copy is unchanged.
- The verification-pipeline script copy (`install_cmd.py` near line 682) copies scripts from an already-installed skill into a
  repo. It is not a placement of a new skill and is out of scope; the plan records it so it is not mistaken for a gap.

### 3. Override, setting and record

- Policy setting `skill_scan: block | warn | off`, default `block`, in aec preferences; an org config can force `block`. `warn`
  and `off` print one line on every install saying the scan was weakened and by which setting. The default is the safe one for a
  first-time user; the people who need less choose it knowingly.
- A single skill can be accepted only with `--accept-scan-risk "<reason>"`. `--yes` never implies it (a test pins this, because
  agents run `aec` with `--yes`). The reason is written to the install manifest item beside `scan: {verdict,
  scanner_version, content_hash, accepted_reason}`. There are two manifests today: `aec skills` writes the v1 shape
  (`build_skill_manifest_item`), while install, upgrade and apply write v2 (`record_install` with `contentHash`) and doctor
  reads v2. This plan uses v2 for the `scan` record, and routing `aec skills` through the chokepoint (section 2) moves it
  onto v2 as well; step 3 defines the key names and how a legacy skill with no record is reported (as "unscanned", with the
  one command that scans it, never silently as clean).
- Findings that are known false positives are accepted through SkillSpector's own `--baseline` file, not through code in aec.
  Where that file lives (catalog-committed or per user) is decided in step 3 below from measured results.

### 4. `aec doctor` and the catalog

- `aec doctor` reports each installed skill whose manifest item has no `scan` record, or whose recorded `content_hash` no longer
  matches the directory, and exits non-zero for it (`run_doctor` returns `(all_passed, issues)` and the CLI already exits 1 on
  failure, so this check adds an issue and needs no new exit-code contract).
- A CI job in aec scans every skill in the catalog with the same module and fails on `blocked`, so the shipped catalog is
  certified once at merge, so a blocked skill cannot ship in the catalog. This does not save a user the local scan: the
  cache lives on each user's machine, and a CI runner cannot fill it. Every installing user needs the scanner (the
  `unavailable` verdict prints how to get it). Shipping a signed or committed attestation that aec could consume instead
  is a separate decision, not part of this plan. Path-filtered so the job runs only when a skill directory or
  `aec/lib/skill_scan.py` changes.

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
  treats non-skill markdown; the chokepoint gains an `item_type` parameter in section 2, so adding one is a small change.
- Replacing `verify_trust` or the signing flow: it answers a different question (who published the config).

## Tests

Real runs wherever we own the code; mocks only for the third party, each with a validation test.

- **Contract test against the real scanner** (marker `requires_skillspector`, runs in the CI job that installs the pinned
  scanner): a clean fixture skill is `passed` and parses; a fixture with a known malicious pattern (a credential read piped to
  a network call, a prompt-injection instruction) is `blocked` and the output names its `issues[].id`, **whatever exit code the
  scanner returns for it** (a CRITICAL finding scores 50 and exits 0, so the test asserts the verdict, not the exit code). The
  test also asserts the JSON keys `execution_successful`, `metadata.llm_requested`, `analysis_completeness.is_complete`,
  `risk_assessment.score`, `risk_assessment.recommendation`, `issues[].id`, `issues[].location.file`.
- **Bytes-scanned-equal-bytes-placed:** a symlink inside a skill is refused; a dotfile payload is either scanned or refused,
  never silently dropped between scan and copy; editing the source between the scan and the copy cannot change what is placed.
- **Writer bypass guard:** a test fails when any `copytree`/`copy2` into an agent skills directory exists outside
  `place_installed_item` (so a new writer, such as the one planned in `2026-11-16-upgrade-detects-vendored-skills.md`, cannot
  land ungated). Plus one test each for `catalog_hooks` wiring, `repair_repo`, global migration (blocked leaves per-repo copies
  intact) and the `install_cmd.py` hook-template `copy2`.
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
`aec/commands/install_cmd.py`, `aec/commands/upgrade.py`, `aec/lib/global_install_prompt.py` (place before delete),
`aec/lib/apply_core.py` and the org apply placement path (failure must surface), `aec/lib/catalog_hooks.py` and
`aec/lib/hooks/drift.py` (hook wiring requires a scan record), `aec/lib/skills_manifest.py` (the `scan` record), `aec/commands/doctor.py`,
aec preferences (`skill_scan`), CI config, README and the generated project instructions in `aec/lib/tracking.py`.

## Review notes for the author of this plan

- Open question for step 1: PyPI availability and the pinned version of SkillSpector.
- Spend: none. Static mode and the OSV lookup are free; no step uses an LLM key.
