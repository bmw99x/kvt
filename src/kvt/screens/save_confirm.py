"""Save-confirm screen — shows a coloured diff of pending changes before writing."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from kvt.models import Action, ActionKind


class SaveConfirmScreen(ModalScreen[bool]):
    """Modal showing a coloured diff of staged changes.

    Presents:
      + Added vars in green
      - Removed vars in red
      ~ Renamed vars (old → new) in yellow
      * Edited vars in blue

    Dismisses True on confirm, False on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("n", "cancel", show=False),
        Binding("q", "cancel", show=False),
        Binding("y", "confirm", show=False),
        Binding("h", "focus_no", show=False),
        Binding("left", "focus_no", show=False),
        Binding("l", "focus_yes", show=False),
        Binding("right", "focus_yes", show=False),
    ]

    def __init__(self, actions: list[Action]) -> None:
        super().__init__()
        self._actions = actions

    def compose(self) -> ComposeResult:
        with Vertical(id="save-confirm-container"):
            yield Label("Save changes?", id="save-confirm-title")
            with ScrollableContainer(id="save-confirm-diff"):
                for line in self._diff_lines():
                    yield Label(line, markup=True)
            with Horizontal(id="save-confirm-buttons"):
                yield Button("Save", variant="success", id="save-confirm-yes")
                yield Button("Cancel", variant="primary", id="save-confirm-no")

    def on_mount(self) -> None:
        self.query_one("#save-confirm-no", Button).focus()

    def _diff_lines(self) -> list[str]:
        lines: list[str] = []
        for action in self._actions:
            if action.kind == ActionKind.RENAME:
                old = action.old_key or "?"
                lines.append(f"[yellow]~  {old}  →  {action.key}[/]")
            elif action.kind == ActionKind.DELETE:
                lines.append(f"[red]-  {action.key}[/]")
            elif action.kind == ActionKind.SET:
                if action.previous_value is None:
                    lines.append(f"[green]+  {action.key}[/]")
                else:
                    lines.append(f"[blue]*  {action.key}[/]")
        return lines or ["[dim](no changes)[/]"]

    def has_change(self, key: str) -> bool:
        """Return True if *key* appears in any staged action (for tests)."""
        for action in self._actions:
            if action.key == key:
                return True
            if action.kind == ActionKind.RENAME and action.old_key == key:
                return True
        return False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "save-confirm-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_focus_yes(self) -> None:
        self.query_one("#save-confirm-yes", Button).focus()

    def action_focus_no(self) -> None:
        self.query_one("#save-confirm-no", Button).focus()
