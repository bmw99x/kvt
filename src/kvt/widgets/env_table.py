"""Environment variable table widget."""

from textual.binding import Binding
from textual.widgets import DataTable

from kvt.constants import TABLE_COLUMNS
from kvt.models import EnvVar


class EnvTable(DataTable):
    """Scrollable table of environment variables with vim-style navigation.

    Rows are keyed by the variable's key name, making it safe to repopulate
    without losing the cursor position across refreshes.
    """

    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns(*TABLE_COLUMNS)

    def load(self, vars: list[EnvVar]) -> None:
        """Replace table contents with a new list of variables."""
        self.clear()
        for i, var in enumerate(vars, start=1):
            self.add_row(str(i), var.key, var.value, key=var.key)

    def selected_value(self) -> str | None:
        """Return the value cell of the currently highlighted row, or None."""
        if self.row_count == 0:
            return None
        cell = self.get_cell_at(self.cursor_coordinate._replace(column=2))
        return str(cell)
