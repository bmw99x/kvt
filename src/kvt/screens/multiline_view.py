"""Multiline secret drill-in screen.

Opens as a modal showing the inner key/value pairs parsed from a .env blob
secret.  Read-only: the table supports navigation but not editing.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Footer, Label

from kvt.domain.secrets import parse_dotenv_blob
from kvt.widgets.env_table import EnvTable


class MultilineViewScreen(ModalScreen[None]):
    """Read-only modal showing the exploded contents of a multiline secret.

    The secret name is shown as a title; the blob is parsed by
    ``parse_dotenv_blob`` and rendered in a standard ``EnvTable``.
    Dismissed (without a value) by Escape or q.
    """

    BINDINGS = [
        Binding("escape", "dismiss_screen", show=False),
        Binding("q", "dismiss_screen", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "jump_top", show=False),
        Binding("G", "jump_bottom", show=False),
    ]

    def __init__(self, secret_name: str, blob: str) -> None:
        super().__init__()
        self._secret_name = secret_name
        self._vars = parse_dotenv_blob(blob)

    def compose(self) -> ComposeResult:
        yield Label(f"  {self._secret_name}  ·  {len(self._vars)} variable(s)", id="ml-title")
        yield EnvTable(id="ml-table")
        yield Label("  j/k navigate · Esc/q close", id="ml-hint")

    def on_mount(self) -> None:
        table = self.query_one("#ml-table", EnvTable)
        table.load(self._vars)
        table.focus()

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        self.query_one("#ml-table", EnvTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#ml-table", EnvTable).action_cursor_up()

    def action_jump_top(self) -> None:
        self.query_one("#ml-table", EnvTable).move_cursor(row=0)

    def action_jump_bottom(self) -> None:
        table = self.query_one("#ml-table", EnvTable)
        table.move_cursor(row=max(0, table.row_count - 1))
