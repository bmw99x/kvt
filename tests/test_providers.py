"""Unit tests for SecretProvider implementations."""

from kvt.models import EnvVar
from kvt.providers import MockProvider


class TestMockProviderListVars:
    def test_returns_list_of_env_vars(self):
        """
        Given a fresh MockProvider
        When we call list_vars
        Then we get a non-empty list of EnvVar instances
        """
        result = MockProvider().list_vars()
        assert len(result) > 0
        assert all(isinstance(v, EnvVar) for v in result)

    def test_all_vars_have_non_empty_keys(self):
        """
        Given a fresh MockProvider
        When we call list_vars
        Then every returned variable has a non-empty key
        """
        result = MockProvider().list_vars()
        assert all(v.key for v in result)

    def test_all_vars_have_values(self):
        """
        Given a fresh MockProvider
        When we call list_vars
        Then every variable has a value that is not None
        """
        result = MockProvider().list_vars()
        assert all(v.value is not None for v in result)

    def test_keys_are_unique(self):
        """
        Given a fresh MockProvider
        When we call list_vars
        Then there are no duplicate keys
        """
        keys = [v.key for v in MockProvider().list_vars()]
        assert len(keys) == len(set(keys))

    def test_known_var_present(self):
        """
        Given a fresh MockProvider (frontend/staging)
        When we call list_vars
        Then APP_ENV is present in the result set
        """
        keys = {v.key for v in MockProvider().list_vars()}
        assert "APP_ENV" in keys


class TestMockProviderGetRaw:
    def test_raw_is_string(self):
        """
        Given a fresh MockProvider
        When we call get_raw
        Then it returns a string
        """
        assert isinstance(MockProvider().get_raw(), str)

    def test_raw_contains_all_keys(self):
        """
        Given a fresh MockProvider
        When we call get_raw
        Then every key from list_vars appears in the raw output
        """
        provider = MockProvider()
        raw = provider.get_raw()
        assert all(v.key in raw for v in provider.list_vars())

    def test_raw_format_is_key_equals_value(self):
        """
        Given a fresh MockProvider
        When we call get_raw and split it into lines
        Then every non-empty line contains an equals sign
        """
        lines = MockProvider().get_raw().splitlines()
        assert all("=" in line for line in lines if line)

    def test_raw_roundtrips_to_list_vars(self):
        """
        Given a fresh MockProvider
        When we parse the raw output and compare to list_vars
        Then both representations contain the same key-value pairs
        """
        provider = MockProvider()
        raw_pairs = dict(line.split("=", 1) for line in provider.get_raw().splitlines())
        list_pairs = {v.key: v.value for v in provider.list_vars()}
        assert raw_pairs == list_pairs


class TestMockProviderCreate:
    def test_create_new_key(self):
        """
        Given a fresh MockProvider without a NEW_KEY variable
        When we call create with NEW_KEY
        Then get returns the new value
        """
        provider = MockProvider()
        provider.create("NEW_KEY", "new_value")
        assert provider.get("NEW_KEY") == "new_value"

    def test_create_new_key_appears_in_list_vars(self):
        """
        Given a fresh MockProvider
        When we call create with a new key
        Then the new variable appears in list_vars
        """
        provider = MockProvider()
        provider.create("NEW_KEY", "new_value")
        keys = {v.key for v in provider.list_vars()}
        assert "NEW_KEY" in keys


class TestMockProviderUpdate:
    def test_update_existing_key_changes_value(self):
        """
        Given a MockProvider with DEBUG=false
        When we call update to change DEBUG to true
        Then get returns the updated value
        """
        provider = MockProvider()
        provider.update("DEBUG", "true")
        assert provider.get("DEBUG") == "true"

    def test_update_does_not_create_duplicate(self):
        """
        Given a MockProvider with an existing key
        When we call update on that key
        Then list_vars still contains only one entry for that key
        """
        provider = MockProvider()
        provider.update("DEBUG", "true")
        keys = [v.key for v in provider.list_vars()]
        assert keys.count("DEBUG") == 1


class TestMockProviderDelete:
    def test_delete_removes_key(self):
        """
        Given a MockProvider containing DEBUG
        When we call delete for DEBUG
        Then get returns None for DEBUG
        """
        provider = MockProvider()
        provider.delete("DEBUG")
        assert provider.get("DEBUG") is None

    def test_delete_removes_from_list_vars(self):
        """
        Given a MockProvider containing DEBUG
        When we call delete for DEBUG
        Then DEBUG does not appear in list_vars
        """
        provider = MockProvider()
        provider.delete("DEBUG")
        keys = {v.key for v in provider.list_vars()}
        assert "DEBUG" not in keys

    def test_delete_absent_key_is_noop(self):
        """
        Given a MockProvider that does not contain NONEXISTENT
        When we call delete for NONEXISTENT
        Then no exception is raised and list_vars is unchanged
        """
        provider = MockProvider()
        count_before = len(provider.list_vars())
        provider.delete("NONEXISTENT")
        assert len(provider.list_vars()) == count_before


class TestMockProviderGet:
    def test_get_existing_key(self):
        """
        Given a MockProvider with APP_ENV=staging
        When we call get for APP_ENV
        Then it returns 'staging'
        """
        assert MockProvider().get("APP_ENV") == "staging"

    def test_get_absent_key_returns_none(self):
        """
        Given a MockProvider that does not contain NONEXISTENT
        When we call get for NONEXISTENT
        Then it returns None
        """
        assert MockProvider().get("NONEXISTENT") is None
