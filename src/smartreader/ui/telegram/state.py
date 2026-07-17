"""TelegramSharedUIState — all Telegram-specific runtime state in one place."""
from __future__ import annotations

import asyncio
import queue
import threading
from typing import TYPE_CHECKING, Literal

from ..command import SharedUIState

if TYPE_CHECKING:
    from ..._types import LiveFeedbackHandler
    from ...types.content import Content

UIMode = Literal["", "add", "skip", "ban", "prompt", "group", "cron", "config"]


class TelegramSharedUIState(SharedUIState):
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.thread: threading.Thread = threading.Thread(
            target=self.loop.run_forever, daemon=True, name="telegram-ui-loop"
        )
        self.trigger_queue: queue.Queue[dict] = queue.Queue()
        self.category_queue: queue.Queue[dict] = queue.Queue()
        self.add_step_queue: queue.Queue[str | None] = queue.Queue()
        self.content_by_id: dict[str, "Content"] = {}
        self.msg_loc_by_content_id: dict[str, tuple[int, int]] = {}
        self.live_feedback_handler: "LiveFeedbackHandler | None" = None
        self.client: object | None = None  # telethon.TelegramClient

        self.current_sender_id: int | None = None
        self.active: bool = False
        self.mode_state: UIMode = ""
        self.waiting_for_category: bool = False
        self.controller_usernames: list[str] = []
        self.upvote_text: str = "👍"
        self.downvote_text: str = "👎"
