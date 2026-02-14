"""Unit tests for config loading, validation, and persistence."""

import json
from pathlib import Path

import pytest

from kvt.config import AzureEnv, Config, ConfigError, load_config, save_config


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


class TestAzureEnv:
    def test_valid_fields(self):
        """
        Given valid field values
        When AzureEnv is constructed
        Then all attributes are set correctly
        """
        env = AzureEnv(
            vault_name="kv-frontend-prod",
            subscription_id="sub-123",
            tenant_id="ten-456",
        )
        assert env.vault_name == "kv-frontend-prod"
        assert env.subscription_id == "sub-123"
        assert env.tenant_id == "ten-456"

    def test_missing_field_raises(self):
        """
        Given a dict missing vault_name
        When AzureEnv.model_validate is called
        Then a ValidationError is raised
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AzureEnv.model_validate({"subscription_id": "s", "tenant_id": "t"})


class TestLoadConfig:
    def test_returns_empty_when_file_missing(self, tmp_path: Path, monkeypatch):
        """
        Given no config file exists
        When load_config is called
        Then it returns an empty dict and creates the file and README
        """
        cfg_path = tmp_path / "config.json"
        readme_path = tmp_path / "README.md"
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("kvt.config._README_PATH", readme_path)

        result = load_config()

        assert result == {}
        assert cfg_path.exists()
        assert readme_path.exists()

    def test_bootstrapped_file_is_valid_json(self, tmp_path: Path, monkeypatch):
        """
        Given no config file exists
        When load_config creates the bootstrap file
        Then config.json is valid JSON containing an empty object
        """
        cfg_path = tmp_path / "config.json"
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("kvt.config._README_PATH", tmp_path / "README.md")

        load_config()

        assert json.loads(cfg_path.read_text()) == {}

    def test_empty_object_returns_empty(self, tmp_path: Path, monkeypatch):
        """
        Given config.json contains {}
        When load_config is called
        Then it returns an empty dict
        """
        cfg_path = tmp_path / "config.json"
        _write(cfg_path, {})
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        assert load_config() == {}

    def test_valid_config_is_parsed(self, tmp_path: Path, monkeypatch):
        """
        Given a valid config.json with one service and one env
        When load_config is called
        Then it returns a Config with the correct AzureEnv
        """
        cfg_path = tmp_path / "config.json"
        _write(
            cfg_path,
            {
                "frontend": {
                    "production": {
                        "vault_name": "kv-fe-prod",
                        "subscription_id": "sub-1",
                        "tenant_id": "ten-1",
                    }
                }
            },
        )
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        result = load_config()

        assert "frontend" in result
        assert "production" in result["frontend"]
        env = result["frontend"]["production"]
        assert isinstance(env, AzureEnv)
        assert env.vault_name == "kv-fe-prod"

    def test_underscore_keys_are_stripped(self, tmp_path: Path, monkeypatch):
        """
        Given config.json contains a top-level key starting with '_'
        When load_config is called
        Then that key is absent from the result
        """
        cfg_path = tmp_path / "config.json"
        _write(
            cfg_path,
            {
                "_example": {
                    "production": {"vault_name": "x", "subscription_id": "s", "tenant_id": "t"}
                },
                "real": {
                    "staging": {
                        "vault_name": "kv-real-stg",
                        "subscription_id": "s2",
                        "tenant_id": "t2",
                    }
                },
            },
        )
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        result = load_config()

        assert "_example" not in result
        assert "real" in result

    def test_underscore_env_keys_are_stripped(self, tmp_path: Path, monkeypatch):
        """
        Given a service has an env key starting with '_'
        When load_config is called
        Then that env is absent from the service's dict
        """
        cfg_path = tmp_path / "config.json"
        _write(
            cfg_path,
            {
                "backend": {
                    "_note": "ignored",
                    "production": {
                        "vault_name": "kv-be-prod",
                        "subscription_id": "s",
                        "tenant_id": "t",
                    },
                }
            },
        )
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        result = load_config()

        assert "_note" not in result["backend"]
        assert "production" in result["backend"]

    def test_invalid_json_raises_config_error(self, tmp_path: Path, monkeypatch):
        """
        Given config.json contains malformed JSON
        When load_config is called
        Then a ConfigError is raised
        """
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{not valid json}")
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        with pytest.raises(ConfigError, match="not valid JSON"):
            load_config()

    def test_non_object_root_raises_config_error(self, tmp_path: Path, monkeypatch):
        """
        Given config.json contains a JSON array at the root
        When load_config is called
        Then a ConfigError is raised
        """
        cfg_path = tmp_path / "config.json"
        _write(cfg_path, [])
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        with pytest.raises(ConfigError, match="top level"):
            load_config()

    def test_invalid_env_object_raises_config_error(self, tmp_path: Path, monkeypatch):
        """
        Given an env entry is missing required fields
        When load_config is called
        Then a ConfigError is raised naming the service/env
        """
        cfg_path = tmp_path / "config.json"
        _write(
            cfg_path,
            {
                "frontend": {
                    "production": {"vault_name": "kv-fe-prod"}  # missing sub/tenant
                }
            },
        )
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        with pytest.raises(ConfigError, match="frontend/production"):
            load_config()

    def test_non_dict_service_raises_config_error(self, tmp_path: Path, monkeypatch):
        """
        Given a service value is not a JSON object
        When load_config is called
        Then a ConfigError is raised naming the service
        """
        cfg_path = tmp_path / "config.json"
        _write(cfg_path, {"frontend": "not-an-object"})
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        with pytest.raises(ConfigError, match="frontend"):
            load_config()

    def test_multiple_services_and_envs(self, tmp_path: Path, monkeypatch):
        """
        Given config.json contains two services each with multiple envs
        When load_config is called
        Then all services and envs are present in the result
        """
        cfg_path = tmp_path / "config.json"
        env_data = {"vault_name": "kv", "subscription_id": "s", "tenant_id": "t"}
        _write(
            cfg_path,
            {
                "frontend": {"production": env_data, "staging": env_data},
                "backend": {"production": env_data},
            },
        )
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        result = load_config()

        assert set(result.keys()) == {"frontend", "backend"}
        assert set(result["frontend"].keys()) == {"production", "staging"}
        assert set(result["backend"].keys()) == {"production"}


class TestSaveConfig:
    def test_round_trip(self, tmp_path: Path, monkeypatch):
        """
        Given a Config object
        When save_config then load_config is called
        Then the loaded config matches the original
        """
        cfg_path = tmp_path / "config.json"
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        original: Config = {
            "frontend": {
                "production": AzureEnv(
                    vault_name="kv-fe-prod",
                    subscription_id="sub-1",
                    tenant_id="ten-1",
                )
            }
        }
        save_config(original)
        result = load_config()

        assert result["frontend"]["production"].vault_name == "kv-fe-prod"
        assert result["frontend"]["production"].subscription_id == "sub-1"

    def test_creates_parent_directory(self, tmp_path: Path, monkeypatch):
        """
        Given the config directory does not exist
        When save_config is called
        Then the directory and file are created
        """
        cfg_path = tmp_path / "nested" / "dir" / "config.json"
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        save_config({})

        assert cfg_path.exists()

    def test_output_is_valid_json(self, tmp_path: Path, monkeypatch):
        """
        Given a non-empty Config
        When save_config is called
        Then the file contains valid, indented JSON
        """
        cfg_path = tmp_path / "config.json"
        monkeypatch.setattr("kvt.config.CONFIG_PATH", cfg_path)

        save_config(
            {
                "infra": {
                    "staging": AzureEnv(
                        vault_name="kv-infra-stg", subscription_id="s", tenant_id="t"
                    )
                }
            }
        )

        data = json.loads(cfg_path.read_text())
        assert data["infra"]["staging"]["vault_name"] == "kv-infra-stg"
