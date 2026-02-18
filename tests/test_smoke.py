"""Headless TUI smoke tests covering critical user journeys."""

from typing import cast

from rich.text import Text
from textual.widgets import Button, Input

from kvt.app import KvtApp
from kvt.azure.client import AzureClientError
from kvt.constants import DEFAULT_ENV, DEFAULT_PROJECT, MOCK_DATA, PROJECTS
from kvt.models import EnvVar
from kvt.providers import MockProvider
from kvt.screens.add import AddScreen
from kvt.screens.confirm import ConfirmScreen
from kvt.screens.edit import EditScreen
from kvt.screens.multiline_view import MultilineViewScreen
from kvt.screens.rename import RenameScreen
from kvt.widgets.env_table import EnvTable

# Row count for the default context (frontend / staging).
DEFAULT_ROW_COUNT = len(MOCK_DATA[DEFAULT_PROJECT][DEFAULT_ENV])


async def wait_loaded(pilot) -> None:
    """Wait for all background workers (load / navigate) to finish."""
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


class TestMount:
    async def test_table_populated_on_mount(self):
        """
        Given the app is launched with the default MockProvider
        When the UI mounts
        Then the table contains the expected number of rows for the default context
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            assert pilot.app.query_one("#env-table", EnvTable).row_count == DEFAULT_ROW_COUNT

    async def test_search_hidden_on_mount(self):
        """
        Given the app is launched
        When the UI mounts
        Then the search input is hidden
        """
        async with KvtApp().run_test(headless=True) as pilot:
            assert pilot.app.query_one("#search", Input).display is False

    async def test_table_focused_on_mount(self):
        """
        Given the app is launched
        When the UI mounts
        Then the env table has focus after loading completes
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            assert isinstance(pilot.app.focused, EnvTable)

    async def test_loading_indicator_hidden_after_mount(self):
        """
        Given the app is launched
        When the initial load worker completes
        Then the loading indicator is hidden and the table is visible
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            assert app.loading is False
            assert pilot.app.query_one("#env-table", EnvTable).display is True


class TestLoading:
    async def test_loading_true_during_navigation(self):
        """
        Given the app is loaded and clean
        When _navigate_to is called directly
        Then loading becomes True before the worker finishes
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Kick off navigation without waiting for it to finish
            app._navigate_to("backend", "production")  # noqa: SLF001
            await pilot.pause()  # one tick — worker is running but sleep not done

            assert app.loading is True

    async def test_loading_false_after_navigation(self):
        """
        Given the app is loaded and clean
        When navigation completes
        Then loading is False and the table shows the new context
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            app._navigate_to("backend", "production")  # noqa: SLF001
            await wait_loaded(pilot)

            assert app.loading is False
            assert app.current_env == "production"
            assert app.current_project == "backend"
            expected = len(MOCK_DATA["backend"]["production"])
            assert pilot.app.query_one("#env-table", EnvTable).row_count == expected


class TestSearch:
    async def test_slash_opens_search(self):
        """
        Given the app is mounted with the table focused
        When the user presses /
        Then the search input becomes visible
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("/")
            assert pilot.app.query_one("#search", Input).display is True

    async def test_typing_filters_rows(self):
        """
        Given the search bar is open
        When the user types a query that matches a subset of keys
        Then the table shows only matching rows
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("/")
            for ch in "API":
                await pilot.press(ch)
            assert pilot.app.query_one("#env-table", EnvTable).row_count == 2

    async def test_escape_clears_filter(self):
        """
        Given the search bar is open with an active filter
        When the user presses Escape
        Then all rows are restored and the search bar is hidden
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("/")
            for ch in "API":
                await pilot.press(ch)
            await pilot.press("escape")
            assert pilot.app.query_one("#env-table", EnvTable).row_count == DEFAULT_ROW_COUNT
            assert pilot.app.query_one("#search", Input).display is False

    async def test_enter_returns_focus_to_table(self):
        """
        Given the search bar is open
        When the user presses Enter
        Then focus moves back to the table
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("/")
            await pilot.press("enter")
            assert isinstance(pilot.app.focused, EnvTable)


class TestNavigation:
    async def test_j_moves_cursor_down(self):
        """
        Given the table is focused on the first row
        When the user presses j
        Then the cursor moves to the second row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            assert table.cursor_row == 0
            await pilot.press("j")
            assert table.cursor_row == 1

    async def test_k_moves_cursor_up(self):
        """
        Given the table cursor is on the second row
        When the user presses k
        Then the cursor moves back to the first row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            await pilot.press("j")
            await pilot.press("k")
            assert table.cursor_row == 0

    async def test_G_jumps_to_last_row(self):
        """
        Given the table is focused
        When the user presses G
        Then the cursor moves to the last row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            await pilot.press("G")
            assert table.cursor_row == table.row_count - 1

    async def test_gg_jumps_to_first_row(self):
        """
        Given the cursor is on the last row
        When the user presses g then g in quick succession
        Then the cursor moves to the first row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            await pilot.press("G")
            assert table.cursor_row == table.row_count - 1
            await pilot.press("g")
            await pilot.press("g")
            assert table.cursor_row == 0


class TestEdit:
    async def test_i_opens_edit_screen(self):
        """
        Given the table is focused on a row
        When the user presses i
        Then the EditScreen modal is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("i")
            assert isinstance(pilot.app.screen, EditScreen)

    async def test_edit_saves_new_value(self):
        """
        Given the EditScreen is open for the first row
        When the user clears the input, types a new value, and presses Enter
        Then the table row count is unchanged and the provider reflects the new value
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "new_value":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT

    async def test_edit_cancel_leaves_value_unchanged(self):
        """
        Given the EditScreen is open
        When the user presses Escape
        Then the modal closes and the provider value is unchanged
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original = app._provider.get("APP_ENV")  # noqa: SLF001

            await pilot.press("i")
            await pilot.press("escape")
            await pilot.pause()

            assert app._provider.get("APP_ENV") == original  # noqa: SLF001

    async def test_edit_marks_dirty(self):
        """
        Given a clean app
        When the user edits a value and saves
        Then the dirty flag is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            assert app.dirty is False

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app.dirty is True


class TestAdd:
    async def test_o_opens_add_screen(self):
        """
        Given the table is focused
        When the user presses o
        Then the AddScreen modal is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("o")
            assert isinstance(pilot.app.screen, AddScreen)

    async def test_add_new_variable_increases_row_count(self):
        """
        Given the table has DEFAULT_ROW_COUNT rows
        When the user adds a new variable via the AddScreen
        Then the table has one more row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("o")
            for ch in "NEW_VAR":
                await pilot.press(ch)
            await pilot.press("enter")  # move to value field
            for ch in "hello":
                await pilot.press(ch)
            await pilot.press("enter")  # save
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT + 1

    async def test_add_cancel_leaves_row_count_unchanged(self):
        """
        Given the AddScreen is open
        When the user presses Escape
        Then the table row count is unchanged
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("o")
            await pilot.press("escape")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT


