"""Main CLI dispatcher for aec."""

import sys
from typing import List, Optional

import typer

from . import __version__
from .lib import Console
from .commands.deprecation import deprecation_warning


def _apply_prompt_globals(answers_path, non_interactive: bool, defaults: bool) -> None:
    """Wire the headless-prompt global options into the prompt seam.

    Called once from the root callback, before any command runs.
    """
    from .lib.prompts import load_answers_file, set_answers, set_mode

    if answers_path:
        try:
            set_answers(load_answers_file(answers_path))
        except (FileNotFoundError, ValueError) as exc:
            Console.error(str(exc))
            raise SystemExit(2) from exc
    else:
        import os

        inline = os.environ.get("AEC_ANSWERS")
        if inline:
            try:
                set_answers(load_answers_file(inline))
            except (FileNotFoundError, ValueError) as exc:
                Console.error(f"AEC_ANSWERS: {exc}")
                raise SystemExit(2) from exc

    set_mode(
        non_interactive=True if non_interactive else None,
        use_defaults=True if defaults else None,
    )


app = typer.Typer(
    name="aec",
    help="agents-environment-config CLI - Manage AI agent configurations",
    add_completion=False,
    no_args_is_help=True,
)

def _run_org_config_gate() -> None:
    """Per-invocation org-config propagation gate. Best-effort: surfaces key
    rotation warnings/lockouts but never breaks the command being run."""
    try:
        from .lib.org_config import OrgPaths
        from .lib.org_config.propagation import run_propagation_gate
    except ImportError:
        return  # org-configs extra not installed
    try:
        paths = OrgPaths.default()
        if not paths.orgs_dir.exists():
            return
        result = run_propagation_gate(paths)
    except Exception:  # noqa: BLE001 - the gate must never break other commands
        return
    for message in result.warnings:
        Console.warning(message)
    try:
        from .commands.org import pending_fix, pending_orgs
        pending = pending_orgs(paths)
    except Exception:  # noqa: BLE001 - same rule as the gate above
        return
    for st in pending:
        Console.warning(pending_fix(st))

@app.callback(invoke_without_command=True)
def _cli_callback(
    ctx: typer.Context,
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Capture errors to ~/.agents-environment-config/logs/aec-debug.log and print the traceback.",
    ),
    answers: str = typer.Option(
        None,
        "--answers",
        metavar="PATH",
        help="JSON file of {prompt_id: value} answers (see `aec prompts template`).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Never prompt; fail with the prompt ID if an answer is missing.",
    ),
    defaults: bool = typer.Option(
        False,
        "--defaults",
        help="Accept each prompt's declared default when no answer is supplied.",
    ),
):
    """Pre-command hook: check for unanswered preferences and register update check."""
    if debug:
        from .lib.debug import enable_debug
        enable_debug()
    _apply_prompt_globals(answers, non_interactive, defaults)
    if ctx.invoked_subcommand is None:
        return
    from .lib import feedback as _feedback
    _feedback.current_command = ctx.invoked_subcommand
    from .lib.preferences import check_pending_preferences
    check_pending_preferences()

    _run_org_config_gate()

    import atexit
    from .lib.version_check import maybe_check_for_update
    atexit.register(maybe_check_for_update)
    atexit.register(_feedback.maybe_notify)

# ------------------------------------------------------------------ #
#  New flat top-level commands                                        #
# ------------------------------------------------------------------ #

@app.command("update")
def update_cmd():
    """Fetch latest sources and report what's outdated."""
    from .commands.org import EXIT_PENDING
    from .commands.update import run_update
    if run_update():
        raise typer.Exit(EXIT_PENDING)

@app.command("upgrade")
def upgrade_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without applying"),
):
    """Apply available upgrades to installed items."""
    from .commands.upgrade import run_upgrade
    run_upgrade(yes=yes, dry_run=dry_run)

