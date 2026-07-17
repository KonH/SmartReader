from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ShowContentCommand
from ..common import run_async, async_send_buttons, async_send_text, send_action_menu
from ..state import TelegramSharedUIState
from ..utils import md_to_html

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramShowContentCommand(ShowContentCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "show"

    def _before_pipeline(self, item_count: int, estimated_seconds: float | None) -> None:
        from ...commands import _fmt_seconds
        sender_id = self._tg.current_sender_id
        if sender_id is None:
            return
        if estimated_seconds is None:
            msg = f"Processing {item_count} item(s)\u2026"
        else:
            msg = f"Processing {item_count} item(s), ~{_fmt_seconds(estimated_seconds)} estimated\u2026"
        run_async(self._tg, async_send_text(self._tg, sender_id, msg))

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        items = self._run_pipeline(self._app_state.trigger_category)

        self._tg.content_by_id = {c.id: c for c in items}
        self._tg.msg_loc_by_content_id = {}

        if not items:
            if sender_id is not None:
                run_async(self._tg, async_send_text(self._tg, sender_id, "No new content found."))
        else:
            for item in items:
                body = md_to_html(item.summary or item.body or "")
                if item.related_ids:
                    title_part = f"🔀 {md_to_html(item.title)}"
                    sources_lines = []
                    for related in item.related_contents:
                        if related.url:
                            sources_lines.append(f'• <a href="{related.url}">{md_to_html(related.title)}</a> [{related.source_id}]')
                        else:
                            sources_lines.append(f"• {md_to_html(related.title)} [{related.source_id}]")
                    sources_block = "\n".join(sources_lines)
                    msg_text = f"<b>{title_part}</b>\n📌 Sources:\n{sources_block}\n\n{body}"
                else:
                    if item.url:
                        title_part = f'<a href="{item.url}">{md_to_html(item.title)}</a>'
                    else:
                        title_part = md_to_html(item.title)
                    msg_text = f"<code>[{item.source_id}]</code> {title_part}\n\n{body}"
                buttons = [[
                    ("inline", self._tg.upvote_text, f"vote:up:{item.id}"),
                    ("inline", self._tg.downvote_text, f"vote:down:{item.id}"),
                ]]
                if sender_id is not None:
                    msg_id = run_async(
                        self._tg,
                        async_send_buttons(self._tg, sender_id, msg_text, buttons, parse_mode="html"),
                    )
                    if isinstance(msg_id, int):
                        self._tg.msg_loc_by_content_id[item.id] = (sender_id, msg_id)

        if sender_id is not None:
            send_action_menu(self._tg, sender_id)

        # Update state; feedback arrives asynchronously via live_feedback_handler
        self._update_source_states()
