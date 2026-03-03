from abc import ABC, abstractmethod

from .._types import Callback
from ..types.content import Content


class PipelineStage(ABC):
    def initialize(self, callback: Callback) -> None:
        callback(True, "")

    @abstractmethod
    def process(self, items: list[Content]) -> list[Content]: ...


class UpdatablePipelineStage(PipelineStage, ABC):
    @abstractmethod
    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None: ...
