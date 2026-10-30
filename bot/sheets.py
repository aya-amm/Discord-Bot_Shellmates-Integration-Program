"""Google Sheets reading + validation. Owner: issue #2."""


def read_sheet() -> tuple[list[dict], list[str]]:
    """Read the sheet and return (rows, errors).

    rows   = [{"username": "member1", "roles": ["Developer"]}, ...]
             usernames already normalized (lowercase, trimmed, no leading '@').
    errors = human-readable problems (empty/duplicate usernames, ...).
    Raises an error with a clear message if the sheet is unreachable.
    """
    raise NotImplementedError
