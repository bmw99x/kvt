"""Context picker modal — select project and environment in one step."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from kvt.constants import PROJECTS


class ContextPickerScreen(ModalScreen[tuple[str, str] | None]):
    """Modal that lets the user choose a project+environment pair.

    Displays every project as a separator followed by its environments as
    selectable options. The currently active project+env pair is pre-highlighted.
    Dismisses with ``(project, env)`` on Enter or ``None`` on Escape/q.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("q", "cancel", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    DEFAULT_CSS = """
    ContextPickerScreen {
        align: center middle;
    }

    #picker-list {
        width: 36;
        max-height: 20;
        background: $surface-darken-2;
        border: round $primary;
    }

    #picker-title {
        width: 36;
        background: $surface-darken-2;
        border-top: round $primary;
        border-left: round $primary;
        border-right: round $primary;
        padding: 1 1 0 1;
        text-style: bold;
        color: $text;
    }

    #picker-hint {
        width: 36;
        background: $surface-darken-2;
        border-bottom: round $primary;
        border-left: round $primary;
        border-right: round $primary;
        padding: 0 1 1 1;
        color: $text-muted;
    }

    #picker-list:focus {
        border: round $primary;
    }

    #picker-list > .option-list--separator {
        color: $text;
        text-style: bold;
        padding: 0 1;
    }

    #picker-list > .option-list--option {
        padding: 0 1;
        color: $text-muted;
    }

    #picker-list > .option-list--option-highlighted {
        background: $primary;
        color: $text;
        text-style: bold;
    }
    """

    def __init__(
        self,
        current_project: str,
        current_env: str,
        projects: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__()
        self._current_project = current_project
        self._current_env = current_env
        self._projects = projects if projects is not None else PROJECTS
        # Map option index → (project, env)
        self._index_map: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        option_list = OptionList(id="picker-list")
        
        for project, envs in self._projects.items():
            # Add project as separator
            option_list.add_option(Option(f"  {project}", disabled=True))
            
            for env in envs:
                is_current = project == self._current_project and env == self._current_env
                self._index_map.append((project, env))
                
                # Add option with appropriate label
                label = f"  → {env}" if is_current else f"      {env}"
                option_list.add_option(Option(label, id=f"{project}/{env}"))
        
        yield Label("  Switch context", id="picker-title")
        yield option_list
        yield Label("  Enter to select · Esc/q to cancel", id="picker-hint")

    def on_mount(self) -> None:
        option_list = self.query_one("#picker-list", OptionList)
        
        # Find and highlight current environment
        for idx, (project, env) in enumerate(self._index_map):
            if project == self._current_project and env == self._current_env:
                option_list.highlighted = idx
                break
        
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        option_index = event.option_index
        if 0 <= option_index < len(self._index_map):
            pair = self._index_map[option_index]
            self.dismiss(pair)

    def action_cursor_down(self) -> None:
        self.query_one("#picker-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#picker-list", OptionList).action_cursor_up()

    def action_cancel(self) -> None:
        self.dismiss(None)
