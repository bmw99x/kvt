"""Secret provider protocol and implementations."""

from typing import Protocol

from kvt.constants import DEFAULT_ENV, DEFAULT_PROJECT, MOCK_DATA
from kvt.domain.secrets import classify_secrets
from kvt.models import EnvVar


class SecretProvider(Protocol):
    """Protocol that all secret backends must satisfy."""

    def list_vars(self) -> list[EnvVar]: ...

    def get_raw(self) -> str:
        """Return the full .env content as a string."""
        ...

    def get(self, key: str) -> str | None:
        """Return the current value for a key, or None if absent."""
        ...

    def create(self, key: str, value: str) -> None:
        """Insert a new variable. Behaviour is undefined if the key already exists."""
        ...

    def update(self, key: str, value: str) -> None:
        """Update the value of an existing variable."""
        ...

    def delete(self, key: str) -> None:
        """Remove a variable by key. No-op if the key does not exist."""
        ...


class MockProvider:
    """In-memory provider seeded from MOCK_DATA for the given project and env."""

    def __init__(self, project: str = DEFAULT_PROJECT, env: str = DEFAULT_ENV) -> None:
        self._data: dict[str, str] = dict(MOCK_DATA.get(project, {}).get(env, {}))

    def list_vars(self) -> list[EnvVar]:
        return classify_secrets(self._data)

    def get_raw(self) -> str:
        return "\n".join(f"{k}={v}" for k, v in self._data.items())

    def get(self, key: str) -> str | None:
        """Return the current value for a key, or None if absent."""
        return self._data.get(key)

    def create(self, key: str, value: str) -> None:
        """Insert a new variable. Preserves insertion order."""
        self._data[key] = value

    def update(self, key: str, value: str) -> None:
        """Update the value of an existing variable."""
        self._data[key] = value

    def delete(self, key: str) -> None:
        """Remove a variable. No-op if absent."""
        self._data.pop(key, None)