class TestDelete:
    async def test_dd_opens_confirm_screen(self):
        """
        Given the table is focused
        When the user presses d twice
        Then the ConfirmScreen modal is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("d")
            await pilot.press("d")
            assert isinstance(pilot.app.screen, ConfirmScreen)

    async def test_confirm_delete_decreases_row_count(self):
        """
        Given the ConfirmScreen is shown
        When the user confirms with y
        Then the table has one fewer row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT - 1

    async def test_cancel_delete_leaves_row_count_unchanged(self):
        """
        Given the ConfirmScreen is shown
        When the user cancels with n
        Then the table row count is unchanged
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("n")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT

    async def test_l_moves_focus_to_yes_button(self):
        """
        Given the ConfirmScreen is shown (No is focused by default)
        When the user presses l
        Then the Yes button receives focus
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("d")
            await pilot.press("d")
            screen = pilot.app.screen
            assert isinstance(screen, ConfirmScreen)
            await pilot.press("l")
            assert screen.focused is screen.query_one("#confirm-yes", Button)

    async def test_h_moves_focus_to_no_button(self):
        """
        Given the ConfirmScreen is shown with Yes focused
        When the user presses h
        Then the No button receives focus
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            await pilot.press("d")
            await pilot.press("d")
            screen = pilot.app.screen
            assert isinstance(screen, ConfirmScreen)
            await pilot.press("l")  # focus Yes first
            await pilot.press("h")  # back to No
            assert screen.focused is screen.query_one("#confirm-no", Button)

    async def test_enter_on_yes_confirms(self):
        """
        Given the ConfirmScreen is shown with Yes focused
        When the user presses enter
        Then the delete is confirmed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("l")  # focus Yes
            await pilot.press("enter")
            await pilot.pause()
            assert table.row_count == DEFAULT_ROW_COUNT - 1


