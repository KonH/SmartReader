"""UICommand and SharedUIState ABCs.

UICommand defines the interface each command must implement.
SharedUIState is an empty marker base class — concrete subclasses (e.g.
TerminalSharedUIState, TelegramSharedUIState) hold UI-specific dependencies
such as the console, bot client, queues and flags.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class SharedUIState(ABC):
    """Marker base for UI-specific shared state (console, bot, queues, …)."""


class UICommand(ABC):
    @property
    @abstractmethod
    def control_title(self) -> str:
        """Short label shown in menus and matched on user input."""
        ...

    @abstractmethod
    def execute(self) -> None:
        """Run the command.  Self-contained, synchronous from the caller's view."""
        ...
