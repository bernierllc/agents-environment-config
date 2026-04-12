"""Dismissal tracking for AEC discovery.

Stub module -- real implementation lives on a separate branch.
"""


def load_dismissed(item_type: str, scope) -> dict:
    """Load dismissed items for the given scope and type."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def save_dismissal(item_type: str, scope, local_name: str, record: dict) -> None:
    """Save a dismissal record for a match result."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def is_dismissed(item_type: str, scope, local_name: str) -> bool:
    """Check if an item is dismissed."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def clear_dismissals(item_type: str, scope) -> None:
    """Clear all dismissals for the given scope and type."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def prune_stale(item_type: str, scope, catalog: dict) -> None:
    """Remove dismissals for items no longer in the catalog."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def should_resurface(item_type: str, scope, name: str) -> bool:
    """Check if a dismissed item should be resurfaced."""
    raise NotImplementedError("Stub -- real implementation on feature branch")