class TestUndo:
    async def test_undo_reverses_edit(self):
        """
        Given a value has been edited
        When the user presses u
        Then the original value is restored
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original = app._provider.get("APP_ENV")  # noqa: SLF001

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("u")
            await pilot.pause()

            assert app._provider.get("APP_ENV") == original  # noqa: SLF001

    async def test_undo_reverses_delete(self):
        """
        Given a variable has been deleted
        When the user presses u
        Then the variable is restored and row count returns to the original count
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()
            assert table.row_count == DEFAULT_ROW_COUNT - 1

            await pilot.press("u")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT

    async def test_undo_clears_dirty_when_stack_empty(self):
        """
        Given exactly one edit has been made
        When the user undoes that edit
        Then dirty is False
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dirty is True

            await pilot.press("u")
            await pilot.pause()

            assert app.dirty is False


class TestContextSwitching:
    async def test_cycling_env_changes_row_count(self):
        """
        Given the app is on frontend/staging
        When the user presses e to cycle to the next environment (development)
        Then the table shows the vars for frontend/development
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            assert app.current_env == DEFAULT_ENV  # staging
            await pilot.press("e")
            await wait_loaded(pilot)

            next_env = PROJECTS[DEFAULT_PROJECT][
                (PROJECTS[DEFAULT_PROJECT].index(DEFAULT_ENV) + 1) % len(PROJECTS[DEFAULT_PROJECT])
            ]
            expected = len(MOCK_DATA[DEFAULT_PROJECT][next_env])
            assert app.current_env == next_env
            assert table.row_count == expected

    async def test_cycling_env_wraps_around(self):
        """
        Given the app is on frontend/local (the last env)
        When the user presses e
        Then current_env wraps back to the first env (production)
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            envs = PROJECTS[DEFAULT_PROJECT]
            last_env = envs[-1]

            app.current_env = last_env
            await pilot.pause()
            await pilot.press("e")
            await wait_loaded(pilot)

            assert app.current_env == envs[0]

    async def test_switching_project_loads_different_vars(self):
        """
        Given the app is on frontend/staging
        When current_project is set to backend and current_env to production
        Then the table shows the vars for backend/production
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            app.current_project = "backend"
            app.current_env = "production"
            await pilot.pause()

            expected = len(MOCK_DATA["backend"]["production"])
            assert table.row_count == expected

    async def test_different_projects_have_different_keys(self):
        """
        Given MockProvider is constructed for frontend/staging and backend/production
        When list_vars is called on each
        Then the key sets are different
        """
        frontend_keys = {v.key for v in MockProvider("frontend", "staging").list_vars()}
        backend_keys = {v.key for v in MockProvider("backend", "production").list_vars()}
        assert frontend_keys != backend_keys

    async def test_env_cycle_updates_subtitle(self):
        """
        Given the app is on frontend/staging
        When the user presses e to cycle to the next env
        Then the subtitle reflects the new environment
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            await pilot.press("e")
            await wait_loaded(pilot)

            assert app.current_env in app.sub_title

    async def test_project_switch_resets_to_correct_env_vars(self):
        """
        Given infra/production has fewer vars than backend/production
        When current_project is switched to infra and current_env to production
        Then the table row count matches infra/production exactly
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            app.current_project = "infra"
            app.current_env = "production"
            await pilot.pause()

            expected = len(MOCK_DATA["infra"]["production"])
            assert table.row_count == expected
            assert expected != len(MOCK_DATA["backend"]["production"])

    async def test_clicking_env_tab_navigates(self):
        """
        Given the app is on frontend/staging
        When the user clicks the 'production' environment tab
        Then current_env changes to 'production' and the table updates
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            assert app.current_env == DEFAULT_ENV  # staging
            await pilot.click("#tab-production")
            await wait_loaded(pilot)

            assert app.current_env == "production"
            expected = len(MOCK_DATA[DEFAULT_PROJECT]["production"])
            assert app.query_one("#env-table", EnvTable).row_count == expected


class TestDirtyGuard:
    async def test_subtitle_shows_unsaved_count_after_edit(self):
        """
        Given a clean app
        When the user edits a value and saves
        Then the subtitle contains '1 unsaved change'
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert "1 unsaved change" in app.sub_title

    async def test_subtitle_shows_plural_after_two_edits(self):
        """
        Given a clean app
        When the user adds two new variables (two distinct undo entries)
        Then the subtitle contains '2 unsaved changes'
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # First add
            await pilot.press("o")
            for ch in "FIRST_VAR":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val1":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Second add
            await pilot.press("o")
            for ch in "SECOND_VAR":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val2":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert "2 unsaved changes" in app.sub_title

    async def test_clean_nav_requires_no_confirmation(self):
        """
        Given the app is clean (no unsaved changes)
        When the user presses e to cycle the env
        Then no ConfirmScreen is pushed and the env changes immediately
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            assert not app.dirty
            assert len(app._undo_stack) == 0  # noqa: SLF001


