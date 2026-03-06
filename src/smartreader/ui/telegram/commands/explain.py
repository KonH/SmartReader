from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ExplainCommand
from ..common import run_async, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramExplainCommand(ExplainCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "explain"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        path = self._generate_report()
        if path is None:
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                "No pipeline data found — run show first.",
            ))
        else:
            run_async(self._tg, _async_send_file(self._tg, sender_id, str(path)))
        send_action_menu(self._tg, sender_id)


async def _async_send_file(s: TelegramSharedUIState, chat_id: int, path: str) -> None:
    from telethon import TelegramClient  # type: ignore[import-untyped]
    client: TelegramClient = s.client  # type: ignore[assignment]
    await client.send_file(chat_id, path, caption="Pipeline Report")
