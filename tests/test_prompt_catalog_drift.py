"""Drift guard: every literal prompt ID at a callsite is in the catalog, and
every catalog ID is actually asked somewhere.

Without this, `aec prompts list` silently rots — an agent reading the catalog
would answer prompts that no longer exist, or hit prompts it was never told
about.
"""

import ast
import importlib
from pathlib import Path

from aec.lib.prompt_catalog import all_families, catalog_ids

PKG = Path(__file__).resolve().parent.parent / "aec"
SEAM_NAMES = {"prompt", "ask_prompt", "_prompt"}
# The seam itself and the catalog describe prompts rather than ask them.
SKIP = {PKG / "lib" / "prompts.py", PKG / "lib" / "prompt_catalog"}


def _module_name(path: Path) -> str:
    rel = path.relative_to(PKG.parent).with_suffix("")
    return ".".join(rel.parts)


def _name_bindings(tree, module_name: str) -> dict:
    """Resolve prompt-ID constants a file imports, module-level or in-function.

    Callsites import their IDs lazily inside functions (the package keeps
    import cost off the CLI startup path), so a module-level getattr alone
    misses most of them.
    """
    bindings = {}
    package = module_name.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = package
        for _ in range(max(node.level - 1, 0)):
            base = base.rsplit(".", 1)[0]
        source = f"{base}.{node.module}" if node.level else node.module
        try:
            mod = importlib.import_module(source)
        except ImportError:
            continue
        for alias in node.names:
            value = getattr(mod, alias.name, None)
            if isinstance(value, str):
                bindings[alias.asname or alias.name] = value
    return bindings


def _callsite_ids() -> dict:
    """{prompt_id: "module:line"} for every statically-resolvable seam call."""
    found = {}
    for path in sorted(PKG.rglob("*.py")):
        if path in SKIP or any(p in SKIP for p in path.parents):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bindings = _name_bindings(tree, _module_name(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            # Attribute calls (typer.prompt) are a different API entirely.
            if not isinstance(node.func, ast.Name) or node.func.id not in SEAM_NAMES:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found[arg.value] = f"{path.name}:{node.lineno}"
            elif isinstance(arg, ast.Name) and arg.id in bindings:
                found[bindings[arg.id]] = f"{path.name}:{node.lineno}"
            # f-strings / builder calls are dynamic families, checked below.
    return found


def test_every_callsite_id_is_in_the_catalog():
    prefixes = tuple(f.prefix + "." for f in all_families())
    catalog = catalog_ids()
    missing = {
        pid: where
        for pid, where in _callsite_ids().items()
        if pid not in catalog and not pid.startswith(prefixes)
    }
    assert not missing, (
        "prompt IDs asked but not in the catalog (add a PromptSpec to the "
        f"matching aec/lib/prompt_catalog/*_area.py): {missing}"
    )


def test_every_catalog_id_is_asked_somewhere():
    asked = set(_callsite_ids())
    orphans = sorted(catalog_ids() - asked)
    assert not orphans, (
        "catalog entries with no callsite (delete the PromptSpec or fix the "
        f"ID): {orphans}"
    )


def test_the_scanner_actually_finds_callsites():
    assert len(_callsite_ids()) > 20
