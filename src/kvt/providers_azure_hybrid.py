"""Hybrid Azure Key Vault secret provider with lazy value loading.

Implements the ``SecretProvider`` protocol with a hybrid approach:
- Lists secret names immediately (fast operation)
- Returns EnvVars with placeholder values initially
- Fetches actual values in background using ThreadPoolExecutor
- Supports progressive updates as values arrive
"""

from kvt.azure.client import AzureClient
from kvt.config import AzureEnv
from kvt.domain.secrets import classify_secrets
from kvt.models import EnvVar


class HybridAzureProvider:
    """SecretProvider with hybrid loading - fast list, lazy values.

    Construction is fast (only lists secret names).
    Values are fetched lazily or in batch using background threads.
    """

    def __init__(self, env: AzureEnv) -> None:
        self._client = AzureClient(env.vault_name, env.subscription_id)
        # Fast operation - just get the names
        self._names = self._client.list_secret_names()
        self._data: dict[str, str | None] = {name: None for name in self._names}
        self._values_loaded = False

    def list_vars(self) -> list[EnvVar]:
        """Return all secrets with values (or placeholders if not loaded)."""
        # For display, use placeholder if value not loaded yet
        display_data = {
            name: value if value is not None else "Loading..." for name, value in self._data.items()
        }
        return classify_secrets(display_data)

    def get_raw(self) -> str:
        return "\n".join(f"{k}={v or ''}" for k, v in self._data.items())

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def is_value_loaded(self, key: str) -> bool:
        """Check if a specific secret's value has been loaded."""
        return self._data.get(key) is not None

    def fetch_all_values(self) -> dict[str, str]:
        """Fetch all secret values in parallel using thread pool.

        Returns dict of name→value, also updates internal cache.
        """
        names_without_values = [name for name, value in self._data.items() if value is None]
        if not names_without_values:
            return {k: v for k, v in self._data.items() if v is not None}

        values = self._client.fetch_values_batch(names_without_values)
        # Update internal cache
        for name, value in values.items():
            self._data[name] = value

        self._values_loaded = all(v is not None for v in self._data.values())
        return values

    def fetch_value(self, name: str) -> str:
        """Fetch a single secret value and cache it."""
        value = self._client.get_secret_value(name)
        self._data[name] = value
        return value

    def create(self, key: str, value: str) -> None:
        self._client.set_secret(key, value)
        self._data[key] = value
        if key not in self._names:
            self._names.append(key)

    def update(self, key: str, value: str) -> None:
        self._client.set_secret(key, value)
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._client.delete_secret(key)
        self._data.pop(key, None)
        if key in self._names:
            self._names.remove(key)
