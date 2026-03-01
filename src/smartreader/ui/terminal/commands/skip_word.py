from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SkipWordCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalSkipWordCommand(SkipWordCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "skip"

    def execute(self) -> None:
        try:
            word = self._terminal.console.input("Word to skip: ").strip().lower()
        except EOFError:
            return
        if word:
            self._add_skip_and_restart(word)
