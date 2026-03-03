"""Telegram Bot UI — non-blocking content delivery via inline keyboard buttons.

Enabled by ``[telegram_ui] active = true`` in config.toml.
Required env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_API_ID, TELEGRAM_API_HASH.
"""
from __future__ import annotations

import asyncio
import logging
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

from ..._types import Callback
from ...types.params import UIParams
from ..command import UICommand
from ..commands import ShowContentCommand
from .commands import (
    TelegramAddSourceCommand,
    TelegramSetCronCommand,
    TelegramSetPromptGroupCommand,
    TelegramShowContentCommand,
    TelegramShowLogsCommand,
    TelegramShowStateCommand,
    TelegramSkipWordCommand,
)
from .common import (
    load_last_chat,
    register_handlers,
    run_async,
    async_send_text,
    send_action_menu,
    send_category_keyboard,
    _SESSION_PATH,
)
from .state import TelegramSharedUIState
from .. import UI

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_COMMAND_TYPES: list[type[UICommand]] = [
    TelegramShowContentCommand,
    TelegramAddSourceCommand,
    TelegramShowLogsCommand,
    TelegramShowStateCommand,
    TelegramSkipWordCommand,
    TelegramSetPromptGroupCommand,
    TelegramSetCronCommand,
]

_MODE_TO_TITLE = {
    "ask": "show",   # show with category selection
    "run": "show",   # show without category selection (used by scheduled triggers)
    "add": "add",
    "logs": "logs",
    "state": "state",
    "skip": "skip",
    "prompt": "prompt",
    "cron": "cron",
}


