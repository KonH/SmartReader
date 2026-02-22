from abc import ABC, abstractmethod

from .._types import Callback, ScoreCallback
from ..types.content import Content


class Scoring(ABC):
    @abstractmethod
    def initialize(self, callback: Callback) -> None: ...

    @abstractmethod
    def score(self, content: Content, effort_level: int, callback: ScoreCallback) -> None: ...

    @abstractmethod
    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None: ...
