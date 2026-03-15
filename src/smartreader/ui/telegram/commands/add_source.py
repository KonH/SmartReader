from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import AddSourceCommand
from ..common import (
    get_existing_categories,
    run_async,
    async_send_buttons,
    async_send_text,
    send_action_menu,
)
from ..state import TelegramSharedUIState
from ..utils import normalize_source_name, normalize_telegram_id
from ....types.params import NewSourceParams

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramAddSourceCommand(AddSourceCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "add"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        self._tg.mode_state = "add"
        try:
            result = self._run_add_conversation(sender_id)
        finally:
            self._tg.mode_state = ""

        if result is None:
            send_action_menu(self._tg, sender_id)
        else:
            self._write_source_and_restart(result)

    def _run_add_conversation(self, sender_id: int) -> NewSourceParams | None:
        s = self._tg

        # Step 1: source type
        run_async(s, async_send_buttons(
            s, sender_id,
            "Step 1/4 \u2014 Select source type:",
            [
                [("inline", "RSS", "add_type:rss")],
                [("inline", "Telegram", "add_type:telegram")],
                [("inline", "Cancel", "add_cancel")],
            ],
        ))
        type_val = s.add_step_queue.get()
        if type_val is None:
            return None
        source_type = type_val

        # Step 2: external ID
        run_async(s, async_send_buttons(
            s, sender_id,
            "Step 2/4 \u2014 Enter the feed URL or Telegram channel link/username:",
            [[("inline", "Cancel", "add_cancel")]],
        ))
        ext_val = s.add_step_queue.get()
        if ext_val is None:
            return None
        external_id = (
            normalize_telegram_id(ext_val) if source_type == "telegram" else ext_val.strip()
        )

        # Step 3: source name
        default_name = normalize_source_name(external_id)
        run_async(s, async_send_buttons(
            s, sender_id,
            f"Step 3/4 \u2014 Enter a source name (config key) or skip to use the default:\n`{default_name}`",
            [
                [("inline", f"Skip \u2014 use \u2018{default_name}\u2019", "add_skip")],
                [("inline", "Cancel", "add_cancel")],
            ],
        ))
        name_val = s.add_step_queue.get()
        if name_val is None:
            return None
        name = name_val.strip() if name_val.strip() else default_name

        # Step 4: category
        existing_cats = get_existing_categories()
        cat_buttons: list[list[tuple[str, str, str]]] = [
            [("inline", cat, f"add_cat:{cat}")] for cat in existing_cats
        ]
        cat_buttons += [
            [("inline", "\uff0b  New category", "add_cat_new")],
            [("inline", "Skip (no category)", "add_skip")],
            [("inline", "Cancel", "add_cancel")],
        ]
        run_async(s, async_send_buttons(
            s, sender_id, "Step 4/4 \u2014 Select a category:", cat_buttons
        ))
        cat_val = s.add_step_queue.get()
        if cat_val is None:
            return None

        if cat_val == "__new__":
            run_async(s, async_send_buttons(
                s, sender_id,
                "Enter the new category name:",
                [[("inline", "Cancel", "add_cancel")]],
            ))
            new_cat_raw = s.add_step_queue.get()
            if new_cat_raw is None:
                return None
            category: str | None = new_cat_raw.strip() if new_cat_raw.strip() else None
        else:
            category = cat_val if cat_val else None

        run_async(s, async_send_text(s, sender_id, "Source added \u2713  Reloading\u2026"))
        return NewSourceParams(
            name=name, source_type=source_type,
            external_id=external_id, category=category,
        )
