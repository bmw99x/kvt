"""Headless TUI smoke tests covering critical user journeys."""

import pytest
from textual.widgets import Input

from kvt.app import KvtApp
from kvt.widgets.env_table import EnvTable


@pytest.fixture
def app():
    return KvtApp()


@pytest.mark.asyncio
class TestMount:
    async def test_table_populated_on_mount(self, app):
        """
        Given the app is launched with the default MockProvider
        When the UI mounts
        Then the table contains 20 rows
        """
        async with app.run_test(headless=True):
            table = app.query_one("#env-table", EnvTable)
            assert table.row_count == 20

    async def test_search_hidden_on_mount(self, app):
        """
        Given the app is launched
        When the UI mounts
        Then the search input is hidden
        """
        async with app.run_test(headless=True):
            search = app.query_one("#search", Input)
            assert search.display is False

    async def test_table_focused_on_mount(self, app):
        """
        Given the app is launched
        When the UI mounts
        Then the env table has focus
        """
        async with app.run_test(headless=True):
            assert isinstance(app.focused, EnvTable)


@pytest.mark.asyncio
class TestSearch:
    async def test_slash_opens_search(self, app):
        """
        Given the app is mounted with the table focused
        When the user presses /
        Then the search input becomes visible
        """
        async with app.run_test(headless=True) as pilot:
            await pilot.press("/")
            assert app.query_one("#search", Input).display is True

    async def test_typing_filters_rows(self, app):
        """
        Given the search bar is open
        When the user types a query that matches a subset of keys
        Then the table shows only matching rows
        """
        async with app.run_test(headless=True) as pilot:
            await pilot.press("/")
            for ch in "DATABASE":
                await pilot.press(ch)
            assert app.query_one("#env-table", EnvTable).row_count == 2

    async def test_escape_clears_filter(self, app):
        """
        Given the search bar is open with an active filter
        When the user presses Escape
        Then all rows are restored and the search bar is hidden
        """
        async with app.run_test(headless=True) as pilot:
            await pilot.press("/")
            for ch in "DATABASE":
                await pilot.press(ch)
            await pilot.press("escape")
            table = app.query_one("#env-table", EnvTable)
            search = app.query_one("#search", Input)
            assert table.row_count == 20
            assert search.display is False

    async def test_enter_returns_focus_to_table(self, app):
        """
        Given the search bar is open
        When the user presses Enter
        Then focus moves back to the table
        """
        async with app.run_test(headless=True) as pilot:
            await pilot.press("/")
            await pilot.press("enter")
            assert isinstance(app.focused, EnvTable)


@pytest.mark.asyncio
class TestNavigation:
    async def test_j_moves_cursor_down(self, app):
        """
        Given the table is focused on the first row
        When the user presses j
        Then the cursor moves to the second row
        """
        async with app.run_test(headless=True) as pilot:
            table = app.query_one("#env-table", EnvTable)
            assert table.cursor_row == 0
            await pilot.press("j")
            assert table.cursor_row == 1

    async def test_k_moves_cursor_up(self, app):
        """
        Given the table cursor is on the second row
        When the user presses k
        Then the cursor moves back to the first row
        """
        async with app.run_test(headless=True) as pilot:
            table = app.query_one("#env-table", EnvTable)
            await pilot.press("j")
            await pilot.press("k")
            assert table.cursor_row == 0

    async def test_G_jumps_to_last_row(self, app):
        """
        Given the table is focused
        When the user presses G
        Then the cursor moves to the last row
        """
        async with app.run_test(headless=True) as pilot:
            table = app.query_one("#env-table", EnvTable)
            await pilot.press("G")
            assert table.cursor_row == table.row_count - 1

    async def test_gg_jumps_to_first_row(self, app):
        """
        Given the cursor is on the last row
        When the user presses g then g in quick succession
        Then the cursor moves to the first row
        """
        async with app.run_test(headless=True) as pilot:
            table = app.query_one("#env-table", EnvTable)
            await pilot.press("G")
            assert table.cursor_row == table.row_count - 1
            await pilot.press("g")
            await pilot.press("g")
            assert table.cursor_row == 0
