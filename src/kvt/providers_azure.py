"""Azure Key Vault secret provider.

Implements the ``SecretProvider`` protocol using ``AzureClient`` for I/O
and domain functions from ``kvt.domain.secrets`` for classification.
"""

from kvt.azure.client import AzureClient
from kvt.config import AzureEnv
from kvt.domain.secrets import classify_secrets
from kvt.models import EnvVar


class AzureProvider:
    """SecretProvider backed by a real Azure Key Vault via the az CLI.

    On construction the full secret list is fetched and cached in memory.
    Write operations (create/update/delete) hit the vault immediately and
    refresh the in-memory cache so subsequent ``list_vars`` calls are consistent.
    """

    def __init__(self, env: AzureEnv) -> None:
        self._client = AzureClient(env.vault_name, env.subscription_id)
        self._data: dict[str, str] = self._client.list_secrets()

    # ------------------------------------------------------------------
    # SecretProvider protocol
    # ------------------------------------------------------------------

    def list_vars(self) -> list[EnvVar]:
        """Return all secrets, tagged as multiline where appropriate."""
        return classify_secrets(self._data)

    def get_raw(self) -> str:
        return "\n".join(f"{k}={v}" for k, v in self._data.items())

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def create(self, key: str, value: str) -> None:
        self._client.set_secret(key, value)
        self._data[key] = value

    def update(self, key: str, value: str) -> None:
        self._client.set_secret(key, value)
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._client.delete_secret(key)
        self._data.pop(key, None)
