"""Apply effective org policy to the user's environment.

Translates an :class:`EffectivePolicy` (already merged + conflict-resolved) into
real changes by reusing existing engines:

  * preferences  -> ``aec.lib.preferences`` (settings / optional_rules sections)
  * prompts      -> ``aec.lib.prompts`` overlay-answer registry
  * items        -> ``aec.lib.apply_core`` (install) + uninstall (block)

Higher-level orchestration (mode, lockout, CLI) lives in later tasks; this
module holds the category appliers.
"""
from __future__ import annotations

from .effective import EffectivePolicy


def apply_preferences(policy: EffectivePolicy) -> list[str]:
    """Write the policy's preferences into prefs.json. Returns applied keys."""
    from ..preferences import OPTIONAL_FEATURES, set_preference, set_setting

    applied: list[str] = []
    for key, value in policy.preferences.items():
        if key in OPTIONAL_FEATURES:
            set_preference(key, bool(value))
        else:
            set_setting(key, value)
        applied.append(key)
    return applied


def apply_prompts(policy: EffectivePolicy) -> None:
    """Register the policy's prompt answers so the prompt() seam pre-answers."""
    from ..prompts import set_overlay_answers

    set_overlay_answers(dict(policy.prompts))
