"""Schedule data carried between persistence and presentation layers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Schedule:
    """A named, persisted typical-week schedule."""

    id: int
    name: str
