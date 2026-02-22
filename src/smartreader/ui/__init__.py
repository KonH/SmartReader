from abc import ABC, abstractmethod

from .._types import Callback, TriggerCallback, FeedbackListCallback
from ..types.content import Content
from ..types.params import UIParams


class UI(ABC):
    @abstractmethod
    def initialize(self, params: UIParams, callback: Callback) -> None: ...

    @abstractmethod
    def wait_trigger(self, callback: TriggerCallback) -> None: ...

    @abstractmethod
    def show_content_list(self, content: list[Content], callback: FeedbackListCallback) -> None: ...

    @abstractmethod
    def receive_score(self, id: str, score: float) -> None: ...

    @abstractmethod
    def terminate(self) -> None: ...
