"""Horizontal environment indicator bar with project label (read-only)."""

import re

from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from kvt.constants import DEFAULT_ENV, DEFAULT_PROJECT, PROJECTS


def _tab_id(env: str) -> str:
    """Return a valid Textual widget ID for an env name.

    Replaces any character that is not a letter, digit, underscore, or hyphen
    with a hyphen, then collapses consecutive hyphens.
    """
    slug = re.sub(r"[^A-Za-z0-9_-]", "-", env)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return f"tab-{slug}"


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

    def _make_tab(self, env: str, active: bool) -> Static:
        """Create a tab Static with the env stored in a data attribute."""
        tab = Static(env, id=_tab_id(env), classes="tab active" if active else "tab")
        tab.data_env = env  # type: ignore[attr-defined]
        return tab

    def compose(self) -> ComposeResult:
        yield Static(f"{DEFAULT_PROJECT} ▸", id="env-tabs-project", classes="tab-project")
        for env in self._projects.get(DEFAULT_PROJECT, []):
            yield self._make_tab(env, active=env == DEFAULT_ENV)

    async def watch_current_project(self, project: str) -> None:
        """Rebuild env tabs when the project changes."""
        self.query_one("#env-tabs-project", Static).update(f"{project} ▸")

        # Await removal so the DOM is clean before mounting new tabs.
        await self.query(".tab").remove()

        envs = self._projects.get(project, [])
        await self.mount(*[self._make_tab(env, active=env == self.current_env) for env in envs])

    def watch_current_env(self, env: str) -> None:
        """Highlight the active env tab."""
        tab_id = _tab_id(env)
        for tab in self.query(".tab"):
            if tab.id == tab_id:
                tab.add_class("active")
            else:
                tab.remove_class("active")

    def on_click(self, event: Click) -> None:
        """Navigate to the clicked environment tab."""
        widget = event.widget
        if widget is None or not widget.has_class("tab") or not widget.id:
            return
        env: str | None = getattr(widget, "data_env", None)
        if env is None:
            return
        self.post_message(EnvTabs.TabClicked(env))
