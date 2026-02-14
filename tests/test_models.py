"""Unit tests for domain models."""

from kvt.models import Action, ActionKind, EnvVar


class TestEnvVarMatches:
    def test_matches_key_exact(self):
        """
        Given a variable whose key exactly equals the query
        When we call matches
        Then it returns True
        """
        var = EnvVar(key="DATABASE_URL", value="postgres://localhost/db")
        assert var.matches("DATABASE_URL") is True

    def test_matches_key_substring(self):
        """
        Given a variable whose key contains the query as a substring
        When we call matches
        Then it returns True
        """
        var = EnvVar(key="DATABASE_URL", value="postgres://localhost/db")
        assert var.matches("DATABASE") is True

    def test_matches_key_case_insensitive(self):
        """
        Given a variable with an uppercase key
        When we call matches with a lowercase query
        Then it still returns True
        """
        var = EnvVar(key="DATABASE_URL", value="postgres://localhost/db")
        assert var.matches("database") is True

    def test_matches_value_substring(self):
        """
        Given a variable whose value contains the query as a substring
        When we call matches
        Then it returns True
        """
        var = EnvVar(key="API_KEY", value="sk-live-abc123")
        assert var.matches("abc123") is True

    def test_matches_value_case_insensitive(self):
        """
        Given a variable with a mixed-case value
        When we call matches with a differently-cased query
        Then it still returns True
        """
        var = EnvVar(key="APP_ENV", value="Staging")
        assert var.matches("staging") is True

    def test_no_match_when_query_absent(self):
        """
        Given a variable whose key and value do not contain the query
        When we call matches
        Then it returns False
        """
        var = EnvVar(key="SMTP_HOST", value="smtp.sendgrid.net")
        assert var.matches("postgres") is False

    def test_matches_empty_query(self):
        """
        Given any variable
        When we call matches with an empty string
        Then it returns True (empty string is a substring of everything)
        """
        var = EnvVar(key="FOO", value="bar")
        assert var.matches("") is True

    def test_matches_partial_value(self):
        """
        Given a variable with a URL as its value
        When we call matches with a fragment of that URL
        Then it returns True
        """
        var = EnvVar(key="SENTRY_DSN", value="https://abc@o123.ingest.sentry.io/456")
        assert var.matches("ingest.sentry") is True


class TestEnvVarConstruction:
    def test_key_and_value_stored(self):
        """
        Given key and value strings
        When constructing an EnvVar
        Then both fields are accessible and unchanged
        """
        var = EnvVar(key="MY_KEY", value="my_value")
        assert var.key == "MY_KEY"
        assert var.value == "my_value"

    def test_equality(self):
        """
        Given two EnvVars with identical key and value
        When compared with ==
        Then they are equal
        """
        assert EnvVar(key="X", value="1") == EnvVar(key="X", value="1")

    def test_inequality_on_value(self):
        """
        Given two EnvVars that share a key but differ in value
        When compared with ==
        Then they are not equal
        """
        assert EnvVar(key="X", value="1") != EnvVar(key="X", value="2")


class TestAction:
    def test_set_action_stores_fields(self):
        """
        Given a SET action with key, value and a previous value
        When constructing the Action
        Then all fields are accessible
        """
        action = Action(kind=ActionKind.SET, key="FOO", value="new", previous_value="old")
        assert action.kind == ActionKind.SET
        assert action.key == "FOO"
        assert action.value == "new"
        assert action.previous_value == "old"

    def test_delete_action_previous_value_defaults_to_none(self):
        """
        Given a DELETE action constructed without a previous_value
        When accessing previous_value
        Then it is None
        """
        action = Action(kind=ActionKind.DELETE, key="FOO", value="old")
        assert action.previous_value is None

    def test_set_action_with_no_previous_value_represents_add(self):
        """
        Given a SET action where previous_value is None
        When inspecting the action
        Then it represents an add (no prior value existed)
        """
        action = Action(kind=ActionKind.SET, key="NEW_KEY", value="val", previous_value=None)
        assert action.previous_value is None
