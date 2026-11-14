"""Pure transform from the legacy AGENTINFO.md layout to the AGENTS.md layout.

Nothing here writes to disk. `plan_migration` returns what every file should
become (None means delete); the caller records and applies it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Tuple

INSTRUCTION_STUBS = ("CLAUDE.md", "GEMINI.md", "QWEN.md")
CURSOR_RULE = ".cursor/rules/CURSOR.mdc"

_LEGACY = "AGENTINFO.md"
_NEW = "AGENTS.md"
_IMPORT_LINE = "@AGENTS.md"
_H1 = re.compile(r"^# .+ Agent Instructions\s*$")
_GENERATED_QUOTES = ("> **Canonical Source**", "> Read that file first", "> 🚨 **Canonical Source**")
_SELF_POINTER = "5. For project-specific info, see `AGENTINFO.md`"


def detect_layout(repo: Path) -> str:
    if (repo / _LEGACY).exists():
        return "agentinfo"
    if (repo / _NEW).exists():
        return "agents-md"
    return "none"


def _trim_blank_edges(lines: list) -> str:
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return "\n".join(lines)


# Lines AEC itself generates in the Quick Start / Regenerating sections.
_BOILERPLATE = {
    "",
    "```",
    "```bash",
    "1. Read `AGENTINFO.md` for project-specific info",
    "2. Read relevant `~/.agent-tools/rules/agents-environment-config/*.md` files on demand",
    "3. Do NOT memorize all rules - reference them when needed",
    "aec files generate",
    "python3 scripts/generate-agent-files.py",
}


def split_stub(text: str) -> Tuple[str, str]:
    """Return (first Rules Reference section, everything else the user wrote).

    Quick Start and Regenerating This File are dropped only when every line in
    them is AEC boilerplate; otherwise the whole section is kept as user content.
    """
    kept: list = []
    rules: list = []
    section: list = []
    mode = "user"  # user | rules | generated
    in_fence = False
    h1_seen = False

    def close() -> None:
        if mode == "generated" and any(l.strip() not in _BOILERPLATE for l in section[1:]):
            kept.extend(section)
        elif mode == "rules":
            rules.extend(l for l in section if l.rstrip() != _SELF_POINTER)

    for line in text.split("\n"):
        heading = not in_fence and line.startswith("#")
        if heading and line.startswith("## "):
            close()
            title = line[3:].strip()
            if title == "Rules Reference" and not rules:
                mode = "rules"
            elif title in ("Quick Start", "Regenerating This File"):
                mode = "generated"
            else:
                mode = "user"
            section = [line]
            if mode == "user":
                kept.append(line)
            continue
        if heading and line.startswith("# "):
            close()
            mode, section = "user", []
            if not h1_seen:
                h1_seen = True
                if _H1.match(line):
                    continue
        if line.startswith("```"):
            in_fence = not in_fence
        if mode != "user":
            section.append(line)
        elif not line.startswith(_GENERATED_QUOTES):
            kept.append(line)
    close()
    return _trim_blank_edges(rules), _trim_blank_edges(kept)


def _rename(text: str) -> str:
    return text.replace(_LEGACY, _NEW)


def migrate_texts(files: Dict[str, str]) -> Dict[str, Optional[str]]:
    """Map relative file name -> new text (None = delete). Empty if not legacy."""
    if _LEGACY not in files:
        return {}
    crlf = {name: "\r\n" in text for name, text in files.items()}
    texts = {name: text.replace("\r\n", "\n") for name, text in files.items()}

    stubs = {name: split_stub(texts[name]) for name in (_NEW,) + INSTRUCTION_STUBS if name in texts}
    rules = next((r for r, _ in stubs.values() if r), "")
    agents_user = stubs[_NEW][1] if _NEW in stubs else ""
    parts = [texts[_LEGACY].rstrip(), rules, agents_user]
    out: Dict[str, Optional[str]] = {
        _NEW: _rename("\n\n".join(p for p in parts if p.strip()) + "\n"),
        _LEGACY: None,
    }
    for name in INSTRUCTION_STUBS:
        if name not in texts:
            continue
        if texts[name].startswith(_IMPORT_LINE):
            out[name] = _rename(texts[name])  # already an import; only fix references
            continue
        own_rules, user = stubs[name]
        # A rules section that differs from the one moved to AGENTS.md stays here.
        user = "\n\n".join(p for p in (own_rules if own_rules != rules else "", user) if p)
        user = _rename(user)
        out[name] = _IMPORT_LINE + "\n" + (f"\n{user}\n" if user else "")
    if _LEGACY in texts.get(CURSOR_RULE, ""):
        out[CURSOR_RULE] = _rename(texts[CURSOR_RULE])

    result: Dict[str, Optional[str]] = {}
    for name, new in out.items():
        if new is not None:
            if crlf[_LEGACY if name == _NEW else name]:
                new = new.replace("\n", "\r\n")
            if new == files.get(name):
                continue
        result[name] = new
    return result


def render_new_layout(templates: Dict[str, str]) -> Dict[str, str]:
    """New-layout texts for legacy template files, without AGENTINFO.md."""
    return {name: text for name, text in migrate_texts(templates).items() if text is not None}


def plan_migration(repo: Path) -> Dict[Path, Optional[str]]:
    if detect_layout(repo) != "agentinfo":
        return {}
    names = (_LEGACY, _NEW, CURSOR_RULE) + INSTRUCTION_STUBS
    # bytes + decode: read_text would translate CRLF before we can preserve it
    files = {n: (repo / n).read_bytes().decode("utf-8") for n in names if (repo / n).is_file()}
    return {repo / name: text for name, text in migrate_texts(files).items()}
