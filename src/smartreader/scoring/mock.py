from .._types import Callback, ScoreCallback
from ..types.content import Content
from . import Scoring


class MockScoring(Scoring):
    def initialize(self, callback: Callback) -> None: callback(True, "")
    def score(self, content: Content, effort_level: int, callback: ScoreCallback) -> None: callback(True, "", 0.0)
    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None: callback(True, "")
