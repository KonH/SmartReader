from __future__ import annotations

import html
from typing import TYPE_CHECKING

from ...commands import SetCronCommand
from ..common import run_async, async_send_buttons, async_send_text, send_action_menu
from ..state import TelegramSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TelegramSetCronCommand(SetCronCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TelegramSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._tg = shared_ui_state

    @property
    def control_title(self) -> str:
        return "cron"

    def execute(self) -> None:
        sender_id = self._tg.current_sender_id
        if not self._tg.active or sender_id is None:
            return

        current = self._read_current_cron()
        if current:
            status = (
                f"Current schedule: <code>{html.escape(current)}</code> (enabled, {self._next_run_label(current)})\n"
                f"<i>(server local time: {self._now_label()})</i>"
            )
        else:
            status = (
                "Schedule: <i>disabled</i>\n"
                f"<i>(server local time: {self._now_label()})</i>"
            )

        help_text = (
            f"{status}\n\n"
            "<b>Set automatic show schedule</b>\n"
            f"Times are in <b>{html.escape(self._local_tz_label())}</b> (server local time)\n"
            "Uses cron syntax: <code>minute hour day-of-month month day-of-week</code>\n\n"
            "Examples:\n"
            "• <code>0 8 * * *</code>     — daily at 08:00\n"
            "• <code>0 */4 * * *</code>   — every 4 hours\n"
            "• <code>30 7 * * 1-5</code>  — weekdays at 07:30\n\n"
            'Reference: <a href="https://crontab.guru/">crontab.guru</a>\n\n'
            "Send a cron expression to enable, or <code>off</code> to disable:"
        )
        run_async(self._tg, async_send_buttons(
            self._tg, sender_id, help_text,
            [[("inline", "Cancel", "cron_cancel")]],
            parse_mode="html",
        ))
        self._tg.in_set_cron_mode = True
        expr_raw = self._tg.add_step_queue.get()
        self._tg.in_set_cron_mode = False

        if expr_raw is None:
            send_action_menu(self._tg, sender_id)
            return

        expr = expr_raw.strip()
        if expr.lower() == "off":
            self._set_cron_and_restart("")
            return

        try:
            valid = self._validate_cron(expr)
        except ImportError:
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                "croniter is not installed on the server.\nRun: <code>pip install croniter</code>",
                parse_mode="html",
            ))
            send_action_menu(self._tg, sender_id)
            return
        if not valid:
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                f"Invalid cron expression: <code>{html.escape(expr)}</code>\n"
                'Tip: build one at <a href="https://crontab.guru/">crontab.guru</a>',
                parse_mode="html",
            ))
            send_action_menu(self._tg, sender_id)
            return

        self._set_cron_and_restart(expr)
