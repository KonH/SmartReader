from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ShowLogsCommand
from ..common import run_async, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramShowLogsCommand(ShowLogsCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "logs"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        lines = self._read_log_lines()
        text = "\n".join(lines) if lines else "No log entries."
        chunk_size = 4000
        for i in range(0, max(len(text), 1), chunk_size):
            chunk = text[i:i + chunk_size]
            run_async(self._tg, async_send_text(self._tg, sender_id, f"```\n{chunk}\n```"))
        send_action_menu(self._tg, sender_id)
