from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from ...commands import RestartCommand
from ..common import run_async, async_send_text
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramRestartCommand(RestartCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "restart"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if self._tg.active and sender_id is not None:
            run_async(self._tg, async_send_text(self._tg, sender_id, "Restarting\u2026"))
        sys.exit(0)
