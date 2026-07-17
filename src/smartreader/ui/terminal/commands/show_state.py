from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ShowStateCommand
from ..state import TerminalSharedUIState
from ..utils import render_state

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalShowStateCommand(ShowStateCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "state"

    def execute(self) -> None:
        data = self._read_state_data()
        render_state(data, self._terminal.console)
