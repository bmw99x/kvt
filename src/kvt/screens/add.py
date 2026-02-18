"""Add screen — modal for inserting a new variable."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Input, Label

from kvt.models import EnvVar

_MULTILINE_PLACEHOLDER = "PLACEHOLDER=\\nEND="


class AddScreen(ModalScreen[EnvVar | None]):
    """Modal that lets the user add a new key/value variable.

    Dismisses with a new EnvVar on save, or None on cancel.
    Inline validation prevents duplicate or blank keys.

    When the "Multiline" checkbox is ticked the value field is hidden and
    the secret is saved as a .env blob stub (``PLACEHOLDER=``).  The user
    then opens the new row via the drill-in to add real inner variables.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, existing_keys: set[str], allow_multiline: bool = True) -> None:
        super().__init__()
        self._existing_keys = existing_keys
        self._allow_multiline = allow_multiline

    def compose(self) -> ComposeResult:
        with Vertical(id="add-container"):
            yield Label("Add variable", id="add-title")
            yield Input(placeholder="KEY", id="add-key")
            checkbox = Checkbox("Multiline (.env blob)", id="add-multiline")
            checkbox.display = self._allow_multiline
            yield checkbox
            yield Input(placeholder="value", id="add-value")
            yield Label("", id="add-error")
            yield Label("Tab · Enter to save · Escape to cancel", id="add-hint")

    def on_mount(self) -> None:
        self.query_one("#add-key", Input).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "add-multiline":
            value_input = self.query_one("#add-value", Input)
            value_input.display = not event.value
            hint = self.query_one("#add-hint", Label)
            if event.value:
                hint.update("Tab · Enter to save · Escape to cancel  [open row with i to edit]")
            else:
                hint.update("Tab · Enter to save · Escape to cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "add-key":
            is_multiline = self.query_one("#add-multiline", Checkbox).value
            if is_multiline:
                self._try_save()
            else:
                self.query_one("#add-value", Input).focus()
            return

        if event.input.id == "add-value":
            self._try_save()

    def _try_save(self) -> None:
        key = self.query_one("#add-key", Input).value.strip()
        error = self.query_one("#add-error", Label)

        if not key:
            error.update("Key cannot be blank")
            self.query_one("#add-key", Input).focus()
            return

        if key in self._existing_keys:
            error.update(f"'{key}' already exists — use edit instead")
            self.query_one("#add-key", Input).focus()
            return

        is_multiline = self.query_one("#add-multiline", Checkbox).value
        if is_multiline:
            self.dismiss(EnvVar(key=key, value=_MULTILINE_PLACEHOLDER, is_multiline=True))
        else:
            value = self.query_one("#add-value", Input).value
            self.dismiss(EnvVar(key=key, value=value))

    def action_cancel(self) -> None:
        self.dismiss(None)
