import logging

from .._types import Callback, ScoreCallback
from ..types.content import Content
from . import Scoring

logger = logging.getLogger(__name__)


class ScoringAdapter(Scoring):
    """
    Delegates scoring to L1 or L2 based on effort_level.
    Both implementations are injected at construction time.
    """

    def __init__(self, l1: Scoring, l2: Scoring) -> None:
        self._l1 = l1
        self._l2 = l2

    def initialize(self, callback: Callback) -> None:
        self._l1.initialize(
            lambda ok, err: self._l2.initialize(callback) if ok else callback(False, err)
        )

    def score(self, content: Content, effort_level: int, callback: ScoreCallback) -> None:
        if effort_level >= 2:
            self._l2.score(content, effort_level, callback)
        else:
            self._l1.score(content, effort_level, callback)

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        """Update interests from both L1 (body) and L2 (summary) text."""
        self._l1.update_score(
            content, upvote,
            lambda ok, err: self._l2.update_score(content, upvote, callback) if ok else callback(False, err),
        )
