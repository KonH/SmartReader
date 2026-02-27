"""Telegram Bot UI — non-blocking content delivery via inline keyboard buttons.

Enabled by ``[telegram_ui] active = true`` in config.toml.
Required secrets (environment variables):
    TELEGRAM_BOT_TOKEN – bot token from @BotFather
    TELEGRAM_API_ID    – integer API id from https://my.telegram.org/apps
    TELEGRAM_API_HASH  – string API hash from https://my.telegram.org/apps

How it works
------------
- A background daemon thread runs ``asyncio.new_event_loop().run_forever()``.
- ``wait_trigger`` blocks on a ``queue.Queue`` until a controller sends /run or /start.
- ``show_content_list`` sends one message per item with 👍/👎 inline buttons, then
  calls back immediately (non-blocking). Button presses fire ``live_feedback_handler``
  asynchronously from the background thread.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from .._types import Callback, FeedbackListCallback, LiveFeedbackHandler, TriggerCallback
from ..types.content import Content
from ..types.params import TriggerParams, UIParams
from . import UI

if TYPE_CHECKING:
    from ..config import Config
    from ..secrets import Secrets

logger = logging.getLogger(__name__)

_SESSION_PATH = ".tmp/telegram_ui.session"


class TelegramUI(UI):
    """Non-blocking Telegram Bot UI.

    Content is delivered as Telegram messages with inline vote buttons.
    Feedback arrives asynchronously via ``live_feedback_handler``.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread: threading.Thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="telegram-ui-loop"
        )
        self._trigger_queue: queue.Queue[dict] = queue.Queue()
        self._category_queue: queue.Queue[dict] = queue.Queue()
        self._content_by_id: dict[str, Content] = {}
        self._live_feedback_handler: LiveFeedbackHandler | None = None
        self._client: object | None = None  # telethon.TelegramClient

        # Per-session sender so we know where to push messages
        self._current_sender_id: int | None = None

        # Config fields (set during initialize)
        self._active = False
        self._controller_usernames: list[str] = []
        self._upvote_text: str = "👍"
        self._downvote_text: str = "👎"

    # ── UI interface ──────────────────────────────────────────────────────────

    def initialize(self, params: UIParams, callback: Callback) -> None:
        self._live_feedback_handler = params.live_feedback

        # We need config and secrets — but UIParams only carries live_feedback.
        # Config/secrets access is deferred to the module-level helpers injected
        # via the coordinator.  We can't call them here directly, so we rely on
        # the TOMLConfig._data being already loaded (coordinator init order ensures
        # secrets → config → state → scoring → summarize → ui).
        # To avoid circular deps we import lazily and reach config via a fresh read.
        #
        # The simplest approach: stash the secrets/config references passed during
        # coordinator init.  Because UIParams is the only parameter we get here,
        # the coordinator wires these in via the UIParams extension point.  For now
        # we defer config/secrets reading to a helper that uses the coordinator's
        # already-initialised objects.
        #
        # IMPORTANT: the coordinator calls ui.initialize AFTER config & secrets are
        # ready, so we can safely import and access them at call time.
        self._do_initialize(params, callback)

    def wait_trigger(self, categories: list[str], callback: TriggerCallback) -> None:
        if not self._active:
            # Inactive: behave like TerminalUI but accept any stdin trigger
            logger.info("telegram_ui inactive — waiting is a no-op; returning immediately")
            callback(True, "", TriggerParams(mode="ask", category=None))
            return

        logger.info("telegram_ui: waiting for /run command from a controller")
        item = self._trigger_queue.get()  # blocks main thread
        sender_id: int = item["sender_id"]
        self._current_sender_id = sender_id

        if not categories:
            callback(True, "", TriggerParams(mode="ask", category=None))
            return

        # Send category selection keyboard
        self._send_category_keyboard(sender_id, categories)
        selected = self._category_queue.get()  # blocks until button pressed
        callback(True, "", TriggerParams(mode="ask", category=selected["category"]))

    def show_content_list(self, content: list[Content], callback: FeedbackListCallback) -> None:
        if not self._active or self._client is None:
            callback(True, "", [])
            return

        self._content_by_id = {c.id: c for c in content}
        sender_id = self._current_sender_id

        if not content:
            if sender_id is not None:
                self._run_async(self._async_send_text(sender_id, "No new content found."))
            callback(True, "", [])
            return

        for item in content:
            text = item.summary or item.body
            title_part = f"[{_escape_md(item.title)}]({item.url})" if item.url else _escape_md(item.title)
            msg_text = f"{title_part}\n\n{text}"
            buttons = [
                [
                    ("inline", self._upvote_text, f"vote:up:{item.id}"),
                    ("inline", self._downvote_text, f"vote:down:{item.id}"),
                ]
            ]
            if sender_id is not None:
                self._run_async(self._async_send_buttons(sender_id, msg_text, buttons))

        # Non-blocking: return immediately, feedback arrives via live_feedback_handler
        callback(True, "", [])

    def receive_score(self, id: str, score: float) -> None:
        pass  # no-op for bot UI

    def terminate(self) -> None:
        if self._client is not None:
            try:
                self._run_async(self._async_disconnect())
            except Exception as exc:
                logger.warning("telegram_ui: disconnect error: %s", exc)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    # ── Internal init ─────────────────────────────────────────────────────────

    def _do_initialize(self, params: UIParams, callback: Callback) -> None:
        """Read config, connect bot, register handlers."""
        # Import here to access the already-loaded config via module globals.
        # We import TOMLConfig only to read the already-loaded singleton; we
        # avoid re-loading from disk.
        try:
            from ..config.toml import TOMLConfig as _TOMLConfig  # noqa: F401
        except ImportError:
            pass

        # Read config directly via a thin TOML file read (avoids circular deps).
        cfg = _read_toml_section("telegram_ui")
        if not cfg.get("active", False):
            logger.info("telegram_ui: disabled (set [telegram_ui] active = true to enable)")
            self._active = False
            callback(True, "")
            return

        self._controller_usernames = [
            str(u).lstrip("@").lower() for u in cfg.get("controller_usernames", [])
        ]
        self._upvote_text = str(cfg.get("upvote_reaction", "👍"))
        self._downvote_text = str(cfg.get("downvote_reaction", "👎"))

        # Read secrets from env directly (EnvSecrets is already init'd but we
        # can just use os.environ to avoid callback indirection).
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
            from telethon import TelegramClient, events  # type: ignore[import-untyped]
        except ImportError:
            callback(False, "telegram_ui: telethon is not installed (pip install telethon)")
            return

        Path(_SESSION_PATH).parent.mkdir(parents=True, exist_ok=True)
        client = TelegramClient(_SESSION_PATH, api_id, api_hash, loop=self._loop)
        self._client = client

        # Register event handlers on the client before starting
        @client.on(events.NewMessage(incoming=True, pattern=r"(?i)^/?(run|start)"))
        async def on_trigger(event: object) -> None:  # type: ignore[type-arg]
            sender = await event.get_sender()  # type: ignore[attr-defined]
            if not self._is_controller(sender):
                logger.info("telegram_ui: ignoring /run from non-controller %s", _username(sender))
                return
            logger.info("telegram_ui: /run received from %s", _username(sender))
            self._trigger_queue.put({"sender_id": event.sender_id})  # type: ignore[attr-defined]

        @client.on(events.CallbackQuery)
        async def on_callback(event: object) -> None:  # type: ignore[type-arg]
            data: str = event.data.decode()  # type: ignore[attr-defined]
            if data.startswith("cat:"):
                cat_raw = data[4:]
                cat: str | None = cat_raw if cat_raw else None
                self._category_queue.put({"category": cat})
                await event.answer()  # type: ignore[attr-defined]
            elif data.startswith("vote:"):
                parts = data.split(":", 2)
                if len(parts) == 3:
                    _, action, content_id = parts
                    content = self._content_by_id.get(content_id)
                    if content and self._live_feedback_handler:
                        self._live_feedback_handler(content, action == "up")
                await event.answer()  # type: ignore[attr-defined]

        # Start background event loop thread
        self._thread.start()

        # Connect and authenticate the bot
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._async_start_bot(bot_token),
                self._loop,
            )
            future.result(timeout=30)
        except Exception as exc:
            callback(False, f"telegram_ui: bot login failed: {exc}")
            return

        self._active = True
        logger.info("telegram_ui: bot connected and listening")
        callback(True, "")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_controller(self, sender: object) -> bool:
        if not self._controller_usernames:
            return True  # no restriction — any user can trigger
        username = _username(sender)
        return username.lower() in self._controller_usernames

    def _send_category_keyboard(self, sender_id: int, categories: list[str]) -> None:
        """Send inline keyboard with ALL + each category button."""
        options = [("ALL", "cat:")] + [(cat, f"cat:{cat}") for cat in categories]
        self._run_async(self._async_send_category_buttons(sender_id, options))

    def _run_async(self, coro: object) -> None:
        """Schedule a coroutine on the background loop and wait for result."""
        import asyncio as _asyncio
        future = _asyncio.run_coroutine_threadsafe(coro, self._loop)  # type: ignore[arg-type]
        try:
            future.result(timeout=30)
        except Exception as exc:
            logger.warning("telegram_ui: async send error: %s", exc)

    async def _async_start_bot(self, token: str) -> None:
        import inspect
        result = self._client.start(bot_token=token)  # type: ignore[union-attr]
        if inspect.isawaitable(result):
            await result

    async def _async_send_text(self, chat_id: int, text: str) -> None:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        client: TelegramClient = self._client  # type: ignore[assignment]
        await client.send_message(chat_id, text)

    async def _async_send_category_buttons(
        self, chat_id: int, options: list[tuple[str, str]]
    ) -> None:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.tl.custom import Button  # type: ignore[import-untyped]
        client: TelegramClient = self._client  # type: ignore[assignment]
        buttons = [[Button.inline(label, data.encode()) for label, data in options]]
        await client.send_message(chat_id, "Select a category:", buttons=buttons)

    async def _async_send_buttons(
        self, chat_id: int, text: str, buttons_spec: list[list[tuple[str, str, str]]]
    ) -> None:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.tl.custom import Button  # type: ignore[import-untyped]
        client: TelegramClient = self._client  # type: ignore[assignment]
        buttons = [
            [Button.inline(label, data.encode()) for _kind, label, data in row]
            for row in buttons_spec
        ]
        await client.send_message(
            chat_id, text, buttons=buttons, link_preview=False, parse_mode="md"
        )

    async def _async_disconnect(self) -> None:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        client: TelegramClient = self._client  # type: ignore[assignment]
        await client.disconnect()


# ── Module-level helpers ───────────────────────────────────────────────────────

def _escape_md(text: str) -> str:
    """Escape Markdown special chars for Telegram MarkdownV1."""
    for ch in ("*", "_", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def _username(sender: object) -> str:
    username = getattr(sender, "username", None)
    return str(username) if username else str(getattr(sender, "id", "unknown"))


def _read_toml_section(section: str) -> dict:
    """Read a single top-level section from config.toml without using the Config module."""
    import tomllib
    try:
        with open("config.toml", "rb") as f:
            data = tomllib.load(f)
        return data.get(section, {})
    except (FileNotFoundError, Exception):
        return {}
