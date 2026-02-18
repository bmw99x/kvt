"""Multiline secret drill-in screen — editable .env blob view.

Opens as a modal showing the inner key/value pairs parsed from a .env blob
secret.  The user can add, edit, rename, and delete inner variables.  On save the
inner vars are re-encoded as a blob and returned; on cancel the original
blob is returned unchanged.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label

from kvt.domain.secrets import encode_dotenv_blob, parse_dotenv_blob
from kvt.models import EnvVar
from kvt.screens.add import AddScreen
from kvt.screens.confirm import ConfirmScreen
from kvt.screens.edit import EditScreen
from kvt.screens.rename import RenameScreen
from kvt.widgets.env_table import EnvTable


class MultilineViewScreen(ModalScreen[str | None]):
    """Editable modal showing the inner variables of a multiline (.env blob) secret.

    The user can add (o), edit (i), rename (r), copy (y), and delete (dd) inner variables.
    Pressing s saves and re-encodes the blob; Esc/q discards changes.
    The result is the new blob string, or None if the user cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("q", "cancel", show=False),
        Binding("s", "save", "Save", show=True),
        Binding("o", "add_var", "Add", show=True),
        Binding("i", "edit_var", "Edit", show=True),
        Binding("r", "rename_var", "Rename", show=True),
        Binding("y", "copy_value", "Copy", show=True),
        Binding("d", "delete_var", "dd Delete", show=True),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "jump_top", show=False),
        Binding("G", "jump_bottom", show=False),
    ]

    def __init__(self, secret_name: str, blob: str) -> None:
        super().__init__()
        self._secret_name = secret_name
        self._original_blob = blob
        self._vars: list[EnvVar] = parse_dotenv_blob(blob)
        self._d_pressed = False
        self._dirty = False

    def compose(self) -> ComposeResult:
        yield Label(f"  {self._secret_name}", id="ml-title")
        yield EnvTable(id="ml-table")
        yield Label("", id="ml-status")
        yield Label(
            "  o add · i edit · r rename · y copy · dd delete · s save · q cancel",
            id="ml-hint",
        )

    def on_mount(self) -> None:
        self._reload_table()
        table = self.query_one("#ml-table", EnvTable)
        table.focus()
        # Focus first row if available
        if table.row_count > 0:
            table.move_cursor(row=0)

    def _reload_table(self) -> None:
        table = self.query_one("#ml-table", EnvTable)
        table.load(self._vars)
        count = len(self._vars)
        self.query_one("#ml-title", Label).update(f"  {self._secret_name}  ·  {count} variable(s)")

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.query_one("#ml-status", Label).update("● unsaved changes")

    def _table(self) -> EnvTable:
        return self.query_one("#ml-table", EnvTable)

    def _selected_key(self) -> str | None:
        table = self._table()
        if table.row_count == 0:
            return None
        cell = table.get_cell_at(table.cursor_coordinate._replace(column=1))
        return str(cell)

    def action_cancel(self) -> None:
        if not self._dirty:
            self.dismiss(None)
            return

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self.dismiss(None)
            else:
                self._table().focus()

        self.app.push_screen(ConfirmScreen("Discard unsaved changes?"), on_confirm)

    def action_save(self) -> None:
        if not self._dirty:
            self.dismiss(None)
            return
        self.dismiss(encode_dotenv_blob(self._vars))

    def action_cursor_down(self) -> None:
        self._table().action_cursor_down()

    def action_cursor_up(self) -> None:
        self._table().action_cursor_up()

    def action_jump_top(self) -> None:
        self._table().move_cursor(row=0)

    def action_jump_bottom(self) -> None:
        table = self._table()
        table.move_cursor(row=max(0, table.row_count - 1))

    def action_add_var(self) -> None:
        existing = {v.key for v in self._vars}

        def on_save(var: EnvVar | None) -> None:
            if var is not None:
                self._vars.append(var)
                self._mark_dirty()
                self._reload_table()
                self._table().move_cursor(row=len(self._vars) - 1)
            self._table().focus()

        self.app.push_screen(AddScreen(existing_keys=existing, allow_multiline=False), on_save)

    def action_edit_var(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        var = next((v for v in self._vars if v.key == key), None)
        if var is None:
            return

        def on_save(new_value: str | None) -> None:
            if new_value is not None:
                var.value = new_value
                self._mark_dirty()
                self._reload_table()
            self._table().focus()

        self.app.push_screen(EditScreen(key=key, current_value=var.value), on_save)

    def action_rename_var(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        var = next((v for v in self._vars if v.key == key), None)
        if var is None:
            return

        existing = {v.key for v in self._vars}

        def on_rename(new_key: str | None) -> None:
            if new_key is not None:
                var.key = new_key
                self._mark_dirty()
                self._reload_table()
            self._table().focus()

        self.app.push_screen(RenameScreen(current_key=key, existing_keys=existing), on_rename)

    def action_copy_value(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        var = next((v for v in self._vars if v.key == key), None)
        if var is None:
            return

        self.app.copy_to_clipboard(var.value)
        self.app.notify("Copied value to clipboard", timeout=2)

    def action_delete_var(self) -> None:
        if self._d_pressed:
            self._d_pressed = False
            key = self._selected_key()
            if key is None:
                return
            self._vars = [v for v in self._vars if v.key != key]
            self._mark_dirty()
            self._reload_table()
            self._table().focus()
        else:
            self._d_pressed = True
            self.set_timer(0.5, self._reset_d)

    def _reset_d(self) -> None:
        self._d_pressed = False

    def on_env_table_row_double_clicked(self, event: EnvTable.RowDoubleClicked) -> None:
        """Handle double-click on a row to open edit modal."""
        self.action_edit_var()
