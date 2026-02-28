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
- After every finished action (startup Ready, content shown, logs shown, add cancelled)
  an action menu with SHOW / ADD SOURCE / LOGS buttons is sent to the controller.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from .._types import Callback, FeedbackListCallback, LiveFeedbackHandler, NewSourceCallback, TriggerCallback
from ..types.content import Content
from ..types.params import NewSourceParams, TriggerParams, UIParams
from ..types.values import StateValue
from . import UI

import tomli_w

if TYPE_CHECKING:
    from ..config import Config
    from ..secrets import Secrets

logger = logging.getLogger(__name__)

_SESSION_PATH = ".tmp/telegram_ui.session"
_LAST_CHAT_FILE = ".tmp/telegram_ui_last_chat.txt"


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
        self._add_step_queue: queue.Queue[str | None] = queue.Queue()
        self._content_by_id: dict[str, Content] = {}
        self._msg_loc_by_content_id: dict[str, tuple[int, int]] = {}  # content_id → (chat_id, msg_id)
        self._live_feedback_handler: LiveFeedbackHandler | None = None
        self._client: object | None = None  # telethon.TelegramClient

        # Per-session sender so we know where to push messages
        self._current_sender_id: int | None = None

        # Config fields (set during initialize)
        self._active = False
        self._in_add_mode = False
        self._waiting_for_category = False
        self._controller_usernames: list[str] = []
        self._upvote_text: str = "👍"
        self._downvote_text: str = "👎"

    # ── UI interface ──────────────────────────────────────────────────────────

    def initialize(self, params: UIParams, callback: Callback) -> None:
        self._live_feedback_handler = params.live_feedback
        self._do_initialize(params, callback)

    def wait_trigger(self, categories: list[str], callback: TriggerCallback) -> None:
        if not self._active:
            logger.info("telegram_ui inactive — waiting is a no-op; returning immediately")
            callback(True, "", TriggerParams(mode="ask", category=None))
            return

        logger.info("telegram_ui: waiting for /run command from a controller")
        while True:
            item = self._trigger_queue.get()  # blocks main thread
            sender_id: int = item["sender_id"]
            self._current_sender_id = sender_id
            mode: str = item.get("mode", "ask")

            if mode != "ask":
                callback(True, "", TriggerParams(mode=mode, category=None))
                return

            if not categories:
                callback(True, "", TriggerParams(mode="ask", category=None))
                return

            # Send category selection keyboard
            self._send_category_keyboard(sender_id, categories)
            self._waiting_for_category = True
            selected = self._category_queue.get()  # blocks until button pressed or cancelled
            self._waiting_for_category = False
            if selected.get("cancelled"):
                # A non-ask command arrived; loop back to pick it up from trigger_queue
                logger.info("telegram_ui: category selection cancelled by new command")
                continue
            callback(True, "", TriggerParams(mode="ask", category=selected["category"]))
            return

    def show_content_list(self, content: list[Content], callback: FeedbackListCallback) -> None:
        if not self._active or self._client is None:
            callback(True, "", [])
            return

        self._content_by_id = {c.id: c for c in content}
        self._msg_loc_by_content_id = {}
        sender_id = self._current_sender_id

        if not content:
            if sender_id is not None:
                self._run_async(self._async_send_text(sender_id, "No new content found."))
        else:
            for item in content:
                text = item.summary or item.body
                title_part = f"[{_escape_md(item.title)}]({item.url})" if item.url else _escape_md(item.title)
                msg_text = f"`[{item.source_id}]` {title_part}\n\n{text}"
                buttons = [
                    [
                        ("inline", self._upvote_text, f"vote:up:{item.id}"),
                        ("inline", self._downvote_text, f"vote:down:{item.id}"),
                    ]
                ]
                if sender_id is not None:
                    msg_id = self._run_async(self._async_send_buttons(sender_id, msg_text, buttons))
                    if isinstance(msg_id, int):
                        self._msg_loc_by_content_id[item.id] = (sender_id, msg_id)

        if sender_id is not None:
            self._send_action_menu(sender_id)
        callback(True, "", [])

    def receive_score(self, id: str, score: float) -> None:
        pass  # no-op for bot UI

    def prompt_new_source(self, callback: NewSourceCallback) -> None:
        sender_id = self._current_sender_id
        if not self._active or sender_id is None:
            callback(False, "not active", None)
            return
        self._in_add_mode = True
        try:
            result = self._run_add_conversation(sender_id)
        finally:
            self._in_add_mode = False
        # Show action menu only on cancel; on success the app is about to restart
        if result is None and sender_id is not None:
            self._send_action_menu(sender_id)
        callback(True, "", result)

    def show_logs(self, lines: list[str], callback: Callback) -> None:
        sender_id = self._current_sender_id
        if not self._active or sender_id is None:
            callback(True, "")
            return
        text = "\n".join(lines) if lines else "No log entries."
        chunk_size = 4000
        for i in range(0, max(len(text), 1), chunk_size):
            chunk = text[i:i + chunk_size]
            self._run_async(self._async_send_text(sender_id, f"```\n{chunk}\n```"))
        self._send_action_menu(sender_id)
        callback(True, "")

    def show_state(self, data: dict[str, StateValue], callback: Callback) -> None:
        import json
        sender_id = self._current_sender_id
        if not self._active or sender_id is None:
            callback(True, "")
            return
        if not data:
            self._run_async(self._async_send_text(sender_id, "State is empty."))
        else:
            # Build one block per key, then chunk at 4000 chars
            entries = [
                f"{key}:\n{json.dumps(data[key], indent=2, ensure_ascii=False)}"
                for key in sorted(data)
            ]
            text = "\n\n".join(entries)
            chunk_size = 4000
            for i in range(0, max(len(text), 1), chunk_size):
                chunk = text[i:i + chunk_size]
                self._run_async(self._async_send_text(sender_id, f"```\n{chunk}\n```"))
        self._send_action_menu(sender_id)
        callback(True, "")

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
        try:
            from ..config.toml import TOMLConfig as _TOMLConfig  # noqa: F401
        except ImportError:
            pass

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
            from telethon.tl.custom import Button  # type: ignore[import-untyped]
        except ImportError:
            callback(False, "telegram_ui: telethon is not installed (pip install telethon)")
            return

        Path(_SESSION_PATH).parent.mkdir(parents=True, exist_ok=True)
        client = TelegramClient(_SESSION_PATH, api_id, api_hash, loop=self._loop)
        self._client = client

        # Register event handlers on the client before starting
        @client.on(events.NewMessage(incoming=True, pattern=r"(?i)^/?(run|start|add|logs|state)"))
        async def on_trigger(event: object) -> None:  # type: ignore[type-arg]
            sender = await event.get_sender()  # type: ignore[attr-defined]
            if not self._is_controller(sender):
                logger.info("telegram_ui: ignoring command from non-controller %s", _username(sender))
                return
            if self._in_add_mode:
                return  # Ignore trigger commands during add conversation
            cmd = event.raw_text.strip().lstrip("/").lower().split()[0]  # type: ignore[attr-defined]
            mode = {"run": "ask", "start": "ask", "add": "add", "logs": "logs", "state": "state"}.get(cmd, "ask")
            logger.info("telegram_ui: /%s received from %s (mode=%s)", cmd, _username(sender), mode)
            _save_last_chat(event.sender_id)  # type: ignore[attr-defined]
            if mode != "ask" and self._waiting_for_category:
                self._category_queue.put({"cancelled": True})
            self._trigger_queue.put({"sender_id": event.sender_id, "mode": mode})  # type: ignore[attr-defined]

        @client.on(events.NewMessage(incoming=True))
        async def on_add_message(event: object) -> None:  # type: ignore[type-arg]
            if not self._in_add_mode:
                return
            sender = await event.get_sender()  # type: ignore[attr-defined]
            if not self._is_controller(sender):
                return
            self._add_step_queue.put(event.raw_text.strip())  # type: ignore[attr-defined]

        @client.on(events.CallbackQuery)
        async def on_callback(event: object) -> None:  # type: ignore[type-arg]
            data: str = event.data.decode()  # type: ignore[attr-defined]
            if data.startswith("cat:"):
                cat_raw = data[4:]
                cat: str | None = cat_raw if cat_raw else None
                self._category_queue.put({"category": cat})
                await event.answer()  # type: ignore[attr-defined]
            elif data.startswith("add_type:"):
                self._add_step_queue.put(data[9:])
                await event.answer()  # type: ignore[attr-defined]
            elif data.startswith("add_cat:"):
                self._add_step_queue.put(data[8:])
                await event.answer()  # type: ignore[attr-defined]
            elif data == "add_cat_new":
                self._add_step_queue.put("__new__")
                await event.answer()  # type: ignore[attr-defined]
            elif data == "add_skip":
                self._add_step_queue.put("")
                await event.answer()  # type: ignore[attr-defined]
            elif data == "add_cancel":
                self._add_step_queue.put(None)
                await event.answer()  # type: ignore[attr-defined]
            elif data.startswith("menu:"):
                cmd = data[5:]
                mode = {"show": "ask", "add": "add", "logs": "logs", "state": "state"}.get(cmd, "ask")
                sender_id = event.sender_id  # type: ignore[attr-defined]
                _save_last_chat(sender_id)
                if mode != "ask" and self._waiting_for_category:
                    self._category_queue.put({"cancelled": True})
                self._trigger_queue.put({"sender_id": sender_id, "mode": mode})
                await event.answer()  # type: ignore[attr-defined]
            elif data.startswith("vote:"):
                parts = data.split(":", 2)
                if len(parts) == 3:
                    _, action, content_id = parts
                    content = self._content_by_id.get(content_id)
                    if content and self._live_feedback_handler:
                        self._live_feedback_handler(content, action == "up")
                    loc = self._msg_loc_by_content_id.get(content_id)
                    if loc is not None:
                        chat_id, msg_id = loc
                        upvoted = action == "up"
                        up_label = f"{self._upvote_text} ✓" if upvoted else self._upvote_text
                        down_label = f"{self._downvote_text} ✓" if not upvoted else self._downvote_text
                        new_buttons = [
                            [
                                Button.inline(up_label, f"vote:up:{content_id}".encode()),
                                Button.inline(down_label, f"vote:down:{content_id}".encode()),
                            ]
                        ]
                        await client.edit_message(chat_id, msg_id, buttons=new_buttons)  # type: ignore[union-attr]
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

        # Send "Ready" + action menu to last known controller chat if available
        last_chat = _load_last_chat()
        if last_chat is not None:
            self._run_async(self._async_send_text(last_chat, "SmartReader ready \u2713"))
            self._send_action_menu(last_chat)

        callback(True, "")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_controller(self, sender: object) -> bool:
        if not self._controller_usernames:
            return True  # no restriction — any user can trigger
        username = _username(sender)
        return username.lower() in self._controller_usernames

    def _send_action_menu(self, sender_id: int) -> None:
        """Send the SHOW / ADD SOURCE / LOGS / STATE action menu."""
        self._run_async(self._async_send_buttons(
            sender_id,
            "What next?",
            [
                [("inline", "\u25b6  SHOW", "menu:show")],
                [("inline", "\uff0b  ADD SOURCE", "menu:add")],
                [("inline", "\U0001f4cb  LOGS", "menu:logs")],
                [("inline", "\U0001f5c4  STATE", "menu:state")],
            ],
        ))

    def _send_category_keyboard(self, sender_id: int, categories: list[str]) -> None:
        """Send inline keyboard with ALL + each category button."""
        options = [("ALL", "cat:")] + [(cat, f"cat:{cat}") for cat in categories]
        self._run_async(self._async_send_category_buttons(sender_id, options))

    def _run_add_conversation(self, sender_id: int) -> NewSourceParams | None:
        """Drive the interactive /add conversation and return params or None if cancelled."""
        # Step 1: source type
        self._run_async(self._async_send_buttons(
            sender_id,
            "Step 1/4 \u2014 Select source type:",
            [[
                ("inline", "RSS", "add_type:rss"),
                ("inline", "Telegram", "add_type:telegram"),
                ("inline", "Cancel", "add_cancel"),
            ]],
        ))
        type_val = self._add_step_queue.get()
        if type_val is None:
            return None
        source_type = type_val  # "rss" or "telegram"

        # Step 2: external ID (URL or channel)
        self._run_async(self._async_send_buttons(
            sender_id,
            "Step 2/4 \u2014 Enter the feed URL or Telegram channel link/username:",
            [[("inline", "Cancel", "add_cancel")]],
        ))
        ext_val = self._add_step_queue.get()
        if ext_val is None:
            return None

        # Normalise t.me links for telegram sources
        if source_type == "telegram":
            external_id = _normalize_telegram_id(ext_val)
        else:
            external_id = ext_val.strip()

        # Step 3: source name (optional — skip uses auto-generated default)
        default_name = _normalize_source_name(external_id)
        self._run_async(self._async_send_buttons(
            sender_id,
            f"Step 3/4 \u2014 Enter a source name (config key) or skip to use the default:\n`{default_name}`",
            [[
                ("inline", f"Skip \u2014 use \u2018{default_name}\u2019", "add_skip"),
                ("inline", "Cancel", "add_cancel"),
            ]],
        ))
        name_val = self._add_step_queue.get()
        if name_val is None:
            return None
        name = name_val.strip() if name_val.strip() else default_name

        # Step 4: category — show existing categories + New / Skip / Cancel
        existing_cats = _get_existing_categories()
        cat_buttons: list[list[tuple[str, str, str]]] = [
            [("inline", cat, f"add_cat:{cat}")] for cat in existing_cats
        ]
        cat_buttons += [
            [("inline", "\uff0b  New category", "add_cat_new")],
            [("inline", "Skip (no category)", "add_skip")],
            [("inline", "Cancel", "add_cancel")],
        ]
        self._run_async(self._async_send_buttons(
            sender_id,
            "Step 4/4 \u2014 Select a category:",
            cat_buttons,
        ))
        cat_val = self._add_step_queue.get()
        if cat_val is None:
            return None

        if cat_val == "__new__":
            # Ask the user to type a new category name
            self._run_async(self._async_send_buttons(
                sender_id,
                "Enter the new category name:",
                [[("inline", "Cancel", "add_cancel")]],
            ))
            new_cat_raw = self._add_step_queue.get()
            if new_cat_raw is None:
                return None
            category: str | None = new_cat_raw.strip() if new_cat_raw.strip() else None
        else:
            category = cat_val if cat_val else None

        # Persist to config.toml BEFORE restart
        self._write_new_source_to_config(
            name=name,
            source_type=source_type,
            external_id=external_id,
            category=category,
        )

        self._run_async(self._async_send_text(
            sender_id, "Source added \u2713  Restarting\u2026"
        ))
        return NewSourceParams(
            name=name, source_type=source_type,
            external_id=external_id, category=category,
        )

    def _write_new_source_to_config(
        self,
        name: str,
        source_type: str,
        external_id: str,
        category: str | None,
    ) -> None:
        """Append new source entry into config.toml."""

        import tomllib
        from pathlib import Path

        config_path = Path("config.toml")

        if not config_path.exists():
            logger.error("telegram_ui: config.toml not found")
            return

        # Load existing config
        with config_path.open("rb") as f:
            data = tomllib.load(f)

        sources = data.setdefault("sources", {})

        entry = {
            "type": source_type,
            "external_id": external_id,
        }

        if category:
            entry["category"] = category

        # Overwrite if same name already exists
        sources[name] = entry

        # Write back to file
        with config_path.open("wb") as f:
            tomli_w.dump(data, f)

        logger.info("telegram_ui: source '%s' written to config.toml", name)

    def _run_async(self, coro: object) -> object | None:
        """Schedule a coroutine on the background loop, wait for result, and return it."""
        import asyncio as _asyncio
        future = _asyncio.run_coroutine_threadsafe(coro, self._loop)  # type: ignore[arg-type]
        try:
            return future.result(timeout=30)
        except Exception as exc:
            logger.warning("telegram_ui: async send error: %s", exc)
            return None

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
        buttons = [[Button.inline(label, data.encode())] for label, data in options]
        await client.send_message(chat_id, "Select a category:", buttons=buttons)

    async def _async_send_buttons(
        self, chat_id: int, text: str, buttons_spec: list[list[tuple[str, str, str]]]
    ) -> int:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.tl.custom import Button  # type: ignore[import-untyped]
        client: TelegramClient = self._client  # type: ignore[assignment]
        buttons = [
            [Button.inline(label, data.encode()) for _kind, label, data in row]
            for row in buttons_spec
        ]
        msg = await client.send_message(
            chat_id, text, buttons=buttons, link_preview=False, parse_mode="md"
        )
        return msg.id

    async def _async_disconnect(self) -> None:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        client: TelegramClient = self._client  # type: ignore[assignment]
        await client.disconnect()


