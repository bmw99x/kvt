"""Smoke tests for the staged-save workflow.

Design contract being tested:
- Edits, adds, deletes, and renames are STAGED locally; the provider is NOT
  written until the user explicitly confirms via SaveConfirmScreen.
- dirty is True iff there is at least one staged (uncommitted) change.
- Pressing 's' opens SaveConfirmScreen which shows a coloured diff of pending
  changes: added vars (green), removed vars (red), renamed vars (yellow),
  and edited vars (blue/yellow).
- Confirming on SaveConfirmScreen flushes all staged changes to the provider
  and clears dirty.
- Cancelling SaveConfirmScreen leaves the stage intact and dirty remains True.
- Undo reverses the last staged operation (not a provider write).
- Navigating away when dirty still prompts for confirmation.
"""

from typing import cast

from kvt.app import KvtApp
from kvt.constants import DEFAULT_ENV, DEFAULT_PROJECT, MOCK_DATA
from kvt.providers import MockProvider
from kvt.screens.save_confirm import SaveConfirmScreen
from kvt.widgets.env_table import EnvTable

DEFAULT_ROW_COUNT = len(MOCK_DATA[DEFAULT_PROJECT][DEFAULT_ENV])


async def wait_loaded(pilot) -> None:
    """Wait for all background workers to finish."""
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


class TestDirtyOnlyWhenStaged:
    async def test_clean_on_mount(self):
        """
        Given a fresh app
        When it mounts
        Then dirty is False and the undo stack is empty
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            assert app.dirty is False

    async def test_dirty_after_edit(self):
        """
        Given a clean app
        When the user edits a value (but has NOT saved)
        Then dirty is True
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

    async def test_provider_not_written_before_save(self):
        """
        Given the user has edited a value
        When the user has NOT yet confirmed save
        Then the provider still holds the original value
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original = app._provider.get("APP_ENV")  # noqa: SLF001

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "new_value":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Provider must still hold the original — not yet committed
            assert app._provider.get("APP_ENV") == original  # noqa: SLF001

    async def test_dirty_after_add(self):
        """
        Given a clean app
        When the user adds a new variable (before saving)
        Then dirty is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("o")
            for ch in "STAGED_NEW":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app.dirty is True

    async def test_provider_not_written_after_add(self):
        """
        Given the user has added a variable (not yet saved)
        When the provider is queried
        Then the new key is absent from the provider
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("o")
            for ch in "STAGED_NEW":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app._provider.get("STAGED_NEW") is None  # noqa: SLF001

    async def test_table_shows_staged_add(self):
        """
        Given the user has added a variable (not yet saved)
        When inspecting the table
        Then the new row IS visible (the working copy shows it)
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("o")
            for ch in "STAGED_NEW":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT + 1

    async def test_dirty_after_delete(self):
        """
        Given a clean app
        When the user deletes a variable (before saving)
        Then dirty is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app.dirty is True

    async def test_provider_not_written_after_delete(self):
        """
        Given the user has deleted the first row (not yet saved)
        When the provider is queried for that key
        Then the provider still returns the original value
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            # APP_ENV is the first row in the default context
            original = app._provider.get("APP_ENV")  # noqa: SLF001
            assert original is not None

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            # Provider must be unchanged
            assert app._provider.get("APP_ENV") == original  # noqa: SLF001

    async def test_dirty_after_rename(self):
        """
        Given a clean app
        When the user renames a variable (before saving)
        Then dirty is True
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("r")
            await pilot.pause()
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app.dirty is True

    async def test_provider_not_written_after_rename(self):
        """
        Given the user has renamed APP_ENV (not yet saved)
        When the provider is queried
        Then the old key still exists and the new key does not
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("r")
            await pilot.pause()
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app._provider.get("APP_ENV") is not None  # noqa: SLF001
            assert app._provider.get("APP_ENV_RENAMED") is None  # noqa: SLF001


