"""hooks.json validator — implements spec §1.6 rules.

Returns (errors, warnings) tuples of lightweight message objects. Keeps rules
pure: no filesystem access beyond what the caller provides (script existence
is deferred to install time per plan P1).
"""

from dataclasses import dataclass
from typing import List, Tuple

from .schema import AgentOverride, GenericHook, HooksFile, GENERIC_EVENTS


RECOGNIZED_GIT_HOOKS = frozenset({
    "pre-commit",
    "pre-push",
    "commit-msg",
    "post-commit",
    "post-merge",
    "post-checkout",
    "pre-rebase",
    "prepare-commit-msg",
})

# Tool-name fragments that suggest a per-agent override is mirroring what a
# generic hook could express. Warning-only — still allowed (spec §1.6 / P1).
_CLAUDE_GENERIC_MATCHER_TOKENS = ("Edit", "Write", "Read")
_GEMINI_GENERIC_TOOL_TOKENS = ("write_file", "read_file", "replace")
_CURSOR_GENERIC_EVENT_TOKENS = ("afterFileEdit", "beforeShellExecution")


@dataclass
class ValidationError:
    message: str
    hook_id: str = ""


@dataclass
class ValidationWarning:
    message: str
    hook_id: str = ""


def _collect_ids(hf: HooksFile) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for h in hf.hooks:
        out.append((h.id, "hooks"))
    for section in ("claude", "cursor", "gemini", "git"):
        for ov in getattr(hf, section):
            if ov.id:
                out.append((ov.id, section))
    return out


def _check_override_mirror(ov: AgentOverride) -> bool:
    """Return True if this override looks like it mirrors a generic hook."""
    payload = ov.payload or {}
    if ov.agent == "claude":
        matcher = str(payload.get("matcher", ""))
        return any(t in matcher for t in _CLAUDE_GENERIC_MATCHER_TOKENS)
    if ov.agent == "gemini":
        tool = str(payload.get("tool", "")) + " " + str(payload.get("matcher", ""))
        return any(t in tool for t in _GEMINI_GENERIC_TOOL_TOKENS)
    if ov.agent == "cursor":
        event = str(payload.get("event", "")) + " " + str(payload.get("type", ""))
        return any(t in event for t in _CURSOR_GENERIC_EVENT_TOKENS)
    return False


def validate_hooks_file(
    hf: HooksFile, expected_version: str
) -> Tuple[List[ValidationError], List[ValidationWarning]]:
    errors: List[ValidationError] = []
    warnings: List[ValidationWarning] = []

    # Rule 1: version match
    if hf.version != expected_version:
        errors.append(ValidationError(
            message=(
                f"hooks.json version {hf.version!r} does not match "
                f"expected version {expected_version!r}"
            ),
        ))

    # Rule 2: unique id across hooks + overrides
    seen: dict = {}
    for hid, section in _collect_ids(hf):
        if hid in seen:
            errors.append(ValidationError(
                message=(
                    f"duplicate id {hid!r} (in {seen[hid]} and {section})"
                ),
                hook_id=hid,
            ))
        else:
            seen[hid] = section

    # Rules 3-5: per-generic-hook checks
    for h in hf.hooks:
        # Rule 3: event must be recognized
        if h.event not in GENERIC_EVENTS:
            errors.append(ValidationError(
                message=(
                    f"hook {h.id!r} uses unknown event {h.event!r}; "
                    f"expected one of {sorted(GENERIC_EVENTS)}"
                ),
                hook_id=h.id,
            ))
        # Rule 4: command must be non-empty
        if not (h.command or "").strip():
            errors.append(ValidationError(
                message=f"hook {h.id!r} has empty command",
                hook_id=h.id,
            ))
        # Rule 5: when.custom_check must be a single line
        if h.when and h.when.custom_check is not None:
            if "\n" in h.when.custom_check or "\r" in h.when.custom_check:
                errors.append(ValidationError(
                    message=(
                        f"hook {h.id!r} when.custom_check contains a newline; "
                        "must be a single-line shell expression"
                    ),
                    hook_id=h.id,
                ))

    # Rule 6: override mirroring generic — warning only
    for section in ("claude", "cursor", "gemini"):
        for ov in getattr(hf, section):
            if _check_override_mirror(ov):
                warnings.append(ValidationWarning(
                    message=(
                        f"{section} override {ov.id or '<unnamed>'!r} appears "
                        f"to mirror a generic hook; prefer expressing it "
                        f"under `hooks[]` so it installs to every agent"
                    ),
                    hook_id=ov.id or "",
                ))

    # Rule 7: git hook_name must be recognized
    for ov in hf.git:
        payload = ov.payload or {}
        name = payload.get("hook_name")
        if name is None:
            errors.append(ValidationError(
                message=(
                    f"git hook {ov.id or '<unnamed>'!r} missing required "
                    "'hook_name' field"
                ),
                hook_id=ov.id or "",
            ))
        elif name not in RECOGNIZED_GIT_HOOKS:
            errors.append(ValidationError(
                message=(
                    f"git hook {ov.id or '<unnamed>'!r} has unrecognized "
                    f"hook_name {name!r}; expected one of "
                    f"{sorted(RECOGNIZED_GIT_HOOKS)}"
                ),
                hook_id=ov.id or "",
            ))

    # Rule 8: script existence is NOT checked here (deferred to install time)

    return errors, warnings
