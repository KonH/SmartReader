import logging

from ...types.content import Content
from .. import PipelineStage

logger = logging.getLogger(__name__)


class TopNStage(PipelineStage):
    """Selects the top N items by score (descending), dropping the rest."""

    def __init__(self, n: int) -> None:
        self._n = n

    def process(self, items: list[Content]) -> list[Content]:
        sorted_items = sorted(items, key=lambda c: c.score or 0.0, reverse=True)
        selected = sorted_items[:self._n]
        logger.info("pipeline top_n: %d/%d selected", len(selected), len(items))
        return selected
