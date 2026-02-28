from abc import ABC, abstractmethod

from .._types import Callback, TriggerCallback, FeedbackListCallback, NewSourceCallback
from ..types.app_state import AppStateData
from ..types.content import Content
from ..types.params import UIParams


class UI(ABC):
    @abstractmethod
    def initialize(self, params: UIParams, callback: Callback) -> None: ...

    @abstractmethod
    def wait_trigger(self, categories: list[str], callback: TriggerCallback) -> None: ...

    @abstractmethod
    def show_content_list(self, content: list[Content], callback: FeedbackListCallback) -> None: ...

    @abstractmethod
    def receive_score(self, id: str, score: float) -> None: ...

    @abstractmethod
    def prompt_new_source(self, callback: NewSourceCallback) -> None: ...

    @abstractmethod
    def show_logs(self, lines: list[str], callback: Callback) -> None: ...

    @abstractmethod
    def show_state(self, data: AppStateData, callback: Callback) -> None: ...

    @abstractmethod
    def terminate(self) -> None: ...
