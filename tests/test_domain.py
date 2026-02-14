"""Unit tests for kvt.domain.secrets — pure parsing functions."""

from kvt.domain.secrets import classify_secrets, is_multiline, parse_dotenv_blob
from kvt.models import EnvVar


class TestIsMultiline:
    def test_single_line_value_is_not_multiline(self):
        """
        Given a plain single-line value with no backslash-n
        When is_multiline is called
        Then it returns False
        """
        assert is_multiline("production") is False

    def test_value_with_backslash_n_and_assignments_is_multiline(self):
        """
        Given a value that looks like a .env blob (KEY=val\\nKEY2=val2)
        When is_multiline is called
        Then it returns True
        """
        assert is_multiline("DB_HOST=localhost\\nDB_PORT=5432") is True

    def test_backslash_n_without_assignments_is_not_multiline(self):
        """
        Given a value containing \\n but no KEY=value lines
        When is_multiline is called
        Then it returns False (not a .env blob)
        """
        assert is_multiline("This is my\\nmultiline\\nsecret") is False

    def test_empty_string_is_not_multiline(self):
        """
        Given an empty string
        When is_multiline is called
        Then it returns False
        """
        assert is_multiline("") is False

    def test_comment_only_lines_are_not_multiline(self):
        """
        Given a blob containing only comments (# lines) separated by \\n
        When is_multiline is called
        Then it returns False
        """
        assert is_multiline("# comment\\n# another comment") is False

    def test_mixed_comments_and_assignments_is_multiline(self):
        """
        Given a blob with both comment lines and KEY=value lines
        When is_multiline is called
        Then it returns True
        """
        assert is_multiline("# comment\\nDB_HOST=localhost") is True


class TestParseDotenvBlob:
    def test_parses_simple_blob(self):
        """
        Given a simple blob with two KEY=value pairs
        When parse_dotenv_blob is called
        Then it returns two EnvVar instances with correct keys and values
        """
        blob = "DB_HOST=localhost\\nDB_PORT=5432"
        result = parse_dotenv_blob(blob)
        assert result == [
            EnvVar(key="DB_HOST", value="localhost"),
            EnvVar(key="DB_PORT", value="5432"),
        ]

    def test_skips_blank_lines(self):
        """
        Given a blob with a blank line between entries
        When parse_dotenv_blob is called
        Then blank lines are ignored
        """
        blob = "A=1\\n\\nB=2"
        result = parse_dotenv_blob(blob)
        assert len(result) == 2

    def test_skips_comment_lines(self):
        """
        Given a blob with a # comment line
        When parse_dotenv_blob is called
        Then comment lines are ignored
        """
        blob = "# header\\nA=1"
        result = parse_dotenv_blob(blob)
        assert result == [EnvVar(key="A", value="1")]

    def test_value_may_contain_equals(self):
        """
        Given a blob where the value itself contains an = sign
        When parse_dotenv_blob is called
        Then the key is the part before the first = and value is the rest
        """
        blob = "TOKEN=abc=def=="
        result = parse_dotenv_blob(blob)
        assert result == [EnvVar(key="TOKEN", value="abc=def==")]

    def test_empty_value_is_preserved(self):
        """
        Given a blob with KEY= (empty value)
        When parse_dotenv_blob is called
        Then the entry is included with an empty string value
        """
        blob = "EMPTY="
        result = parse_dotenv_blob(blob)
        assert result == [EnvVar(key="EMPTY", value="")]

    def test_whitespace_around_key_is_stripped(self):
        """
        Given a blob with extra spaces around the key
        When parse_dotenv_blob is called
        Then the key is stripped of whitespace
        """
        blob = "  SPACED  =value"
        result = parse_dotenv_blob(blob)
        assert result[0].key == "SPACED"

    def test_returns_empty_list_for_empty_blob(self):
        """
        Given an empty blob string
        When parse_dotenv_blob is called
        Then it returns an empty list
        """
        assert parse_dotenv_blob("") == []


class TestClassifySecrets:
    def test_single_line_secrets_have_is_multiline_false(self):
        """
        Given a dict of plain single-line secrets
        When classify_secrets is called
        Then all EnvVars have is_multiline=False
        """
        raw = {"APP_ENV": "production", "API_KEY": "sk-abc123"}
        result = classify_secrets(raw)
        assert all(not v.is_multiline for v in result)

    def test_dotenv_blob_secret_has_is_multiline_true(self):
        """
        Given a dict containing a .env blob secret
        When classify_secrets is called
        Then the corresponding EnvVar has is_multiline=True
        """
        raw = {"APP_ENV": "staging", "ENV": "DB_HOST=db\\nDB_PORT=5432"}
        result = classify_secrets(raw)
        by_key = {v.key: v for v in result}
        assert by_key["APP_ENV"].is_multiline is False
        assert by_key["ENV"].is_multiline is True

    def test_raw_blob_value_is_preserved_in_envvar(self):
        """
        Given a multiline secret
        When classify_secrets is called
        Then the raw blob is stored in EnvVar.value (not exploded)
        """
        blob = "DB_HOST=db\\nDB_PORT=5432"
        raw = {"ENV": blob}
        result = classify_secrets(raw)
        assert result[0].value == blob
