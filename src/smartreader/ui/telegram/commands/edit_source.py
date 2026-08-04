from __future__ import annotations

import html
from typing import TYPE_CHECKING

from ...commands import EditSourceCommand
from ..common import (
    get_existing_categories,
    run_async,
    async_send_buttons,
    async_send_text,
    send_action_menu,
)
from ..state import TelegramSharedUIState
from ..utils import normalize_telegram_id
from ....types.params import NewSourceParams

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramEditSourceCommand(EditSourceCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "edit"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        while not self._tg.add_step_queue.empty():
            self._tg.add_step_queue.get_nowait()
        self._tg.mode_state = "edit"
        try:
            result = self._run_edit_conversation(sender_id)
        finally:
            self._tg.mode_state = ""

        if result is None:
            send_action_menu(self._tg, sender_id)
        else:
            self._update_source_and_restart(result)
            send_action_menu(self._tg, sender_id)

    def _run_edit_conversation(self, sender_id: int) -> NewSourceParams | None:
        s = self._tg
        names = self._list_source_names()
        if not names:
            run_async(s, async_send_text(s, sender_id, "No sources configured."))
            return None

        pick_buttons: list[list[tuple[str, str, str]]] = [
            [("inline", name, f"src_pick:{i}")] for i, name in enumerate(names)
        ]
        pick_buttons.append([("inline", "Cancel", "edit_cancel")])
        run_async(s, async_send_buttons(
            s, sender_id, "Select a source to edit:", pick_buttons,
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

        entry = self._read_source_entry(name)
        if entry is None:
            run_async(s, async_send_text(s, sender_id, f"Source `{name}` not found."))
            return None

        cur_type = str(entry.get("type", "rss"))
        cur_ext = str(entry.get("externalId", ""))
        cur_cat = entry.get("category")
        cur_cat_str = str(cur_cat) if cur_cat else ""

        # Type
        run_async(s, async_send_buttons(
            s, sender_id,
            (
                f"Editing <b>{html.escape(name)}</b>\n"
                f"Current type: <code>{html.escape(cur_type)}</code>\n\n"
                "Select new type or keep current:"
            ),
            [
                [("inline", "RSS", "add_type:rss")],
                [("inline", "Telegram", "add_type:telegram")],
                [("inline", f"Keep — {cur_type}", "edit_keep")],
                [("inline", "Cancel", "edit_cancel")],
            ],
            parse_mode="html",
        ))
        type_val = s.add_step_queue.get()
        if type_val is None:
            return None
        source_type = cur_type if type_val == "__keep__" else str(type_val)

        # External ID
        run_async(s, async_send_buttons(
            s, sender_id,
            (
                f"Current ID/URL: <code>{html.escape(cur_ext)}</code>\n\n"
                "Enter a new feed URL or Telegram channel, or keep current:"
            ),
            [
                [("inline", "Keep current", "edit_keep")],
                [("inline", "Cancel", "edit_cancel")],
            ],
            parse_mode="html",
        ))
        ext_val = s.add_step_queue.get()
        if ext_val is None:
            return None
        if ext_val == "__keep__":
            external_id = cur_ext
        else:
            external_id = (
                normalize_telegram_id(ext_val)
                if source_type == "telegram"
                else str(ext_val).strip()
            )
            if not external_id:
                run_async(s, async_send_text(s, sender_id, "External ID cannot be empty."))
                return None

        # Category
        existing_cats = get_existing_categories()
        cat_label = cur_cat_str if cur_cat_str else "(none)"
        cat_buttons: list[list[tuple[str, str, str]]] = [
            [("inline", cat, f"add_cat:{cat}")] for cat in existing_cats
        ]
        cat_buttons += [
            [("inline", "＋  New category", "add_cat_new")],
            [("inline", "Clear category", "add_skip")],
            [("inline", f"Keep — {cat_label}", "edit_keep")],
            [("inline", "Cancel", "edit_cancel")],
        ]
        run_async(s, async_send_buttons(
            s, sender_id,
            (
                f"Current category: <code>{html.escape(cat_label)}</code>\n\n"
                "Select a category:"
            ),
            cat_buttons,
            parse_mode="html",
        ))
        cat_val = s.add_step_queue.get()
        if cat_val is None:
            return None

        if cat_val == "__keep__":
            category: str | None = cur_cat_str if cur_cat_str else None
        elif cat_val == "__new__":
            run_async(s, async_send_buttons(
                s, sender_id,
                "Enter the new category name:",
                [[("inline", "Cancel", "edit_cancel")]],
            ))
            new_cat_raw = s.add_step_queue.get()
            if new_cat_raw is None:
                return None
            category = new_cat_raw.strip() if new_cat_raw.strip() else None
        else:
            category = cat_val if cat_val else None

        run_async(s, async_send_text(
            s, sender_id, f"Source `{name}` updated ✓  Reloading…",
        ))
        return NewSourceParams(
            name=name,
            source_type=source_type,
            external_id=external_id,
            category=category,
        )
