"""Config file loading, validation, and persistence.

Schema on disk (~/.config/kvt/config.json):

    {
        "frontend": {
            "production": {
                "vault_name": "kv-frontend-prod",
                "subscription_id": "00000000-0000-0000-0000-000000000000",
                "tenant_id": "00000000-0000-0000-0000-000000000001"
            }
        }
    }

Keys prefixed with "_" are reserved (e.g. "_example") and are stripped on load.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

CONFIG_PATH = Path("~/.config/kvt/config.json").expanduser()

_README_PATH = Path("~/.config/kvt/README.md").expanduser()

_README_CONTENT = """\
# kvt configuration

Edit `config.json` in this directory to register your Azure Key Vault projects.

## Schema

```json
{
    "<service-name>": {
        "<environment-name>": {
            "vault_name": "kv-myapp-prod",
            "subscription_id": "00000000-0000-0000-0000-000000000000",
            "tenant_id": "00000000-0000-0000-0000-000000000001"
        }
    }
}
```

## Example

```json
{
    "frontend": {
        "production": {
            "vault_name": "kv-frontend-prod",
            "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "tenant_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
        },
        "staging": {
            "vault_name": "kv-frontend-stg",
            "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "tenant_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
        }
    }
}
```

Keys prefixed with `_` (e.g. `_example`) are ignored by kvt.
"""


class AzureEnv(BaseModel):
    """A single Azure Key Vault environment binding."""

    vault_name: str
    subscription_id: str
    tenant_id: str


# service_name -> env_name -> AzureEnv
Config = dict[str, dict[str, AzureEnv]]


class ConfigError(Exception):
    """Raised when config.json exists but cannot be parsed or validated."""


def load_config() -> Config:
    """Load and validate the config file.

    Creates the config directory, an empty config.json, and a README on first
    run.  Returns an empty dict if the file is empty or contains no real
    entries.  Raises ConfigError if the file exists but is malformed.
    """
    if not CONFIG_PATH.exists():
        _bootstrap()
        return {}

    try:
        raw: object = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config.json is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("config.json must be a JSON object at the top level")

    # Strip reserved/comment keys.
    services = {k: v for k, v in raw.items() if not k.startswith("_")}

    config: Config = {}
    for service, envs in services.items():
        if not isinstance(envs, dict):
            raise ConfigError(f"Service '{service}' must be a JSON object")
        config[service] = {}
        for env_name, env_data in envs.items():
            if env_name.startswith("_"):
                continue
            try:
                config[service][env_name] = AzureEnv.model_validate(env_data)
            except ValidationError as exc:
                raise ConfigError(f"Invalid config for {service}/{env_name}: {exc}") from exc

    return config


def save_config(config: Config) -> None:
    """Persist config to disk, creating directories as needed."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        service: {env_name: azure_env.model_dump() for env_name, azure_env in envs.items()}
        for service, envs in config.items()
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2))


def _bootstrap() -> None:
    """Create the config directory, an empty config.json, and a README."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text("{}\n")
    if not _README_PATH.exists():
        _README_PATH.write_text(_README_CONTENT)


# Theme persistence
THEME_CONFIG_PATH = Path("~/.config/kvt/theme.json").expanduser()


def load_theme() -> str | None:
    """Load the saved theme preference.
    
    Returns the theme name if set, None otherwise.
    """
    if not THEME_CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(THEME_CONFIG_PATH.read_text())
        return data.get("theme")
    except (json.JSONDecodeError, AttributeError):
        return None


def save_theme(theme: str) -> None:
    """Save the theme preference to disk."""
    THEME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    THEME_CONFIG_PATH.write_text(json.dumps({"theme": theme}, indent=2))
