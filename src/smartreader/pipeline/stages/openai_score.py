import logging
from typing import Callable

from ..._types import Callback
from ...scoring.openai_scorer import OpenAIScoring
from ...secrets import Secrets
from ...state import State
from ...types.content import Content
from .. import UpdatablePipelineStage

logger = logging.getLogger(__name__)


class OpenAIScoreStage(UpdatablePipelineStage):
    """Adds OpenAI LLM-based score to each item (accumulates into item.score)."""

    def __init__(
        self,
        state: State,
        secrets: Secrets,
        entry: dict,
        max_repeat_count: int = 3,
        on_circuit_trip: Callable[[str], None] | None = None,
    ) -> None:
        self._inner = OpenAIScoring(
            state=state,
            secrets=secrets,
            entry=entry,
            max_repeat_count=max_repeat_count,
            on_circuit_trip=on_circuit_trip,
        )

    def initialize(self, callback: Callback) -> None:
        self._inner.initialize(callback)

    def process(self, items: list[Content]) -> list[Content]:
        self._inner.reset_run()
        for item in items:
            score: list[float] = [0.0]

            def on_score(ok: bool, err: str, s: float = 0.0, _item: Content = item, _s: list[float] = score) -> None:
                if ok:
                    _s[0] = s
                else:
                    logger.warning("openai_score error for %s: %s", _item.id, err)

            self._inner.score(item, 2, on_score)
            item.score = (item.score or 0.0) + score[0]
            logger.info("pipeline openai_score scored %r: %.3f", item.id, item.score)
        return items

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        self._inner.update_score(content, upvote, callback)
