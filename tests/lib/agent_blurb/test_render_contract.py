"""Spec §10.3: every command name classified by the blurb must exist in the
real `aec` CLI. Prevents drift between the renderer's command vocabulary and
the actual Typer app.

We enumerate commands by introspecting the Typer app rather than parsing
`aec --help` output, because the help renderer (Rich) produces decorated text
that is brittle to scrape.
"""

from aec.cli import app
from aec.lib.agent_blurb.profile import (
    READ_ONLY_COMMANDS,
    ADDITIVE_COMMANDS,
    DESTRUCTIVE_COMMANDS,
)


def _aec_commands() -> set[str]:
    """Return the set of registered top-level command names on the Typer app."""
    return {cmd.name for cmd in app.registered_commands if cmd.name}


def test_every_classified_command_is_real():
    real = _aec_commands()
    classified = READ_ONLY_COMMANDS | ADDITIVE_COMMANDS | DESTRUCTIVE_COMMANDS
    missing = classified - real
    assert not missing, (
        f"Classified commands missing from the aec Typer app: {missing}. "
        "Either add them to aec/cli.py or remove them from the classifier sets."
    )


def test_classifier_sets_are_disjoint():
    """A command must be classified as exactly one risk class."""
    pairs = [
        ("read_only ∩ additive", READ_ONLY_COMMANDS & ADDITIVE_COMMANDS),
        ("read_only ∩ destructive", READ_ONLY_COMMANDS & DESTRUCTIVE_COMMANDS),
        ("additive ∩ destructive", ADDITIVE_COMMANDS & DESTRUCTIVE_COMMANDS),
    ]
    for label, overlap in pairs:
        assert not overlap, f"Classifier overlap ({label}): {overlap}"
