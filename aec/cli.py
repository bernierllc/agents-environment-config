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

if HAS_TYPER:
    # Typer-based CLI (preferred)
    app = typer.Typer(
        name="aec",
        help="agents-environment-config CLI - Manage AI agent configurations",
        add_completion=False,
        no_args_is_help=True,
    )

    # Import and register command groups
    from .commands import repo, agent_tools, rules, install

    app.add_typer(repo.app, name="repo", help="Manage project repositories")
    app.add_typer(agent_tools.app, name="agent-tools", help="Manage ~/.agent-tools/ directory")
    app.add_typer(rules.app, name="rules", help="Manage agent rules")

    # Register top-level commands
    app.command("install")(install.install)

    @app.command("version")
    def version():
        """Show version information."""
        Console.print(f"aec version {__version__}")

    @app.command("doctor")
    def doctor():
        """Check installation health."""
        from .commands.doctor import run_doctor
        run_doctor()

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

        # repo commands
        repo_parser = subparsers.add_parser("repo", help="Manage project repositories")
        repo_sub = repo_parser.add_subparsers(dest="repo_command")

        repo_setup = repo_sub.add_parser("setup", help="Setup a project with agent files")
        repo_setup.add_argument("path", help="Project name or path")
        repo_setup.add_argument("--skip-raycast", action="store_true")

        repo_sub.add_parser("list", help="List tracked repositories")

        repo_update = repo_sub.add_parser("update", help="Update repositories")
        repo_update.add_argument("path", nargs="?", help="Specific project to update")
        repo_update.add_argument("--all", action="store_true", help="Update all repos")
        repo_update.add_argument("--dry-run", action="store_true")

        # agent-tools commands
        at_parser = subparsers.add_parser("agent-tools", help="Manage ~/.agent-tools/")
        at_sub = at_parser.add_subparsers(dest="at_command")
        at_sub.add_parser("setup", help="Create ~/.agent-tools/ structure")
        at_migrate = at_sub.add_parser("migrate", help="Migrate from old structure")
        at_migrate.add_argument("--dry-run", action="store_true")
        at_rollback = at_sub.add_parser("rollback", help="Rollback migration")
        at_rollback.add_argument("backup_dir", help="Backup directory")

        # rules commands
        rules_parser = subparsers.add_parser("rules", help="Manage agent rules")
        rules_sub = rules_parser.add_subparsers(dest="rules_command")
        rules_sub.add_parser("generate", help="Generate .agent-rules/")
        rules_sub.add_parser("validate", help="Validate rule parity")

        # Top-level commands
        subparsers.add_parser("install", help="Full setup")
        subparsers.add_parser("doctor", help="Check installation health")
        subparsers.add_parser("version", help="Show version")

        args = parser.parse_args()

        if args.command is None:
            parser.print_help()
            return

        # Dispatch to command handlers
        from .commands import repo as repo_cmd
        from .commands import agent_tools as at_cmd
        from .commands import rules as rules_cmd
        from .commands import install as install_cmd
        from .commands import doctor as doctor_cmd

        if args.command == "version":
            Console.print(f"aec version {__version__}")

        elif args.command == "install":
            install_cmd.install()

        elif args.command == "doctor":
            doctor_cmd.run_doctor()

        elif args.command == "repo":
            if args.repo_command == "setup":
                repo_cmd.setup(args.path, args.skip_raycast)
            elif args.repo_command == "list":
                repo_cmd.list_repos()
            elif args.repo_command == "update":
                repo_cmd.update(args.path, args.dry_run, args.all)
            else:
                repo_parser.print_help()

        elif args.command == "agent-tools":
            if args.at_command == "setup":
                at_cmd.setup()
            elif args.at_command == "migrate":
                at_cmd.migrate(args.dry_run)
            elif args.at_command == "rollback":
                at_cmd.rollback(args.backup_dir)
            else:
                at_parser.print_help()

        elif args.command == "rules":
            if args.rules_command == "generate":
                rules_cmd.generate()
            elif args.rules_command == "validate":
                rules_cmd.validate()
            else:
                rules_parser.print_help()


def main():
    """Entry point."""
    if HAS_TYPER:
        app()
    else:
        app()


if __name__ == "__main__":
    main()
