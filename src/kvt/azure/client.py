"""Thin wrapper around the Azure CLI for Key Vault secret operations.

All calls shell out to ``az keyvault secret`` so no Azure SDK dependency
is required.  The caller is responsible for ensuring ``az`` is authenticated
(``az login`` or a service principal in the environment).

Raises ``AzureClientError`` on any non-zero exit code.
"""

import json
import subprocess
import tempfile
from pathlib import Path


class AzureClientError(Exception):
    """Raised when an ``az`` CLI call returns a non-zero exit code."""


class AzureClient:
    """Shells out to the Azure CLI to read and write Key Vault secrets.

    Args:
        vault_name: The short vault name (not the full URI).
        subscription_id: Azure subscription ID to set as active context.
    """

    def __init__(self, vault_name: str, subscription_id: str) -> None:
        self._vault = vault_name
        self._subscription = subscription_id

    def list_secrets(self) -> dict[str, str]:
        """Return all enabled secrets as a key→value dict.

        Fetches the list of secret names first, then fetches each value
        individually (the list API does not return values).
        """
        names = self._list_names()
        return {name: self._get_value(name) for name in names}

    def get_secret(self, name: str) -> str:
        """Return the current value of a single secret."""
        return self._get_value(name)

    def set_secret(self, name: str, value: str) -> None:
        """Create or update a secret.

        Multiline values (containing actual newlines or ``\\n``) are written
        via a temp file to avoid shell quoting issues.
        """
        if "\n" in value or "\\n" in value:
            self._set_via_file(name, value)
        else:
            self._run(
                [
                    "az",
                    "keyvault",
                    "secret",
                    "set",
                    "--vault-name",
                    self._vault,
                    "--name",
                    name,
                    "--value",
                    value,
                ]
            )

    def delete_secret(self, name: str) -> None:
        """Soft-delete a secret (can be recovered until purge)."""
        self._run(
            ["az", "keyvault", "secret", "delete", "--vault-name", self._vault, "--name", name]
        )

    def _list_names(self) -> list[str]:
        result = self._run(
            [
                "az",
                "keyvault",
                "secret",
                "list",
                "--vault-name",
                self._vault,
                "--subscription",
                self._subscription,
                "--query",
                "[?attributes.enabled].name",
                "--output",
                "json",
            ]
        )
        names: list[str] = json.loads(result)
        return names

    def _get_value(self, name: str) -> str:
        result = self._run(
            [
                "az",
                "keyvault",
                "secret",
                "show",
                "--vault-name",
                self._vault,
                "--subscription",
                self._subscription,
                "--name",
                name,
                "--query",
                "value",
                "--output",
                "tsv",
            ]
        )
        # tsv output strips surrounding quotes; strip trailing newline.
        return result.rstrip("\n")

    def _set_via_file(self, name: str, value: str) -> None:
        """Write a multiline value through a temporary file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(value)
            tmp = Path(f.name)
        try:
            self._run(
                [
                    "az",
                    "keyvault",
                    "secret",
                    "set",
                    "--vault-name",
                    self._vault,
                    "--name",
                    name,
                    "--file",
                    str(tmp),
                ]
            )
        finally:
            tmp.unlink(missing_ok=True)

    def _run(self, cmd: list[str]) -> str:
        """Run a command, returning stdout. Raises AzureClientError on failure."""
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise AzureClientError(
                f"Command failed (exit {result.returncode}):\n"
                f"  {' '.join(cmd)}\n"
                f"  stderr: {result.stderr.strip()}"
            )
        return result.stdout
