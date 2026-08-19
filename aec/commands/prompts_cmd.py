"""``aec prompts {list|template|check}`` — the discovery surface for agents.

An agent driving AEC unattended needs three things: to see what a command will
ask before running it, to write the answers down, and to find out its answers
are wrong *before* the run rather than halfway through a side effect. Those are
the three subcommands here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.prompt_catalog import all_families, all_specs, get_spec
from ..lib.prompts import PromptInvalidAnswer, env_var_name, normalize


def _selected_specs(command: Optional[str]) -> list:
    specs = all_specs(expand_dynamic=True)
    if command:
        needle = command.strip().lower()
        specs = [s for s in specs if needle in s.command.lower()]
    return specs


def _selected_families(command: Optional[str]) -> list:
    families = all_families()
    if command:
        needle = command.strip().lower()
        families = [f for f in families if needle in f.command.lower()]
    return families


def run_prompts_list(command: Optional[str] = None, json_out: bool = False) -> None:
    """Show every prompt AEC can ask, optionally filtered to one command."""
    specs = _selected_specs(command)
    families = _selected_families(command)

    if json_out:
        payload = {
            "prompts": [s.to_dict() for s in specs],
            "dynamic_families": [
                {
                    "prefix": f.prefix,
                    "command": f.command,
                    "summary": f.summary,
                    "type": f.type,
                }
                for f in sorted(families, key=lambda f: f.prefix)
            ],
        }
        print(json.dumps(payload, indent=2))
        return

    if not specs and not families:
        Console.info(f"No catalogued prompts match {command!r}.")
        return

    by_command: dict[str, list] = {}
    for spec in specs:
        by_command.setdefault(spec.command, []).append(spec)

    for cmd in sorted(by_command):
        Console.subheader(f"aec {cmd}")
        for spec in by_command[cmd]:
            flags = [spec.type]
            if spec.sensitive:
                flags.append("sensitive")
            if spec.default is None:
                flags.append("no default")
            else:
                flags.append(f"default={spec.default!r}")
            Console.print(f"  {spec.prompt_id}  ({', '.join(flags)})")
            Console.print(f"      {spec.summary}")
            if spec.choices:
                Console.print(f"      choices: {', '.join(str(c) for c in spec.choices)}")
            Console.print(f"      env: {env_var_name(spec.prompt_id)}")

    dynamic = sorted(families, key=lambda f: f.prefix)
    if dynamic:
        Console.subheader("Dynamic prompt families")
        Console.print(
            "  One prompt per item at run time; the concrete ID is "
            "<prefix>.<item name>."
        )
        for family in dynamic:
            Console.print(f"  {family.prefix}.<name>  ({family.type})  [aec {family.command}]")
            Console.print(f"      {family.summary}")


def run_prompts_template(command: Optional[str] = None, output: Optional[str] = None) -> None:
    """Emit a skeleton answers file: every prompt ID mapped to its default."""
    specs = _selected_specs(command)
    if not specs:
        Console.warning(f"No catalogued prompts match {command!r}.")
        return

    template = {s.prompt_id: s.default for s in specs}
    text = json.dumps(template, indent=2)

    if output:
        path = Path(output).expanduser()
        path.write_text(text + "\n", encoding="utf-8")
        Console.success(f"Wrote {len(template)} prompt(s) to {path}")
        Console.info("Prompts with null have no safe default — fill them in.")
        return

    print(text)


def run_prompts_check(answers_file: str) -> int:
    """Validate an answers file against the catalog. Returns an exit code."""
    from ..lib.prompts import load_answers_file

    try:
        answers = load_answers_file(answers_file)
    except (FileNotFoundError, ValueError) as exc:
        Console.error(str(exc))
        return 1

    problems: list[str] = []
    for prompt_id, value in sorted(answers.items()):
        spec = get_spec(prompt_id)
        if spec is None:
            if any(prompt_id.startswith(f.prefix + ".") for f in all_families()):
                # Dynamic family member: the prefix is real, the item name is
                # only knowable at run time, so the ID is as checkable as it gets.
                continue
            problems.append(f"{prompt_id}: not a known prompt ID")
            continue
        if value is None:
            problems.append(
                f"{prompt_id}: null — this prompt has no default, fill it in or drop the key"
            )
            continue
        try:
            normalized = normalize(value, spec.type)
        except PromptInvalidAnswer:
            problems.append(f"{prompt_id}: {value!r} is not a valid {spec.type}")
            continue
        if spec.choices and normalized not in [str(c) for c in spec.choices]:
            problems.append(
                f"{prompt_id}: {value!r} is not one of "
                f"{', '.join(str(c) for c in spec.choices)}"
            )

    if problems:
        Console.error(f"{len(problems)} problem(s) in {answers_file}:")
        for line in problems:
            Console.print(f"  {line}")
        return 1

    Console.success(f"{len(answers)} answer(s) valid.")
    return 0
