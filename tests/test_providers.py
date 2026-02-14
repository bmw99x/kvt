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
        Given a fresh MockProvider
        When we call list_vars
        Then DATABASE_URL is present in the result set
        """
        keys = {v.key for v in MockProvider().list_vars()}
        assert "DATABASE_URL" in keys


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
