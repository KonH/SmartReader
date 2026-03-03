from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SetSummarizePromptCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalSetSummarizePromptCommand(SetSummarizePromptCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "summarize"

    def execute(self) -> None:
        current = self._read_current_summarize_prompt()
        if current:
            self._terminal.console.print("[dim]Current summarize prompt:[/dim]")
            self._terminal.console.print(current)
            self._terminal.console.print()
        try:
            prompt = self._terminal.console.input("New summarize prompt (Enter to keep current): ").strip()
        except EOFError:
            return
        if prompt:
            self._set_summarize_prompt_and_restart(prompt)
