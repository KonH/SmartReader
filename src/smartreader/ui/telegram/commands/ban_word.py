from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import BanWordCommand
from ..common import run_async, async_send_buttons, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState

_DONE = "__done__"


class TelegramBanWordCommand(BanWordCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "ban"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        # Drain any stale entries left by a previous interaction
        while not self._tg.add_step_queue.empty():
            self._tg.add_step_queue.get_nowait()
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            "Type word(s) to ban (separated by spaces, commas, semicolons, or one per line), then click Done:",
            [[("inline", "✅ Done", "ban_done"), ("inline", "Cancel", "ban_cancel")]],
        ))
        self._tg.mode_state = "ban"
        collected: list[str] = []
        while True:
            val = self._tg.add_step_queue.get()
            if val is None:
                self._tg.mode_state = ""
                send_action_menu(self._tg, sender_id)
                return
            if val == _DONE:
                break
            collected.append(val)
        self._tg.mode_state = ""
        words_str = " ".join(collected).strip()
        if words_str:
            self._add_ban_and_restart(words_str)
        send_action_menu(self._tg, sender_id)
