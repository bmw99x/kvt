from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Static

from kvt.models import EnvVar
from kvt.providers import MockProvider, SecretProvider

# ---------------------------------------------------------------------------
# Help overlay
# ---------------------------------------------------------------------------

HELP_TEXT = """\
 Navigation
 ──────────────────────────────
 j / ↓        Move down
 k / ↑        Move up
 g g          Jump to top
 G            Jump to bottom

 Search
 ──────────────────────────────
 /            Open search
 Escape       Clear search / close

 General
 ──────────────────────────────
 y            Copy value to clipboard
 ?            Toggle this help
 q            Quit\
"""


class HelpScreen(ModalScreen):
    """Full-screen help overlay."""

    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("?", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static(HELP_TEXT, id="help-text"),
            id="help-container",
        )

    def on_click(self) -> None:
        self.dismiss()


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------


class EnvTable(DataTable):
    """DataTable with j/k vim navigation wired up."""

    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]


class MainScreen(Vertical):
    """The root widget: search bar + env var table."""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search keys and values…", id="search")
        yield EnvTable(id="env-table", cursor_type="row", zebra_stripes=True)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


class KvtApp(App):
    """kvt — Azure Key Vault TUI."""

    CSS_PATH = "app.tcss"
    TITLE = "kvt"
    SUB_TITLE = "Azure Key Vault · mock"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "toggle_help", "Help"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "clear_search", show=False),
        Binding("g", "jump_top", show=False),
        Binding("G", "jump_bottom", "Bottom", show=False),
        Binding("y", "copy_value", "Copy value"),
    ]

    def __init__(self, provider: SecretProvider | None = None) -> None:
        super().__init__()
        self._provider: SecretProvider = provider or MockProvider()
        self._all_vars: list[EnvVar] = []
        self._filter: str = ""
        self._g_pressed: bool = False  # for gg double-tap detection

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield MainScreen(id="main")
        yield Footer()

    def on_mount(self) -> None:
        self._all_vars = self._provider.list_vars()
        search = self.query_one("#search", Input)
        search.display = False
        self._populate_table(self._all_vars)
        self._get_table().focus()

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def _get_table(self) -> EnvTable:
        return self.query_one("#env-table", EnvTable)

    def _populate_table(self, vars: list[EnvVar]) -> None:
        table = self._get_table()
        table.clear(columns=True)
        table.add_columns("#", "Key", "Value")
        for i, var in enumerate(vars, start=1):
            table.add_row(str(i), var.key, var.value, key=var.key)

    def _refresh_table(self) -> None:
        if self._filter:
            filtered = [v for v in self._all_vars if v.matches(self._filter)]
        else:
            filtered = self._all_vars
        self._populate_table(filtered)

    # ------------------------------------------------------------------
    # Key actions
    # ------------------------------------------------------------------

    def action_toggle_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_focus_search(self) -> None:
        search = self.query_one("#search", Input)
        search.display = True
        search.focus()

    def action_clear_search(self) -> None:
        search = self.query_one("#search", Input)
        if search.value:
            search.value = ""
            self._filter = ""
            self._refresh_table()
        search.display = False
        self._get_table().focus()

    def action_jump_top(self) -> None:
        # Second 'g' in 'gg' — first press sets flag
        if self._g_pressed:
            self._g_pressed = False
            self._get_table().move_cursor(row=0)
        else:
            self._g_pressed = True
            # Reset after a short delay so a lone 'g' doesn't hang
            self.set_timer(0.5, self._reset_g)

    def _reset_g(self) -> None:
        self._g_pressed = False

    def action_jump_bottom(self) -> None:
        table = self._get_table()
        table.move_cursor(row=table.row_count - 1)

    def action_copy_value(self) -> None:
        table = self._get_table()
        row_key = table.cursor_row
        if row_key < 0 or row_key >= table.row_count:
            return
        # Value is in column index 2
        cell = table.get_cell_at(table.cursor_coordinate._replace(column=2))
        self.app.copy_to_clipboard(str(cell))
        self.notify("Copied value to clipboard", timeout=2)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._filter = event.value
            self._refresh_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            # Enter from search → move focus back to table
            self._get_table().focus()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = KvtApp()
    app.run()


if __name__ == "__main__":
    main()
