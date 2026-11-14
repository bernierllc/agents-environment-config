"""Tests for the AGENTINFO.md -> AGENTS.md layout transform."""

from __future__ import annotations

import re
from pathlib import Path

from aec.lib.agents_md_layout import (
    INSTRUCTION_STUBS,
    detect_layout,
    plan_migration,
    render_new_layout,
)

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
CURSOR = ".cursor/rules/CURSOR.mdc"
PORT_BLOCK = "<!-- aec-port-registry:start -->\n| 3000 | web |\n<!-- aec-port-registry:end -->"

CLAUDE_NOTES = "## My Notes\n\nnote line one\nnote line two\n\n"
CLAUDE_TAIL = "\n## Scripts\n\n- `scripts/x.sh` runs x, see `AGENTINFO.md`\n"
AGENTS_TAIL = "\n## Codex Notes\n\ncodex only line\n"

# Lines AEC generates in stubs; they are dropped on purpose.
GENERATED = {
    "## Quick Start",
    "## Regenerating This File",
    "## Rules Reference",
    "1. Read `AGENTS.md` for project-specific info",
    "2. Read relevant `~/.agent-tools/rules/agents-environment-config/*.md` files on demand",
    "3. Do NOT memorize all rules - reference them when needed",
    "5. For project-specific info, see `AGENTS.md`",
    "```bash",
    "aec files generate",
    "```",
}


def build_repo(root: Path, with_user_content: bool = True) -> Path:
    for src in list(TEMPLATES.glob("*.md")) + [TEMPLATES / CURSOR]:
        dest = root / src.relative_to(TEMPLATES)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    if with_user_content:
        claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
        claude = claude.replace("## Regenerating This File", CLAUDE_NOTES + "## Regenerating This File")
        (root / "CLAUDE.md").write_text(claude + CLAUDE_TAIL, encoding="utf-8")
        with (root / "AGENTS.md").open("a", encoding="utf-8") as f:
            f.write(AGENTS_TAIL)
    return root


def apply(plan) -> None:
    for path, text in plan.items():
        if text is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))


def assert_no_loss(inputs: dict, outputs: dict) -> None:
    """Every input line is generated boilerplate or appears in some output."""
    out_lines = {
        ln for text in outputs.values() for ln in text.replace("\r\n", "\n").split("\n")
    }
    h1 = re.compile(r"^# .+ Agent Instructions\s*$")
    for name, text in inputs.items():
        for line in text.replace("\r\n", "\n").split("\n"):
            line = line.replace("AGENTINFO.md", "AGENTS.md")
            if not line.strip() or line in GENERATED or line.startswith(">"):
                continue
            if name != CURSOR and h1.match(line):
                continue
            assert line in out_lines, f"lost from {name}: {line!r}"


def read_inputs(repo: Path) -> dict:
    return {
        p.relative_to(repo).as_posix(): p.read_bytes().decode("utf-8")
        for p in repo.rglob("*")
        if p.is_file()
    }


def test_detect_layout(tmp_path):
    assert detect_layout(tmp_path) == "none"
    (tmp_path / "AGENTS.md").write_text("x", encoding="utf-8")
    assert detect_layout(tmp_path) == "agents-md"
    (tmp_path / "AGENTINFO.md").write_text("x", encoding="utf-8")
    assert detect_layout(tmp_path) == "agentinfo"


def test_migrates_real_templates_with_user_content(tmp_path):
    repo = build_repo(tmp_path)
    inputs = read_inputs(repo)
    plan = plan_migration(repo)
    new = {p.relative_to(repo).as_posix(): t for p, t in plan.items()}

    agentinfo = (TEMPLATES / "AGENTINFO.md").read_text(encoding="utf-8").rstrip()
    assert new["AGENTS.md"].startswith(agentinfo.replace("AGENTINFO.md", "AGENTS.md"))
    assert new["AGENTS.md"].count("## Rules Reference") == 1
    assert "codex only line" in new["AGENTS.md"]
    assert "AGENTINFO.md" not in "".join(t for t in new.values() if t)
    assert new["AGENTINFO.md"] is None
    assert new["CLAUDE.md"].startswith("@AGENTS.md\n")
    for line in ("## My Notes", "note line one", "note line two", "## Scripts"):
        assert line in new["CLAUDE.md"]
    assert "- `scripts/x.sh` runs x, see `AGENTS.md`" in new["CLAUDE.md"]
    for gone in ("# Claude Code Agent Instructions", "## Quick Start", "## Regenerating This File",
                 "Canonical Source", "## Rules Reference"):
        assert gone not in new["CLAUDE.md"]
    assert new["CLAUDE.md"].index("note line two") < new["CLAUDE.md"].index("## Scripts")
    assert_no_loss(inputs, {k: v for k, v in new.items() if v is not None})


def test_idempotent(tmp_path):
    repo = build_repo(tmp_path)
    apply(plan_migration(repo))
    assert detect_layout(repo) == "agents-md"
    assert plan_migration(repo) == {}


def test_missing_stubs_not_created_and_import_stub_untouched(tmp_path):
    repo = build_repo(tmp_path, with_user_content=False)
    (repo / "GEMINI.md").unlink()
    (repo / "QWEN.md").write_text("@AGENTS.md\n\nmine\n", encoding="utf-8")
    plan = plan_migration(repo)
    assert repo / "GEMINI.md" not in plan
    assert repo / "QWEN.md" not in plan
    assert plan[repo / "CLAUDE.md"] == "@AGENTS.md\n"


def test_crlf_preserved(tmp_path):
    repo = build_repo(tmp_path)
    claude = (repo / "CLAUDE.md").read_bytes().replace(b"\n", b"\r\n")
    (repo / "CLAUDE.md").write_bytes(claude)
    plan = plan_migration(repo)
    new_claude = plan[repo / "CLAUDE.md"]
    assert new_claude.startswith("@AGENTS.md\r\n")
    assert "\n" not in new_claude.replace("\r\n", "")
    assert "note line one" in new_claude
    assert "\r" not in plan[repo / "AGENTS.md"]


def test_crlf_agentinfo_gives_crlf_agents(tmp_path):
    repo = build_repo(tmp_path)
    (repo / "AGENTINFO.md").write_bytes(b"# Proj\r\n\r\nbody\r\n")
    new = plan_migration(repo)[repo / "AGENTS.md"]
    assert new.startswith("# Proj\r\n\r\nbody\r\n\r\n")
    assert "\n" not in new.replace("\r\n", "")


def test_cursor_rule_rewritten(tmp_path):
    repo = build_repo(tmp_path)
    new = plan_migration(repo)[repo / CURSOR]
    assert "AGENTINFO.md" not in new
    assert "AGENTS.md" in new


def test_port_registry_block_preserved(tmp_path):
    repo = build_repo(tmp_path)
    with (repo / "AGENTINFO.md").open("a", encoding="utf-8") as f:
        f.write("\n" + PORT_BLOCK + "\n")
    assert PORT_BLOCK in plan_migration(repo)[repo / "AGENTS.md"]


def test_render_new_layout_from_templates():
    templates = {p.name: p.read_text(encoding="utf-8") for p in TEMPLATES.glob("*.md")}
    out = render_new_layout(templates)
    assert "AGENTINFO.md" not in out
    assert "AGENTINFO.md" not in "".join(out.values())
    assert out["AGENTS.md"].count("## Rules Reference") == 1
    for name in INSTRUCTION_STUBS:
        assert out[name] == "@AGENTS.md\n"
