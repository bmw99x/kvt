"""Main view: search bar stacked above the environment variable table."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, LoadingIndicator

from kvt.widgets.env_table import EnvTable


class MainView(Vertical):
    """Composes the search input and the env var table into a single panel."""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search keys and values…", id="search")
        yield EnvTable(id="env-table")
        yield LoadingIndicator(id="loading")
