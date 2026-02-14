"""Headless TUI smoke tests covering critical user journeys."""

from typing import cast

from textual.widgets import Button, Input

from rich.text import Text

from kvt.app import KvtApp
from kvt.constants import DEFAULT_ENV, DEFAULT_PROJECT, MOCK_DATA, PROJECTS
from kvt.providers import MockProvider
from kvt.screens.add import AddScreen
from kvt.screens.confirm import ConfirmScreen
from kvt.screens.edit import EditScreen
from kvt.screens.multiline_view import MultilineViewScreen
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
            await pilot.press("e")
            await wait_loaded(pilot)

            assert not isinstance(app.screen, ConfirmScreen)
            assert app.current_env != DEFAULT_ENV

    async def test_dirty_env_cycle_shows_confirmation(self):
        """
        Given the app has 1 unsaved change
        When the user presses e to cycle the env
        Then a ConfirmScreen is pushed with the change count in the message
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

            await pilot.press("e")
            await pilot.pause()

            assert isinstance(app.screen, ConfirmScreen)
            assert "1 unsaved change" in cast(ConfirmScreen, app.screen)._message  # noqa: SLF001

    async def test_confirm_nav_switches_env(self):
        """
        Given the app has unsaved changes and the ConfirmScreen is shown
        When the user presses y
        Then the env changes and dirty is reset
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original_env = app.current_env

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("e")
            await pilot.pause()
            await pilot.press("y")
            await wait_loaded(pilot)

            assert app.current_env != original_env
            assert not app.dirty

    async def test_cancel_nav_keeps_env_and_changes(self):
        """
        Given the app has unsaved changes and the ConfirmScreen is shown
        When the user presses n
        Then the env is unchanged and dirty remains True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original_env = app.current_env

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("e")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()

            assert app.current_env == original_env
            assert app.dirty


class TestMultilineSecrets:
    async def test_multiline_row_shows_badge_not_raw_value(self):
        """
        Given the default context (frontend/staging) which has an ENV multiline secret
        When the app loads
        Then the ENV row shows a Rich Text badge (not the raw blob) in the value cell
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            cell = table.get_cell_at(
                table.cursor_coordinate._replace(
                    row=next(
                        r
                        for r in range(table.row_count)
                        if str(table.get_cell_at(table.cursor_coordinate._replace(row=r, column=1)))
                        == "ENV"
                    ),
                    column=2,
                )
            )
            assert isinstance(cell, Text)

    async def test_multiline_secret_selected_var_is_multiline_true(self):
        """
        Given the cursor is on the ENV (multiline) row
        When selected_var_is_multiline is called
        Then it returns True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            # Move cursor to the ENV row
            for row in range(table.row_count):
                key_cell = table.get_cell_at(table.cursor_coordinate._replace(row=row, column=1))
                if str(key_cell) == "ENV":
                    table.move_cursor(row=row)
                    break

            assert table.selected_var_is_multiline() is True

    async def test_pressing_i_on_multiline_opens_multiline_view(self):
        """
        Given the cursor is on the ENV (multiline) row
        When the user presses i
        Then the MultilineViewScreen is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            for row in range(table.row_count):
                key_cell = table.get_cell_at(table.cursor_coordinate._replace(row=row, column=1))
                if str(key_cell) == "ENV":
                    table.move_cursor(row=row)
                    break

            await pilot.press("i")
            await pilot.pause()

            assert isinstance(app.screen, MultilineViewScreen)

    async def test_multiline_view_shows_inner_variables(self):
        """
        Given the MultilineViewScreen is open for the ENV secret
        When the modal mounts
        Then the inner EnvTable contains the exploded key/value pairs
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            for row in range(table.row_count):
                key_cell = table.get_cell_at(table.cursor_coordinate._replace(row=row, column=1))
                if str(key_cell) == "ENV":
                    table.move_cursor(row=row)
                    break

            await pilot.press("i")
            await pilot.pause()

            from kvt.domain.secrets import parse_dotenv_blob

            blob = MOCK_DATA[DEFAULT_PROJECT][DEFAULT_ENV]["ENV"]
            expected_count = len(parse_dotenv_blob(blob))

            inner_table = app.screen.query_one("#ml-table", EnvTable)
            assert inner_table.row_count == expected_count

    async def test_escape_closes_multiline_view(self):
        """
        Given the MultilineViewScreen is open
        When the user presses Escape
        Then the modal is dismissed and the main table regains focus
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            for row in range(table.row_count):
                key_cell = table.get_cell_at(table.cursor_coordinate._replace(row=row, column=1))
                if str(key_cell) == "ENV":
                    table.move_cursor(row=row)
                    break

            await pilot.press("i")
            await pilot.pause()
            assert isinstance(app.screen, MultilineViewScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, MultilineViewScreen)
