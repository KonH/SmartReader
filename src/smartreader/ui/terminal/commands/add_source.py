from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import AddSourceCommand
from ..state import TerminalSharedUIState
from ....types.params import NewSourceParams

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalAddSourceCommand(AddSourceCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "add"

    def execute(self) -> None:
        console = self._terminal.console
        try:
            source_type = console.input(
                "[bold]Source type[/bold] [dim](rss/telegram)[/dim]: "
            ).strip().lower()
            if source_type not in ("rss", "telegram"):
                console.print("[yellow]Invalid type; expected 'rss' or 'telegram'[/yellow]")
                return

            external_id = console.input(
                "[bold]Source URL or channel ID:[/bold] "
            ).strip()
            if not external_id:
                console.print("[yellow]External ID cannot be empty[/yellow]")
                return

            name = console.input(
                "[bold]Source name[/bold] [dim](config key, no spaces)[/dim]: "
            ).strip()
            if not name or " " in name:
                console.print("[yellow]Name must be non-empty and have no spaces[/yellow]")
                return

            category_raw = console.input(
                "[bold]Category[/bold] [dim](optional, Enter to skip)[/dim]: "
            ).strip()
            category: str | None = category_raw if category_raw else None
        except EOFError:
            return

        self._write_source_and_restart(NewSourceParams(
            name=name,
            source_type=source_type,
            external_id=external_id,
            category=category,
        ))
