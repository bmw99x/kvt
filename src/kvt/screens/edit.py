"""Edit screen — modal for changing an existing variable's value."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class EditScreen(ModalScreen[str | None]):
    """Modal that lets the user edit the value of an existing variable.

    Dismisses with the new value string on save, or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, key: str, current_value: str) -> None:
        super().__init__()
        self._key = key
        self._current_value = current_value

    def compose(self) -> ComposeResult:
        with Vertical(id="edit-container"):
            yield Label(f"Edit  {self._key}", id="edit-title")
            yield Input(value=self._current_value, id="edit-value")
            yield Label("Enter to save · Escape to cancel", id="edit-hint")

    def on_mount(self) -> None:
        input = self.query_one("#edit-value", Input)
        input.focus()
        input.cursor_position = len(self._current_value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
