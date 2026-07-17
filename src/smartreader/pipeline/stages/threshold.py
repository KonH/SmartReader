from __future__ import annotations

from ..._types import Callback
from ...types.content import Content
from .. import PipelineStage


class ThresholdStage(PipelineStage):
    def __init__(self, threshold: float = 0.0) -> None:
        self._threshold = threshold

    def initialize(self, callback: Callback) -> None:
        callback(True, "")

    def process(self, items: list[Content]) -> list[Content]:
        return [item for item in items if (item.score or 0.0) >= self._threshold]
