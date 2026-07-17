from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ExplainCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalExplainCommand(ExplainCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "explain"

    def execute(self) -> None:
        path = self._generate_report()
        if path is None:
            self._terminal.console.print(
                "[yellow]No pipeline data found — run 'show' first.[/yellow]"
            )
        else:
            self._terminal.console.print(
                f"[green]Report generated:[/green] {path.resolve()}"
            )
