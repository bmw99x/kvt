"""Main application entry point."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input

from kvt.constants import APP_SUBTITLE, APP_TITLE
from kvt.models import EnvVar
from kvt.providers import MockProvider, SecretProvider
from kvt.screens.help import HelpScreen
from kvt.widgets.env_table import EnvTable
from kvt.widgets.main_view import MainView


class KvtApp(App):
    """kvt — Azure Key Vault TUI."""

    CSS_PATH = "app.tcss"
    TITLE = APP_TITLE
    SUB_TITLE = APP_SUBTITLE

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "toggle_help", "Help"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "clear_search", show=False),
        Binding("g", "jump_top", show=False),
        Binding("G", "jump_bottom", show=False),
        Binding("y", "copy_value", "Copy value"),
    ]

    def __init__(self, provider: SecretProvider | None = None) -> None:
        super().__init__()
        self._provider: SecretProvider = provider or MockProvider()
        self._all_vars: list[EnvVar] = []
        self._filter: str = ""
        self._g_pressed: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield MainView(id="main")
        yield Footer()

    def on_mount(self) -> None:
        self._all_vars = self._provider.list_vars()
        self.query_one("#search", Input).display = False
        self._refresh_table()
        self._get_table().focus()

    def _get_table(self) -> EnvTable:
        return self.query_one("#env-table", EnvTable)

    def _refresh_table(self) -> None:
        """Repopulate the table, applying the current filter if any."""
        vars = (
            [v for v in self._all_vars if v.matches(self._filter)]
            if self._filter
            else self._all_vars
        )
        self._get_table().load(vars)

    def action_toggle_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_focus_search(self) -> None:
        """Show and focus the search bar."""
        search = self.query_one("#search", Input)
        search.display = True
        search.focus()

    def action_clear_search(self) -> None:
        """Clear active filter and hide the search bar."""
        search = self.query_one("#search", Input)
        if search.value:
            search.value = ""
            self._filter = ""
            self._refresh_table()
        search.display = False
        self._get_table().focus()

    def action_jump_top(self) -> None:
        """Implement vim-style gg: move to the first row on the second g press.

        First g press arms the chord and starts a short timer. If a second g
        arrives before the timer fires the cursor jumps to row 0. If the timer
        fires first the flag is cleared and the lone g is silently consumed.
        """
        if self._g_pressed:
            self._g_pressed = False
            self._get_table().move_cursor(row=0)
        else:
            self._g_pressed = True
            self.set_timer(0.5, self._reset_g)

    def _reset_g(self) -> None:
        self._g_pressed = False

    def action_jump_bottom(self) -> None:
        """Move cursor to the last row (vim G)."""
        table = self._get_table()
        table.move_cursor(row=table.row_count - 1)

    def action_copy_value(self) -> None:
        """Copy the selected row's value to the system clipboard."""
        value = self._get_table().selected_value()
        if value is None:
            return
        self.app.copy_to_clipboard(value)
        self.notify("Copied value to clipboard", timeout=2)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._filter = event.value
            self._refresh_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            self._get_table().focus()


def main() -> None:
    KvtApp().run()


if __name__ == "__main__":
    main()