# ── Module-level helpers ───────────────────────────────────────────────────────

def _save_last_chat(sender_id: int) -> None:
    """Persist the last controller chat ID to a file for "Ready" on next startup."""
    try:
        p = Path(_LAST_CHAT_FILE).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(sender_id))
        logger.info("telegram_ui: saved last_chat_id=%s to %s", sender_id, p)
    except Exception as exc:
        logger.warning("telegram_ui: could not save last_chat_id: %s", exc)


def _load_last_chat() -> int | None:
    """Load the last controller chat ID from file, or return None if not found."""
    try:
        p = Path(_LAST_CHAT_FILE).resolve()
        text = p.read_text().strip()
        return int(text)
    except Exception:
        return None


def _normalize_telegram_id(raw: str) -> str:
    """For t.me links, extract the channel username; otherwise return as-is."""
    m = re.match(r'^(?:https?://)?t\.me/([^/?#]+)', raw.strip())
    return m.group(1) if m else raw.strip()


def _normalize_source_name(external_id: str) -> str:
    """Derive a clean config-key name from an external ID or URL.

    Examples:
        "bbcrussian"                                    → "bbcrussian"
        "https://t.me/bbcrussian"  (after t.me strip)  → "bbcrussian"
        "https://feeds.bbci.co.uk/news/world/rss.xml"  → "world"
        "https://feeds.feedburner.com/TechCrunch"       → "techcrunch"
    """
    s = external_id.strip()
    s = re.sub(r'^https?://', '', s)
    s = re.sub(r'^www\.', '', s, flags=re.I)
    parts = [p for p in s.split('/') if p]
    if not parts:
        return 'source'

    _SKIP = {'rss', 'feed', 'feeds', 'atom', 'news', 'index', 'latest', 'all'}
    _TLDS = {'com', 'net', 'org', 'io', 'co', 'uk', 'de', 'ru', 'me', 'tv', 'app', 'dev'}
    _PFXS = {'www', 'feeds', 'rss', 'feed', 'news', 'media'}

    # Try meaningful path components (skip domain = parts[0])
    candidates: list[str] = []
    for p in parts[1:]:
        p = re.sub(r'\.(rss|xml|atom|json|feed|html?)$', '', p, flags=re.I)
        p = re.sub(r'[-_]?(rss|feed|atom)$', '', p, flags=re.I)
        if p and p.lower() not in _SKIP:
            candidates.append(p)

    if candidates:
        base = candidates[-1]
    else:
        domain_parts = parts[0].split('.')
        significant = [p for p in domain_parts
                       if p.lower() not in _TLDS and p.lower() not in _PFXS]
        base = significant[-1] if significant else domain_parts[0]

    base = re.sub(r'[^a-z0-9]+', '_', base.lower())
    return base.strip('_') or 'source'


def _get_existing_categories() -> list[str]:
    """Return sorted unique category names from the current config."""
    sources = _read_toml_section("sources")
    cats: set[str] = set()
    for entries in sources.values():
        for entry in (entries if isinstance(entries, list) else [entries]):
            if isinstance(entry, dict):
                cat = entry.get("category")
                if cat:
                    cats.add(str(cat))
    return sorted(cats)


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
