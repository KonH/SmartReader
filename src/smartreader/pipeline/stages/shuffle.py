from random import random

from ...types.content import Content
from .. import PipelineStage


class ShuffleStage(PipelineStage):
    """Adds random noise to item scores — useful for diversifying results."""

    def __init__(self, noise_factor: float) -> None:
        self._factor = noise_factor

    def process(self, items: list[Content]) -> list[Content]:
        for item in items:
            item.score = (item.score or 0.0) + random() * self._factor
        return items
