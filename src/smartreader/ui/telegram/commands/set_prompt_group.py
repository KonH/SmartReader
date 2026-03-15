from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SetPromptGroupCommand
from ...command import UICommand
from ..common import run_async, async_send_buttons, send_action_menu
from ..state import TelegramSharedUIState
from .set_prompt import TelegramSetPromptCommand
from .set_interests_prompt import TelegramSetInterestsPromptCommand
from .set_summarize_prompt import TelegramSetSummarizePromptCommand
from .set_merge_prompt import TelegramSetMergePromptCommand
from .set_cluster_prompt import TelegramSetClusterPromptCommand

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramSetPromptGroupCommand(SetPromptGroupCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state
        self._subcmds: list[UICommand] = [
            TelegramSetPromptCommand(app_state, shared_ui_state),
            TelegramSetInterestsPromptCommand(app_state, shared_ui_state),
            TelegramSetSummarizePromptCommand(app_state, shared_ui_state),
            TelegramSetMergePromptCommand(app_state, shared_ui_state),
            TelegramSetClusterPromptCommand(app_state, shared_ui_state),
        ]
        self._subcmd_keys = ["eval", "interest", "summarize", "merge", "cluster"]

    @property
    def subcommands(self) -> list[UICommand]:
        return self._subcmds

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return

        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            "Select prompt to edit:",
            [
                [("inline", "EVAL", "group_select:eval")],
                [("inline", "INTEREST", "group_select:interest")],
                [("inline", "SUMMARIZE", "group_select:summarize")],
                [("inline", "MERGE", "group_select:merge")],
                [("inline", "CLUSTER", "group_select:cluster")],
                [("inline", "Cancel", "group_cancel")],
            ],
        ))
        self._tg.mode_state = "group"
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
