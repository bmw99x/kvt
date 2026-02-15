# AGENTS.md

## Project overview

`kvt` is a terminal UI (TUI) for managing Azure Key Vault `.env` secrets.
It is built with [Textual](https://textual.textualize.io/) and managed with
[uv](https://docs.astral.sh/uv/). The project is developed in phases:

- **Phase 1** (current): View-only single-page UI with mock data
- **Phase 2**: Edit, add, and delete variables in-UI
- **Phase 3**: Named environments backed by `~/.config/kvt/config.toml`
- **Phase 4**: Live Azure Key Vault integration via `az` CLI

## Setup

```bash
uv sync          # install all deps including dev group
uv run kvt       # run the app
```

## Commands

| Command | Purpose |
|---|---|
| `uv run kvt` | Launch the TUI |
| `uv run pytest` | Run all tests |
| `uv run ruff check src/ tests/` | Lint |
| `uv run ruff format src/ tests/` | Format |
| `uv run ty check src/` | Type check |

Always run lint, format, and type checks before committing.

## Project structure

```
src/kvt/
  app.py               # KvtApp — thin wiring layer only
  app.tcss             # Textual CSS
  constants.py         # All display strings and column definitions
  models.py            # Plain dataclasses (EnvVar, etc.)
  providers.py         # SecretProvider protocol + MockProvider
  screens/             # One file per Textual Screen subclass
  widgets/             # One file per Textual Widget subclass
tests/
  test_models.py       # Unit tests for models
  test_providers.py    # Unit tests for providers
  test_smoke.py        # Headless TUI smoke tests
```

## Code style

- **Python 3.13**, modern type syntax (`X | Y`, `list[X]`, no `Optional`)
- Formatter and linter: `ruff`. Line length 100.
- Type checker: `ty`.
- Docstrings on all public classes and non-trivial methods.
- **No section-divider comments.** Never use `# --- Read operations ---`,
  `# ------------------------------------------------------------------`,
  or any equivalent banner/divider comment to group methods. If a class
  needs that kind of organisation, split it into multiple files or use
  docstrings. The code should be self-evident without decoration.
- Constants (strings, column names, etc.) live in `constants.py`, not inline.
- UI components are composed — one class per file under `screens/` or
  `widgets/`. `app.py` must stay thin (wiring only, no business logic).
- `SecretProvider` is a Protocol. Business logic must not depend on a concrete
  provider — always depend on the protocol.

## Testing

### Two categories of tests

**Unit tests** (`test_models.py`, `test_providers.py`, …)

Cover all non-UI business logic: parsing, filtering, searching, data
transformations. These must not import anything from `textual`.

**Smoke tests** (`test_smoke.py`)

Headless Textual tests using `app.run_test()`. Cover critical user journeys
(mount, navigate, search, edit). Keep them coarse — they verify the app
doesn't crash and key interactions produce the right state, not pixel-perfect
layout.

Smoke tests are `async` functions. `asyncio_mode = "auto"` is configured in
`pyproject.toml`, so no `@pytest.mark.asyncio` decorator is needed.

### Test style

All tests follow **GIVEN / WHEN / THEN** structure expressed as comments:

```python
def test_filter_matches_key():
    """
    Given a variable whose key contains the query
    When we call matches with a lowercase query
    Then it matches case-insensitively
    """
    var = EnvVar(key="DATABASE_URL", value="postgres://localhost/db")
    assert var.matches("database") is True
```

Test function names follow `test_<what>_<condition>` (e.g.
`test_filter_no_match_when_query_absent`).

### Running tests

```bash
uv run pytest                   # all tests
uv run pytest tests/test_models.py   # one file
uv run pytest -k "filter"       # by keyword
```

All tests must pass before committing.
