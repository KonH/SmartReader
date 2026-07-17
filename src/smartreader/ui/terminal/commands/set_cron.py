from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SetCronCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalSetCronCommand(SetCronCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "cron"

    def execute(self) -> None:
        console = self._terminal.console
        current = self._read_current_cron()

        if current:
            console.print(f"[dim]Current schedule:[/dim] [bold]{current}[/bold] (enabled, {self._next_run_label(current)})")
        else:
            console.print("[dim]Schedule: disabled[/dim]")
        console.print(f"[dim](UTC now: {self._now_label()})[/dim]")
        console.print()
        console.print(
            "[dim]Timezone:[/dim]    UTC\n"
            "[dim]Cron format:[/dim]  minute  hour  day-of-month  month  day-of-week\n"
            "[dim]Examples:[/dim]\n"
            "  [cyan]0 8 * * *[/cyan]      daily at 08:00\n"
            "  [cyan]0 */4 * * *[/cyan]    every 4 hours\n"
            "  [cyan]30 7 * * 1-5[/cyan]   weekdays at 07:30\n"
            "[dim]Reference:[/dim] https://crontab.guru/"
        )
        console.print()
        try:
            raw = console.input(
                "[bold]Enter cron expression[/bold] [dim](empty = disable, Enter to cancel)[/dim]: "
            ).strip()
        except EOFError:
            return

        if not raw:
            console.print("[dim]Cancelled.[/dim]")
            return

        if raw.lower() == "off":
            self._set_cron_and_restart("")
            return

        try:
            valid = self._validate_cron(raw)
        except ImportError:
            console.print("[red]croniter is not installed.[/red] Run: pip install croniter")
            return
        if not valid:
            console.print(f"[red]Invalid cron expression:[/red] {raw!r}")
            console.print("[dim]Tip: use https://crontab.guru/ to build one[/dim]")
            return

        self._set_cron_and_restart(raw)
