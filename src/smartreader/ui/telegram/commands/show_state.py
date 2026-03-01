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

        # Block 2: Common interests
        n_common = len(data.common_interests)
        block2_lines = [f"Common interests ({n_common} keywords)"]
        for k, v in data.common_interests.items():
            block2_lines.append(f"- {k}: {v:.1f}")
        block2 = "\n".join(block2_lines)
        if len(block2) > 4000:
            truncated: list[str] = [block2_lines[0]]
            for line in block2_lines[1:]:
                if len("\n".join(truncated + [line])) + 20 > 4000:
                    remaining = n_common - (len(truncated) - 1)
                    truncated.append(f"... +{remaining} more")
                    break
                truncated.append(line)
            block2 = "\n".join(truncated)
        send_block(block2)

        # Block per category
        for cat, keywords in data.category_interests.items():
            n_cat = len(keywords)
            cat_lines = [f"Category: {cat} ({n_cat} keywords)"]
            for k, v in keywords.items():
                cat_lines.append(f"- {k}: {v:.1f}")
            block = "\n".join(cat_lines)
            if len(block) > 4000:
                truncated_cat: list[str] = [cat_lines[0]]
                for line in cat_lines[1:]:
                    if len("\n".join(truncated_cat + [line])) + 20 > 4000:
                        remaining_cat = n_cat - (len(truncated_cat) - 1)
                        truncated_cat.append(f"... +{remaining_cat} more")
                        break
                    truncated_cat.append(line)
                block = "\n".join(truncated_cat)
            send_block(block)

        send_action_menu(self._tg, sender_id)