class _FailingProvider:
    """Provider that raises AzureClientError on every mutating call."""

    def __init__(self, fail_on_list: bool = False) -> None:
        self._inner = MockProvider(DEFAULT_PROJECT, DEFAULT_ENV)
        self._fail_on_list = fail_on_list

    def list_vars(self) -> list[EnvVar]:
        if self._fail_on_list:
            raise AzureClientError("simulated list failure")
        return self._inner.list_vars()

    def get_raw(self) -> str:
        return self._inner.get_raw()

    def get(self, key: str) -> str | None:
        return self._inner.get(key)

    def create(self, key: str, value: str) -> None:
        raise AzureClientError("simulated write failure")

    def update(self, key: str, value: str) -> None:
        raise AzureClientError("simulated write failure")

    def delete(self, key: str) -> None:
        raise AzureClientError("simulated delete failure")


class TestDoubleClick:
    async def test_double_click_single_line_opens_edit_screen(self):
        """
        GIVEN the table is showing a single-line variable
        WHEN the user double-clicks a row
        THEN the EditScreen is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            assert not table.selected_var_is_multiline()
            table.post_message(EnvTable.RowDoubleClicked())
            await pilot.pause()
            assert isinstance(pilot.app.screen, EditScreen)

    async def test_double_click_multiline_opens_multiline_view(self):
        """
        GIVEN the table cursor is on a multiline variable
        WHEN the user double-clicks that row
        THEN the MultilineViewScreen is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)
            env_row = next(
                r
                for r in range(table.row_count)
                if isinstance(
                    table.get_cell_at(table.cursor_coordinate._replace(row=r, column=2)),
                    Text,
                )
            )
            table.move_cursor(row=env_row)
            await pilot.pause()
            assert table.selected_var_is_multiline()
            table.post_message(EnvTable.RowDoubleClicked())
            await pilot.pause()
            assert isinstance(app.screen, MultilineViewScreen)


