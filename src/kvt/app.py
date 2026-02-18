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
from kvt.screens.save_confirm import SaveConfirmScreen
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
        "screens/save_confirm.tcss",
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
        Binding("s", "save_changes", "Save"),
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
        # _all_vars is the local working copy (includes uncommitted staged changes).
        self._all_vars: list[EnvVar] = []
        self._filter: str = ""
        self._g_pressed: bool = False
        self._d_pressed: bool = False
        # _undo_stack holds staged (uncommitted) changes.  Nothing is written to
        # the provider until the user confirms via SaveConfirmScreen.
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
        self.current_project = self._default_project
        self.current_env = self._default_env
        self.query_one("#search", Input).display = False
        self.query_one("#loading", LoadingIndicator).display = False
        saved_theme = load_theme()
        if saved_theme:
            self.theme = saved_theme
        self._load_initial()

    @work
    async def _load_initial(self) -> None:
        """Fetch secrets on startup using hybrid loading."""
        try:
            if self._using_mock or self._provider_injected:
                self._all_vars = self._provider.list_vars()
                self._refresh_table()
                self._get_table().focus()
                self._update_subtitle()
                return

            azure_env = self._config[self.current_project][self.current_env]
            self._provider = HybridAzureProvider(azure_env)

            self._all_vars = self._provider.list_vars()
            self._refresh_table()
            self._get_table().focus()
            self._update_subtitle()

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
                pass
            elif self._using_mock:
                self._provider = MockProvider(self.current_project, env)
                self._all_vars = self._provider.list_vars()
            else:
                azure_env = self._config[self.current_project][env]
                self._provider = HybridAzureProvider(azure_env)
                self._all_vars = self._provider.list_vars()
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

    def _stage_set(self, key: str, value: str) -> None:
        """Stage a set (add or edit) change in the local working copy.

        The provider is NOT written here.  Call _commit_staged() to flush.
        """
        previous = next((v.value for v in self._all_vars if v.key == key), None)
        # Update working copy.
        if previous is None:
            self._all_vars.append(EnvVar(key=key, value=value))
        else:
            for v in self._all_vars:
                if v.key == key:
                    v.value = value
                    break
        self._undo_stack.append(
            Action(kind=ActionKind.SET, key=key, value=value, previous_value=previous)
        )
        self.dirty = True
        self._refresh_table()
        self._update_subtitle()

    def _stage_delete(self, key: str) -> None:
        """Stage a delete in the local working copy.

        If an existing staged action already covers this key the operations are
        collapsed to avoid redundant provider writes:

        - Staged ADD (previous_value=None): simply cancel the add — net zero,
          nothing to persist.
        - Staged EDIT (previous_value=<str>): drop the edit, push a DELETE for
          the original value so only the original is deleted at commit time.
        - Staged RENAME (old_key → key): drop the rename, push a DELETE for
          the original key/value so only the original is deleted.

        The provider is NOT written here.  Call _commit_staged() to flush.
        """
        existing = next((v for v in self._all_vars if v.key == key), None)
        if existing is None:
            return

        current_value = existing.value

        # Check whether a prior staged action covers this key.
        prior = next(
            (a for a in reversed(self._undo_stack) if a.key == key),
            None,
        )

        self._all_vars = [v for v in self._all_vars if v.key != key]

        if prior is not None and prior.kind == ActionKind.SET and prior.previous_value is None:
            # Was a staged add that never existed in the provider — cancel it out.
            self._undo_stack.remove(prior)
        elif (
            prior is not None and prior.kind == ActionKind.SET and prior.previous_value is not None
        ):
            # Was a staged edit — replace with a delete of the original value.
            original_value: str = prior.previous_value
            self._undo_stack.remove(prior)
            self._undo_stack.append(Action(kind=ActionKind.DELETE, key=key, value=original_value))
        elif prior is not None and prior.kind == ActionKind.RENAME and prior.old_key is not None:
            # Was a staged rename — replace with a delete of the original key/value.
            self._undo_stack.remove(prior)
            self._undo_stack.append(
                Action(kind=ActionKind.DELETE, key=prior.old_key, value=prior.value)
            )
        else:
            # No prior staged action — straightforward staged delete.
            self._undo_stack.append(Action(kind=ActionKind.DELETE, key=key, value=current_value))

        self.dirty = bool(self._undo_stack)
        self._refresh_table()
        self._update_subtitle()

    def _stage_rename(self, old_key: str, new_key: str) -> None:
        """Stage a rename in the local working copy.

        The provider is NOT written here.  Call _commit_staged() to flush.
        """
        var = next((v for v in self._all_vars if v.key == old_key), None)
        if var is None:
            return
        value = var.value
        var.key = new_key
        self._undo_stack.append(
            Action(kind=ActionKind.RENAME, key=new_key, value=value, old_key=old_key)
        )
        self.dirty = True
        self._refresh_table()
        self._update_subtitle()

    def _commit_staged(self) -> None:
        """Flush all staged changes to the provider in order.

        On any provider error the commit is aborted, an error is shown, and
        the remaining staged changes are left intact so the user can retry.
        """
        committed: list[Action] = []
        for action in self._undo_stack:
            try:
                if action.kind == ActionKind.SET:
                    if action.previous_value is None:
                        self._provider.create(action.key, action.value)
                    else:
                        self._provider.update(action.key, action.value)
                elif action.kind == ActionKind.DELETE:
                    self._provider.delete(action.key)
                elif action.kind == ActionKind.RENAME and action.old_key is not None:
                    self._provider.delete(action.old_key)
                    self._provider.create(action.key, action.value)
            except AzureClientError as exc:
                self.notify(f"Save failed: {exc}", severity="error", timeout=8)
                for done in committed:
                    self._undo_stack.remove(done)
                return
            committed.append(action)

        self._undo_stack.clear()
        self.dirty = False
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
        """Implement vim-style gg: move to the first row on the second g press."""
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

        For multiline (.env blob) rows the blob is decoded to a proper
        .env file (literal ``\\n`` → real newlines) before copying.
        """
        table = self._get_table()
        is_multiline = table.selected_var_is_multiline()
        value = table.selected_value()
        if value is None:
            key = self._selected_key()
            if key is None:
                return
            value = next((v.value for v in self._all_vars if v.key == key), None)
            if value is None:
                return
        if is_multiline:
            value = value.replace("\\n", "\n")
        self.app.copy_to_clipboard(value)
        msg = "Copied .env blob to clipboard" if is_multiline else "Copied value to clipboard"
        self.notify(msg, timeout=2)

    def action_edit_var(self) -> None:
        """Open the appropriate modal for the currently selected variable."""
        table = self._get_table()
        key = self._selected_key()
        if key is None:
            return

        if (
            isinstance(self._provider, HybridAzureProvider)
            and not self._is_staged_only(key)
            and self._provider.get(key) == "Loading..."
        ):
            self.notify("Value is still loading, please wait", timeout=2)
            return

        if table.selected_var_is_multiline():
            var = next((v for v in self._all_vars if v.key == key), None)
            blob = var.value if var else ""

            def on_blob_save(new_blob: str | None) -> None:
                if new_blob is not None and new_blob != blob:
                    self._stage_set(key, new_blob)
                    self.notify(f"Staged update to {key}", timeout=2)
                self._get_table().focus()

            self.push_screen(MultilineViewScreen(key, blob), on_blob_save)
            return

        var = next((v for v in self._all_vars if v.key == key), None)
        current = var.value if var else ""

        def on_save(new_value: str | None) -> None:
            if new_value is not None and new_value != current:
                self._stage_set(key, new_value)
                self.notify(f"Staged update to {key}", timeout=2)
            self._get_table().focus()

        self.push_screen(EditScreen(key=key, current_value=current), on_save)

    def action_rename_var(self) -> None:
        """Open the rename modal to rename the selected variable's key."""
        key_check = self._selected_key()
        if (
            isinstance(self._provider, HybridAzureProvider)
            and not self._provider._values_loaded
            and (key_check is None or not self._is_staged_only(key_check))
        ):
            self.notify("Values are still loading, please wait", timeout=2)
            return

        key = self._selected_key()
        if key is None:
            return

        existing = {v.key for v in self._all_vars}

        def on_rename(new_key: str | None) -> None:
            if new_key is not None:
                self._stage_rename(key, new_key)
                self.notify(f"Staged rename {key} → {new_key}", timeout=2)
            self._get_table().focus()

        self.push_screen(RenameScreen(current_key=key, existing_keys=existing), on_rename)

    def action_add_var(self) -> None:
        """Open the add modal to insert a new variable."""
        if isinstance(self._provider, HybridAzureProvider) and not self._provider._values_loaded:
            self.notify("Values are still loading, please wait", timeout=2)
            return

        existing = {v.key for v in self._all_vars}

        def on_save(var: EnvVar | None) -> None:
            if var is not None:
                self._stage_set(var.key, var.value)
                self.notify(f"Staged add {var.key}", timeout=2)
            self._get_table().focus()

        self.push_screen(AddScreen(existing_keys=existing), on_save)

    def _is_staged_only(self, key: str) -> bool:
        """Return True if *key* exists only in the local stage (never in the provider).

        A key is staged-only when the most recent staged action for it is a SET
        with no previous value — meaning it was added locally and the provider
        has never seen it.
        """
        prior = next((a for a in reversed(self._undo_stack) if a.key == key), None)
        return prior is not None and prior.kind == ActionKind.SET and prior.previous_value is None

    def action_delete_var(self) -> None:
        """Implement vim-style dd: stage deletion of selected variable on second d."""
        if self._d_pressed:
            self._d_pressed = False
            key = self._selected_key()
            if key is None:
                return

            # Only check "still loading" for provider-backed vars.  A staged-only
            # var was never in the provider so it can never be in a loading state.
            if isinstance(self._provider, HybridAzureProvider) and not self._is_staged_only(key):
                value = self._provider.get(key)
                if value == "Loading...":
                    self.notify("Value is still loading, please wait", timeout=2)
                    return

            self._stage_delete(key)
            self.notify(f"Staged delete {key}", timeout=2)
            self._get_table().focus()
        else:
            self._d_pressed = True
            self.set_timer(0.5, self._reset_d)

    def _reset_d(self) -> None:
        self._d_pressed = False

    def action_save_changes(self) -> None:
        """Open SaveConfirmScreen to review and commit staged changes."""
        if not self._undo_stack:
            self.notify("No unsaved changes", timeout=2)
            return

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._commit_staged()
            self._get_table().focus()

        self.push_screen(SaveConfirmScreen(list(self._undo_stack)), on_confirm)

    def action_undo(self) -> None:
        """Reverse the most recent staged mutation."""
        if not self._undo_stack:
            self.notify("Nothing to undo", timeout=2)
            return

        action = self._undo_stack.pop()

        if action.kind == ActionKind.SET:
            if action.previous_value is None:
                # Was an add — remove from working copy.
                self._all_vars = [v for v in self._all_vars if v.key != action.key]
            else:
                for v in self._all_vars:
                    if v.key == action.key:
                        v.value = action.previous_value
                        break
        elif action.kind == ActionKind.DELETE:
            self._all_vars.append(EnvVar(key=action.key, value=action.value))
        elif action.kind == ActionKind.RENAME and action.old_key is not None:
            old_key: str = action.old_key
            for v in self._all_vars:
                if v.key == action.key:
                    v.key = old_key
                    break

        self.dirty = bool(self._undo_stack)
        self._refresh_table()
        self._update_subtitle()
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
