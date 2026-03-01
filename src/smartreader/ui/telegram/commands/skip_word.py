from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SkipWordCommand
from ..common import run_async, async_send_buttons, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramSkipWordCommand(SkipWordCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "skip"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            "Type the word to add to skip list:",
            [[("inline", "Cancel", "skip_cancel")]],
        ))
        self._tg.in_skip_mode = True
        word_raw = self._tg.add_step_queue.get()
        self._tg.in_skip_mode = False
        if word_raw is None:
            send_action_menu(self._tg, sender_id)
            return
        self._add_skip_and_restart(word_raw.lower().strip())
