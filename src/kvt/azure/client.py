"""Thin wrapper around the Azure CLI for Key Vault secret operations.

All calls shell out to ``az keyvault secret`` so no Azure SDK dependency
is required.  The caller is responsible for ensuring ``az`` is authenticated
(``az login`` or a service principal in the environment).

Raises ``AzureClientError`` on any non-zero exit code.
"""

import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        names = self.list_secret_names()
        return {name: self._get_value(name) for name in names}

    def list_secret_names(self) -> list[str]:
        """Return list of all enabled secret names (fast operation)."""
        return self._list_names()

    def get_secret_value(self, name: str) -> str:
        """Return the current value of a single secret."""
        return self._get_value(name)

    def fetch_values_batch(self, names: list[str], max_workers: int = 10) -> dict[str, str]:
        """Fetch multiple secret values in parallel using thread pool.
        
        Args:
            names: List of secret names to fetch
            max_workers: Maximum number of parallel threads
            
        Returns:
            Dict mapping secret names to their values
        """
        values = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all fetch jobs
            future_to_name = {executor.submit(self._get_value, name): name for name in names}
            
            # Collect results as they complete
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    values[name] = future.result()
                except Exception as exc:
                    # Log error but continue fetching other secrets
                    raise AzureClientError(f"Failed to fetch secret '{name}': {exc}") from exc
        
        return values

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
        # tsv output appends a trailing newline of its own; remove exactly one.
        value = result.removesuffix("\n")
        # Azure stores multiline blobs with real newlines; normalise to the
        # canonical literal-\n form that the domain layer expects.
        return value.replace("\n", "\\n")

    def _set_via_file(self, name: str, value: str) -> None:
        """Write a multiline value through a temporary file.

        The domain layer stores multiline blobs with literal ``\\n`` sequences;
        expand them to real newlines before writing so Azure stores the value
        correctly.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(value.replace("\\n", "\n"))
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
