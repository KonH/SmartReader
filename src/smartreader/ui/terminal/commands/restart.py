from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from ...commands import RestartCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalRestartCommand(RestartCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "restart"

    def execute(self) -> None:
        self._terminal.console.print("[yellow]Restarting…[/yellow]")
        sys.exit(0)
