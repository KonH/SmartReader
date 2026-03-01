import random

from .._types import Callback, ScoreCallback
from ..types.content import Content
from . import Scoring


class NoiseScoring(Scoring):
    """Adds random() * noise_factor to score — useful for shuffling results."""

    def __init__(self, noise_factor: float) -> None:
        self._factor = noise_factor

    def initialize(self, callback: Callback) -> None:
        callback(True, "")

    def score(self, content: Content, effort_level: int, callback: ScoreCallback) -> None:
        callback(True, "", random.random() * self._factor)

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        callback(True, "")
