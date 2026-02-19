"""Add screen — modal for inserting a new variable."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, TextArea

from kvt.models import EnvVar

_MULTILINE_PLACEHOLDER = "PLACEHOLDER=\\nEND="


class AddScreen(ModalScreen[EnvVar | None]):
    """Modal that lets the user add a new key/value variable.

    Dismisses with a new EnvVar on save, or None on cancel.
    Inline validation prevents duplicate or blank keys.

    When the "Multiline" checkbox is ticked the single-line value Input is
    replaced by a TextArea.  Save / Cancel buttons appear below the textarea;
    ``ctrl+w`` saves from anywhere in the modal without moving focus.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+w", "save", show=False, priority=True),
        Binding("h", "focus_save", show=False),
        Binding("l", "focus_cancel", show=False),
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
            yield TextArea(id="add-blob", show_line_numbers=False)
            yield Label("", id="add-error")
            yield Label("Tab · Enter to save · Escape to cancel", id="add-hint")
            with Horizontal(id="add-buttons"):
                yield Button("Save", variant="success", id="add-save")
                yield Button("Cancel", variant="primary", id="add-cancel")

    def on_mount(self) -> None:
        self.query_one("#add-blob", TextArea).display = False
        self.query_one("#add-buttons").display = False
        self.query_one("#add-key", Input).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "add-multiline":
            return
        value_input = self.query_one("#add-value", Input)
        blob_area = self.query_one("#add-blob", TextArea)
        buttons = self.query_one("#add-buttons")
        hint = self.query_one("#add-hint", Label)
        if event.value:
            value_input.display = False
            blob_area.display = True
            buttons.display = True
            blob_area.focus()
            hint.update("ctrl+w to save · Tab to reach buttons · Escape to cancel")
        else:
            blob_area.display = False
            buttons.display = False
            value_input.display = True
            hint.update("Tab · Enter to save · Escape to cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "add-key":
            if self.query_one("#add-multiline", Checkbox).value:
                self.query_one("#add-blob", TextArea).focus()
            else:
                self.query_one("#add-value", Input).focus()
            return

        if event.input.id == "add-value":
            self._try_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-save":
            self._try_save()
        elif event.button.id == "add-cancel":
            self.dismiss(None)

    def action_save(self) -> None:
        """Save — triggered by ctrl+w from anywhere in the modal."""
        self._try_save()

    def action_focus_save(self) -> None:
        if self.query_one("#add-buttons").display:
            self.query_one("#add-save", Button).focus()

    def action_focus_cancel(self) -> None:
        if self.query_one("#add-buttons").display:
            self.query_one("#add-cancel", Button).focus()

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

        if self.query_one("#add-multiline", Checkbox).value:
            raw = self.query_one("#add-blob", TextArea).text
            blob = raw.replace("\n", "\\n").rstrip("\\n") if raw.strip() else _MULTILINE_PLACEHOLDER
            self.dismiss(EnvVar(key=key, value=blob, is_multiline=True))
        else:
            value = self.query_one("#add-value", Input).value
            self.dismiss(EnvVar(key=key, value=value))

    def action_cancel(self) -> None:
        self.dismiss(None)
