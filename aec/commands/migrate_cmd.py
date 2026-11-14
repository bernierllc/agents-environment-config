"""aec migrate agents-md: move a repo from the AGENTINFO.md layout to AGENTS.md.

AEC does the move itself (aec.lib.agents_md_layout) and records every file it
touches as a changeset (aec.lib.changesets), so `aec rollback` restores the
exact previous bytes. An agent is only used for the optional --tidy-with pass,
which is recorded as its own changeset.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from ..lib import changesets
from ..lib.agents_md_layout import INSTRUCTION_STUBS, detect_layout, plan_migration
from ..lib.console import Console
from ..lib.prompt_catalog.maintenance_area import (
    MIGRATE_AGENTS_MD_CONFIRM,
    MIGRATE_AGENTS_MD_TIDY_CONFIRM,
)
from ..lib.prompts import prompt
from .repo import AGENTS_MD_DOCS_URL

TIDY_TIMEOUT_SECONDS = 15 * 60

TIDY_PROMPT = (
    "Tidy this repository's agent instruction files. AEC just merged AGENTINFO.md "
    "into AGENTS.md mechanically: AGENTS.md holds the old AGENTINFO.md content, then "
    "the AEC rules reference, then any notes from the old AGENTS.md. CLAUDE.md, "
    "GEMINI.md and QWEN.md start with the line `@AGENTS.md`, which imports AGENTS.md. "
    "Edit only AGENTS.md, CLAUDE.md, GEMINI.md and QWEN.md. Remove instructions that "
    "are duplicated, merge sections that say the same thing, and fix leftover "
    "references to AGENTINFO.md. Never drop an instruction: when two disagree, keep "
    "both and add a line noting the conflict. Keep `@AGENTS.md` as the first line of "
    "each per-agent file. Keep the block between `<!-- aec-port-registry:start -->` "
    "and `<!-- aec-port-registry:end -->` exactly as it is. Do not touch any other "
    "file and do not run git commands."
)

WHY_TEXT = [
    "AGENTS.md is the shared instructions file Codex and Cursor read, and Claude Code",
    f"reads it too: {AGENTS_MD_DOCS_URL}",
    "This moves AGENTINFO.md's content into AGENTS.md and turns CLAUDE.md, GEMINI.md and",
    "QWEN.md into `@AGENTS.md` imports (plus any notes you added to them). Benefits:",
    "  - every agent loads your project instructions directly, instead of being told",
    "    to go and read AGENTINFO.md;",
    "  - one file to edit, and one less file in the repo.",
    "Nothing is lost: content you added to any of these files is kept. Every change is",
    f"recorded, and {Console.cmd('aec rollback')} restores the exact previous files.",
]


def _target_repos(paths: List[str], all_repos: bool) -> List[Path]:
    if all_repos:
        from ..lib.scope import get_all_tracked_repos

        # Linked worktrees have a .git file, not a directory: migrate the main checkout only.
        return [p for p in get_all_tracked_repos() if (p / ".git").is_dir()]
    return [Path(p).expanduser().resolve() for p in (paths or ["."])]


def _apply_plan(repo: Path, plan: dict) -> Optional[changesets.Changeset]:
    pending = changesets.begin(
        plan.keys(),
        short=f"Migrate {repo.name} to AGENTS.md",
        long=(
            f"aec migrate agents-md in {repo}:\n"
            "moved AGENTINFO.md into AGENTS.md, turned the per-agent files into "
            "@AGENTS.md imports and updated references to AGENTINFO.md.\n"
            "Files: " + ", ".join(str(p.relative_to(repo)) for p in plan)
        ),
        kind="migrate-agents-md",
    )
    try:
        for path, text in plan.items():
            if text is None:
                path.unlink()
            else:
                # bytes, so CRLF files stay CRLF on every OS
                path.write_bytes(text.encode("utf-8"))
    finally:
        # Record whatever was written, even after a failure, so it can be rolled back.
        cs = pending.commit()
    return cs


def _headless_agents() -> dict:
    from ..lib.config import detect_agents
    from ..lib.registry import get_supported_agents

    supported = get_supported_agents()
    return {
        name: supported[name]
        for name in detect_agents()
        if supported.get(name, {}).get("headless_args")
    }


def _tidy(repo: Path, agent: str, config: dict, yes: bool) -> bool:
    exe = shutil.which(config["commands"][0])  # resolves .cmd/.exe on Windows too
    if exe is None:
        Console.error(f"{agent} is not on PATH")
        return False
    args = [exe] + [TIDY_PROMPT if a == "{prompt}" else a for a in config["headless_args"]]
    Console.subheader(f"Tidy {repo.name} with {agent}")
    Console.print("  The agent runs headless in the repo with this prompt:")
    Console.print()
    Console.print("  " + TIDY_PROMPT)
    Console.print()
    if not yes:
        answer = prompt(MIGRATE_AGENTS_MD_TIDY_CONFIRM, f"  Run {agent} now? [y/N]: ", type="yes_no", default=False)
        if answer.strip().lower() != "y":
            Console.skip("Tidy skipped")
            return True

    files = [repo / "AGENTS.md"] + [repo / n for n in INSTRUCTION_STUBS]
    pending = changesets.begin(
        files,
        short=f"Tidy {repo.name} instructions with {agent}",
        long=f"{agent} ran headless in {repo} with this prompt:\n\n{TIDY_PROMPT}",
        kind="tidy",
    )
    try:
        result = subprocess.run(args, cwd=str(repo), timeout=TIDY_TIMEOUT_SECONDS)
    finally:
        cs = pending.commit()
    if cs is not None:
        Console.success(f"Recorded as {cs.id} (undo: {Console.cmd('aec rollback apply ' + cs.id)})")
    if result.returncode != 0:
        Console.error(f"{agent} exited with code {result.returncode}")
        return False
    return True


def run_migrate_agents_md(
    paths: Optional[List[str]] = None,
    all_repos: bool = False,
    yes: bool = False,
    dry_run: bool = False,
    tidy_with: Optional[str] = None,
) -> int:
    """Migrate repos to the AGENTS.md layout. Returns a process exit code."""
    tidy_config = None
    if tidy_with:
        agents = _headless_agents()
        if tidy_with not in agents:
            Console.error(f"--tidy-with {tidy_with}: not an installed agent that can run headless")
            Console.print(f"  Available: {', '.join(sorted(agents)) or 'none detected'}")
            return 2
        tidy_config = agents[tidy_with]

    repos = _target_repos(paths or [], all_repos)
    plans = {}
    for repo in repos:
        if not repo.is_dir():
            Console.error(f"Not a directory: {repo}")
            return 2
        plan = plan_migration(repo)
        if plan:
            plans[repo] = plan
        elif not tidy_with:
            Console.skip(f"{repo}: already on the {detect_layout(repo)} layout, nothing to migrate")

    if plans:
        Console.header("Migrate to AGENTS.md")
        for line in WHY_TEXT:
            Console.print("  " + line)
        Console.print()
        for repo, plan in plans.items():
            Console.print(f"  {Console.path(str(repo))}")
            for path, text in plan.items():
                verb = "delete" if text is None else ("update" if path.exists() else "create")
                Console.print(f"    {verb:<7} {path.relative_to(repo)}")
        Console.print()

        if dry_run:
            Console.info("Dry run: nothing changed")
            return 0
        if not yes:
            answer = prompt(MIGRATE_AGENTS_MD_CONFIRM, "  Migrate these repos? [y/N]: ", type="yes_no", default=False)
            if answer.strip().lower() != "y":
                Console.skip("Nothing changed")
                return 0

        for repo, plan in plans.items():
            cs = _apply_plan(repo, plan)
            if cs is not None:
                Console.success(f"{repo.name}: migrated (undo: {Console.cmd('aec rollback apply ' + cs.id)})")

    if dry_run:
        return 0
    if tidy_config is not None:
        ok = True
        for repo in repos:
            if detect_layout(repo) == "agents-md":
                ok = _tidy(repo, tidy_with, tidy_config, yes) and ok
        return 0 if ok else 1
    if plans:
        agents = sorted(_headless_agents())
        if agents:
            Console.info(
                "Optional: have an agent remove duplication: "
                + Console.cmd(f"aec migrate agents-md --tidy-with {agents[0]}")
                + (f" (also: {', '.join(agents[1:])})" if len(agents) > 1 else "")
            )
    return 0
