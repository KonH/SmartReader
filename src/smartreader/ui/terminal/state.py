import queue

from rich.console import Console

from ..command import SharedUIState


class TerminalSharedUIState(SharedUIState):
    def __init__(self) -> None:
        self.console: Console = Console()
        # Scheduled trigger payload: category name, or None for ALL categories
        self.trigger_queue: queue.Queue[str | None] = queue.Queue()
