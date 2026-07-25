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

        console.print("[bold]Current schedules[/bold]")
        for line in self._format_schedule_status_lines():
            console.print(f"  [dim]•[/dim] {line}")
        console.print(f"[dim](UTC now: {self._now_label()})[/dim]")
        console.print()

        categories = self._schedule_target_categories()
        options: list[str | None] = [None] + list(categories)
        console.print("[bold]Edit schedule for:[/bold]")
        for i, cat in enumerate(options):
            label = "ALL (all categories)" if cat is None else cat
            console.print(f"  [dim]{i}.[/dim] {label}")
        console.print()
        try:
            pick = console.input(
                "[bold]Select target (number)[/bold] [dim](Enter to cancel)[/dim]: "
            ).strip()
        except EOFError:
            return
        if not pick:
            console.print("[dim]Cancelled.[/dim]")
            return
        if not pick.isdigit() or not (0 <= int(pick) < len(options)):
            console.print("[red]Invalid selection.[/red]")
            return
        category = options[int(pick)]
        target_label = "ALL" if category is None else category

        current = self._read_current_cron(category)
        if current:
            console.print(
                f"[dim]Current for {target_label}:[/dim] [bold]{current}[/bold] "
                f"(enabled, {self._next_run_label(current)})"
            )
        else:
            console.print(f"[dim]Current for {target_label}: disabled[/dim]")
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
                f"[bold]Enter cron for {target_label}[/bold] "
                "[dim](off = disable, Enter to cancel)[/dim]: "
            ).strip()
        except EOFError:
            return

        if not raw:
            console.print("[dim]Cancelled.[/dim]")
            return

        if raw.lower() == "off":
            self._set_cron_and_restart("", category)
            console.print(f"[green]Schedule for {target_label} disabled.[/green]")
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

        self._set_cron_and_restart(raw, category)
        console.print(
            f"[green]Schedule for {target_label} set to[/green] [bold]{raw}[/bold] "
            f"({self._next_run_label(raw)})."
        )
