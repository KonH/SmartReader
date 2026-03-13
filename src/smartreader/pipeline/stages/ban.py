import logging
import re

from ..._types import Callback
from ...config import Config
from ...types.content import Content
from .. import PipelineStage

logger = logging.getLogger(__name__)


class BanStage(PipelineStage):
    """Drops any content whose title or body contains a banned word."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._ban: list[str] = []

    def initialize(self, callback: Callback) -> None:
        def on_scoring(ok: bool, err: str, val: object) -> None:
            if ok and isinstance(val, dict):
                self._ban = [w.lower() for w in val.get("ban", [])]
            callback(True, "")

        self._config.read_value("scoring", on_scoring)

    def process(self, items: list[Content]) -> list[Content]:
        if not self._ban:
            return items
        result = [c for c in items if not self._is_banned(c)]
        dropped = len(items) - len(result)
        if dropped:
            logger.info("pipeline ban: %d/%d item(s) dropped", dropped, len(items))
        return result

    def _is_banned(self, content: Content) -> bool:
        text = f"{content.title} {content.body}".lower()
        return any(_word_in_text(word, text) for word in self._ban)


def _word_in_text(word: str, text: str) -> bool:
    """Return True if *word* appears as a whole word (Unicode-aware) in *text*."""
    pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"
    return bool(re.search(pattern, text, re.IGNORECASE | re.UNICODE))
