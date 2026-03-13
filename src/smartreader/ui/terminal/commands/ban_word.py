from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import BanWordCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalBanWordCommand(BanWordCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "ban"

    def execute(self) -> None:
        try:
            words = self._terminal.console.input("Word(s) to ban (space-separated): ").strip().lower()
        except EOFError:
            return
        if words:
            self._add_ban_and_restart(words)
