import logging

from ...types.content import Content
from .. import PipelineStage

logger = logging.getLogger(__name__)


class NormalizeScoreStage(PipelineStage):
    """Rescales item scores per-category from observed [min, max] to a target range."""

    def __init__(self, normalized_min: float = 0.0, normalized_max: float = 1.0) -> None:
        self._norm_min = normalized_min
        self._norm_max = normalized_max

    def process(self, items: list[Content]) -> list[Content]:
        groups: dict[str | None, list[Content]] = {}
        for item in items:
            groups.setdefault(item.category, []).append(item)

        for category, group in groups.items():
            scores = [item.score or 0.0 for item in group]
            lo, hi = min(scores), max(scores)
            span = hi - lo
            for item in group:
                s = item.score or 0.0
                if span > 0:
                    normalized = self._norm_min + (s - lo) / span * (self._norm_max - self._norm_min)
                else:
                    normalized = (self._norm_min + self._norm_max) / 2
                item.score = normalized
                logger.info("pipeline normalize_score [%s] %r: %.3f → %.3f", category, item.id, s, normalized)

        return items
