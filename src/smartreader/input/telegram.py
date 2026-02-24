"""Telegram input: reads messages from channels via the Telethon user API.

Enabled by ``[telegram] active = true`` in config.toml.
Required secrets (environment variables):
    TELEGRAM_API_ID    – integer API id from https://my.telegram.org/apps
    TELEGRAM_API_HASH  – string API hash from https://my.telegram.org/apps
Optional secrets:
    TELEGRAM_SESSION   – Telethon StringSession export; when absent the
                         session is persisted to .tmp/telegram.session and
                         Telethon may prompt for phone/OTP on first run.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .._types import Callback, ContentListCallback
from ..types.content import Content
from .source_reader import SourceEntry

if TYPE_CHECKING:
    from ..config import Config
    from ..secrets import Secrets

logger = logging.getLogger(__name__)

_SESSION_PATH = ".tmp/telegram.session"
_DEFAULT_LIMIT = 200


class TelegramReader:
    """Reads Telegram channel messages since a given timestamp.

    Lifecycle
    ---------
    ``initialize(secrets, config, callback)`` — called once during app init.
    ``read(source, start_ts, callback)``       — called per-source per-run.

    If ``[telegram] active`` is false (or absent) in config, ``initialize``
    succeeds immediately and ``read`` returns an empty list.

    Init errors (missing secrets, login failure) call back with
    ``success=False``, which the coordinator treats as a fatal error.

    Runtime read errors call back with ``success=False``; the coordinator
    logs a warning and does *not* update that source's lastReadTs.
    """

    def __init__(self) -> None:
        self._active = False
        self._client: object | None = None  # telethon.TelegramClient
        self._loop: asyncio.AbstractEventLoop | None = None
        self._min_interval_s: float = 0.0
        self._max_interval_s: float = 0.0

    # ── Initialization ────────────────────────────────────────────────────────

    def initialize(self, secrets: Secrets, config: Config, callback: Callback) -> None:
        """Connect to Telegram if enabled; fail app immediately on any error."""
        cfg: dict = {}
        config.read_value("telegram", lambda ok, err, val: cfg.update(val if isinstance(val, dict) else {}))

        if not cfg.get("active", False):
            logger.info("telegram input: disabled (set [telegram] active = true to enable)")
            callback(True, "")
            return

        min_ms = float(cfg.get("read_source_min_interval", 1000))
        max_ms = float(cfg.get("read_source_max_interval", 3000))
        self._min_interval_s = min(min_ms, max_ms) / 1000
        self._max_interval_s = max(min_ms, max_ms) / 1000
        logger.info(
            "telegram: inter-source delay %.0f–%.0f ms",
            self._min_interval_s * 1000, self._max_interval_s * 1000,
        )

        # --- read required secrets -------------------------------------------
        api_id_str = _read_secret(secrets, "TELEGRAM_API_ID")
        if api_id_str is None:
            callback(False, "telegram: secret TELEGRAM_API_ID is not set")
            return

        api_hash = _read_secret(secrets, "TELEGRAM_API_HASH")
        if api_hash is None:
            callback(False, "telegram: secret TELEGRAM_API_HASH is not set")
            return

        try:
            api_id = int(api_id_str)
        except ValueError:
            callback(False, f"telegram: TELEGRAM_API_ID must be an integer, got {api_id_str!r}")
            return

        session_str = _read_secret(secrets, "TELEGRAM_SESSION")  # may be None

        # --- create event loop and client ------------------------------------
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            from telethon import TelegramClient  # type: ignore[import-untyped]
            from telethon.sessions import StringSession  # type: ignore[import-untyped]
        except ImportError:
            callback(False, "telegram: telethon is not installed (pip install telethon)")
            return

        if session_str:
            session = StringSession(session_str)
            logger.info("telegram: using session from TELEGRAM_SESSION env var")
        else:
            Path(_SESSION_PATH).parent.mkdir(parents=True, exist_ok=True)
            session = _SESSION_PATH
            logger.info("telegram: using file session at %s", _SESSION_PATH)

        self._client = TelegramClient(session, api_id, api_hash, loop=self._loop)

        try:
            self._loop.run_until_complete(self._client.start())  # type: ignore[union-attr]
        except Exception as exc:
            callback(False, f"telegram: login failed: {exc}")
            return

        self._active = True
        logger.info("telegram: connected and authenticated")
        callback(True, "")

    # ── Reading ───────────────────────────────────────────────────────────────

    def read(self, source: SourceEntry, start_ts: float, callback: ContentListCallback) -> None:
        """Fetch messages from *source.external_id* published after *start_ts*."""
        if not self._active or self._client is None or self._loop is None:
            callback(True, "", [])
            return

        try:
            items = self._loop.run_until_complete(self._async_read(source, start_ts))
            logger.info("telegram %r: %d new message(s) since ts=%.0f", source.external_id, len(items), start_ts)
            callback(True, "", items)
        except Exception as exc:
            logger.warning("telegram read error for source %r (%s): %s", source.id, source.external_id, exc)
            callback(False, str(exc), [])
        finally:
            if self._max_interval_s > 0:
                delay = random.uniform(self._min_interval_s, self._max_interval_s)
                try:
                    time.sleep(delay)
                except Exception as exc:
                    logger.warning("telegram: interval sleep interrupted: %s", exc)

    async def _async_read(self, source: SourceEntry, start_ts: float) -> list[Content]:
        from telethon import TelegramClient  # type: ignore[import-untyped]

        client: TelegramClient = self._client  # type: ignore[assignment]
        min_date = datetime.fromtimestamp(start_ts, tz=timezone.utc)

        items: list[Content] = []
        async for message in client.iter_messages(
            source.external_id,
            reverse=True,       # oldest-first so we stop naturally when past start_ts
            offset_date=min_date,
            limit=_DEFAULT_LIMIT,
        ):
            if not message.text:
                continue
            pub_ts = message.date.timestamp()
            if pub_ts <= start_ts:
                continue

            lines = message.text.strip().splitlines()
            title = lines[0][:200] if lines else ""
            items.append(Content(
                id=f"tg_{source.external_id}_{message.id}",
                title=title,
                body=message.text,
                source_id=source.id,
                source_type="telegram",
                published_ts=pub_ts,
                category=source.category,
            ))

        return items


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_secret(secrets: Secrets, key: str) -> str | None:
    """Call secrets.read_value synchronously; return value or None on failure."""
    result: list[str | None] = [None]

    def cb(ok: bool, err: str, val: str) -> None:
        if ok and val:
            result[0] = val

    secrets.read_value(key, cb)
    return result[0]
