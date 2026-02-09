#!/usr/bin/env python3
"""Generate _agent-config.sh from agents.json.

Reads the agent registry and produces a bash 3-compatible shell config
that can be sourced by setup-repo.sh and other shell scripts.

Usage:
    python3 scripts/generate-agent-config.py
"""

import json
import sys
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    agents_json = repo_root / "agents.json"
    output_path = script_dir / "_agent-config.sh"

    if not agents_json.exists():
        print(f"Error: {agents_json} not found", file=sys.stderr)
        return 1

    with open(agents_json) as f:
        registry = json.load(f)

    agents = registry.get("agents", {})

    lines = [
        "#!/bin/bash",
        "# AUTO-GENERATED from agents.json - DO NOT EDIT",
        f"# Regenerate with: python3 scripts/generate-agent-config.py",
        "",
        "# --- Agent names ---",
    ]

    # Agent names array
    agent_names = list(agents.keys())
    lines.append(f'AGENT_NAMES=({" ".join(json.dumps(n) for n in agent_names)})')

    # Instruction files (AGENTINFO.md + each agent's instruction_file)
    instruction_files = ["AGENTINFO.md"]
    for agent in agents.values():
        f_name = agent.get("instruction_file")
        if f_name and f_name not in instruction_files:
            instruction_files.append(f_name)
    lines.append("")
    lines.append("# --- Instruction files to copy during repo setup ---")
    lines.append(
        f'AGENT_INSTRUCTION_FILES=({" ".join(json.dumps(f) for f in instruction_files)})'
    )

    # Migration files (only those with use_agent_rules=true)
    migration_files = []
    for agent in agents.values():
        if agent.get("use_agent_rules") and agent.get("instruction_file"):
            migration_files.append(agent["instruction_file"])
    lines.append("")
    lines.append("# --- Files that need .agent-rules migration checks ---")
    lines.append(
        f'MIGRATION_FILES=({" ".join(json.dumps(f) for f in migration_files)})'
    )

    # Gitignore patterns
    gitignore_patterns = instruction_files + [".cursor/rules", "/plans/"]
    lines.append("")
    lines.append("# --- Patterns to add to .gitignore ---")
    lines.append(
        f'GITIGNORE_AGENT_PATTERNS=({" ".join(json.dumps(p) for p in gitignore_patterns)})'
    )

    # Per-agent config via prefixed vars (bash 3 compatible)
    lines.append("")
    lines.append("# --- Per-agent configuration (bash 3 compatible, no associative arrays) ---")

    for name, agent in agents.items():
        safe_name = name  # agent names are already safe identifiers
        lines.append(f"")
        lines.append(f"# {agent.get('display_name', name)}")
        lines.append(f'AGENT_{safe_name}_DISPLAY_NAME={json.dumps(agent.get("display_name", name))}')
        lines.append(f'AGENT_{safe_name}_COMMANDS={json.dumps(" ".join(agent["commands"]))}')

        alt_paths = agent.get("alt_paths", [])
        # Convert ~ to $HOME for shell expansion
        shell_paths = [p.replace("~", "$HOME") for p in alt_paths]
        lines.append(f'AGENT_{safe_name}_ALT_PATHS={json.dumps(" ".join(shell_paths))}')

        lines.append(
            f'AGENT_{safe_name}_TERMINAL_LAUNCH={json.dumps(str(agent["terminal_launch"]).lower())}'
        )

        if agent["terminal_launch"]:
            lines.append(
                f'AGENT_{safe_name}_LAUNCH_ARGS={json.dumps(agent.get("launch_args", ""))}'
            )
        else:
            lines.append(
                f'AGENT_{safe_name}_LAUNCH_TEMPLATE={json.dumps(agent.get("launch_template", f"{name} {{path}}/"))}'
            )

        lines.append(
            f'AGENT_{safe_name}_HAS_RESUME={json.dumps(str(agent["has_resume"]).lower())}'
        )
        if agent["has_resume"]:
            lines.append(
                f'AGENT_{safe_name}_RESUME_ARGS={json.dumps(agent.get("resume_args", ""))}'
            )

    # Generated detection function
    lines.append("")
    lines.append("# --- Generated agent detection function ---")
    lines.append("detect_installed_agents() {")
    lines.append("    # Detect which supported agents are installed on this machine.")
    lines.append("    # Sets DETECTED_AGENTS as a space-separated list of agent names.")
    lines.append('    DETECTED_AGENTS=""')
    lines.append("")

    for name, agent in agents.items():
        commands = agent["commands"]
        alt_paths = agent.get("alt_paths", [])

        conditions = []
        for cmd in commands:
            conditions.append(f'command -v {cmd} &>/dev/null')
        for p in alt_paths:
            shell_p = p.replace("~", "$HOME")
            # Use -d for directories, -e for files/apps
            if shell_p.endswith(".app"):
                conditions.append(f'[ -d "{shell_p}" ]')
            else:
                conditions.append(f'[ -d "{shell_p}" ]')

        condition_str = " || ".join(conditions)
        lines.append(f"    # {agent.get('display_name', name)}")
        lines.append(f"    if {condition_str}; then")
        lines.append(f'        DETECTED_AGENTS="$DETECTED_AGENTS {name}"')
        lines.append(f"    fi")
        lines.append("")

    lines.append("    # Trim leading whitespace")
    lines.append('    DETECTED_AGENTS="$(echo "$DETECTED_AGENTS" | xargs)"')
    lines.append("}")

    # Generated raycast launch command function
    lines.append("")
    lines.append("# --- Generated Raycast launch command function ---")
    lines.append("generate_raycast_launch_command() {")
    lines.append("    # Generate the launch command portion of a Raycast script.")
    lines.append('    # Args: $1=agent_name $2=project_path $3=is_resume(true/false)')
    lines.append('    local agent="$1"')
    lines.append('    local proj_path="$2"')
    lines.append('    local is_resume="${3:-false}"')
    lines.append("")
    lines.append('    case "$agent" in')

    for name, agent in agents.items():
        if not agent["terminal_launch"]:
            template = agent.get("launch_template", f"{name} {{path}}/")
            # Replace {path} with ${proj_path} for shell
            shell_cmd = template.replace("{path}", "${proj_path}")
            lines.append(f"        {name})")
            lines.append(f'            echo "{shell_cmd}"')
            lines.append(f"            ;;")
        elif agent["has_resume"]:
            launch_args = agent.get("launch_args", "")
            resume_args = agent.get("resume_args", "")
            lines.append(f"        {name})")
            lines.append(f'            if [ "$is_resume" = true ]; then')
            args_str = f" {resume_args}" if resume_args else ""
            lines.append(
                f"                echo \"osascript -e 'tell application \\\"Terminal\\\" to do script "
                f"\\\"cd ${{proj_path}}/; {name}{args_str}\\\"'\""
            )
            args_str = f" {launch_args}" if launch_args else ""
            lines.append(f"            else")
            lines.append(
                f"                echo \"osascript -e 'tell application \\\"Terminal\\\" to do script "
                f"\\\"cd ${{proj_path}}/; {name}{args_str}\\\"'\""
            )
            lines.append(f"            fi")
            lines.append(f"            ;;")
        else:
            launch_args = agent.get("launch_args", "")
            args_str = f" {launch_args}" if launch_args else ""
            lines.append(f"        {name})")
            lines.append(
                f"            echo \"osascript -e 'tell application \\\"Terminal\\\" to do script "
                f"\\\"cd ${{proj_path}}/; {name}{args_str}\\\"'\""
            )
            lines.append(f"            ;;")

    lines.append("    esac")
    lines.append("}")

    lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content)
    print(f"Generated {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
