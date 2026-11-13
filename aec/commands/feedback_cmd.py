"""`aec feedback ...`: hand off to the installed feedback-loop skill's feedback.py.

The skill owns the store and every operation on it; this command only finds the script
and offers short aliases for the switches, so there is one implementation of the store.
"""

import subprocess
import sys

try:
    import typer
except ImportError:  # the argparse CLI only uses run_feedback
    typer = None

from ..lib.console import Console
from ..lib.feedback import locate_script

# `aec feedback enable` reads better than `aec feedback config --enable`.
ALIASES = {
    "enable": ["config", "--enable"],
    "disable": ["config", "--disable"],
    "opt-out": ["config", "--opt-out"],
    "opt-in": ["config", "--opt-in"],
}


def translate(args: list) -> list:
    if args and args[0] in ALIASES:
        return ALIASES[args[0]] + args[1:]
    return args


def run_feedback(args: list) -> int:
    """Run feedback.py with ``args`` (aliases translated); its exit code, or 1 if not installed."""
    script = locate_script()
    if script is None:
        Console.error("the feedback-loop skill is not installed")
        Console.print("  Install it with: aec install skill feedback-loop")
        return 1
    args = translate(list(args)) or ["--help"]
    return subprocess.run([sys.executable, str(script), *args]).returncode


def feedback(ctx: "typer.Context") -> None:
    """Log, review and toggle feedback on skills, agents, hooks, plugins, AEC and your process.

    Passes everything to the feedback-loop skill's feedback.py
    (status, review, log, resolve, mark-reviewed, report, config).
    Shortcuts: enable, disable, opt-out <kind:name>, opt-in <kind:name>.
    """
    raise typer.Exit(run_feedback(ctx.args))
