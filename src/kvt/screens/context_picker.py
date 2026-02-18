"""Context picker modal — select project and environment in one step."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from kvt.constants import PROJECTS


class ContextPickerScreen(ModalScreen[tuple[str, str] | None]):
    """Modal that lets the user choose a project+environment pair.

    Displays every project as a non-selectable header followed by its
    environments as indented selectable rows.  The currently active
    project+env pair is pre-highlighted.  Dismisses with
    ``(project, env)`` on Enter or ``None`` on Escape/q.
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
        # Map list-view index → (project, env) for selectable rows.
        self._index_map: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        items: list[ListItem] = []
        initial_index = 0

        for project, envs in self._projects.items():
            header = ListItem(
                Static(f"  {project}", classes="picker-project"),
                classes="picker-project-item",
            )
            header.disabled = True
            items.append(header)

            for env in envs:
                is_current = project == self._current_project and env == self._current_env
                if is_current:
                    initial_index = len(self._index_map)
                self._index_map.append((project, env))
                label = f"  → {env}" if is_current else f"      {env}"
                classes = "picker-env-item picker-env-active" if is_current else "picker-env-item"
                items.append(ListItem(Static(label, classes="picker-env"), classes=classes))

        list_view = ListView(*items, id="picker-list")
        yield Static("  Switch context", id="picker-title")
        yield list_view
        yield Static("  Enter to select · Esc/q to cancel", id="picker-hint")

    def on_mount(self) -> None:
        list_view = self.query_one("#picker-list", ListView)
        # Move to the pre-selected env row; account for project headers.
        target_list_index = self._selectable_to_list_index(self._current_project, self._current_env)
        if target_list_index is not None:
            list_view.index = target_list_index
        list_view.focus()

    def _selectable_to_list_index(self, project: str, env: str) -> int | None:
        """Return the ListView index (including non-selectable headers) for a given pair."""
        list_index = 0
        for proj, envs in self._projects.items():
            list_index += 1  # project header
            for e in envs:
                if proj == project and e == env:
                    return list_index
                list_index += 1
        return None

    def _list_index_to_pair(self, list_index: int) -> tuple[str, str] | None:
        """Convert a ListView index back to (project, env), skipping headers."""
        idx = 0
        for project, envs in self._projects.items():
            idx += 1  # project header
            for env in envs:
                if idx == list_index:
                    return (project, env)
                idx += 1
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_index = event.list_view.index
        if list_index is None:
            return
        pair = self._list_index_to_pair(list_index)
        if pair is not None:
            self.dismiss(pair)

    def action_cursor_down(self) -> None:
        self.query_one("#picker-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#picker-list", ListView).action_cursor_up()

    def action_cancel(self) -> None:
        self.dismiss(None)
