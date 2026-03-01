from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ShowLogsCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalShowLogsCommand(ShowLogsCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "logs"

    def execute(self) -> None:
        lines = self._read_log_lines()
        for line in lines:
            self._terminal.console.print(line)
