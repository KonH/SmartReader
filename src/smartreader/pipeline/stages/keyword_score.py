import logging

from ..._types import Callback
from ...config import Config
from ...scoring.keyword import L2KeywordScoring
from ...state import State
from ...types.content import Content
from .. import UpdatablePipelineStage

logger = logging.getLogger(__name__)


class KeywordScoreStage(UpdatablePipelineStage):
    """Adds keyword-based score to each item (accumulates into item.score)."""

    def __init__(
        self,
        state: State,
        config: Config,
        shared_common: dict[str, float],
        shared_category: dict[str, dict[str, float]],
        common_weight: float = 1.0,
        category_weight: float = 1.5,
    ) -> None:
        self._inner = L2KeywordScoring(
            state=state,
            config=config,
            common_kw=shared_common,
            category_kw=shared_category,
            common_weight=common_weight,
            category_weight=category_weight,
        )

    def initialize(self, callback: Callback) -> None:
        self._inner.initialize(callback)

    def process(self, items: list[Content]) -> list[Content]:
        for item in items:
            score: list[float] = [0.0]

            def on_score(ok: bool, err: str, s: float = 0.0, _item: Content = item, _s: list[float] = score) -> None:
                if ok:
                    _s[0] = s
                else:
                    logger.warning("keyword_score error for %s: %s", _item.id, err)

            self._inner.score(item, 2, on_score)
            item.score = (item.score or 0.0) + score[0]
            logger.info("pipeline keyword_score scored %r: %.3f", item.id, item.score)
        return items

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        self._inner.update_score(content, upvote, callback)
