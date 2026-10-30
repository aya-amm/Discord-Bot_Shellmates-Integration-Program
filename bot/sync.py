"""Pure role-comparison logic (no Discord needed). Owner: issue #3."""


def compute_changes(
    current: set[str], wanted: set[str], managed: set[str]
) -> tuple[set[str], set[str]]:
    """Return (to_add, to_remove).

    Only roles in `managed` may be added or removed; all others are untouched.
    """
    raise NotImplementedError
