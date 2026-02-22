from abc import ABC, abstractmethod

from .._types import ContentListCallback


class Input(ABC):
    @abstractmethod
    def read_sources(self, start_ts: float, type: str, id: str, callback: ContentListCallback) -> None: ...
