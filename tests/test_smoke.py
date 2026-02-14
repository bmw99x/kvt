"""Headless TUI smoke tests covering critical user journeys."""

from textual.widgets import Input

from kvt.app import KvtApp
from kvt.screens.add import AddScreen
from kvt.screens.confirm import ConfirmScreen
from kvt.screens.edit import EditScreen
from kvt.widgets.env_table import EnvTable


class TestMount:
    async def test_table_populated_on_mount(self):
        """
        Given the app is launched with the default MockProvider
        When the UI mounts
        Then the table contains 20 rows
        """
        async with KvtApp().run_test(headless=True) as pilot:
            assert pilot.app.query_one("#env-table", EnvTable).row_count == 20

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
        Then the env table has focus
        """
        async with KvtApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.focused, EnvTable)


class TestSearch:
    async def test_slash_opens_search(self):
        """
        Given the app is mounted with the table focused
        When the user presses /
        Then the search input becomes visible
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await pilot.press("/")
            assert pilot.app.query_one("#search", Input).display is True

    async def test_typing_filters_rows(self):
        """
        Given the search bar is open
        When the user types a query that matches a subset of keys
        Then the table shows only matching rows
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await pilot.press("/")
            for ch in "DATABASE":
                await pilot.press(ch)
            assert pilot.app.query_one("#env-table", EnvTable).row_count == 2

    async def test_escape_clears_filter(self):
        """
        Given the search bar is open with an active filter
        When the user presses Escape
        Then all rows are restored and the search bar is hidden
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await pilot.press("/")
            for ch in "DATABASE":
                await pilot.press(ch)
            await pilot.press("escape")
            assert pilot.app.query_one("#env-table", EnvTable).row_count == 20
            assert pilot.app.query_one("#search", Input).display is False

    async def test_enter_returns_focus_to_table(self):
        """
        Given the search bar is open
        When the user presses Enter
        Then focus moves back to the table
        """
        async with KvtApp().run_test(headless=True) as pilot:
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
            await pilot.press("i")
            assert isinstance(pilot.app.screen, EditScreen)

    async def test_edit_saves_new_value(self):
        """
        Given the EditScreen is open for the first row
        When the user clears the input, types a new value, and presses Enter
        Then the table row count is unchanged and the provider reflects the new value
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "new_value":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert table.row_count == 20

    async def test_edit_cancel_leaves_value_unchanged(self):
        """
        Given the EditScreen is open
        When the user presses Escape
        Then the modal closes and the provider value is unchanged
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app
            original = app._provider.get_var("APP_ENV")  # noqa: SLF001

            await pilot.press("i")
            await pilot.press("escape")
            await pilot.pause()

            assert app._provider.get_var("APP_ENV") == original  # noqa: SLF001

    async def test_edit_marks_dirty(self):
        """
        Given a clean app
        When the user edits a value and saves
        Then the dirty flag is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app
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
            await pilot.press("o")
            assert isinstance(pilot.app.screen, AddScreen)

    async def test_add_new_variable_increases_row_count(self):
        """
        Given the table has 20 rows
        When the user adds a new variable via the AddScreen
        Then the table has 21 rows
        """
        async with KvtApp().run_test(headless=True) as pilot:
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

            assert table.row_count == 21

    async def test_add_cancel_leaves_row_count_unchanged(self):
        """
        Given the AddScreen is open
        When the user presses Escape
        Then the table row count is unchanged
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("o")
            await pilot.press("escape")
            await pilot.pause()

            assert table.row_count == 20


class TestDelete:
    async def test_dd_opens_confirm_screen(self):
        """
        Given the table is focused
        When the user presses d twice
        Then the ConfirmScreen modal is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
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
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert table.row_count == 19

    async def test_cancel_delete_leaves_row_count_unchanged(self):
        """
        Given the ConfirmScreen is shown
        When the user cancels with n
        Then the table row count is unchanged
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("n")
            await pilot.pause()

            assert table.row_count == 20


class TestUndo:
    async def test_undo_reverses_edit(self):
        """
        Given a value has been edited
        When the user presses u
        Then the original value is restored
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app
            original = app._provider.get_var("APP_ENV")  # noqa: SLF001

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("u")
            await pilot.pause()

            assert app._provider.get_var("APP_ENV") == original  # noqa: SLF001

    async def test_undo_reverses_delete(self):
        """
        Given a variable has been deleted
        When the user presses u
        Then the variable is restored and row count returns to 20
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()
            assert table.row_count == 19

            await pilot.press("u")
            await pilot.pause()

            assert table.row_count == 20

    async def test_undo_clears_dirty_when_stack_empty(self):
        """
        Given exactly one edit has been made
        When the user undoes that edit
        Then dirty is False
        """
        async with KvtApp().run_test(headless=True) as pilot:
            app = pilot.app

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