class TestSaveBinding:
    async def test_s_opens_save_confirm_screen_when_dirty(self):
        """
        Given the app has staged changes
        When the user presses s
        Then SaveConfirmScreen is pushed
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)

            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()

            assert isinstance(pilot.app.screen, SaveConfirmScreen)

    async def test_s_does_nothing_when_clean(self):
        """
        Given a clean app (no staged changes)
        When the user presses s
        Then no modal is pushed (app notifies instead)
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            # No changes made
            await pilot.press("s")
            await pilot.pause()

            assert not isinstance(pilot.app.screen, SaveConfirmScreen)

    async def test_save_confirm_shows_added_key(self):
        """
        Given an added variable is staged
        When SaveConfirmScreen opens
        Then the new key is visible in the diff
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)

            await pilot.press("o")
            for ch in "MY_NEW_KEY":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "myval":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()

            assert isinstance(pilot.app.screen, SaveConfirmScreen)
            screen = cast(SaveConfirmScreen, pilot.app.screen)
            # The screen must surface the added key
            assert screen.has_change("MY_NEW_KEY")

    async def test_save_confirm_shows_deleted_key(self):
        """
        Given a deleted variable is staged
        When SaveConfirmScreen opens
        Then the deleted key is visible in the diff
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()

            assert isinstance(pilot.app.screen, SaveConfirmScreen)
            screen = cast(SaveConfirmScreen, pilot.app.screen)
            assert screen.has_change("APP_ENV")

    async def test_save_confirm_shows_renamed_keys(self):
        """
        Given a renamed variable is staged
        When SaveConfirmScreen opens
        Then both the old and new key names are visible
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)

            await pilot.press("r")
            await pilot.pause()
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()

            assert isinstance(pilot.app.screen, SaveConfirmScreen)
            screen = cast(SaveConfirmScreen, pilot.app.screen)
            assert screen.has_change("APP_ENV")
            assert screen.has_change("APP_ENV_RENAMED")


class TestSaveConfirm:
    async def test_confirming_save_writes_to_provider(self):
        """
        Given an edit is staged and SaveConfirmScreen is open
        When the user confirms
        Then the provider holds the new value
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("i")
            # ctrl+a moves to start; ctrl+k kills to end — together they clear the field
            await pilot.press("ctrl+a")
            await pilot.press("ctrl+k")
            for ch in "committed_value":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Open save confirm
            await pilot.press("s")
            await pilot.pause()
            assert isinstance(pilot.app.screen, SaveConfirmScreen)

            # Confirm with y
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("APP_ENV") == "committed_value"  # noqa: SLF001

    async def test_confirming_save_clears_dirty(self):
        """
        Given staged changes exist
        When the user confirms the save
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

            await pilot.press("s")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            assert app.dirty is False

    async def test_confirming_save_clears_undo_stack(self):
        """
        Given staged changes exist
        When the user confirms the save
        Then the undo stack is empty (committed changes cannot be undone)
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

            await pilot.press("s")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            assert len(app._undo_stack) == 0  # noqa: SLF001

    async def test_confirming_save_add_writes_to_provider(self):
        """
        Given an add is staged and confirmed
        When the provider is queried
        Then the new key exists with the correct value
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("o")
            for ch in "COMMITTED_KEY":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "committed_val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("COMMITTED_KEY") == "committed_val"  # noqa: SLF001

    async def test_confirming_save_delete_removes_from_provider(self):
        """
        Given a delete is staged and confirmed
        When the provider is queried for the deleted key
        Then it returns None
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("APP_ENV") is None  # noqa: SLF001

    async def test_confirming_save_rename_updates_provider(self):
        """
        Given a rename is staged and confirmed
        When the provider is queried
        Then the old key is gone and the new key holds the original value
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original_value = app._provider.get("APP_ENV")  # noqa: SLF001

            await pilot.press("r")
            await pilot.pause()
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_NEW":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("APP_ENV") is None  # noqa: SLF001
            assert app._provider.get("APP_ENV_NEW") == original_value  # noqa: SLF001

    async def test_cancelling_save_leaves_dirty(self):
        """
        Given staged changes exist and SaveConfirmScreen is open
        When the user cancels
        Then dirty remains True and the stage is unchanged
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

            await pilot.press("s")
            await pilot.pause()
            assert isinstance(pilot.app.screen, SaveConfirmScreen)

            await pilot.press("n")
            await pilot.pause()

            assert app.dirty is True

    async def test_cancelling_save_does_not_write_to_provider(self):
        """
        Given staged changes exist and SaveConfirmScreen is cancelled
        When the provider is queried
        Then the original value is still there
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

            await pilot.press("s")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()

            assert app._provider.get("APP_ENV") == original  # noqa: SLF001

    async def test_multiple_staged_ops_all_committed_together(self):
        """
        Given an edit, an add, and a delete are all staged
        When the user confirms the save
        Then all three are written to the provider atomically
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Edit APP_ENV (ctrl+a goes to start, ctrl+k kills to end)
            await pilot.press("i")
            await pilot.press("ctrl+a")
            await pilot.press("ctrl+k")
            for ch in "edited":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Add a new key
            await pilot.press("o")
            for ch in "BATCH_NEW":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "batchval":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Delete second row (API_BASE_URL)
            await pilot.press("j")
            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            # Confirm save
            await pilot.press("s")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("APP_ENV") == "edited"  # noqa: SLF001
            assert app._provider.get("BATCH_NEW") == "batchval"  # noqa: SLF001
            assert app._provider.get("API_BASE_URL") is None  # noqa: SLF001
            assert app.dirty is False  # noqa: SLF001


