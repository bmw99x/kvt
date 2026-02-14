"""Horizontal environment indicator bar with project label (read-only)."""

from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from kvt.constants import DEFAULT_ENV, DEFAULT_PROJECT, PROJECTS


class EnvTabs(Widget):
    """A read-only bar showing the active project and its environments.

    Renders as:  frontend ▸  production  [staging]  development  local

    Both ``current_project`` and ``current_env`` are reactives kept in
    sync by the app.  When either changes the bar re-renders in place.

    Clicking an env tab posts ``EnvTabs.TabClicked`` for the app to handle
    via ``_confirm_navigate``, matching the same flow as pressing ``e``.
    """

    class TabClicked(Message):
        """Posted when the user clicks an environment tab."""

        def __init__(self, env: str) -> None:
            super().__init__()
            self.env = env

    can_focus = False
    BINDINGS = []

    current_project: reactive[str] = reactive(DEFAULT_PROJECT, init=False)
    current_env: reactive[str] = reactive(DEFAULT_ENV, init=False)

    def __init__(
        self,
        projects: dict[str, list[str]] | None = None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._projects = projects if projects is not None else PROJECTS

    def compose(self) -> ComposeResult:
        yield Static(f"{DEFAULT_PROJECT} ▸", id="env-tabs-project", classes="tab-project")
        for env in self._projects.get(DEFAULT_PROJECT, []):
            active = env == DEFAULT_ENV
            yield Static(
                env,
                id=f"tab-{env}",
                classes="tab active" if active else "tab",
            )

    async def watch_current_project(self, project: str) -> None:
        """Rebuild env tabs when the project changes."""
        self.query_one("#env-tabs-project", Static).update(f"{project} ▸")

        # Await removal so the DOM is clean before mounting new tabs.
        await self.query(".tab").remove()

        # Mount new env tabs for the new project.
        envs = self._projects.get(project, [])
        await self.mount(
            *[
                Static(
                    env,
                    id=f"tab-{env}",
                    classes="tab active" if env == self.current_env else "tab",
                )
                for env in envs
            ]
        )

    def watch_current_env(self, env: str) -> None:
        """Highlight the active env tab."""
        for tab in self.query(".tab"):
            if tab.id == f"tab-{env}":
                tab.add_class("active")
            else:
                tab.remove_class("active")

    def on_click(self, event: Click) -> None:
        """Navigate to the clicked environment tab."""
        widget = event.widget
        if (
            widget is not None
            and widget.has_class("tab")
            and widget.id
            and widget.id.startswith("tab-")
        ):
            env = widget.id[len("tab-") :]
            self.post_message(EnvTabs.TabClicked(env))
