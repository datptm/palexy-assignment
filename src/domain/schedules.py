"""Pure validation rules for schedules."""

MAX_SCHEDULE_NAME_LENGTH = 100


def normalize_schedule_name(name: str) -> str:
    """Trim and validate a user-provided schedule name.

    Raises:
        ValueError: If the name is not text, empty, or too long.
    """
    if not isinstance(name, str):
        raise ValueError("schedule name must be text")
    normalized = name.strip()
    if not normalized or len(normalized) > MAX_SCHEDULE_NAME_LENGTH:
        raise ValueError("schedule name must contain 1 to 100 characters")
    return normalized
