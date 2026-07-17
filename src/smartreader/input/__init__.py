from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .._types import Callback, ContentListCallback

if TYPE_CHECKING:
    from ..config import Config
    from ..secrets import Secrets


class Input(ABC):
    def initialize(self, secrets: Secrets, config: Config, callback: Callback) -> None:
        """Optional initialization called once during app startup.

        Override in implementations that require authentication or deferred
        setup (e.g. TelegramReader).  The default is a no-op success.
        Returning ``success=False`` aborts the application.
        """
        callback(True, "")

    @abstractmethod
    def read_sources(self, start_ts: float, type: str, id: str, callback: ContentListCallback) -> None: ...
