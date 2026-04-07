"""Main CLI dispatcher for aec."""

import sys
from typing import Optional

# Check for typer, fall back to argparse if not available
try:
    import typer
    from typing_extensions import Annotated
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from . import __version__
from .lib import Console
from .commands.deprecation import deprecation_warning

if HAS_TYPER:
    # Typer-based CLI (preferred)
    app = typer.Typer(
        name="aec",
        help="agents-environment-config CLI - Manage AI agent configurations",
        add_completion=False,
        no_args_is_help=True,
    )

    @app.callback(invoke_without_command=True)
    def _cli_callback(ctx: typer.Context):
        """Pre-command hook: check for unanswered preferences and register update check."""
        if ctx.invoked_subcommand is None:
            return
        from .lib.preferences import check_pending_preferences
        check_pending_preferences()

        import atexit
        from .lib.version_check import maybe_check_for_update
        atexit.register(maybe_check_for_update)

    # ------------------------------------------------------------------ #
    #  New flat top-level commands                                        #
    # ------------------------------------------------------------------ #

    @app.command("update")
    def update_cmd():
        """Fetch latest sources and report what's outdated."""
        from .commands.update import run_update
        run_update()

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
        item_type: str = typer.Argument(..., help="Type: skill, rule, or agent"),
        name: str = typer.Argument(..., help="Name of the item to install"),
        global_flag: bool = typer.Option(False, "-g", "--global", help="Install globally"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    ):
        """Install a skill, rule, or agent."""
        from .commands.install_cmd import run_install
        run_install(item_type=item_type, name=name, global_flag=global_flag, yes=yes)

    @app.command("uninstall")
    def uninstall_cmd(
        item_type: str = typer.Argument(..., help="Type: skill, rule, or agent"),
        name: str = typer.Argument(..., help="Name of the item to uninstall"),
        global_flag: bool = typer.Option(False, "-g", "--global", help="Uninstall globally"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    ):
        """Remove an installed skill, rule, or agent."""
        from .commands.uninstall import run_uninstall
        run_uninstall(item_type=item_type, name=name, global_flag=global_flag, yes=yes)

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
        item_type: str = typer.Argument(..., help="Type: skill, rule, or agent"),
        name: str = typer.Argument(..., help="Name of the item"),
    ):
        """Show detailed metadata for an installed item."""
        from .commands.info import run_info
        run_info(item_type=item_type, name=name)

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

    # --- existing top-level commands ---
    from .commands import discover
    app.command("discover")(discover.discover_cmd)

    @app.command("doctor")
    def doctor_cmd():
        """Check installation health."""
        from .commands.doctor import run_doctor
        run_doctor()

    @app.command("version")
    def version_cmd():
        """Show version information."""
        Console.print(f"aec version {__version__}")

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

