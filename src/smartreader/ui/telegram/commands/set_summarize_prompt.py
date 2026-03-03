from __future__ import annotations

import html
from typing import TYPE_CHECKING

from ...commands import SetSummarizePromptCommand
from ..common import run_async, async_send_buttons, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramSetSummarizePromptCommand(SetSummarizePromptCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "summarize"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        current = self._read_current_summarize_prompt()
        if current:
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                f"Current summarize prompt:\n<code>{html.escape(current)}</code>",
                parse_mode="html",
            ))
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            "Send the new summarize prompt:",
            [[("inline", "Cancel", "group_cancel")]],
        ))
        self._tg.in_set_prompt_mode = True
        prompt_raw = self._tg.add_step_queue.get()
        self._tg.in_set_prompt_mode = False
        if prompt_raw is None:
            send_action_menu(self._tg, sender_id)
            return
        self._set_summarize_prompt_and_restart(prompt_raw.strip())
