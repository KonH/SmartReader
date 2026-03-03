from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SetPromptGroupCommand
from ...command import UICommand
from ..state import TerminalSharedUIState
from .set_prompt import TerminalSetPromptCommand
from .set_interests_prompt import TerminalSetInterestsPromptCommand
from .set_summarize_prompt import TerminalSetSummarizePromptCommand
from .set_merge_prompt import TerminalSetMergePromptCommand
from .set_cluster_prompt import TerminalSetClusterPromptCommand

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalSetPromptGroupCommand(SetPromptGroupCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state
        self._subcmds: list[UICommand] = [
            TerminalSetPromptCommand(app_state, shared_ui_state),
            TerminalSetInterestsPromptCommand(app_state, shared_ui_state),
            TerminalSetSummarizePromptCommand(app_state, shared_ui_state),
            TerminalSetMergePromptCommand(app_state, shared_ui_state),
            TerminalSetClusterPromptCommand(app_state, shared_ui_state),
        ]

    @property
    def subcommands(self) -> list[UICommand]:
        return self._subcmds

    def execute(self) -> None:
        titles = " / ".join(cmd.control_title for cmd in self._subcmds)
        try:
            choice = self._terminal.console.input(f"{titles}: ").strip().lower()
        except EOFError:
            return
        for cmd in self._subcmds:
            if cmd.control_title == choice:
                cmd.execute()
                return
        self._terminal.console.print(f"[yellow]Unknown sub-command '{choice}'[/yellow]")