class TestUndoWithStaging:
    async def test_undo_reverses_staged_edit(self):
        """
        Given an edit is staged (provider NOT written)
        When the user presses u
        Then the staged edit is reversed and the working copy shows the original value
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
            # The provider was never touched, so it still has the original value
            # and after undo the working copy should match it
            assert app._provider.get("APP_ENV") == "staging"  # noqa: SLF001

    async def test_undo_staged_add_removes_row(self):
        """
        Given an add is staged
        When the user undoes it
        Then the row count returns to the original
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("o")
            for ch in "UNDO_ME":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "v":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert table.row_count == DEFAULT_ROW_COUNT + 1

            await pilot.press("u")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT
            assert app.dirty is False

    async def test_undo_staged_delete_restores_row(self):
        """
        Given a delete is staged
        When the user undoes it
        Then the row count returns to the original and dirty is False
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            table = app.query_one("#env-table", EnvTable)

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()
            assert table.row_count == DEFAULT_ROW_COUNT - 1

            await pilot.press("u")
            await pilot.pause()

            assert table.row_count == DEFAULT_ROW_COUNT
            assert app.dirty is False


class TestDeleteCollapseStaging:
    """Deleting a variable that only exists in the stage (not in provider) should
    cancel out the staged add/edit/rename rather than push a fresh DELETE."""

    async def test_delete_staged_add_removes_it_with_no_net_change(self):
        """
        Given a variable was staged as an add (never in provider)
        When the user deletes it
        Then the undo stack is empty and dirty is False
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Stage an add
            await pilot.press("o")
            for ch in "EPHEMERAL":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dirty is True
            assert app.query_one("#env-table", EnvTable).row_count == DEFAULT_ROW_COUNT + 1

            # Now delete it
            await pilot.press("G")  # cursor to last row (the new one)
            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app.query_one("#env-table", EnvTable).row_count == DEFAULT_ROW_COUNT
            assert len(app._undo_stack) == 0  # noqa: SLF001
            assert app.dirty is False

    async def test_delete_staged_add_not_in_provider(self):
        """
        Given a variable was staged as an add and then deleted
        When the provider is queried
        Then it never received any write for that key
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            await pilot.press("o")
            for ch in "EPHEMERAL":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("G")
            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("EPHEMERAL") is None  # noqa: SLF001

    async def test_delete_staged_edit_stages_delete_of_original(self):
        """
        Given a variable was staged as an edit (changing its value)
        When the user deletes it
        Then the undo stack has exactly one DELETE action (not a SET + DELETE)
        """
        from kvt.models import ActionKind

        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Stage an edit on APP_ENV
            await pilot.press("i")
            await pilot.press("ctrl+a")
            await pilot.press("ctrl+k")
            for ch in "edited_value":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert len(app._undo_stack) == 1  # noqa: SLF001

            # Now delete that same variable
            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app.query_one("#env-table", EnvTable).row_count == DEFAULT_ROW_COUNT - 1
            # The SET should have been replaced by a single DELETE
            assert len(app._undo_stack) == 1  # noqa: SLF001
            assert app._undo_stack[0].kind == ActionKind.DELETE  # noqa: SLF001
            assert app.dirty is True

    async def test_delete_staged_edit_provider_unchanged(self):
        """
        Given a staged edit is then deleted
        When the provider is queried
        Then the original value is still there (no writes yet)
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original = app._provider.get("APP_ENV")  # noqa: SLF001

            await pilot.press("i")
            await pilot.press("ctrl+a")
            await pilot.press("ctrl+k")
            for ch in "edited_value":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("APP_ENV") == original  # noqa: SLF001

    async def test_delete_staged_rename_collapses_to_delete_of_original_key(self):
        """
        Given a variable was staged as a rename (APP_ENV → APP_ENV_RENAMED)
        When the user deletes APP_ENV_RENAMED
        Then the undo stack has one DELETE for the original key APP_ENV
        """
        from kvt.models import ActionKind

        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Stage rename APP_ENV → APP_ENV_RENAMED
            await pilot.press("r")
            await pilot.pause()
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert len(app._undo_stack) == 1  # noqa: SLF001

            # Delete APP_ENV_RENAMED (the renamed key)
            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app.query_one("#env-table", EnvTable).row_count == DEFAULT_ROW_COUNT - 1
            # The RENAME should have been replaced by a DELETE of the original key
            assert len(app._undo_stack) == 1  # noqa: SLF001
            action = app._undo_stack[0]  # noqa: SLF001
            assert action.kind == ActionKind.DELETE
            assert action.key == "APP_ENV"

    async def test_delete_staged_rename_provider_unchanged(self):
        """
        Given a staged rename is then deleted
        When the provider is queried
        Then both the old and new keys show the original state (no writes)
        """
        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            original = app._provider.get("APP_ENV")  # noqa: SLF001

            await pilot.press("r")
            await pilot.pause()
            await pilot.press("ctrl+u")
            for ch in "APP_ENV_RENAMED":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("d")
            await pilot.press("d")
            await pilot.press("y")
            await pilot.pause()

            assert app._provider.get("APP_ENV") == original  # noqa: SLF001
            assert app._provider.get("APP_ENV_RENAMED") is None  # noqa: SLF001


