"""Environment variable table widget."""

from rich.text import Text
from textual.binding import Binding
from textual.events import Click
from textual.message import Message
from textual.widgets import DataTable

from kvt.constants import TABLE_COLUMNS
from kvt.models import EnvVar

_MULTILINE_BADGE = Text("[ env ]", style="bold cyan")


class EnvTable(DataTable):
    """Scrollable table of environment variables with vim-style navigation.

    Rows are keyed by the variable's key name, making it safe to repopulate
    without losing the cursor position across refreshes.

    Multiline secrets (``EnvVar.is_multiline=True``) are rendered with a
    cyan ``[ env ]`` badge in the value column instead of the raw blob, so
    the distinction is immediately visible.  Pressing Enter/i on such a row
    opens a drill-in modal (handled by the app).

    Double-clicking a row posts ``EnvTable.RowDoubleClicked`` so the app
    can open the appropriate edit modal without any keyboard interaction.
    """

    class RowDoubleClicked(Message):
        """Posted when the user double-clicks a row."""

    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    def action_cursor_down(self) -> None:
        """Move down one row, wrapping from the last row to the first."""
        if self.row_count == 0:
            return
        if self.cursor_row == self.row_count - 1:
            self.move_cursor(row=0)
        else:
            super().action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move up one row, wrapping from the first row to the last."""
        if self.row_count == 0:
            return
        if self.cursor_row == 0:
            self.move_cursor(row=self.row_count - 1)
        else:
            super().action_cursor_up()

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns(*TABLE_COLUMNS)

    def load(self, vars: list[EnvVar]) -> None:
        """Replace table contents with a new list of variables."""
        self.clear()
        for i, var in enumerate(vars, start=1):
            value_cell: str | Text = _MULTILINE_BADGE if var.is_multiline else var.value
            self.add_row(str(i), var.key, value_cell, key=var.key)

    def selected_value(self) -> str | None:
        """Return the value cell of the currently highlighted row, or None.

        Returns None for multiline rows (their raw blob is not copyable
        directly; use the drill-in modal instead).
        """
        if self.row_count == 0:
            return None
        cell = self.get_cell_at(self.cursor_coordinate._replace(column=2))
        if isinstance(cell, Text):
            return None
        return str(cell)

    def selected_var_is_multiline(self) -> bool:
        """Return True if the currently selected row is a multiline secret."""
        if self.row_count == 0:
            return False
        cell = self.get_cell_at(self.cursor_coordinate._replace(column=2))
        return isinstance(cell, Text)

    def on_click(self, event: Click) -> None:
        """Post RowDoubleClicked on a double-click (chain == 2)."""
        if event.chain == 2 and self.row_count > 0:
            self.post_message(EnvTable.RowDoubleClicked())