class TelegramUI(UI):
    """Non-blocking Telegram Bot UI."""

    def __init__(self, shared_ui_state: TelegramSharedUIState) -> None:
        self._shared = shared_ui_state

    def initialize(self, params: UIParams, callback: Callback) -> None:
        self._shared.live_feedback_handler = params.live_feedback
        self._do_initialize(callback)

    def get_commands(self) -> list[type[UICommand]]:
        return list(_COMMAND_TYPES)

    def loop(self, commands: list[UICommand]) -> None:
        s = self._shared
        if not s.active:
            logger.info("telegram_ui inactive — loop returns immediately")
            return

        # Get app_state from ShowContentCommand
        app_state = None
        for cmd in commands:
            if isinstance(cmd, ShowContentCommand):
                app_state = cmd._app_state
                break

        cmd_by_title = {cmd.control_title.lower(): cmd for cmd in commands}

        while True:
            # Refresh categories
            categories: list[str] = []
            if app_state is not None and app_state.config is not None:
                cats_result: list[list[str]] = [[]]

                def on_sources(ok: bool, err: str, val: object) -> None:
                    if ok and isinstance(val, dict):
                        cats_result[0] = _extract_categories(val)

                app_state.config.read_value("sources", on_sources)
                categories = cats_result[0]
                app_state.categories = categories

            logger.info("telegram_ui: waiting for trigger (state: in_add=%s in_skip=%s in_prompt=%s in_group=%s in_cron=%s waiting_cat=%s)",
                        s.in_add_mode, s.in_skip_mode, s.in_set_prompt_mode, s.in_group_mode, s.in_set_cron_mode, s.waiting_for_category)
            item = s.trigger_queue.get()
            sender_id: int = item["sender_id"]
            s.current_sender_id = sender_id
            mode: str = item.get("mode", "ask")

            title = _MODE_TO_TITLE.get(mode, "show")
            cmd = cmd_by_title.get(title)
            logger.info("telegram_ui: got trigger sender_id=%s mode=%r -> title=%r cmd=%s",
                        sender_id, mode, title, type(cmd).__name__ if cmd else None)
            if cmd is None:
                logger.warning("telegram_ui: no command for mode=%s", mode)
                send_action_menu(s, sender_id)
                continue

            if mode == "ask":
                if categories:
                    send_category_keyboard(s, sender_id, categories)
                    s.waiting_for_category = True
                    selected = s.category_queue.get()
                    s.waiting_for_category = False
                    if selected.get("cancelled"):
                        logger.info("telegram_ui: category selection cancelled")
                        continue
                    cat = selected.get("category")
                else:
                    cat = None

                if app_state is not None:
                    app_state.trigger_category = cat
                logger.info("telegram_ui: executing %s (category=%r)", type(cmd).__name__, cat)
                cmd.execute()
                logger.info("telegram_ui: %s.execute() returned", type(cmd).__name__)
            else:
                if app_state is not None:
                    app_state.trigger_category = None
                logger.info("telegram_ui: executing %s (no category selection)", type(cmd).__name__)
                cmd.execute()
                logger.info("telegram_ui: %s.execute() returned", type(cmd).__name__)

    def terminate(self) -> None:
        s = self._shared
        if s.client is not None:
            try:
                run_async(s, _async_disconnect(s))
            except Exception as exc:
                logger.warning("telegram_ui: disconnect error: %s", exc)
        s.loop.call_soon_threadsafe(s.loop.stop)
        s.thread.join(timeout=5)

    # ── Internal init ──────────────────────────────────────────────────────────

    def _do_initialize(self, callback: Callback) -> None:
        import tomllib
        try:
            with open("config.toml", "rb") as f:
                cfg_data = tomllib.load(f)
            cfg = cfg_data.get("telegram_ui", {})
        except Exception:
            cfg = {}

        if not cfg.get("active", False):
            logger.info("telegram_ui: disabled (set [telegram_ui] active = true to enable)")
            self._shared.active = False
            callback(True, "")
            return

        s = self._shared
        s.controller_usernames = [
            str(u).lstrip("@").lower() for u in cfg.get("controller_usernames", [])
        ]
        s.upvote_text = str(cfg.get("upvote_reaction", "👍"))
        s.downvote_text = str(cfg.get("downvote_reaction", "👎"))

        import os
        api_id_str = os.environ.get("TELEGRAM_API_ID")
        api_hash = os.environ.get("TELEGRAM_API_HASH")
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")

        if not api_id_str:
            callback(False, "telegram_ui: TELEGRAM_API_ID env var not set")
            return
        if not api_hash:
            callback(False, "telegram_ui: TELEGRAM_API_HASH env var not set")
            return
        if not bot_token:
            callback(False, "telegram_ui: TELEGRAM_BOT_TOKEN env var not set")
            return
        try:
            api_id = int(api_id_str)
        except ValueError:
            callback(False, f"telegram_ui: TELEGRAM_API_ID must be integer, got {api_id_str!r}")
            return

        try:
            from telethon import TelegramClient  # type: ignore[import-untyped]
        except ImportError:
            callback(False, "telegram_ui: telethon is not installed (pip install telethon)")
            return

        Path(_SESSION_PATH).parent.mkdir(parents=True, exist_ok=True)
        s.client = TelegramClient(_SESSION_PATH, api_id, api_hash, loop=s.loop)

        register_handlers(s)
        s.thread.start()

        try:
            future = asyncio.run_coroutine_threadsafe(
                _async_start_bot(s, bot_token), s.loop
            )
            future.result(timeout=30)
        except Exception as exc:
            callback(False, f"telegram_ui: bot login failed: {exc}")
            return

        s.active = True
        logger.info("telegram_ui: bot connected and listening")

        last_chat = load_last_chat()
        if last_chat is not None:
            run_async(s, async_send_text(s, last_chat, "SmartReader ready \u2713"))
            send_action_menu(s, last_chat)

        callback(True, "")


async def _async_start_bot(s: TelegramSharedUIState, token: str) -> None:
    result = s.client.start(bot_token=token)  # type: ignore[union-attr]
    if inspect.isawaitable(result):
        await result


async def _async_disconnect(s: TelegramSharedUIState) -> None:
    from telethon import TelegramClient  # type: ignore[import-untyped]
    client: TelegramClient = s.client  # type: ignore[assignment]
    await client.disconnect()


def _extract_categories(sources_val: dict) -> list[str]:
    cats: set[str] = set()
    for entries in sources_val.values():
        for entry in (entries if isinstance(entries, list) else [entries]):
            cat = entry.get("category") if isinstance(entry, dict) else None
            if cat:
                cats.add(cat)
    return sorted(cats)
