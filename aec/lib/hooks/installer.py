"""Hook installation orchestrator.

Pure merge helpers live here alongside the `install_item_hooks` /
`remove_item_hooks` entrypoints. The helpers operate on plain dicts with no
I/O so they can be tested in isolation — this file grows across Tasks 9a-9g.
"""

from typing import List

from .fingerprint import fingerprint_hook


def _merge_claude_entries(config: dict, entries: List[dict]) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        new_payload = entry["payload"]
        fp_new = fingerprint_hook(new_payload)
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(new_payload)
    return settings


def _merge_gemini_entries(config: dict, entries: List[dict]) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        new_payload = entry["payload"]
        fp_new = fingerprint_hook(new_payload)
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(new_payload)
    return settings


def _merge_cursor_entries(config: dict, entries: List[dict]) -> dict:
    cfg = dict(config) if config else {}
    hooks = cfg.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        fp_new = fingerprint_hook(entry["payload"])
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(entry["payload"])
    return cfg


def _remove_from_claude(config: dict, event_key: str, fingerprint: str) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.get("hooks", {})
    if event_key not in hooks:
        return settings
    hooks[event_key] = [e for e in hooks[event_key] if fingerprint_hook(e) != fingerprint]
    if not hooks[event_key]:
        del hooks[event_key]
    if not hooks:
        settings.pop("hooks", None)
    return settings


def _remove_from_gemini(config: dict, event_key: str, fingerprint: str) -> dict:
    return _remove_from_claude(config, event_key, fingerprint)


def _remove_from_cursor(config: dict, event_key: str, fingerprint: str) -> dict:
    return _remove_from_claude(config, event_key, fingerprint)
