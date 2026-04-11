"""Dismissal tracking for AEC discovery.

Stub module -- real implementation lives on a separate branch.
"""


def load_dismissed(scope, item_type: str) -> dict:
    """Load dismissed items for the given scope and type."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def save_dismissal(scope, result) -> None:
    """Save a dismissal record for a match result."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def is_dismissed(scope, item_type: str, name: str) -> bool:
    """Check if an item is dismissed."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def clear_dismissals(scope, item_type: str) -> None:
    """Clear all dismissals for the given scope and type."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def prune_stale(scope, item_type: str, catalog: dict) -> None:
    """Remove dismissals for items no longer in the catalog."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def should_resurface(scope, item_type: str, name: str) -> bool:
    """Check if a dismissed item should be resurfaced."""
    raise NotImplementedError("Stub -- real implementation on feature branch")