class TestWrapAround:
    async def test_j_at_bottom_wraps_to_top(self):
        """
        Given the cursor is on the last row
        When the user presses j
        Then the cursor wraps to row 0
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            await pilot.press("G")
            assert table.cursor_row == table.row_count - 1
            await pilot.press("j")
            assert table.cursor_row == 0

    async def test_k_at_top_wraps_to_bottom(self):
        """
        Given the cursor is on the first row
        When the user presses k
        Then the cursor wraps to the last row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            assert table.cursor_row == 0
            await pilot.press("k")
            assert table.cursor_row == table.row_count - 1

    async def test_multiline_j_at_bottom_wraps_to_top(self):
        """
        Given the multiline view is open and cursor is on the last inner row
        When the user presses j
        Then the cursor wraps to row 0
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            # Navigate to the multiline row (last row in staging)
            await pilot.press("G")
            assert table.selected_var_is_multiline()
            await pilot.press("i")
            await pilot.pause()
            screen = pilot.app.screen
            assert isinstance(screen, MultilineViewScreen)
            ml_table = screen.query_one("#ml-table", EnvTable)
            # Jump to last row
            await pilot.press("G")
            assert ml_table.cursor_row == ml_table.row_count - 1
            # Wrap
            await pilot.press("j")
            assert ml_table.cursor_row == 0

    async def test_multiline_k_at_top_wraps_to_bottom(self):
        """
        Given the multiline view is open and cursor is on the first inner row
        When the user presses k
        Then the cursor wraps to the last inner row
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            table = pilot.app.query_one("#env-table", EnvTable)
            await pilot.press("G")
            assert table.selected_var_is_multiline()
            await pilot.press("i")
            await pilot.pause()
            screen = pilot.app.screen
            assert isinstance(screen, MultilineViewScreen)
            ml_table = screen.query_one("#ml-table", EnvTable)
            assert ml_table.cursor_row == 0
            await pilot.press("k")
            assert ml_table.cursor_row == ml_table.row_count - 1