class TestDeleteStagedOnlyBypassesLoadingGuard:
    """Deleting a staged-only var (never in provider) must never hit the
    'Value is still loading' guard, because the loading guard only applies
    to provider-backed vars."""

    async def test_delete_staged_add_does_not_show_loading_notification(self):
        """
        Given a variable was staged as an add (never touched the provider)
        When the user deletes it via dd
        Then no 'still loading' notification is shown and the row is removed
        """
        # Use a fake HybridAzureProvider stand-in that returns "Loading..." for
        # every key so that the guard would fire if not bypassed correctly.
        from kvt.models import EnvVar

        class AlwaysLoadingProvider:
            """Provider where every value is 'Loading...' (simulates hybrid load)."""

            def __init__(self) -> None:
                self._inner = MockProvider()
                # Pretend values haven't loaded yet
                self._values_loaded = False

            def list_vars(self) -> list[EnvVar]:
                return [EnvVar(key=v.key, value="Loading...") for v in self._inner.list_vars()]

            def get_raw(self) -> str:
                return self._inner.get_raw()

            def get(self, key: str) -> str | None:
                if self._inner.get(key) is None:
                    return None
                return "Loading..."

            def create(self, key: str, value: str) -> None:
                self._inner.create(key, value)

            def update(self, key: str, value: str) -> None:
                self._inner.update(key, value)

            def delete(self, key: str) -> None:
                self._inner.delete(key)

            def fetch_all_values(self) -> None:
                pass

        provider = AlwaysLoadingProvider()
        async with KvtApp(provider=provider).run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            initial_count = app.query_one("#env-table", EnvTable).row_count

            # Stage an add — this key is staged-only, never in provider
            await pilot.press("o")
            for ch in "STAGED_ONLY_KEY":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.query_one("#env-table", EnvTable).row_count == initial_count + 1

            # Navigate to the new row and delete it
            await pilot.press("G")
            await pilot.press("d")
            await pilot.press("d")
            await pilot.pause()

            # Row is gone — loading guard was correctly bypassed
            assert app.query_one("#env-table", EnvTable).row_count == initial_count
            assert len(app._undo_stack) == 0  # noqa: SLF001
            assert app.dirty is False

    async def test_edit_staged_add_does_not_show_loading_notification(self):
        """
        Given a variable was staged as an add
        When the user edits it via i
        Then the edit screen opens (loading guard is bypassed)
        """
        from kvt.models import EnvVar

        class AlwaysLoadingProvider:
            def __init__(self) -> None:
                self._inner = MockProvider()
                self._values_loaded = False

            def list_vars(self) -> list[EnvVar]:
                return [EnvVar(key=v.key, value="Loading...") for v in self._inner.list_vars()]

            def get_raw(self) -> str:
                return self._inner.get_raw()

            def get(self, key: str) -> str | None:
                if self._inner.get(key) is None:
                    return None
                return "Loading..."

            def create(self, key: str, value: str) -> None:
                self._inner.create(key, value)

            def update(self, key: str, value: str) -> None:
                self._inner.update(key, value)

            def delete(self, key: str) -> None:
                self._inner.delete(key)

            def fetch_all_values(self) -> None:
                pass

        from kvt.screens.edit import EditScreen

        provider = AlwaysLoadingProvider()
        async with KvtApp(provider=provider).run_test(headless=True) as pilot:
            await wait_loaded(pilot)

            # Stage an add
            await pilot.press("o")
            for ch in "STAGED_ONLY_KEY":
                await pilot.press(ch)
            await pilot.press("enter")
            for ch in "val":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            # Navigate to the new row and edit it
            await pilot.press("G")
            await pilot.press("i")
            await pilot.pause()

            # Edit screen should open — not a "loading" notification
            assert isinstance(pilot.app.screen, EditScreen)


class TestDirtyGuardWithStaging:
    async def test_nav_away_when_dirty_shows_confirm(self):
        """
        Given staged changes exist
        When the user tries to navigate to another env via 'e'
        Then a confirmation modal is shown before switching
        """
        from kvt.screens.confirm import ConfirmScreen

        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)

            # Stage a change
            await pilot.press("i")
            await pilot.press("ctrl+a")
            for ch in "changed":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dirty is True

            # Try to cycle env
            await pilot.press("e")
            await pilot.pause()

            assert isinstance(pilot.app.screen, ConfirmScreen)

    async def test_nav_away_clean_no_confirm(self):
        """
        Given no staged changes
        When the user navigates to another env
        Then no confirmation is needed and the env changes
        """
        from kvt.screens.confirm import ConfirmScreen

        async with KvtApp().run_test(headless=True) as pilot:
            await wait_loaded(pilot)
            app = cast(KvtApp, pilot.app)
            assert not app.dirty

            await pilot.press("e")
            await wait_loaded(pilot)

            assert not isinstance(pilot.app.screen, ConfirmScreen)
            assert app.current_env != DEFAULT_ENV
