"""Secret provider protocol and implementations."""

from typing import Protocol

from kvt.models import EnvVar


class SecretProvider(Protocol):
    """Protocol that all secret backends must satisfy."""

    def list_vars(self) -> list[EnvVar]: ...

    def get_raw(self) -> str:
        """Return the full .env content as a string."""
        ...

    def set_var(self, key: str, value: str) -> None:
        """Insert or update a variable by key."""
        ...

    def delete_var(self, key: str) -> None:
        """Remove a variable by key. No-op if the key does not exist."""
        ...

    def get_var(self, key: str) -> str | None:
        """Return the current value for a key, or None if absent."""
        ...


class MockProvider:
    """In-memory provider for UI development and testing."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {
            "APP_ENV": "staging",
            "DEBUG": "false",
            "LOG_LEVEL": "info",
            "SECRET_KEY": "s3cr3t-k3y-do-not-share-xK9mP2nQ",
            "DATABASE_URL": "postgres://app_user:p@ssw0rd@db.internal:5432/appdb",
            "DATABASE_POOL_SIZE": "10",
            "REDIS_URL": "redis://:r3d1s_p@ss@cache.internal:6379/0",
            "API_KEY": "sk-live-4fGhJ8kLmNpQrStUvWxYz",
            "API_BASE_URL": "https://api.example.com/v2",
            "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "SENTRY_DSN": "https://abc123def456@o987654.ingest.sentry.io/1234567",
            "SMTP_HOST": "smtp.sendgrid.net",
            "SMTP_PORT": "587",
            "SMTP_USER": "apikey",
            "SMTP_PASSWORD": "SG.aBcDeFgHiJkLmNoPqRsTuVwXyZ",
            "CORS_ORIGINS": "https://app.example.com,https://admin.example.com",
            "JWT_SECRET": "jwt-secret-xYz-7a8b9c0d1e2f3g4h",
            "JWT_EXPIRY_SECONDS": "3600",
        }

    def list_vars(self) -> list[EnvVar]:
        return [EnvVar(key=k, value=v) for k, v in self._data.items()]

    def get_raw(self) -> str:
        return "\n".join(f"{k}={v}" for k, v in self._data.items())

    def set_var(self, key: str, value: str) -> None:
        """Insert or update a variable. Preserves insertion order for new keys."""
        self._data[key] = value

    def delete_var(self, key: str) -> None:
        """Remove a variable. No-op if absent."""
        self._data.pop(key, None)

    def get_var(self, key: str) -> str | None:
        """Return the current value for a key, or None if absent."""
        return self._data.get(key)
