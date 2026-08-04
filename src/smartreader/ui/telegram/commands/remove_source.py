from __future__ import annotations

import html
from typing import TYPE_CHECKING

from ...commands import RemoveSourceCommand
from ..common import run_async, async_send_buttons, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramRemoveSourceCommand(RemoveSourceCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "remove"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        while not self._tg.add_step_queue.empty():
            self._tg.add_step_queue.get_nowait()
        self._tg.mode_state = "remove"
        try:
            name = self._run_remove_conversation(sender_id)
        finally:
            self._tg.mode_state = ""

        if name is None:
            send_action_menu(self._tg, sender_id)
        else:
            self._remove_source_and_restart(name)
            send_action_menu(self._tg, sender_id)

    def _run_remove_conversation(self, sender_id: int) -> str | None:
        s = self._tg
        names = self._list_source_names()
        if not names:
            run_async(s, async_send_text(s, sender_id, "No sources configured."))
            return None

        pick_buttons: list[list[tuple[str, str, str]]] = [
            [("inline", name, f"src_pick:{i}")] for i, name in enumerate(names)
        ]
        pick_buttons.append([("inline", "Cancel", "remove_cancel")])
        run_async(s, async_send_buttons(
            s, sender_id, "Select a source to remove:", pick_buttons,
        ))
        pick_val = s.add_step_queue.get()
        if pick_val is None:
            return None
        try:
            idx = int(pick_val)
        except (TypeError, ValueError):
            return None
        if idx < 0 or idx >= len(names):
            return None
        name = names[idx]

        run_async(s, async_send_buttons(
            s, sender_id,
            f"Remove source <b>{html.escape(name)}</b>?",
            [
                [("inline", "Yes, remove", "remove_confirm")],
                [("inline", "Cancel", "remove_cancel")],
            ],
            parse_mode="html",
        ))
        confirm = s.add_step_queue.get()
        if confirm != "__confirm__":
            return None

        run_async(s, async_send_text(
            s, sender_id, f"Source `{name}` removed ✓  Reloading…",
        ))
        return name
