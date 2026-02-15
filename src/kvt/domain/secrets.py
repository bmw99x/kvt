"""Pure domain functions for secret classification and parsing.

Azure Key Vault stores multiline secrets (e.g. a .env-file blob) as a
single string value with literal ``\\n`` characters (backslash-n, not
actual newlines).  These functions classify and explode such values into
individual key/value pairs without any I/O.
"""

from kvt.models import EnvVar


def is_multiline(value: str) -> bool:
    """Return True if the secret value is a multiline .env blob.

    Azure serialises newlines as the two-character sequence ``\\n``.
    A value is considered multiline if it contains at least one such
    sequence AND at least one of the resulting lines looks like a shell
    variable assignment (``KEY=value`` or ``KEY=``).
    """
    if "\\n" not in value:
        return False
    lines = value.split("\\n")
    return any("=" in line and not line.startswith("#") for line in lines if line.strip())


def parse_dotenv_blob(blob: str) -> list[EnvVar]:
    """Explode a multiline .env blob into individual EnvVar instances.

    Each ``\\n``-separated line is processed:
    - Blank lines and lines starting with ``#`` are skipped.
    - Lines containing ``=`` are split on the first ``=`` only, so values
      may themselves contain ``=`` (e.g. base64 tokens).
    - Leading/trailing whitespace is stripped from keys; values are kept
      as-is (no quote stripping, to avoid mangling quoted strings).
    """
    vars: list[EnvVar] = []
    for line in blob.split("\\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key:
            vars.append(EnvVar(key=key, value=value))
    return vars


def encode_dotenv_blob(vars: list[EnvVar]) -> str:
    """Encode a list of EnvVar instances back into an Azure-style .env blob.

    Lines are joined with literal ``\\n`` (backslash-n), matching the format
    Azure Key Vault uses when storing multiline secrets.  Each entry is
    serialised as ``KEY=value`` with no quoting.

    An empty list produces an empty string.
    """
    return "\\n".join(f"{v.key}={v.value}" for v in vars)


def classify_secrets(raw: dict[str, str]) -> list[EnvVar]:
    """Convert a flat key→value dict from Azure into a typed EnvVar list.

    Multiline secrets are tagged with ``is_multiline=True``; their
    ``value`` is kept as the raw blob so the caller can call
    ``parse_dotenv_blob`` on demand (e.g. when the user drills in).
    """
    result: list[EnvVar] = []
    for key, value in raw.items():
        multiline = is_multiline(value)
        result.append(EnvVar(key=key, value=value, is_multiline=multiline))
    return result
