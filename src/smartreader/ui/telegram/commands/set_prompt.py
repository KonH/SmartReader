from __future__ import annotations

import html
from typing import TYPE_CHECKING

from ...commands import SetPromptCommand
from ..common import run_async, async_send_buttons, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState

_CLEAR = "__clear__"
_NEW = "__new__"


class TelegramSetPromptCommand(SetPromptCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "prompt"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        while not self._tg.add_step_queue.empty():
            self._tg.add_step_queue.get_nowait()

        self._tg.mode_state = "prompt"
        try:
            self._run_eval_flow(sender_id)
        finally:
            self._tg.mode_state = ""
        send_action_menu(self._tg, sender_id)

    def _run_eval_flow(self, sender_id: int) -> None:
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            "Select EVAL prompt scope\n"
            "(precedence: stage > channel > category > global)",
            [
                [("inline", "Global", "prompt_scope:global")],
                [("inline", "Category", "prompt_scope:category")],
                [("inline", "Channel", "prompt_scope:channel")],
                [("inline", "Cancel", "prompt_cancel")],
            ],
        ))
        choice = self._tg.add_step_queue.get()
        if choice is None:
            return
        if choice == "scope:global":
            self._edit_global(sender_id)
        elif choice == "scope:category":
            self._edit_mapped(sender_id, "category_prompts", "category", self._list_categories())
        elif choice == "scope:channel":
            self._edit_mapped(sender_id, "channel_prompts", "channel", self._list_channels())

    def _edit_global(self, sender_id: int) -> None:
        current = self._read_current_prompt()
        if current:
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                f"Current global scoring prompt:\n<code>{html.escape(current)}</code>",
                parse_mode="html",
            ))
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            "Send the new global scoring prompt:",
            [[("inline", "Cancel", "prompt_cancel")]],
        ))
        prompt_raw = self._tg.add_step_queue.get()
        if prompt_raw is None or prompt_raw in (_CLEAR, _NEW) or str(prompt_raw).startswith(("scope:", "pick:")):
            return
        self._set_prompt_and_restart(str(prompt_raw).strip())

    def _edit_mapped(
        self,
        sender_id: int,
        map_key: str,
        label: str,
        keys: list[str],
    ) -> None:
        prompts = self._read_prompt_map(map_key)
        buttons: list[list[tuple[str, str, str]]] = []
        for i, key in enumerate(keys):
            mark = " ✓" if key in prompts else ""
            buttons.append([("inline", f"{key}{mark}", f"prompt_pick:{i}")])
        buttons.append([("inline", f"+ New {label}", "prompt_new")])
        buttons.append([("inline", "Cancel", "prompt_cancel")])
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            f"Select {label} to edit EVAL prompt:",
            buttons,
        ))
        pick = self._tg.add_step_queue.get()
        if pick is None:
            return
        entry_key = ""
        if pick == _NEW:
            run_async(self._tg, async_send_buttons(
                self._tg, sender_id,
                f"Send the new {label} name:",
                [[("inline", "Cancel", "prompt_cancel")]],
            ))
            name_raw = self._tg.add_step_queue.get()
            if name_raw is None or name_raw in (_CLEAR, _NEW) or str(name_raw).startswith(("scope:", "pick:")):
                return
            entry_key = str(name_raw).strip()
            if not entry_key:
                return
        elif isinstance(pick, str) and pick.startswith("pick:"):
            try:
                idx = int(pick[5:])
            except ValueError:
                return
            if idx < 0 or idx >= len(keys):
                return
            entry_key = keys[idx]
        else:
            return

        current = prompts.get(entry_key, "")
        if current:
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                f"Current {label} prompt for <code>{html.escape(entry_key)}</code>:\n"
                f"<code>{html.escape(current)}</code>",
                parse_mode="html",
            ))
        else:
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                f"No custom {label} prompt for <code>{html.escape(entry_key)}</code> yet.",
                parse_mode="html",
            ))
        clear_row: list[tuple[str, str, str]] = []
        if current:
            clear_row.append(("inline", "Clear", "prompt_clear"))
        clear_row.append(("inline", "Cancel", "prompt_cancel"))
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id,
            f"Send the new {label} scoring prompt:",
            [clear_row],
        ))
        prompt_raw = self._tg.add_step_queue.get()
        if prompt_raw is None or str(prompt_raw).startswith(("scope:", "pick:")) or prompt_raw == _NEW:
            return
        if prompt_raw == _CLEAR:
            self._set_mapped_prompt_and_restart(map_key, entry_key, "")
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                f"✓ Cleared {label} prompt for <code>{html.escape(entry_key)}</code>",
                parse_mode="html",
            ))
            return
        text = str(prompt_raw).strip()
        if not text:
            return
        self._set_mapped_prompt_and_restart(map_key, entry_key, text)
        run_async(self._tg, async_send_text(
            self._tg, sender_id,
            f"✓ Updated {label} prompt for <code>{html.escape(entry_key)}</code>",
            parse_mode="html",
        ))
