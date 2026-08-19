"""Catalogued prompts for the discovery flows: ``discover`` and ``discover catalog``.

These are read-then-decide prompts — scan depth, what to do with the matches
found, whether to back up before replacing. None are org-overlay-eligible
(they depend entirely on what the local scan turned up), but they are
catalogued so an agent can run a discovery pass headlessly with ``--answers``.
"""
from __future__ import annotations

from .spec import DynamicPromptFamily, PromptSpec

DISCOVER_ADD_PATHS = "discover.add_paths"
DISCOVER_CATALOG_DEPTH = "discover_catalog.depth"
DISCOVER_CATALOG_ACTION = "discover_catalog.action"
DISCOVER_CATALOG_BACKUP = "discover_catalog.backup"

# Concrete ID appends the item name being reviewed.
DISCOVER_CATALOG_REVIEW_PREFIX = "discover_catalog.review"

SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        DISCOVER_ADD_PATHS,
        command="discover",
        summary=(
            "Add the newly discovered project paths to tracking. Same decision "
            "as --auto."
        ),
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        DISCOVER_CATALOG_DEPTH,
        command="discover catalog",
        summary=(
            "Scan depth: 1 quick (name match), 2 normal (name + content hash), "
            "3 deep (full similarity, finds renames)."
        ),
        type="enum[1,2,3]",
        default="2",
        choices=("1", "2", "3"),
    ),
    PromptSpec(
        DISCOVER_CATALOG_ACTION,
        command="discover catalog",
        summary=(
            "What to do with the matches: 1 install exact then ask, 2 review "
            "one by one, 3 replace all, 4 skip."
        ),
        type="enum[1,2,3,4]",
        default="1",
        choices=("1", "2", "3", "4"),
    ),
    PromptSpec(
        DISCOVER_CATALOG_BACKUP,
        command="discover catalog",
        summary="Back up the original file before replacing it with the AEC version.",
        type="yes_no",
        default=True,
    ),
)

FAMILIES: tuple[DynamicPromptFamily, ...] = (
    DynamicPromptFamily(
        DISCOVER_CATALOG_REVIEW_PREFIX,
        command="discover catalog",
        summary=(
            "Replace one reviewed item with the AEC version. The concrete ID "
            "appends that item's local name."
        ),
    ),
)
