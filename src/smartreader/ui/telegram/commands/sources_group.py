from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SourcesGroupCommand
from ...command import UICommand
from ..common import run_async, async_send_buttons, send_action_menu
from ..state import TelegramSharedUIState
from .add_source import TelegramAddSourceCommand
from .edit_source import TelegramEditSourceCommand
from .remove_source import TelegramRemoveSourceCommand

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramSourcesGroupCommand(SourcesGroupCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state
        self._subcmds: list[UICommand] = [
            TelegramAddSourceCommand(app_state, shared_ui_state),
            TelegramEditSourceCommand(app_state, shared_ui_state),
            TelegramRemoveSourceCommand(app_state, shared_ui_state),
        ]
        self._subcmd_keys = ["add", "edit", "remove"]

    @property
    def subcommands(self) -> list[UICommand]:
        return self._subcmds

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return

        while not self._tg.add_step_queue.empty():
            self._tg.add_step_queue.get_nowait()

        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            "Manage sources:",
            [
                [("inline", "＋  ADD SOURCE", "group_select:add")],
                [("inline", "✏  EDIT SOURCE", "group_select:edit")],
                [("inline", "🗑  REMOVE SOURCE", "group_select:remove")],
                [("inline", "Cancel", "sources_cancel")],
            ],
        ))
        self._tg.mode_state = "sources"
        choice = self._tg.add_step_queue.get()
        self._tg.mode_state = ""

        if choice is None:
            send_action_menu(self._tg, sender_id)
            return

        subcmd_map = dict(zip(self._subcmd_keys, self._subcmds))
        subcmd = subcmd_map.get(str(choice))
        if subcmd is not None:
            subcmd.execute()
        else:
            send_action_menu(self._tg, sender_id)
