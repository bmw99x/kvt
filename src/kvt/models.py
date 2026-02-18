"""Domain models."""

from dataclasses import dataclass
from enum import Enum, auto


@dataclass
class EnvVar:
    key: str
    value: str
    is_multiline: bool = False

    def matches(self, query: str) -> bool:
        """Return True if key or value contains the query (case-insensitive)."""
        q = query.lower()
        return q in self.key.lower() or q in self.value.lower()


class ActionKind(Enum):
    SET = auto()
    DELETE = auto()
    RENAME = auto()


@dataclass
class Action:
    """A reversible mutation applied to the variable set.

    Used to build an undo stack. Each action records enough information to
    reverse itself:
    - SET (add or edit): reverse by restoring previous_value (or deleting if
      there was no previous value, i.e. it was an add).
    - DELETE: reverse by re-inserting the deleted key/value.
    - RENAME: reverse by renaming new_key back to key (old_key stores the original).
    """

    kind: ActionKind
    key: str
    value: str
    previous_value: str | None = None
    old_key: str | None = None
