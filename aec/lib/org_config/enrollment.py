"""Declarative enrollment_script runner (Phase 4c).

Executes the closed set of actions (``add_source``, ``install_items``,
``set_hooks``, ``run_doctor``, ``set_pref``) in declared order. Any action
failure halts the script, *except* ``add_source`` failures, which are
captured into ``failed_sources`` so subsequent ``install_items`` skips items
from that source — keeping a single inaccessible repo from breaking
enrollment for everyone else's items.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .effective import EffectivePolicy
from .paths import OrgPaths
from .schema import ITEM_TYPES, OrgConfig
from .sources_sync import sync_source


@dataclass(frozen=True)
class StepResult:
    action: str
    success: bool
    message: str = ""


@dataclass(frozen=True)
class EnrollmentResult:
    steps: tuple
    failed_sources: tuple

    @property
    def ok(self) -> bool:
        """True iff every non-``add_source`` step succeeded.

        ``add_source`` failures are reported via ``failed_sources`` and do not
        fail the overall enroll, so a single inaccessible source repo cannot
        block onboarding for the rest of the org's policy.
        """
        return all(s.success for s in self.steps if s.action != "add_source")


_INSTALL_STANCES = frozenset({"required", "recommended", "pinned"})


def run_enrollment_script(
    config: OrgConfig,
    paths: OrgPaths,
    *,
    mode: str = "managed",
    cloner=None,
    doctor: Optional[Callable[[], tuple]] = None,
) -> EnrollmentResult:
    steps: list = []
    failed_sources: set = set()
    for entry in config.enrollment_script:
        action = entry["action"]
        if action == "add_source":
            step = _do_add_source(config, entry, paths, cloner, failed_sources)
        elif action == "install_items":
            step = _do_install_items(config, entry, failed_sources)
        elif action == "set_hooks":
            step = _do_set_hooks(config, entry)
        elif action == "set_pref":
            step = _do_set_pref(entry, mode)
        elif action == "run_doctor":
            step = _do_run_doctor(doctor)
        else:  # validator guards this, but be defensive
            step = StepResult(action, False, f"unknown action {action}")
        steps.append(step)
        if not step.success and action != "add_source":
            break
    return EnrollmentResult(
        steps=tuple(steps), failed_sources=tuple(sorted(failed_sources))
    )


def _do_add_source(config, entry, paths, cloner, failed_sources):
    source_id = entry["source_id"]
    cs = next((s for s in config.custom_sources if s.id == source_id), None)
    if cs is None:
        return StepResult("add_source", False, f"source {source_id!r} not declared")
    result = sync_source(cs, sources_dir=paths.sources_dir, cloner=cloner)
    if result.success:
        return StepResult("add_source", True, f"synced {source_id} -> {result.path}")
    failed_sources.add(source_id)
    return StepResult(
        "add_source", False, f"sync failed for {source_id}: {result.error}"
    )


def _do_install_items(config, entry, failed_sources):
    types = entry.get("types") or list(ITEM_TYPES)
    sources_filter = set(entry.get("sources") or [])

    items: dict = {}
    skipped = 0
    for item_type in types:
        for name, policy in config.items.get(item_type, {}).items():
            if sources_filter and policy.source not in sources_filter:
                continue
            if policy.source in failed_sources:
                skipped += 1
                continue
            if policy.stance.value not in _INSTALL_STANCES:
                continue
            items[f"{item_type}/{name}"] = (config.org_id, policy)

    if not items:
        msg = "no installable items"
        if skipped:
            msg += f" (skipped {skipped} from failed sources)"
        return StepResult("install_items", True, msg)

    from . import apply as apply_mod

    pol = EffectivePolicy(
        items=items,
        preferences={},
        prompts={},
        default_sources={},
        custom_sources=[],
        install_mode=None,
        held=(),
    )
    source_dirs, available, manifest_path = apply_mod._catalog("global")
    result, _removed = apply_mod.apply_items(
        pol,
        "global",
        source_dirs=source_dirs,
        available_by_type=available,
        manifest_path=manifest_path,
    )
    msg = f"installed {len(result.applied)} item(s)"
    if skipped:
        msg += f"; skipped {skipped} from failed sources"
    return StepResult("install_items", True, msg)


def _do_set_hooks(config, entry):
    policy = entry.get("policy") or config.install_preferences.get("hook_mode")
    if policy is None:
        return StepResult("set_hooks", True, "no policy specified; left unchanged")
    from .. import preferences as prefs

    prefs.set_setting("hook_mode", policy)
    return StepResult("set_hooks", True, f"hook_mode={policy}")


def _do_set_pref(entry, mode):
    from .. import preferences as prefs

    key = entry["key"]
    value = entry["value"]
    if_unset = entry.get("if_unset", mode == "guided")
    if if_unset and prefs.get_setting(key) is not None:
        return StepResult("set_pref", True, f"{key} already set; skipped")
    if key in prefs.OPTIONAL_FEATURES:
        prefs.set_preference(key, bool(value))
    else:
        prefs.set_setting(key, value)
    return StepResult("set_pref", True, f"set {key}={value!r}")


def _do_run_doctor(doctor):
    if doctor is None:
        from ...commands.doctor import run_doctor as _doctor
        doctor = _doctor
    ok, msgs = doctor()
    summary = "; ".join(msgs) if msgs else ("ok" if ok else "failed")
    return StepResult("run_doctor", ok, summary)