else:
    # Argparse fallback (no external dependencies)
    import argparse

    def app():
        """Argparse-based CLI fallback."""
        parser = argparse.ArgumentParser(
            prog="aec",
            description="agents-environment-config CLI - Manage AI agent configurations",
        )
        parser.add_argument(
            "--version", "-V",
            action="version",
            version=f"aec {__version__}",
        )

        subparsers = parser.add_subparsers(dest="command", help="Commands")

        # ---------------------------------------------------------- #
        #  New flat top-level commands                                #
        # ---------------------------------------------------------- #

        # update
        subparsers.add_parser("update", help="Fetch latest sources and report outdated items")

        # upgrade
        upgrade_parser = subparsers.add_parser("upgrade", help="Apply available upgrades")
        upgrade_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
        upgrade_parser.add_argument("--dry-run", action="store_true", help="Preview without applying")

        # install
        install_new = subparsers.add_parser("install", help="Install a skill, rule, or agent")
        install_new.add_argument("item_type", help="Type: skill, rule, or agent")
        install_new.add_argument("name", help="Name of the item")
        install_new.add_argument("-g", "--global", dest="global_flag", action="store_true", help="Install globally")
        install_new.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

        # uninstall
        uninstall_parser = subparsers.add_parser("uninstall", help="Remove a skill, rule, or agent")
        uninstall_parser.add_argument("item_type", help="Type: skill, rule, or agent")
        uninstall_parser.add_argument("name", help="Name of the item")
        uninstall_parser.add_argument("-g", "--global", dest="global_flag", action="store_true", help="Uninstall globally")
        uninstall_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

        # list
        list_parser = subparsers.add_parser("list", help="Show installed items")
        list_parser.add_argument("--type", dest="type_filter", help="Filter by type")
        list_parser.add_argument("--scope", dest="scope_filter", help="Filter by scope")
        list_parser.add_argument("--all", dest="show_all", action="store_true", help="Show across all repos")

        # search
        search_parser = subparsers.add_parser("search", help="Search available items")
        search_parser.add_argument("term", help="Search term")
        search_parser.add_argument("--type", dest="type_filter", help="Filter by type")

        # outdated
        outdated_parser = subparsers.add_parser("outdated", help="Show items with available upgrades")
        outdated_parser.add_argument("--type", dest="type_filter", help="Filter by type")
        outdated_parser.add_argument("--all", dest="show_all", action="store_true", help="Check all repos")

        # info
        info_parser = subparsers.add_parser("info", help="Show detailed item metadata")
        info_parser.add_argument("item_type", help="Type: skill, rule, or agent")
        info_parser.add_argument("name", help="Name of the item")

        # setup
        setup_parser = subparsers.add_parser("setup", help="Set up a project or all projects")
        setup_parser.add_argument("path", nargs="?", default=None, help="Project path")
        setup_parser.add_argument("--all", dest="setup_all", action="store_true", help="Set up all projects")
        setup_parser.add_argument("--skip-raycast", action="store_true", help="Skip Raycast scripts")
        setup_parser.add_argument("--dry-run", action="store_true", help="Preview without changes")

        # untrack
        untrack_parser = subparsers.add_parser("untrack", help="Stop tracking a repository")
        untrack_parser.add_argument("path", help="Project path")
        untrack_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

        # config
        config_parser = subparsers.add_parser("config", help="Manage configuration preferences")
        config_sub = config_parser.add_subparsers(dest="config_command")
        config_sub.add_parser("list", help="List preferences")
        config_set = config_sub.add_parser("set", help="Set a preference")
        config_set.add_argument("key", help="Preference key")
        config_set.add_argument("value", help="Value: 'on' or 'off'")
        config_reset = config_sub.add_parser("reset", help="Reset a preference")
        config_reset.add_argument("key", help="Preference key")

        # generate
        generate_parser = subparsers.add_parser("generate", help="Generate agent files and rules")
        generate_sub = generate_parser.add_subparsers(dest="generate_command")
        generate_sub.add_parser("rules", help="Generate .agent-rules/")
        generate_sub.add_parser("files", help="Generate agent instruction files")

        # validate
        subparsers.add_parser("validate", help="Validate rule parity")

        # prune
        prune_parser = subparsers.add_parser("prune", help="Remove stale tracking entries")
        prune_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
        prune_parser.add_argument("--dry-run", action="store_true", help="Preview without changes")

        # ports
        ports_parser = subparsers.add_parser("ports", help="Manage project port registry")
        ports_sub = ports_parser.add_subparsers(dest="ports_command")
        ports_sub.add_parser("list", help="List registered ports")
        ports_check = ports_sub.add_parser("check", help="Check ports against registry")
        ports_check.add_argument("path", nargs="?", default=".", help="Project path")
        ports_reg = ports_sub.add_parser("register", help="Register ports from .aec.json")
        ports_reg.add_argument("path", nargs="?", default=".", help="Project path")
        ports_unreg = ports_sub.add_parser("unregister", help="Unregister project ports")
        ports_unreg.add_argument("path", nargs="?", default=".", help="Project path")
        ports_sub.add_parser("validate", help="Validate registry entries")

        # discover
        discover_parser = subparsers.add_parser("discover", help="Discover repos from Raycast scripts")
        discover_parser.add_argument("--dry-run", action="store_true", help="Preview")
        discover_parser.add_argument("--auto", action="store_true", help="Add without prompting")

        # doctor
        subparsers.add_parser("doctor", help="Check installation health")

        # version
        subparsers.add_parser("version", help="Show version")

        # ---------------------------------------------------------- #
        #  Deprecated command groups (kept as shims)                  #
        # ---------------------------------------------------------- #

        # repo (deprecated)
        repo_parser = subparsers.add_parser("repo", help="[DEPRECATED] Manage repositories")
        repo_sub = repo_parser.add_subparsers(dest="repo_command")
        repo_setup = repo_sub.add_parser("setup", help="[DEPRECATED] Use `aec setup`")
        repo_setup.add_argument("path", nargs="?", default=None)
        repo_setup.add_argument("--skip-raycast", action="store_true")
        repo_sub.add_parser("list", help="[DEPRECATED] Use `aec list`")
        repo_sub.add_parser("setup-all", help="[DEPRECATED] Use `aec setup --all`")
        repo_prune = repo_sub.add_parser("prune", help="[DEPRECATED] Use `aec prune`")
        repo_prune.add_argument("--yes", "-y", action="store_true")
        repo_prune.add_argument("--dry-run", action="store_true")
        repo_update = repo_sub.add_parser("update", help="[DEPRECATED] Use `aec update`")
        repo_update.add_argument("path", nargs="?")
        repo_update.add_argument("--all", action="store_true")
        repo_update.add_argument("--dry-run", action="store_true")

        # agent-tools (deprecated)
        at_parser = subparsers.add_parser("agent-tools", help="[DEPRECATED] Manage ~/.agent-tools/")
        at_sub = at_parser.add_subparsers(dest="at_command")
        at_sub.add_parser("setup", help="[DEPRECATED] Use `aec setup`")
        at_migrate = at_sub.add_parser("migrate", help="[DEPRECATED] Use `aec upgrade`")
        at_migrate.add_argument("--dry-run", action="store_true")
        at_rollback = at_sub.add_parser("rollback", help="[DEPRECATED] Use `aec doctor`")
        at_rollback.add_argument("backup_dir")

        # rules (deprecated)
        rules_parser = subparsers.add_parser("rules", help="[DEPRECATED] Use `aec generate rules` or `aec validate`")
        rules_sub = rules_parser.add_subparsers(dest="rules_command")
        rules_sub.add_parser("generate", help="[DEPRECATED] Use `aec generate rules`")
        rules_sub.add_parser("validate", help="[DEPRECATED] Use `aec validate`")

        # files (deprecated)
        files_parser = subparsers.add_parser("files", help="[DEPRECATED] Use `aec generate files`")
        files_sub = files_parser.add_subparsers(dest="files_command")
        files_sub.add_parser("generate", help="[DEPRECATED] Use `aec generate files`")

        # skills (deprecated)
        skills_parser = subparsers.add_parser("skills", help="[DEPRECATED] Use `aec install/uninstall/list`")
        skills_sub = skills_parser.add_subparsers(dest="skills_command")
        skills_sub.add_parser("list", help="[DEPRECATED] Use `aec list --type skill`")
        skills_install = skills_sub.add_parser("install", help="[DEPRECATED] Use `aec install skill <name>`")
        skills_install.add_argument("names", nargs="+")
        skills_install.add_argument("--yes", "-y", action="store_true")
        skills_uninstall = skills_sub.add_parser("uninstall", help="[DEPRECATED] Use `aec uninstall skill <name>`")
        skills_uninstall.add_argument("names", nargs="+")
        skills_uninstall.add_argument("--yes", "-y", action="store_true")
        skills_update = skills_sub.add_parser("update", help="[DEPRECATED] Use `aec upgrade`")
        skills_update.add_argument("name", nargs="?", default=None)
        skills_update.add_argument("--yes", "-y", action="store_true")

        # preferences (deprecated)
        prefs_parser = subparsers.add_parser("preferences", help="[DEPRECATED] Use `aec config`")
        prefs_sub = prefs_parser.add_subparsers(dest="prefs_command")
        prefs_sub.add_parser("list", help="[DEPRECATED] Use `aec config list`")
        prefs_set = prefs_sub.add_parser("set", help="[DEPRECATED] Use `aec config set`")
        prefs_set.add_argument("feature")
        prefs_set.add_argument("value")
        prefs_reset = prefs_sub.add_parser("reset", help="[DEPRECATED] Use `aec config reset`")
        prefs_reset.add_argument("feature")

        # ---------------------------------------------------------- #
        #  Parse and dispatch                                         #
        # ---------------------------------------------------------- #

        args = parser.parse_args()

        if args.command is None:
            parser.print_help()
            return

        # Check for unanswered optional features
        from .lib.preferences import check_pending_preferences
        check_pending_preferences()

        import atexit
        from .lib.version_check import maybe_check_for_update
        atexit.register(maybe_check_for_update)

        # --- New flat commands ---
        if args.command == "version":
            Console.print(f"aec version {__version__}")

        elif args.command == "update":
            from .commands.update import run_update
            run_update()

        elif args.command == "upgrade":
            from .commands.upgrade import run_upgrade
            run_upgrade(yes=args.yes, dry_run=args.dry_run)

        elif args.command == "install":
            from .commands.install_cmd import run_install
            run_install(
                item_type=args.item_type, name=args.name,
                global_flag=args.global_flag, yes=args.yes,
            )

        elif args.command == "uninstall":
            from .commands.uninstall import run_uninstall
            run_uninstall(
                item_type=args.item_type, name=args.name,
                global_flag=args.global_flag, yes=args.yes,
            )

        elif args.command == "list":
            from .commands.list_cmd import run_list
            run_list(
                type_filter=args.type_filter,
                scope_filter=args.scope_filter,
                show_all=args.show_all,
            )

        elif args.command == "search":
            from .commands.search import run_search
            run_search(term=args.term, type_filter=args.type_filter)

        elif args.command == "outdated":
            from .commands.outdated import run_outdated
            run_outdated(type_filter=args.type_filter, show_all=args.show_all)

        elif args.command == "info":
            from .commands.info import run_info
            run_info(item_type=args.item_type, name=args.name)

        elif args.command == "setup":
            from .commands.setup import run_setup, run_setup_path, run_setup_all
            if args.setup_all:
                run_setup_all(skip_raycast=args.skip_raycast, dry_run=args.dry_run)
            elif args.path:
                run_setup_path(path=args.path, skip_raycast=args.skip_raycast, dry_run=args.dry_run)
            else:
                run_setup(skip_raycast=args.skip_raycast, dry_run=args.dry_run)

        elif args.command == "untrack":
            from .commands.untrack import run_untrack
            run_untrack(path=args.path, yes=args.yes)

        elif args.command == "config":
            from .commands.config_cmd import run_config_list, run_config_set, run_config_reset
            if args.config_command == "list":
                run_config_list()
            elif args.config_command == "set":
                run_config_set(key=args.key, value=args.value)
            elif args.config_command == "reset":
                run_config_reset(key=args.key)
            else:
                config_parser.print_help()

        elif args.command == "generate":
            from .commands.generate import run_generate_rules, run_generate_files
            if args.generate_command == "rules":
                run_generate_rules()
            elif args.generate_command == "files":
                run_generate_files()
            else:
                generate_parser.print_help()

        elif args.command == "validate":
            from .commands.generate import run_validate
            run_validate()

        elif args.command == "prune":
            from .commands.generate import run_prune
            run_prune(yes=args.yes, dry_run=args.dry_run)

        elif args.command == "discover":
            from .commands import discover as discover_cmd
            discover_cmd.discover(dry_run=args.dry_run, auto=args.auto)

        elif args.command == "doctor":
            from .commands.doctor import run_doctor
            run_doctor()

        elif args.command == "ports":
            from .commands.ports import (
                run_ports_list, run_ports_check, run_ports_register,
                run_ports_unregister, run_ports_validate,
            )
            if args.ports_command == "list":
                run_ports_list()
            elif args.ports_command == "check":
                run_ports_check(args.path)
            elif args.ports_command == "register":
                run_ports_register(args.path)
            elif args.ports_command == "unregister":
                run_ports_unregister(args.path)
            elif args.ports_command == "validate":
                run_ports_validate()
            else:
                ports_parser.print_help()

        # --- Deprecated command groups ---
        elif args.command == "repo":
            from .commands import repo as repo_cmd
            if args.repo_command == "setup":
                deprecation_warning("aec repo setup", "aec setup")
                repo_cmd.setup(args.path, args.skip_raycast)
            elif args.repo_command == "setup-all":
                deprecation_warning("aec repo setup-all", "aec setup --all")
                repo_cmd.setup_all()
            elif args.repo_command == "list":
                deprecation_warning("aec repo list", "aec list --scope global")
                repo_cmd.list_repos()
            elif args.repo_command == "prune":
                deprecation_warning("aec repo prune", "aec prune")
                repo_cmd.prune(args.yes, args.dry_run)
            elif args.repo_command == "update":
                deprecation_warning("aec repo update", "aec update")
                repo_cmd.update(args.path, args.dry_run, getattr(args, 'all', False))
            else:
                repo_parser.print_help()

        elif args.command == "agent-tools":
            from .commands import agent_tools as at_cmd
            if args.at_command == "setup":
                deprecation_warning("aec agent-tools setup", "aec setup")
                at_cmd.setup()
            elif args.at_command == "migrate":
                deprecation_warning("aec agent-tools migrate", "aec upgrade")
                at_cmd.migrate(args.dry_run)
            elif args.at_command == "rollback":
                deprecation_warning("aec agent-tools rollback", "aec doctor")
                at_cmd.rollback(args.backup_dir)
            else:
                at_parser.print_help()

        elif args.command == "rules":
            if args.rules_command == "generate":
                deprecation_warning("aec rules generate", "aec generate rules")
                from .commands.generate import run_generate_rules
                run_generate_rules()
            elif args.rules_command == "validate":
                deprecation_warning("aec rules validate", "aec validate")
                from .commands.generate import run_validate
                run_validate()
            else:
                rules_parser.print_help()

        elif args.command == "files":
            if args.files_command == "generate":
                deprecation_warning("aec files generate", "aec generate files")
                from .commands.generate import run_generate_files
                run_generate_files()
            else:
                files_parser.print_help()

        elif args.command == "skills":
            from .commands import skills as skills_cmd
            if args.skills_command == "list":
                deprecation_warning("aec skills list", "aec list --type skill")
                skills_cmd.list_skills()
            elif args.skills_command == "install":
                deprecation_warning("aec skills install", "aec install skill <name>")
                skills_cmd.install_skills(names=args.names, yes=args.yes)
            elif args.skills_command == "uninstall":
                deprecation_warning("aec skills uninstall", "aec uninstall skill <name>")
                skills_cmd.uninstall_skills(names=args.names, yes=args.yes)
            elif args.skills_command == "update":
                deprecation_warning("aec skills update", "aec upgrade")
                names = [args.name] if args.name else None
                skills_cmd.update_skills(names=names, yes=args.yes)
            else:
                skills_parser.print_help()

        elif args.command == "preferences":
            if args.prefs_command == "list":
                deprecation_warning("aec preferences list", "aec config list")
                from .commands.config_cmd import run_config_list
                run_config_list()
            elif args.prefs_command == "set":
                deprecation_warning("aec preferences set", "aec config set")
                from .commands.config_cmd import run_config_set
                run_config_set(key=args.feature, value=args.value)
            elif args.prefs_command == "reset":
                deprecation_warning("aec preferences reset", "aec config reset")
                from .commands.config_cmd import run_config_reset
                run_config_reset(key=args.feature)
            else:
                prefs_parser.print_help()


def main():
    """Entry point."""
    if HAS_TYPER:
        app()
    else:
        app()


if __name__ == "__main__":
    main()
