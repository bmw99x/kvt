"""Add screen — modal for inserting a new variable."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from kvt.models import EnvVar


class AddScreen(ModalScreen[EnvVar | None]):
    """Modal that lets the user add a new key/value variable.

    Dismisses with a new EnvVar on save, or None on cancel.
    Inline validation prevents duplicate or blank keys.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, existing_keys: set[str]) -> None:
        super().__init__()
        self._existing_keys = existing_keys

    def compose(self) -> ComposeResult:
        with Vertical(id="add-container"):
            yield Label("Add variable", id="add-title")
            yield Input(placeholder="KEY", id="add-key")
            yield Input(placeholder="value", id="add-value")
            yield Label("", id="add-error")
            yield Label("Tab to next field · Enter to save · Escape to cancel", id="add-hint")

    def on_mount(self) -> None:
        self.query_one("#add-key", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "add-key":
            self.query_one("#add-value", Input).focus()
            return

        if event.input.id == "add-value":
            self._try_save()

    def _try_save(self) -> None:
        key = self.query_one("#add-key", Input).value.strip()
        value = self.query_one("#add-value", Input).value
        error = self.query_one("#add-error", Label)

        if not key:
            error.update("Key cannot be blank")
            self.query_one("#add-key", Input).focus()
            return

        if key in self._existing_keys:
            error.update(f"'{key}' already exists — use edit instead")
            self.query_one("#add-key", Input).focus()
            return

        self.dismiss(EnvVar(key=key, value=value))

    def action_cancel(self) -> None:
        self.dismiss(None)
