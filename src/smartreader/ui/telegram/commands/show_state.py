from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ShowStateCommand
from ..common import run_async, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramShowStateCommand(ShowStateCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "state"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return
        data = self._read_state_data()

        def send_block(text: str) -> None:
            run_async(self._tg, async_send_text(self._tg, sender_id, text))

        # Block 1: Sources
        lines = [f"Sources ({len(data.source_states)})"]
        for entry in data.source_states:
            status = "active" if entry.active else "inactive"
            if entry.last_read_ts:
                from datetime import datetime
                ts_str = datetime.fromtimestamp(entry.last_read_ts).strftime("%b %d %H:%M")
            else:
                ts_str = "never read"
            lines.append(f"{entry.source_id}: {status}, last read {ts_str}")
        send_block("\n".join(lines))

        # Block 2: Skip / Ban words
        skip_str = ", ".join(sorted(data.skip_words)) if data.skip_words else "none"
        ban_str = ", ".join(sorted(data.ban_words)) if data.ban_words else "none"
        send_block(
            f"Skip words ({len(data.skip_words)}): {skip_str}\n"
            f"Ban words ({len(data.ban_words)}): {ban_str}"
        )

        # Block 3: Common interests
        n_common = len(data.common_interests)
        send_block(_format_scored_block(f"Common interests ({n_common} keywords)", list(data.common_interests.items())))

        # Block per category
        for cat, keywords in data.category_interests.items():
            n_cat = len(keywords)
            send_block(_format_scored_block(f"Category: {cat} ({n_cat} keywords)", list(keywords.items())))

        # Block: OpenAI state
        ai_lines = ["OpenAI scoring state"]
        ai_lines.append(f"Pending actions: {data.openai_pending_count}")
        if data.openai_user_summary:
            ai_lines.append(f"User summary: {data.openai_user_summary}")
        else:
            ai_lines.append("User summary: (none)")
        send_block("\n".join(ai_lines))

        send_action_menu(self._tg, sender_id)


def _format_scored_block(header: str, items: list[tuple[str, float]]) -> str:
    """Format a scored keyword block with top-10 / middle-skip / bottom-10."""
    lines = [header]
    if not items:
        lines.append("  (none)")
        return "\n".join(lines)
    if len(items) <= 20:
        for k, v in items:
            lines.append(f"- {k}: {v:.1f}")
    else:
        for k, v in items[:10]:
            lines.append(f"- {k}: {v:.1f}")
        middle = len(items) - 20
        lines.append(f"... (+{middle} words) ...")
        for k, v in items[-10:]:
            lines.append(f"- {k}: {v:.1f}")
    return "\n".join(lines)
