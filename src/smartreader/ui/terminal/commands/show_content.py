from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import ShowContentCommand
from ..state import TerminalSharedUIState
from ..utils import collect_feedback, render_content_table

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalShowContentCommand(ShowContentCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "show"

    def execute(self) -> None:
        items = self._run_pipeline(self._app_state.trigger_category)
        render_content_table(items, self._terminal.console)
        feedback = collect_feedback(items, self._terminal.console) if items else []
        self._update_source_states()
        self._process_feedback(feedback)
