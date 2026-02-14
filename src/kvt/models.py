from dataclasses import dataclass


@dataclass
class EnvVar:
    key: str
    value: str

    def matches(self, query: str) -> bool:
        """Return True if key or value contains the query (case-insensitive)."""
        q = query.lower()
        return q in self.key.lower() or q in self.value.lower()
