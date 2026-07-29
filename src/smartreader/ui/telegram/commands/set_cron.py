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

        # Drain stale queue entries from a previous interaction
        while not self._tg.add_step_queue.empty():
            self._tg.add_step_queue.get_nowait()

        status_lines = self._format_schedule_status_lines()
        status = "\n".join(
            f"• <code>{html.escape(line)}</code>" for line in status_lines
        )
        categories = self._schedule_target_categories()

        pick_text = (
            f"<b>Current schedules</b>\n"
            f"{status}\n"
            f"<i>(UTC now: {self._now_label()})</i>\n\n"
            "Choose which schedule to edit:"
        )
        buttons: list[list[tuple[str, str, str]]] = [
            [("inline", "ALL (all categories)", "cron_target:")],
        ]
        for cat in categories:
            buttons.append([("inline", cat, f"cron_target:{cat}")])
        buttons.append([("inline", "Cancel", "cron_cancel")])

        self._tg.mode_state = "cron"
        try:
            run_async(self._tg, async_send_buttons(
                self._tg, sender_id, pick_text, buttons, parse_mode="html",
            ))
            target_raw = self._tg.add_step_queue.get()
            if target_raw is None:
                return

            # "" = ALL; anything else = category name
            category: str | None = target_raw if target_raw else None
            target_label = category if category is not None else "ALL"

            current = self._read_current_cron(category)
            if current:
                cur_status = (
                    f"Current for <b>{html.escape(target_label)}</b>: "
                    f"<code>{html.escape(current)}</code> "
                    f"(enabled, {self._next_run_label(current)})"
                )
            else:
                cur_status = (
                    f"Current for <b>{html.escape(target_label)}</b>: <i>disabled</i>"
                )

            help_text = (
                f"{cur_status}\n"
                f"<i>(UTC now: {self._now_label()})</i>\n\n"
                f"<b>Set schedule for {html.escape(target_label)}</b>\n"
                "Times are in <b>UTC</b>\n"
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
            expr_raw = self._tg.add_step_queue.get()
            if expr_raw is None:
                return

            expr = expr_raw.strip()
            if expr.lower() == "off":
                self._set_cron_and_restart("", category)
                run_async(self._tg, async_send_text(
                    self._tg, sender_id,
                    f"Schedule for <b>{html.escape(target_label)}</b> disabled.",
                    parse_mode="html",
                ))
                return

            try:
                valid = self._validate_cron(expr)
            except ImportError:
                run_async(self._tg, async_send_text(
                    self._tg, sender_id,
                    "croniter is not installed on the server.\n"
                    "Run: <code>pip install croniter</code>",
                    parse_mode="html",
                ))
                return
            if not valid:
                run_async(self._tg, async_send_text(
                    self._tg, sender_id,
                    f"Invalid cron expression: <code>{html.escape(expr)}</code>\n"
                    'Tip: build one at <a href="https://crontab.guru/">crontab.guru</a>',
                    parse_mode="html",
                ))
                return

            self._set_cron_and_restart(expr, category)
            run_async(self._tg, async_send_text(
                self._tg, sender_id,
                f"Schedule for <b>{html.escape(target_label)}</b> set to "
                f"<code>{html.escape(expr)}</code> ({self._next_run_label(expr)}).",
                parse_mode="html",
            ))
        finally:
            self._tg.mode_state = ""
            send_action_menu(self._tg, sender_id)