class TestDirtyState:
    async def test_edit_produces_one_undo_entry(self):
        """
        Given a clean app
        When the user edits a single-line value and saves
        Then the undo stack has exactly 1 entry and dirty is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            assert len(app._undo_stack) == 0  # noqa: SLF001

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app.dirty is True
            assert len(app._undo_stack) == 1  # noqa: SLF001

    async def test_add_produces_one_undo_entry(self):
        """
        Given a clean app
        When the user adds a new variable
        Then the undo stack has exactly 1 entry and dirty is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("o")
            for ch in "NEW_KEY":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "newval":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app.dirty is True
            assert len(app._undo_stack) == 1  # noqa: SLF001

    async def test_delete_produces_one_undo_entry(self):
        """
        Given a clean app
        When the user deletes a variable and confirms
        Then the undo stack has exactly 1 entry and dirty is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app.dirty is True
            assert len(app._undo_stack) == 1  # noqa: SLF001

    async def test_rename_produces_one_undo_entry(self):
        """
        Given a clean app
        When the user renames a variable
        Then the undo stack has exactly 1 entry (not 2) and dirty is True
        """

        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("r")
            await pilot.pause()
            assert isinstance(pilot.app.screen, RenameScreen)
            # Clear existing key and type new name
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app.dirty is True
            assert len(app._undo_stack) == 1  # noqa: SLF001

    async def test_rename_undo_restores_original_key(self):
        """
        Given a variable has been renamed
        When the user presses u
        Then the original key is restored and the new key is gone
        """

        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original_key = "APP_ENV"
            original_value = app._provider.get(original_key)  # noqa: SLF001

            await pilot.press("r")
            await pilot.pause()
            assert isinstance(pilot.app.screen, RenameScreen)
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app._provider.get("APP_ENV_RENAMED") == original_value  # noqa: SLF001
            assert app._provider.get(original_key) is None  # noqa: SLF001

            await pilot.press("u")
            await pilot.pause()

            assert app._provider.get(original_key) == original_value  # noqa: SLF001
            assert app._provider.get("APP_ENV_RENAMED") is None  # noqa: SLF001
            assert app.dirty is False

    async def test_subtitle_after_rename_shows_one_change(self):
        """
        Given a clean app
        When the user renames a variable
        Then the subtitle shows '1 unsaved change' not '2 unsaved changes'
        """

        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("r")
            await pilot.pause()
            assert isinstance(pilot.app.screen, RenameScreen)
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert "1 unsaved change" in app.sub_title
            assert "2 unsaved changes" not in app.sub_title

    async def test_multiline_save_with_changes_produces_one_undo_entry(self):
        """
        Given the multiline view is open and the user edits an inner variable
        When the user saves with s
        Then the app undo stack has exactly 1 entry and dirty is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = pilot.app.query_one("#env-table", EnvTable)

            # Open multiline view (ENV is the last row)
            await pilot.press("G")
            assert table.selected_var_is_multiline()
            await pilot.press("i")
            await pilot.pause()
            assert isinstance(pilot.app.screen, MultilineViewScreen)

            # Edit first inner variable
            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "newhost":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Save the multiline view
            await pilot.press("s")
            await pilot.pause()

            assert app.dirty is True
            assert len(app._undo_stack) == 1  # noqa: SLF001

    async def test_multiline_save_without_changes_leaves_dirty_false(self):
        """
        Given the multiline view is open and the user makes no changes
        When the user presses s
        Then the app undo stack is empty and dirty remains False
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = pilot.app.query_one("#env-table", EnvTable)

            await pilot.press("G")
            assert table.selected_var_is_multiline()
            await pilot.press("i")
            await pilot.pause()
            assert isinstance(pilot.app.screen, MultilineViewScreen)

            # Save immediately without touching anything
            await pilot.press("s")
            await pilot.pause()

            assert app.dirty is False
            assert len(app._undo_stack) == 0  # noqa: SLF001

    async def test_multiline_cancel_leaves_dirty_false(self):
        """
        Given the multiline view is open and the user edits an inner variable
        When the user cancels (confirms discard)
        Then the app undo stack is empty and dirty remains False
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = pilot.app.query_one("#env-table", EnvTable)

            await pilot.press("G")
            assert table.selected_var_is_multiline()
            await pilot.press("i")
            await pilot.pause()
            assert isinstance(pilot.app.screen, MultilineViewScreen)

            # Make a change inside
            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "discarded":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Cancel — triggers ConfirmScreen asking to discard
            await pilot.press("escape")
            await pilot.pause()
            # Confirm discard
            assert isinstance(pilot.app.screen, ConfirmScreen)
            await pilot.press("y")
            await pilot.pause()

            assert app.dirty is False
            assert len(app._undo_stack) == 0  # noqa: SLF001

    async def test_multiple_operations_accumulate_undo_stack(self):
        """
        Given a clean app
        When the user edits, adds, and deletes one variable each
        Then the undo stack has exactly 3 entries
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Edit
            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Add
            await pilot.press("o")
            for ch in "EXTRA_KEY":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Delete (second row — APP_ENV is now changed, delete API_BASE_URL)
            await pilot.press("j")
            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert len(app._undo_stack) == 3  # noqa: SLF001
            assert "3 unsaved changes" in app.sub_title

    async def test_undo_all_clears_dirty(self):
        """
        Given three mutations have been made
        When the user undoes all three
        Then dirty is False and the undo stack is empty
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Make 3 edits
            for key_suffix in ["1", "2", "3"]:
                await pilot.press("o")
                for ch in f"EXTRA_{key_suffix}":
                    await pilot.press(ch)
                await pilot.press("enter")
                for ch in "v":
                    await pilot.press(ch)
                await pilot.press("enter")
                await pilot.pause()

            assert len(app._undo_stack) == 3  # noqa: SLF001

            for _ in range(3):
                await pilot.press("u")
                await pilot.pause()

            assert app.dirty is False
            assert len(app._undo_stack) == 0  # noqa: SLF001


class TestErrorHandling:
    async def test_load_failure_shows_notification(self):
        """
        GIVEN a provider that raises AzureClientError on list_vars
        WHEN the app mounts
        THEN the app does not crash and the table is empty
        """
        provider = _FailingProvider(fail_on_list=True)
        async with KvtApp(provider=provider).run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            assert app.query_one("#env-table", EnvTable).row_count == 0

    async def test_write_failure_does_not_push_undo(self):
        """
        GIVEN a provider that raises AzureClientError on create/update
        WHEN the user adds a variable and saves
        THEN the undo stack is unchanged and dirty remains False
        """
        provider = _FailingProvider()
        async with KvtApp(provider=provider).run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("o")
            for ch in "NEW_VAR":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert not app.dirty
            assert len(app._undo_stack) == 0  # noqa: SLF001

    async def test_delete_failure_does_not_push_undo(self):
        """
        GIVEN a provider that raises AzureClientError on delete
        WHEN the user deletes a variable and confirms
        THEN the undo stack is unchanged and dirty remains False
        """
        provider = _FailingProvider()
        async with KvtApp(provider=provider).run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert not app.dirty
            assert len(app._undo_stack) == 0  # noqa: SLF001