@app.command("install")
def install_cmd(
    item_type: Optional[str] = typer.Argument(None, help="Type: skill, rule, agent, mcp, or plugin"),
    name: Optional[str] = typer.Argument(None, help="Name of the item to install"),
    global_flag: bool = typer.Option(False, "-g", "--global", help="Install globally"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    org_config: Optional[str] = typer.Option(
        None,
        "--org-config",
        help="Enroll an org config (local path or https url) and apply its policy",
    ),
    allow_unsigned: bool = typer.Option(
        False, "--allow-unsigned", help="Allow an unsigned --org-config source"
    ),
    allow_dormant_hooks: bool = typer.Option(
        False, "--allow-dormant-hooks",
        help="Allow installing a hook-bearing skill globally (hooks stay dormant)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview full setup without making changes (bare `aec install`)",
    ),
):
    """Run full setup (no arguments), install a skill, rule, agent, or MCP server,
    or apply an org config with --org-config."""
    if org_config:
        from .commands.org import perform_enroll
        from .lib.org_config import OrgPaths
        from .lib.org_config.apply import apply_org_policy

        perform_enroll(org_config, allow_unsigned=allow_unsigned, yes=yes)
        confirm = (lambda _policy: True) if yes else None
        apply_org_policy(OrgPaths.default(), confirm=confirm)
        return
    if not item_type and not name:
        from .commands.install import install
        install(dry_run=dry_run)
        return
    if not item_type or not name:
        Console.error("install requires <type> <name> (or no arguments for full setup)")
        raise typer.Exit(code=2)
    from .commands.install_cmd import run_install
    run_install(item_type=item_type, name=name, global_flag=global_flag, yes=yes,
                allow_dormant_hooks=allow_dormant_hooks)

@app.command("uninstall")
def uninstall_cmd(
    item_type: str = typer.Argument(..., help="Type: skill, rule, agent, mcp, or plugin"),
    name: str = typer.Argument(..., help="Name of the item to uninstall"),
    global_flag: bool = typer.Option(False, "-g", "--global", help="Uninstall globally"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    repos: Optional[str] = typer.Option(
        None, "--repos",
        help="For a global uninstall, also remove repo-scoped installs: "
             "all | none | comma-separated paths (default: none)",
    ),
):
    """Remove an installed skill, rule, or agent."""
    from .commands.uninstall import run_uninstall
    run_uninstall(item_type=item_type, name=name, global_flag=global_flag,
                  yes=yes, repos=repos)

@app.command("list")
def list_cmd(
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by type"),
    scope_filter: Optional[str] = typer.Option(None, "--scope", help="Filter by scope"),
    show_all: bool = typer.Option(False, "--all", help="Show items across all tracked repos"),
):
    """Show installed items."""
    from .commands.list_cmd import run_list
    run_list(type_filter=type_filter, scope_filter=scope_filter, show_all=show_all)

@app.command("search")
def search_cmd(
    term: str = typer.Argument(..., help="Search term"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by type"),
):
    """Search available items."""
    from .commands.search import run_search
    run_search(term=term, type_filter=type_filter)

@app.command("outdated")
def outdated_cmd(
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by type"),
    show_all: bool = typer.Option(False, "--all", help="Check all tracked repos"),
):
    """Show items with available upgrades."""
    from .commands.outdated import run_outdated
    run_outdated(type_filter=type_filter, show_all=show_all)

@app.command("info")
def info_cmd(
    item_type: str = typer.Argument(..., help="Type: skill, rule, agent, mcp, or plugin"),
    name: str = typer.Argument(..., help="Name of the item"),
):
    """Show detailed metadata for an installed item."""
    from .commands.info import run_info
    run_info(item_type=item_type, name=name)

@app.command("export")
def export_cmd(
    out: Optional[str] = typer.Option(None, "--out", "-o", help="Write manifest to FILE (default: stdout)"),
    latest: bool = typer.Option(False, "--latest", help="Record versions as 'latest' instead of pinning"),
    no_repos: bool = typer.Option(False, "--no-repos", help="Export global scope only"),
):
    """Export the current setup to a portable manifest file."""
    from .commands.export_cmd import run_export
    run_export(out=out, latest=latest, include_repos=not no_repos)

@app.command("apply")
def apply_cmd(
    file: str = typer.Argument(..., help="Path to a portable manifest file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without making changes"),
    latest: bool = typer.Option(False, "--latest", help="Install latest catalog versions"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip prompts (plugins apply non-interactively)"),
):
    """Apply a portable manifest - reproduce its setup on this machine."""
    from .commands.apply_cmd import run_apply
    run_apply(file=file, dry_run=dry_run, latest=latest, yes=yes)

@app.command("setup")
def setup_cmd(
    path: Optional[str] = typer.Argument(None, help="Project path to set up"),
    all_flag: bool = typer.Option(False, "--all", help="Set up all projects"),
    skip_raycast: bool = typer.Option(False, "--skip-raycast", help="Skip Raycast script creation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without making changes"),
):
    """Set up a project or all projects."""
    from .commands.setup import run_setup, run_setup_path, run_setup_all
    if all_flag:
        run_setup_all(skip_raycast=skip_raycast, dry_run=dry_run)
    elif path:
        run_setup_path(path=path, skip_raycast=skip_raycast, dry_run=dry_run)
    else:
        run_setup(skip_raycast=skip_raycast, dry_run=dry_run)

@app.command("untrack")
def untrack_cmd(
    path: str = typer.Argument(..., help="Project path to stop tracking"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Stop tracking a repository."""
    from .commands.untrack import run_untrack
    run_untrack(path=path, yes=yes)

# --- config subcommands ---
config_app = typer.Typer(help="Manage configuration preferences")
app.add_typer(config_app, name="config")

@config_app.command("list")
def config_list_cmd():
    """List all configuration preferences."""
    from .commands.config_cmd import run_config_list
    run_config_list()

@config_app.command("set")
def config_set_cmd(
    key: str = typer.Argument(..., help="Preference key"),
    value: str = typer.Argument(..., help="Value: 'on' or 'off'"),
):
    """Set a configuration preference."""
    from .commands.config_cmd import run_config_set
    run_config_set(key=key, value=value)

@config_app.command("reset")
def config_reset_cmd(
    key: str = typer.Argument(..., help="Preference key to reset"),
):
    """Reset a configuration preference to default."""
    from .commands.config_cmd import run_config_reset
    run_config_reset(key=key)

# --- generate subcommands ---
generate_app = typer.Typer(help="Generate agent files and rules")
app.add_typer(generate_app, name="generate")

@generate_app.command("rules")
def generate_rules_cmd():
    """Generate .agent-rules/ from source rules."""
    from .commands.generate import run_generate_rules
    run_generate_rules()

@generate_app.command("files")
def generate_files_cmd():
    """Generate agent instruction files in templates/."""
    from .commands.generate import run_generate_files
    run_generate_files()

@app.command("validate")
def validate_cmd():
    """Validate rule parity across agents."""
    from .commands.generate import run_validate
    run_validate()

@app.command("prune")
def prune_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without making changes"),
):
    """Remove stale tracking entries."""
    from .commands.generate import run_prune
    run_prune(yes=yes, dry_run=dry_run)

# --- ports subcommands ---
ports_app = typer.Typer(help="Manage project port registry")
app.add_typer(ports_app, name="ports")

@ports_app.command("list")
def ports_list_cmd():
    """Show all registered ports grouped by project."""
    from .commands.ports import run_ports_list
    run_ports_list()

@ports_app.command("check")
def ports_check_cmd(
    path: str = typer.Argument(".", help="Project path containing .aec.json"),
):
    """Check a project's ports against the registry."""
    from .commands.ports import run_ports_check
    run_ports_check(path)

@ports_app.command("register")
def ports_register_cmd(
    path: str = typer.Argument(".", help="Project path containing .aec.json"),
):
    """Register ports from a project's .aec.json."""
    from .commands.ports import run_ports_register
    run_ports_register(path)

@ports_app.command("unregister")
def ports_unregister_cmd(
    path: str = typer.Argument(".", help="Project path to unregister"),
):
    """Remove all port registrations for a project."""
    from .commands.ports import run_ports_unregister
    run_ports_unregister(path)

@ports_app.command("validate")
def ports_validate_cmd():
    """Scan registry for stale entries (dead paths)."""
    from .commands.ports import run_ports_validate
    run_ports_validate()

# --- test ---
test_app = typer.Typer(help="Manage test suites, scheduling, and reports")
app.add_typer(test_app, name="test")

@test_app.command("run")
def test_run_cmd(
    global_flag: bool = typer.Option(
        False, "-g", "--global",
        help="Run scheduled suites across all tracked projects",
    ),
):
    """Run test suites for the current project (or all with -g)."""
    from .commands.test_cmd import run_test_run
    run_test_run(global_flag=global_flag)

@test_app.command("schedule")
def test_schedule_cmd(
    global_flag: bool = typer.Option(
        False, "-g", "--global",
        help="Configure global daily time and OS scheduler",
    ),
    do: List[str] = typer.Option(
        None, "--do",
        help="One schedule command, repeatable; same verbs as the schedule> REPL (e.g. 'merge', '+ unit', 'r 2', 'n e2e :: npm run e2e', 'o unit,e2e', 'mv 1 2')",
    ),
    list_only: bool = typer.Option(
        False, "--list", help="Print the current schedule and exit (no prompts)"
    ),
):
    """Edit this repo's scheduled suites, or use -g for system-wide setup."""
    from .commands.test_cmd import run_test_schedule
    raise typer.Exit(
        run_test_schedule(global_flag=global_flag, commands=do, list_only=list_only)
    )

@test_app.command("status")
def test_status_cmd(
    global_flag: bool = typer.Option(False, "-g", "--global", help="Global schedule status"),
):
    """Show test configuration or global schedule status."""
    from .commands.test_cmd import run_test_status
    run_test_status(global_flag=global_flag)

@test_app.command("enable")
def test_enable_cmd():
    """Re-enable scheduled runs with the OS scheduler."""
    from .commands.test_cmd import run_test_enable
    run_test_enable()

@test_app.command("disable")
def test_disable_cmd():
    """Disable scheduled runs (keeps config)."""
    from .commands.test_cmd import run_test_disable
    run_test_disable()

@test_app.command("report")
def test_report_cmd(
    global_flag: bool = typer.Option(False, "-g", "--global", help="Full cross-project summary"),
):
    """View latest test results."""
    from .commands.test_cmd import run_test_report
    run_test_report(global_flag=global_flag)

@test_app.command("detect")
def test_detect_cmd():
    """Re-detect test frameworks and update .aec.json."""
    from .commands.test_cmd import run_test_detect
    run_test_detect()

# --- existing top-level commands ---
from .commands import discover
app.command("discover-repos")(discover.discover_cmd)

@app.command("discover")
def discover_catalog_cmd(
    global_flag: bool = typer.Option(False, "-g", "--global", help="Scan global scope"),
    rediscover: bool = typer.Option(False, "--rediscover", help="Re-surface dismissed items"),
    depth: Optional[int] = typer.Option(None, "--depth", help="Scan depth: 1=Quick, 2=Normal, 3=Deep"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Install exact matches, skip rest"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
):
    """Scan for local items similar to AEC catalog entries."""
    from .commands.discover_catalog import run_discover
    run_discover(
        global_flag=global_flag,
        rediscover=rediscover,
        depth=depth,
        yes=yes,
        dry_run=dry_run,
    )

@app.command("doctor")
def doctor_cmd():
    """Check installation health."""
    from .commands.doctor import run_doctor
    run_doctor()

@app.command("configure-agent")
def configure_agent_cmd(
    scope: Optional[str] = typer.Option(None, "--scope", help="project|global|both"),
    profile: Optional[str] = typer.Option(None, "--profile", help="conservative|balanced|permissive|custom"),
    agent_files: Optional[str] = typer.Option(None, "--agent-files", help="all|<csv>"),
    check: bool = typer.Option(False, "--check", help="Exit non-zero on drift"),
    refresh: bool = typer.Option(False, "--refresh", help="Re-render from stored config"),
    remove: bool = typer.Option(False, "--remove", help="Remove the blurb and config"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan; write nothing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
):
    """Manage the AEC agent-instruction blurb."""
    from .commands.configure_agent import run_configure_agent
    raise typer.Exit(run_configure_agent(
        scope=scope, profile=profile, agent_files=agent_files,
        check=check, refresh=refresh, remove=remove, dry_run=dry_run, yes=yes,
    ))

@app.command("version")
def version_cmd():
    """Show version information."""
    Console.print(f"aec version {__version__}")

# --- hooks ---
from .commands.hooks_cmd import hooks_app
app.add_typer(hooks_app, name="hooks")

# --- run-script (top-level; invoked from hook bodies) ---
from .commands.run_script_cmd import run_script
app.command("run-script")(run_script)

# --- feedback (hands off to the feedback-loop skill's feedback.py) ---
from .commands.feedback_cmd import feedback as feedback_cmd
app.command(
    "feedback",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True,
                      "help_option_names": []},
)(feedback_cmd)

# ------------------------------------------------------------------ #
#  Deprecated command groups (kept as shims)                          #
# ------------------------------------------------------------------ #

# --- repo (deprecated) ---
repo_app = typer.Typer(
    help="[DEPRECATED] Use top-level commands instead",
    deprecated=True,
)
app.add_typer(repo_app, name="repo")

@repo_app.command("list")
def repo_list_deprecated():
    """[DEPRECATED] Use `aec list` instead."""
    deprecation_warning("aec repo list", "aec list --scope global")
    from .commands.repo import list_repos
    list_repos()

@repo_app.command("setup")
def repo_setup_deprecated(
    path: Optional[str] = typer.Argument(None, help="Project name or path"),
    skip_raycast: bool = typer.Option(False, "--skip-raycast"),
):
    """[DEPRECATED] Use `aec setup` instead."""
    deprecation_warning("aec repo setup", "aec setup")
    from .commands.repo import setup
    setup(path, skip_raycast)

@repo_app.command("setup-all")
def repo_setup_all_deprecated():
    """[DEPRECATED] Use `aec setup --all` instead."""
    deprecation_warning("aec repo setup-all", "aec setup --all")
    from .commands.repo import setup_all
    setup_all()

@repo_app.command("update")
def repo_update_deprecated(
    path: Optional[str] = typer.Argument(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
    update_all: bool = typer.Option(False, "--all"),
):
    """[DEPRECATED] Use `aec update` instead."""
    deprecation_warning("aec repo update", "aec update")
    from .commands.repo import update
    update(path, dry_run, update_all)

@repo_app.command("prune")
def repo_prune_deprecated(
    yes: bool = typer.Option(False, "--yes", "-y"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """[DEPRECATED] Use `aec prune` instead."""
    deprecation_warning("aec repo prune", "aec prune")
    from .commands.repo import prune
    prune(yes, dry_run)

# --- skills (deprecated) ---
skills_app = typer.Typer(
    help="[DEPRECATED] Use `aec install/uninstall/list` instead",
    deprecated=True,
)
app.add_typer(skills_app, name="skills")

@skills_app.command("list")
def skills_list_deprecated():
    """[DEPRECATED] Use `aec list --type skill` instead."""
    deprecation_warning("aec skills list", "aec list --type skill")
    from .commands.skills import list_skills
    list_skills()

@skills_app.command("install")
def skills_install_deprecated(
    names: list[str] = typer.Argument(..., help="Skill name(s)"),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """[DEPRECATED] Use `aec install skill <name>` instead."""
    deprecation_warning("aec skills install", "aec install skill <name>")
    from .commands.skills import install_skills
    install_skills(names=names, yes=yes)

@skills_app.command("uninstall")
def skills_uninstall_deprecated(
    names: list[str] = typer.Argument(..., help="Skill name(s)"),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """[DEPRECATED] Use `aec uninstall skill <name>` instead."""
    deprecation_warning("aec skills uninstall", "aec uninstall skill <name>")
    from .commands.skills import uninstall_skills
    uninstall_skills(names=names, yes=yes)

@skills_app.command("update")
def skills_update_deprecated(
    name: Optional[str] = typer.Argument(None),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """[DEPRECATED] Use `aec upgrade` instead."""
    deprecation_warning("aec skills update", "aec upgrade")
    from .commands.skills import update_skills
    names = [name] if name else None
    update_skills(names=names, yes=yes)

# --- agent-tools (deprecated) ---
agent_tools_app = typer.Typer(
    help="[DEPRECATED] Use `aec setup` or `aec doctor` instead",
    deprecated=True,
)
app.add_typer(agent_tools_app, name="agent-tools")

@agent_tools_app.command("setup")
def at_setup_deprecated(
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """[DEPRECATED] Use `aec setup` instead."""
    deprecation_warning("aec agent-tools setup", "aec setup")
    from .commands.agent_tools import setup
    setup(dry_run=dry_run)

@agent_tools_app.command("migrate")
def at_migrate_deprecated(
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """[DEPRECATED] Use `aec upgrade` instead."""
    deprecation_warning("aec agent-tools migrate", "aec upgrade")
    from .commands.agent_tools import migrate
    migrate(dry_run=dry_run)

@agent_tools_app.command("rollback")
def at_rollback_deprecated(
    backup_dir: str = typer.Argument(..., help="Backup directory"),
):
    """[DEPRECATED] No direct replacement."""
    deprecation_warning("aec agent-tools rollback", "aec doctor")
    from .commands.agent_tools import rollback
    rollback(backup_dir)

# --- rules (deprecated) ---
rules_app = typer.Typer(
    help="[DEPRECATED] Use `aec generate rules` or `aec validate` instead",
    deprecated=True,
)
app.add_typer(rules_app, name="rules")

@rules_app.command("generate")
def rules_generate_deprecated():
    """[DEPRECATED] Use `aec generate rules` instead."""
    deprecation_warning("aec rules generate", "aec generate rules")
    from .commands.generate import run_generate_rules
    run_generate_rules()

@rules_app.command("validate")
def rules_validate_deprecated():
    """[DEPRECATED] Use `aec validate` instead."""
    deprecation_warning("aec rules validate", "aec validate")
    from .commands.generate import run_validate
    run_validate()

# --- files (deprecated) ---
files_app = typer.Typer(
    help="[DEPRECATED] Use `aec generate files` instead",
    deprecated=True,
)
app.add_typer(files_app, name="files")

@files_app.command("generate")
def files_generate_deprecated():
    """[DEPRECATED] Use `aec generate files` instead."""
    deprecation_warning("aec files generate", "aec generate files")
    from .commands.generate import run_generate_files
    run_generate_files()

# --- prompts (headless discovery) ---
prompts_app = typer.Typer(
    help="Discover, template, and validate the prompts AEC can ask",
)
app.add_typer(prompts_app, name="prompts")

@prompts_app.command("list")
def prompts_list_cmd(
    command: str = typer.Option(
        None, "--command", "-c", help="Only show prompts for commands matching this text"
    ),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output"),
):
    """Show every prompt AEC can ask, with its ID, type, and default."""
    from .commands.prompts_cmd import run_prompts_list
    run_prompts_list(command=command, json_out=json_output)

@prompts_app.command("template")
def prompts_template_cmd(
    command: str = typer.Option(
        None, "--command", "-c", help="Only include prompts for commands matching this text"
    ),
    output: str = typer.Option(None, "--output", "-o", help="Write to this file instead of stdout"),
):
    """Emit a skeleton answers file for use with --answers."""
    from .commands.prompts_cmd import run_prompts_template
    run_prompts_template(command=command, output=output)

@prompts_app.command("check")
def prompts_check_cmd(
    answers_file: str = typer.Argument(..., help="Answers file to validate"),
):
    """Validate an answers file against the prompt catalog."""
    from .commands.prompts_cmd import run_prompts_check
    raise typer.Exit(run_prompts_check(answers_file))

# --- org (phase 1) ---
from .commands.org import org_app
app.add_typer(org_app, name="org", help="Manage organization configurations")

# --- preferences (deprecated) ---
prefs_app = typer.Typer(
    help="[DEPRECATED] Use `aec config` instead",
    deprecated=True,
)
app.add_typer(prefs_app, name="preferences")

@prefs_app.command("list")
def prefs_list_deprecated():
    """[DEPRECATED] Use `aec config list` instead."""
    deprecation_warning("aec preferences list", "aec config list")
    from .commands.config_cmd import run_config_list
    run_config_list()

@prefs_app.command("set")
def prefs_set_deprecated(
    feature: str = typer.Argument(..., help="Feature name"),
    value: str = typer.Argument(..., help="'on' or 'off'"),
):
    """[DEPRECATED] Use `aec config set` instead."""
    deprecation_warning("aec preferences set", "aec config set")
    from .commands.config_cmd import run_config_set
    run_config_set(key=feature, value=value)

@prefs_app.command("reset")
def prefs_reset_deprecated(
    feature: str = typer.Argument(..., help="Feature name"),
):
    """[DEPRECATED] Use `aec config reset` instead."""
    deprecation_warning("aec preferences reset", "aec config reset")
    from .commands.config_cmd import run_config_reset
    run_config_reset(key=feature)


def main():
    """Entry point with global error capture.

    Without --debug: print a friendly message and exit 1, no traceback.
    With --debug or AEC_DEBUG=1: write a redacted report to the debug log
    and re-print the traceback so it can be copied into a GitHub issue.
    """
    from .lib import debug as _debug

    if _debug.debug_from_env_or_argv():
        _debug.enable_debug()
        # Strip --debug so it can appear before OR after the subcommand
        # without confusing typer's subcommand parsing.
        sys.argv = [a for a in sys.argv if a != "--debug"]
    _run()


def _report(exc) -> None:
    """Print an AecError: the cause, the tool's output, and numbered fix steps."""
    Console.error(exc.message)
    if exc.detail:
        Console.print("")
        Console.print("  Output:")
        for line in exc.detail.splitlines()[-8:]:
            Console.print(f"    {line}")
    if exc.fix:
        Console.print("")
        Console.print("  To fix:")
        for n, step in enumerate(exc.fix, 1):
            Console.print(f"    {n}. {step}")


def _remedy_accepted(remedy) -> bool:
    """Ask before AEC fixes its own checkout; no answer available means no."""
    from .lib.prompts import PromptUnanswered

    Console.print("")
    try:
        return remedy.confirm()
    except PromptUnanswered:
        return False  # headless: the printed steps are the answer


def _run(retried: bool = False) -> None:
    """Run the CLI once; an accepted AecError remedy re-runs it one time."""
    from .lib import debug as _debug
    from .lib.errors import AecError as _AecError
    from .lib.prompts import PromptInvalidAnswer as _PromptInvalidAnswer
    from .lib.prompts import PromptUnanswered as _PromptUnanswered
    from .lib.prompts import env_var_name as _prompt_env_var

    try:
        app()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        Console.print("\nAborted.")
        sys.exit(130)
    except _PromptUnanswered as exc:
        from .lib.feedback import capture as _capture, prompt_label as _prompt_label
        _capture("medium", f"run stopped on unanswered prompt {_prompt_label(exc.prompt_id)}")
        # Not a bug — the run needed an answer nobody supplied. Tell the caller
        # exactly which key to add rather than burying it in a debug report.
        Console.error(f"Unanswered prompt: {exc.prompt_id}")
        Console.print(f"  {exc.reason}")
        Console.print(f"  Supply it with: --answers FILE (key {exc.prompt_id!r})")
        Console.print(f"  or the environment variable {_prompt_env_var(exc.prompt_id)}")
        if not exc.sensitive:
            Console.print("  Run `aec prompts list` to see every prompt this command can ask.")
        sys.exit(2)
    except _AecError as exc:
        from .lib.feedback import capture as _capture
        _capture("medium", f"{type(exc).__name__}: {exc.message}")
        # A known cause with user-fixable steps: say what to do, not "file an issue".
        _report(exc)
        if exc.remedy and not retried and _remedy_accepted(exc.remedy):
            try:
                Console.success(exc.remedy.apply())
            except _AecError as failed:
                _report(failed)
                sys.exit(1)
            Console.print("Retrying...")
            return _run(retried=True)
        sys.exit(1)
    except _PromptInvalidAnswer as exc:
        Console.error(f"Invalid answer for prompt: {exc.prompt_id}")
        Console.print(f"  {exc.value!r} is not a valid {exc.expected}")
        sys.exit(2)
    except BaseException as exc:
        from .lib.feedback import capture as _capture, crash_summary as _crash_summary
        _capture("high", _crash_summary(exc))
        try:
            log_path = _debug.log_exception(exc)
        except Exception:
            log_path = None
        if _debug.is_debug():
            import traceback as _tb
            _tb.print_exception(type(exc), exc, exc.__traceback__)
            if log_path is not None:
                Console.print("")
                Console.print(_debug.debug_error_message(log_path))
        else:
            Console.print("")
            Console.print(_debug.friendly_error_message(log_path))
        sys.exit(1)


if __name__ == "__main__":
    main()
