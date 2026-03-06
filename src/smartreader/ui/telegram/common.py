"""Shared async helpers for TelegramUI — bot connection and message sending."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .state import TelegramSharedUIState
from .utils import username

logger = logging.getLogger(__name__)

_SESSION_PATH = ".tmp/telegram_ui.session"
_LAST_CHAT_FILE = ".tmp/telegram_ui_last_chat.txt"


def save_last_chat(sender_id: int) -> None:
    try:
        p = Path(_LAST_CHAT_FILE).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(sender_id))
        logger.info("telegram_ui: saved last_chat_id=%s", sender_id)
    except Exception as exc:
        logger.warning("telegram_ui: could not save last_chat_id: %s", exc)


def load_last_chat() -> int | None:
    try:
        p = Path(_LAST_CHAT_FILE).resolve()
        return int(p.read_text().strip())
    except Exception:
        return None


def run_async(s: TelegramSharedUIState, coro: object) -> object | None:
    future = asyncio.run_coroutine_threadsafe(coro, s.loop)  # type: ignore[arg-type]
    try:
        return future.result(timeout=30)
    except Exception as exc:
        logger.warning("telegram_ui: async error: %s", exc)
        return None


async def async_send_text(s: TelegramSharedUIState, chat_id: int, text: str, parse_mode: str | None = None) -> None:
    from telethon import TelegramClient  # type: ignore[import-untyped]
    client: TelegramClient = s.client  # type: ignore[assignment]
    if parse_mode is not None:
        await client.send_message(chat_id, text, parse_mode=parse_mode)
    else:
        await client.send_message(chat_id, text)


async def async_send_buttons(
    s: TelegramSharedUIState,
    chat_id: int,
    text: str,
    buttons_spec: list[list[tuple[str, str, str]]],
    parse_mode: str = "md",
) -> int:
    from telethon import TelegramClient  # type: ignore[import-untyped]
    from telethon.tl.custom import Button  # type: ignore[import-untyped]
    client: TelegramClient = s.client  # type: ignore[assignment]
    buttons = [
        [Button.inline(label, data.encode()) for _kind, label, data in row]
        for row in buttons_spec
    ]
    msg = await client.send_message(
        chat_id, text, buttons=buttons, link_preview=False, parse_mode=parse_mode
    )
    return msg.id


async def async_send_category_buttons(
    s: TelegramSharedUIState,
    chat_id: int,
    options: list[tuple[str, str]],
) -> None:
    from telethon import TelegramClient  # type: ignore[import-untyped]
    from telethon.tl.custom import Button  # type: ignore[import-untyped]
    client: TelegramClient = s.client  # type: ignore[assignment]
    buttons = [[Button.inline(label, data.encode())] for label, data in options]
    await client.send_message(chat_id, "Select a category:", buttons=buttons)


def send_action_menu(s: TelegramSharedUIState, sender_id: int) -> None:
    run_async(s, async_send_buttons(
        s, sender_id,
        "What next?",
        [
            [("inline", "\u25b6  SHOW", "menu:show")],
            [("inline", "\uff0b  ADD SOURCE", "menu:add")],
            [("inline", "\U0001f4cb  LOGS", "menu:logs")],
            [("inline", "\U0001f5c4  STATE", "menu:state")],
            [("inline", "\u26d4  SKIP WORD", "menu:skip")],
            [("inline", "\U0001f4dd  PROMPT", "menu:prompt")],
            [("inline", "\U0001f5d3  SCHEDULE", "menu:cron")],
            [("inline", "\U0001f4ca  EXPLAIN", "menu:explain")],
        ],
    ))


def send_category_keyboard(
    s: TelegramSharedUIState, sender_id: int, categories: list[str]
) -> None:
    options = [("ALL", "cat:")] + [(cat, f"cat:{cat}") for cat in categories]
    run_async(s, async_send_category_buttons(s, sender_id, options))


def register_handlers(s: TelegramSharedUIState) -> None:
    """Register all event handlers on the already-created client."""
    from telethon import events  # type: ignore[import-untyped]
    client = s.client  # type: ignore[union-attr]

    @client.on(events.NewMessage(incoming=True, pattern=r"(?i)^/?(run|start|add|logs|state|skip|prompt|cron|explain)"))
    async def on_trigger(event: object) -> None:  # type: ignore[type-arg]
        sender = await event.get_sender()  # type: ignore[attr-defined]
        if not _is_controller(s, sender):
            logger.info("telegram_ui: ignoring command from non-controller %s", username(sender))
            return
        if s.in_add_mode or s.in_skip_mode or s.in_set_prompt_mode or s.in_group_mode or s.in_set_cron_mode:
            return
        cmd = event.raw_text.strip().lstrip("/").lower().split()[0]  # type: ignore[attr-defined]
        mode = {"run": "ask", "start": "ask", "add": "add", "logs": "logs", "state": "state", "skip": "skip", "prompt": "prompt", "cron": "cron", "explain": "explain"}.get(cmd, "ask")
        logger.info("telegram_ui: /%s from %s (mode=%s)", cmd, username(sender), mode)
        save_last_chat(event.sender_id)  # type: ignore[attr-defined]
        if mode != "ask" and s.waiting_for_category:
            s.category_queue.put({"cancelled": True})
        s.trigger_queue.put({"sender_id": event.sender_id, "mode": mode})  # type: ignore[attr-defined]

    @client.on(events.NewMessage(incoming=True))
    async def on_add_message(event: object) -> None:  # type: ignore[type-arg]
        if not s.in_add_mode and not s.in_skip_mode and not s.in_set_prompt_mode and not s.in_group_mode and not s.in_set_cron_mode:
            return
        sender = await event.get_sender()  # type: ignore[attr-defined]
        if not _is_controller(s, sender):
            return
        s.add_step_queue.put(event.raw_text.strip())  # type: ignore[attr-defined]

    @client.on(events.CallbackQuery)
    async def on_callback(event: object) -> None:  # type: ignore[type-arg]
        data: str = event.data.decode()  # type: ignore[attr-defined]
        if data.startswith("cat:"):
            cat_raw = data[4:]
            cat: str | None = cat_raw if cat_raw else None
            s.category_queue.put({"category": cat})
            await event.answer()  # type: ignore[attr-defined]
        elif data.startswith("add_type:"):
            s.add_step_queue.put(data[9:])
            await event.answer()  # type: ignore[attr-defined]
        elif data.startswith("add_cat:"):
            s.add_step_queue.put(data[8:])
            await event.answer()  # type: ignore[attr-defined]
        elif data == "add_cat_new":
            s.add_step_queue.put("__new__")
            await event.answer()  # type: ignore[attr-defined]
        elif data == "add_skip":
            s.add_step_queue.put("")
            await event.answer()  # type: ignore[attr-defined]
        elif data in ("add_cancel", "skip_cancel", "prompt_cancel", "interests_cancel", "group_cancel", "cron_cancel"):
            s.add_step_queue.put(None)
            await event.answer()  # type: ignore[attr-defined]
        elif data.startswith("group_select:"):
            s.add_step_queue.put(data[13:])
            await event.answer()  # type: ignore[attr-defined]
        elif data.startswith("menu:"):
            cmd = data[5:]
            mode = {"show": "ask", "add": "add", "logs": "logs", "state": "state", "skip": "skip", "prompt": "prompt", "cron": "cron", "explain": "explain"}.get(cmd, "ask")
            sender_id = event.sender_id  # type: ignore[attr-defined]
            save_last_chat(sender_id)
            if mode != "ask" and s.waiting_for_category:
                s.category_queue.put({"cancelled": True})
            s.trigger_queue.put({"sender_id": sender_id, "mode": mode})
            await event.answer()  # type: ignore[attr-defined]
        elif data.startswith("vote:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                _, action, content_id = parts
                content = s.content_by_id.get(content_id)
                if content and s.live_feedback_handler:
                    s.live_feedback_handler(content, action == "up")
                loc = s.msg_loc_by_content_id.get(content_id)
                if loc is not None:
                    from telethon.tl.custom import Button  # type: ignore[import-untyped]
                    chat_id, msg_id = loc
                    upvoted = action == "up"
                    up_label = f"{s.upvote_text} ✓" if upvoted else s.upvote_text
                    down_label = f"{s.downvote_text} ✓" if not upvoted else s.downvote_text
                    new_buttons = [[
                        Button.inline(up_label, f"vote:up:{content_id}".encode()),
                        Button.inline(down_label, f"vote:down:{content_id}".encode()),
                    ]]
                    await client.edit_message(chat_id, msg_id, buttons=new_buttons)  # type: ignore[union-attr]
            await event.answer()  # type: ignore[attr-defined]


def _is_controller(s: TelegramSharedUIState, sender: object) -> bool:
    if not s.controller_usernames:
        return True
    return username(sender).lower() in s.controller_usernames


def get_existing_categories() -> list[str]:
    import tomllib
    try:
        with open("config.toml", "rb") as f:
            data = tomllib.load(f)
        sources = data.get("sources", {})
    except Exception:
        return []
    cats: set[str] = set()
    for entries in sources.values():
        for entry in (entries if isinstance(entries, list) else [entries]):
            if isinstance(entry, dict):
                cat = entry.get("category")
                if cat:
                    cats.add(str(cat))
    return sorted(cats)
