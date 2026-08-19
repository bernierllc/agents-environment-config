"""Catalog of every prompt AEC can ask, keyed by stable prompt ID.

The catalog is what makes AEC answerable by an agent: ``aec prompts list``
renders it, ``aec prompts template`` turns it into a skeleton answers file, and
``aec prompts check`` validates a filled-in one. Each command area contributes
its own module so concurrent work on different areas never touches the same
file.
"""
from __future__ import annotations

from .install_area import FAMILIES as _INSTALL_FAMILIES, SPECS as _INSTALL_SPECS
from .install_flow_area import (
    FAMILIES as _INSTALL_FLOW_FAMILIES,
    SPECS as _INSTALL_FLOW_SPECS,
)
from .repo_area import (
    FAMILIES as _REPO_FAMILIES,
    SPECS as _REPO_SPECS,
)
from .discovery_area import (
    FAMILIES as _DISCOVERY_FAMILIES,
    SPECS as _DISCOVERY_SPECS,
)
from .lifecycle_area import (
    FAMILIES as _LIFECYCLE_FAMILIES,
    SPECS as _LIFECYCLE_SPECS,
)
from .test_area import FAMILIES as _TEST_FAMILIES, SPECS as _TEST_SPECS
from .spec import DynamicPromptFamily, PromptSpec

__all__ = [
    "PromptSpec",
    "DynamicPromptFamily",
    "all_specs",
    "all_families",
    "get_spec",
    "catalog_ids",
]

_AREA_SPECS: tuple[tuple[PromptSpec, ...], ...] = (
    _INSTALL_SPECS,
    _INSTALL_FLOW_SPECS,
    _LIFECYCLE_SPECS,
    _DISCOVERY_SPECS,
    _REPO_SPECS,
    _TEST_SPECS,
)
_AREA_FAMILIES: tuple[tuple[DynamicPromptFamily, ...], ...] = (
    _INSTALL_FAMILIES,
    _INSTALL_FLOW_FAMILIES,
    _LIFECYCLE_FAMILIES,
    _DISCOVERY_FAMILIES,
    _REPO_FAMILIES,
    _TEST_FAMILIES,
)


def all_specs(*, expand_dynamic: bool = False) -> list:
    """Every static spec, sorted by ID. With ``expand_dynamic`` the runtime
    registries are consulted to add the concrete dynamic-family prompts."""
    specs = [s for area in _AREA_SPECS for s in area]
    if expand_dynamic:
        for family in all_families():
            specs.extend(family.expand())
    return sorted(specs, key=lambda s: s.prompt_id)


def all_families() -> list:
    return [f for area in _AREA_FAMILIES for f in area]


def get_spec(prompt_id: str):
    """Look up a spec by exact ID, or ``None``. Dynamic IDs are expanded only
    if the exact ID does not match a static one."""
    for spec in all_specs():
        if spec.prompt_id == prompt_id:
            return spec
    for family in all_families():
        if prompt_id.startswith(family.prefix + "."):
            for spec in family.expand():
                if spec.prompt_id == prompt_id:
                    return spec
    return None


def catalog_ids() -> set:
    """The set of static prompt IDs — used by the drift test against callsites."""
    return {s.prompt_id for s in all_specs()}
