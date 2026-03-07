import logging

from ..._types import Callback
from ...summarize import Summarize
from ...types.content import Content
from .. import PipelineStage

logger = logging.getLogger(__name__)


class SummarizeStage(PipelineStage):
    """Summarizes each item by delegating to a Summarize implementation."""

    def __init__(self, inner: Summarize) -> None:
        self._inner = inner

    def initialize(self, callback: Callback) -> None:
        self._inner.initialize(callback)

    def process(self, items: list[Content]) -> list[Content]:
        for item in items:
            if item.related_ids:
                logger.info("skipping summarize for merged item %r", item.id)
                continue
            summary: list[str | None] = [item.summary]

            def on_done(
                ok: bool,
                err: str,
                s: Content,
                _item: Content = item,
                _summary: list[str | None] = summary,
            ) -> None:
                if not ok:
                    logger.warning("summarize error for %s: %s", _item.id, err)
                else:
                    _summary[0] = s.summary

            logger.info("summarizing %r", item.id)
            self._inner.summarize(item, on_done)
            item.summary = summary[0]
        return items
