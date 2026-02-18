"""Main application entry point."""

import asyncio
import contextlib

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, LoadingIndicator

from kvt.azure.client import AzureClientError
from kvt.config import Config, ConfigError, load_config, load_theme, save_theme
from kvt.constants import APP_TITLE, DEFAULT_ENV, DEFAULT_PROJECT, PROJECTS
from kvt.models import Action, ActionKind, EnvVar
from kvt.providers import MockProvider, SecretProvider
from kvt.providers_azure_hybrid import HybridAzureProvider
from kvt.screens.add import AddScreen
from kvt.screens.confirm import ConfirmScreen
from kvt.screens.context_picker import ContextPickerScreen
from kvt.screens.edit import EditScreen
from kvt.screens.help import HelpScreen
from kvt.screens.multiline_view import MultilineViewScreen
from kvt.screens.rename import RenameScreen
from kvt.widgets.env_table import EnvTable
from kvt.widgets.env_tabs import EnvTabs
from kvt.widgets.main_view import MainView


class KvtApp(App):
    """kvt — Azure Key Vault TUI."""

    CSS_PATH = [
        "app.tcss",
        "widgets/env_tabs.tcss",
        "widgets/main_view.tcss",
        "screens/multiline_view.tcss",
    ]
    TITLE = APP_TITLE

    dirty: reactive[bool] = reactive(False)
    loading: reactive[bool] = reactive(False)
    current_env: reactive[str] = reactive("")
    current_project: reactive[str] = reactive("")

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "toggle_help", "Help"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "clear_search", show=False),
        Binding("g", "jump_top", show=False),
        Binding("G", "jump_bottom", show=False),
        Binding("y", "copy_value", "Copy"),
        Binding("i", "edit_var", "Edit"),
        Binding("enter", "edit_var", show=False),
        Binding("r", "rename_var", "Rename"),
        Binding("o", "add_var", "Add"),
        Binding("d", "delete_var", "dd Delete"),
        Binding("u", "undo", "Undo"),
        Binding("p", "pick_context", "Project"),
        Binding("e", "cycle_env_next", "Env"),
        Binding("tab", "cycle_env_next", show=False),
    ]

    def __init__(
        self,
        provider: SecretProvider | None = None,
        _use_config: bool = False,
    ) -> None:
        super().__init__()
        self._config: Config = {}
        if _use_config:
            with contextlib.suppress(ConfigError):
                self._config = load_config()
        if not _use_config or not self._config:
            self._projects: dict[str, list[str]] = PROJECTS
            default_project = DEFAULT_PROJECT
            default_env = DEFAULT_ENV
            self._using_mock = True
        else:
            self._projects = {svc: list(envs.keys()) for svc, envs in self._config.items()}
            default_project = next(iter(self._projects))
            default_env = self._projects[default_project][0]
            self._using_mock = False

        self._default_project = default_project
        self._default_env = default_env
        self._provider_injected: bool = provider is not None
        self._provider: SecretProvider = provider or MockProvider(default_project, default_env)
        self._all_vars: list[EnvVar] = []
        self._filter: str = ""
        self._g_pressed: bool = False
        self._d_pressed: bool = False
        self._undo_stack: list[Action] = []
        self._project_env_memory: dict[str, str] = {
            p: envs[0] for p, envs in self._projects.items()
        }

    def compose(self) -> ComposeResult:
        yield Header()
        yield EnvTabs(self._projects, id="env-tabs")
        yield MainView(id="main")
        yield Footer()

    def on_mount(self) -> None:
        # Apply config-derived defaults now that the DOM is ready.
        self.current_project = self._default_project
        self.current_env = self._default_env
        self.query_one("#search", Input).display = False
        self.query_one("#loading", LoadingIndicator).display = False
        # Load and apply saved theme
        saved_theme = load_theme()
        if saved_theme:
            self.theme = saved_theme
        self._load_initial()

    @work
    async def _load_initial(self) -> None:
        """Fetch secrets on startup using hybrid loading."""
        try:
            # For mock provider, just load everything
            if self._using_mock or self._provider_injected:
                self._all_vars = self._provider.list_vars()
                self._refresh_table()
                self._get_table().focus()
                self._update_subtitle()
                return

            # For Azure provider, use hybrid loading
            azure_env = self._config[self.current_project][self.current_env]
            self._provider = HybridAzureProvider(azure_env)

            # Show list immediately (fast operation - just names)
            self._all_vars = self._provider.list_vars()
            self._refresh_table()
            self._get_table().focus()
            self._update_subtitle()

            # Fetch values in background
            self._fetch_values_background()

        except (AzureClientError, KeyError) as exc:
            self.notify(f"Load failed: {exc}", severity="error", timeout=8)
            self._all_vars = []
            self._refresh_table()

    @work(thread=True)
    def _fetch_values_background(self) -> None:
        """Fetch all secret values in background thread."""
        if not isinstance(self._provider, HybridAzureProvider):
            return

        try:
            self._provider.fetch_all_values()
            # Update UI on main thread
            self.call_from_thread(self._update_values)
        except AzureClientError:
            self.call_from_thread(
                lambda: self.notify("Failed to load values", severity="error", timeout=8)
            )

    def _update_values(self) -> None:
        """Update table after values are loaded (called from main thread)."""
        self._all_vars = self._provider.list_vars()
        self._refresh_table()

    def _update_subtitle(self) -> None:
        backend = "mock" if self._using_mock else "Azure Key Vault"
        base = f"[{self.current_project} · {self.current_env}] · {backend}"
        n = len(self._undo_stack)
        if n == 1:
            self.sub_title = f"{base}  1 unsaved change"
        elif n > 1:
            self.sub_title = f"{base}  {n} unsaved changes"
        else:
            self.sub_title = base

    def watch_dirty(self, dirty: bool) -> None:
        """Reflect unsaved state in the subtitle."""
        self._update_subtitle()

    def watch_loading(self, loading: bool) -> None:
        """Show or hide the loading overlay."""
        indicator = self.query_one("#loading", LoadingIndicator)
        indicator.display = loading
        self.query_one("#env-table", EnvTable).display = not loading

    def watch_theme(self, theme: str) -> None:
        """Persist theme changes whenever the theme is changed."""
        save_theme(theme)

    def watch_current_env(self, env: str) -> None:
        """Reload provider data whenever the active environment changes."""
        if not env or not self.current_project:
            return
        try:
            if self._provider_injected:
                pass  # keep the injected provider as-is; _load_initial handles the first load
            elif self._using_mock:
                self._provider = MockProvider(self.current_project, env)
                self._all_vars = self._provider.list_vars()
            else:
                # Use hybrid provider for Azure
                azure_env = self._config[self.current_project][env]
                self._provider = HybridAzureProvider(azure_env)
                # Show list immediately (fast)
                self._all_vars = self._provider.list_vars()
                # Fetch values in background
                self._fetch_values_background()
        except KeyError as exc:
            self.notify(
                f"Config missing {self.current_project}/{env}: {exc}",
                severity="error",
                timeout=8,
            )
            self._all_vars = []
        except AzureClientError as exc:
            self.notify(f"Load failed: {exc}", severity="error", timeout=8)
            self._all_vars = []
        self._undo_stack.clear()
        self.dirty = False
        self._refresh_table()
        tabs = self.query_one("#env-tabs", EnvTabs)
        tabs.current_env = env
        self._update_subtitle()

    def watch_current_project(self, project: str) -> None:
        """Push the new project into the tab bar and update subtitle."""
        if not project:
            return
        self.query_one("#env-tabs", EnvTabs).current_project = project
        self._update_subtitle()

    def on_env_tabs_tab_clicked(self, event: EnvTabs.TabClicked) -> None:
        """Handle a tab click — same confirm-navigate flow as pressing e."""
        event.stop()
        self._confirm_navigate(self.current_project, event.env)

    def on_env_tabs_project_clicked(self, event: EnvTabs.ProjectClicked) -> None:
        """Open the context picker when the project label is clicked."""
        event.stop()
        self.action_pick_context()

    def on_env_table_row_double_clicked(self, event: EnvTable.RowDoubleClicked) -> None:
        """Open the appropriate edit modal on double-click."""
        event.stop()
        self.action_edit_var()

    def _get_table(self) -> EnvTable:
        return self.query_one("#env-table", EnvTable)

    def _refresh_table(self) -> None:
        """Repopulate the table, applying the current filter if any."""
        vars = (
            [v for v in self._all_vars if v.matches(self._filter)]
            if self._filter
            else self._all_vars
        )
        self._get_table().load(vars)

    def _apply_set(self, key: str, value: str) -> None:
        """Write a variable to the provider and sync local state.

        On provider failure the undo stack and local cache are left unchanged
        and an error notification is shown.
        """
        previous = self._provider.get(key)
        try:
            if previous is None:
                self._provider.create(key, value)
            else:
                self._provider.update(key, value)
        except AzureClientError as exc:
            self.notify(f"Write failed: {exc}", severity="error", timeout=8)
            return
        self._all_vars = self._provider.list_vars()
        self._undo_stack.append(
            Action(kind=ActionKind.SET, key=key, value=value, previous_value=previous)
        )
        self.dirty = True
        self._refresh_table()
        self._update_subtitle()

    def _apply_delete(self, key: str) -> None:
        """Delete a variable from the provider and sync local state.

        On provider failure the undo stack and local cache are left unchanged
        and an error notification is shown.
        """
        previous = self._provider.get(key)
        if previous is None:
            return
        try:
            self._provider.delete(key)
        except AzureClientError as exc:
            self.notify(f"Delete failed: {exc}", severity="error", timeout=8)
            return
        self._all_vars = self._provider.list_vars()
        self._undo_stack.append(Action(kind=ActionKind.DELETE, key=key, value=previous))
        self.dirty = True
        self._refresh_table()
        self._update_subtitle()

    def _selected_key(self) -> str | None:
        """Return the key of the currently highlighted table row, or None."""
        table = self._get_table()
        if table.row_count == 0:
            return None
        cell = table.get_cell_at(table.cursor_coordinate._replace(column=1))
        return str(cell)

    def action_toggle_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_focus_search(self) -> None:
        """Show and focus the search bar."""
        search = self.query_one("#search", Input)
        search.display = True
        search.focus()

    def action_clear_search(self) -> None:
        """Clear active filter and hide the search bar."""
        search = self.query_one("#search", Input)
        if search.value:
            search.value = ""
            self._filter = ""
            self._refresh_table()
        search.display = False
        self._get_table().focus()

    @work
    async def _navigate_to(self, project: str, env: str) -> None:
        """Switch to project/env unconditionally, resetting dirty state."""
        self._project_env_memory[self.current_project] = self.current_env
        self.loading = True
        self.current_project = project
        await asyncio.sleep(0.4)
        self.current_env = env
        self.loading = False
        self._get_table().focus()

    def _confirm_navigate(self, project: str, env: str) -> None:
        """Navigate to project/env, prompting if there are unsaved changes."""
        if not self.dirty:
            self._navigate_to(project, env)
            return

        n = len(self._undo_stack)
        noun = "change" if n == 1 else "changes"
        msg = f"You have {n} unsaved {noun}. Switch anyway?"

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._navigate_to(project, env)
            else:
                self._get_table().focus()

        self.push_screen(ConfirmScreen(msg), on_confirm)

    def action_cycle_env_next(self) -> None:
        """Advance to the next environment for the current project (wraps around)."""
        envs = self._projects[self.current_project]
        idx = envs.index(self.current_env) if self.current_env in envs else 0
        next_env = envs[(idx + 1) % len(envs)]
        self._confirm_navigate(self.current_project, next_env)

    def action_pick_context(self) -> None:
        """Open the unified project+env picker modal."""

        def on_pick(result: tuple[str, str] | None) -> None:
            if result is not None:
                project, env = result
                self._confirm_navigate(project, env)
            else:
                self._get_table().focus()

        self.push_screen(
            ContextPickerScreen(self.current_project, self.current_env, self._projects),
            on_pick,
        )

    def action_jump_top(self) -> None:
        """Implement vim-style gg: move to the first row on the second g press.

        First g press arms the chord and starts a short timer. If a second g
        arrives before the timer fires the cursor jumps to row 0. If the timer
        fires first the flag is cleared and the lone g is silently consumed.
        """
        if self._g_pressed:
            self._g_pressed = False
            self._get_table().move_cursor(row=0)
        else:
            self._g_pressed = True
            self.set_timer(0.5, self._reset_g)

    def _reset_g(self) -> None:
        self._g_pressed = False

    def action_jump_bottom(self) -> None:
        """Move cursor to the last row (vim G)."""
        table = self._get_table()
        table.move_cursor(row=table.row_count - 1)

    def action_copy_value(self) -> None:
        """Copy the selected row's value to the system clipboard.

        For multiline rows the raw blob is fetched from the provider and
        copied verbatim (the badge in the table is not the real value).
        """
        value = self._get_table().selected_value()
        if value is None:
            # Multiline row — copy the raw blob.
            key = self._selected_key()
            if key is None:
                return
            value = self._provider.get(key)
            if value is None:
                return
        self.app.copy_to_clipboard(value)
        self.notify("Copied value to clipboard", timeout=2)

    def action_edit_var(self) -> None:
        """Open the appropriate modal for the currently selected variable.

        Multiline secrets open the editable drill-in view where inner vars
        can be added/edited/deleted; single-line secrets open the standard
        edit modal.
        """
        table = self._get_table()
        key = self._selected_key()
        if key is None:
            return

        # Check if value is still loading
        if isinstance(self._provider, HybridAzureProvider):
            value = self._provider.get(key)
            if value is None or value == "Loading...":
                self.notify("Value is still loading, please wait", timeout=2)
                return

        if table.selected_var_is_multiline():
            blob = self._provider.get(key) or ""

            def on_blob_save(new_blob: str | None) -> None:
                if new_blob is not None and new_blob != blob:
                    self._apply_set(key, new_blob)
                    self.notify(f"Updated {key}", timeout=2)
                self._get_table().focus()

            self.push_screen(MultilineViewScreen(key, blob), on_blob_save)
            return

        current = self._provider.get(key) or ""

        def on_save(new_value: str | None) -> None:
            if new_value is not None and new_value != current:
                self._apply_set(key, new_value)
                self.notify(f"Updated {key}", timeout=2)
            self._get_table().focus()

        self.push_screen(EditScreen(key=key, current_value=current), on_save)

    def _apply_rename(self, old_key: str, new_key: str) -> None:
        """Rename a variable atomically as a single undo entry."""
        value = self._provider.get(old_key)
        if value is None:
            return
        try:
            self._provider.delete(old_key)
            self._provider.create(new_key, value)
        except AzureClientError as exc:
            self.notify(f"Rename failed: {exc}", severity="error", timeout=8)
            return
        self._all_vars = self._provider.list_vars()
        self._undo_stack.append(
            Action(kind=ActionKind.RENAME, key=new_key, value=value, old_key=old_key)
        )
        self.dirty = True
        self._refresh_table()
        self._update_subtitle()

    def action_rename_var(self) -> None:
        """Open the rename modal to rename the selected variable's key."""
        if isinstance(self._provider, HybridAzureProvider) and not self._provider._values_loaded:
            self.notify("Values are still loading, please wait", timeout=2)
            return

        key = self._selected_key()
        if key is None:
            return

        existing = {v.key for v in self._all_vars}

        def on_rename(new_key: str | None) -> None:
            if new_key is not None:
                self._apply_rename(key, new_key)
                self.notify(f"Renamed {key} to {new_key}", timeout=2)
            self._get_table().focus()

        self.push_screen(RenameScreen(current_key=key, existing_keys=existing), on_rename)

    def action_add_var(self) -> None:
        """Open the add modal to insert a new variable."""
        # Check if values are still loading
        if isinstance(self._provider, HybridAzureProvider) and not self._provider._values_loaded:
            self.notify("Values are still loading, please wait", timeout=2)
            return

        existing = {v.key for v in self._all_vars}

        def on_save(var: EnvVar | None) -> None:
            if var is not None:
                self._apply_set(var.key, var.value)
                self.notify(f"Added {var.key}", timeout=2)
            self._get_table().focus()

        self.push_screen(AddScreen(existing_keys=existing), on_save)

    def action_delete_var(self) -> None:
        """Implement vim-style dd: delete the selected variable on second d press."""
        if self._d_pressed:
            self._d_pressed = False
            key = self._selected_key()
            if key is None:
                return

            # Check if value is still loading
            if isinstance(self._provider, HybridAzureProvider):
                value = self._provider.get(key)
                if value is None or value == "Loading...":
                    self.notify("Value is still loading, please wait", timeout=2)
                    return

            def on_confirm(confirmed: bool | None) -> None:
                if confirmed:
                    self._apply_delete(key)
                    self.notify(f"Deleted {key}", timeout=2)
                self._get_table().focus()

            self.push_screen(ConfirmScreen(f"Delete  {key}?"), on_confirm)
        else:
            self._d_pressed = True
            self.set_timer(0.5, self._reset_d)

    def _reset_d(self) -> None:
        self._d_pressed = False

    def action_undo(self) -> None:
        """Reverse the most recent mutation."""
        if not self._undo_stack:
            self.notify("Nothing to undo", timeout=2)
            return

        action = self._undo_stack.pop()

        if action.kind == ActionKind.SET:
            if action.previous_value is None:
                self._provider.delete(action.key)
            else:
                self._provider.update(action.key, action.previous_value)
        elif action.kind == ActionKind.DELETE:
            self._provider.create(action.key, action.value)
        elif action.kind == ActionKind.RENAME:
            self._provider.delete(action.key)
            self._provider.create(action.old_key, action.value)  # type: ignore[arg-type]

        self._all_vars = self._provider.list_vars()
        self.dirty = bool(self._undo_stack)
        self._refresh_table()
        self.notify(f"Undid change to {action.key}", timeout=2)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._filter = event.value
            self._refresh_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            self._get_table().focus()


def main() -> None:
    KvtApp(_use_config=True).run()


if __name__ == "__main__":
    main()
