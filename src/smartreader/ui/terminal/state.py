from rich.console import Console

from ..command import SharedUIState


class TerminalSharedUIState(SharedUIState):
    def __init__(self) -> None:
        self.console: Console = Console()
