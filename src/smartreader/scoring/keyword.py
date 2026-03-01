import logging
import re
from abc import abstractmethod

from .._types import Callback, ScoreCallback
from ..config import Config
from ..state import State
from ..types.content import Content
from . import Scoring

logger = logging.getLogger(__name__)

_DEFAULT_UPVOTE_POWER = 1.5
_DEFAULT_DOWNVOTE_POWER = -1.0


def _tokenize(text: str, skip: set[str]) -> list[str]:
    """Lower-case alphabetic tokens, 2+ chars, not in skip set."""
    return [w for w in re.findall(r'[a-z]{2,}', text.lower()) if w not in skip]


class BaseKeywordScoring(Scoring):
    """
    Abstract base for keyword-based scoring.

    Subclasses implement _get_text() to select which content fields to use.
    Accepts optional shared common_kw / category_kw dicts so multiple
    instances (L1, L2) can stay in sync through the same objects.
    """

    def __init__(
        self,
        state: State,
        config: Config,
        common_kw: dict[str, float] | None = None,
        category_kw: dict[str, dict[str, float]] | None = None,
        common_weight: float = 1.0,
        category_weight: float = 1.5,
    ) -> None:
        self._state = state
        self._config = config
        self._common_kw: dict[str, float] = common_kw if common_kw is not None else {}
        self._category_kw: dict[str, dict[str, float]] = category_kw if category_kw is not None else {}
        self._common_weight = common_weight
        self._category_weight = category_weight
        self._upvote_power = _DEFAULT_UPVOTE_POWER
        self._downvote_power = _DEFAULT_DOWNVOTE_POWER
        self._skip: set[str] = set()

    @abstractmethod
    def _get_text(self, content: Content) -> str: ...

    # ── Initialization ────────────────────────────────────────────────────────

    def initialize(self, callback: Callback) -> None:
        self._config.read_value(
            "scoring",
            lambda ok, err, val: self._on_config(ok, err, val, callback),
        )

    def _on_config(self, ok: bool, err: str, val: dict, callback: Callback) -> None:
        if ok and isinstance(val, dict):
            self._upvote_power = float(val.get("upvote_power", _DEFAULT_UPVOTE_POWER))
            self._downvote_power = float(val.get("downvote_power", _DEFAULT_DOWNVOTE_POWER))
            self._skip = set(val.get("skip", []))
            logger.info(
                "keyword scoring weights: common=%.2f category=%.2f "
                "upvote=%.2f downvote=%.2f skip=%d word(s)",
                self._common_weight, self._category_weight,
                self._upvote_power, self._downvote_power, len(self._skip),
            )
        self._state.read_value(
            "common_keyword_interests",
            lambda ok2, err2, val2: self._on_common_kw(ok2, err2, val2, callback),
        )

    def _on_common_kw(self, ok: bool, err: str, val: dict, callback: Callback) -> None:
        if ok and isinstance(val, dict):
            self._common_kw.update(val)
            logger.info("loaded %d common keyword interest(s)", len(self._common_kw))
        self._state.read_value(
            "category_interests",
            lambda ok2, err2, val2: self._on_category_kw(ok2, err2, val2, callback),
        )

    def _on_category_kw(self, ok: bool, err: str, val: dict, callback: Callback) -> None:
        if ok and isinstance(val, dict):
            self._category_kw.update(val)
            logger.info("loaded %d category interest(s)", len(self._category_kw))
        callback(True, "")

    # ── Scoring ───────────────────────────────────────────────────────────────

    def score(self, content: Content, effort_level: int, callback: ScoreCallback) -> None:
        try:
            text = self._get_text(content)
            tokens = set(_tokenize(text, self._skip))

            common_score = sum(
                weight * self._common_weight
                for kw, weight in self._common_kw.items()
                if kw.lower() in tokens
            )

            category_score = 0.0
            if content.category:
                cat_kw = self._category_kw.get(content.category, {})
                category_score = sum(
                    weight * self._category_weight
                    for kw, weight in cat_kw.items()
                    if kw.lower() in tokens
                )

            callback(True, "", common_score + category_score)
        except Exception as e:
            logger.error(f"Error scoring content: {e}")
            callback(False, str(e))

    # ── Interest update ───────────────────────────────────────────────────────

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        delta = self._upvote_power if upvote else self._downvote_power
        words = _tokenize(self._get_text(content), self._skip)
        for word in words:
            self._common_kw[word] = self._common_kw.get(word, 0.0) + delta
        if content.category:
            cat = self._category_kw.setdefault(content.category, {})
            for word in words:
                cat[word] = cat.get(word, 0.0) + delta
        logger.info(
            "interest update (%s): %d word(s), category=%s",
            "upvote" if upvote else "downvote", len(words), content.category,
        )
        self._state.write_value(
            "common_keyword_interests",
            self._common_kw,
            lambda ok, err: self._write_category_interests(ok, err, callback),
        )

    def _write_category_interests(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"write common_keyword_interests: {err}")
            return
        self._state.write_value("category_interests", self._category_kw, callback)


class L1KeywordScoring(BaseKeywordScoring):
    """L1 (fast pass): scores title + body."""

    def _get_text(self, content: Content) -> str:
        return f"{content.title} {content.body}"


class L2KeywordScoring(BaseKeywordScoring):
    """L2 (refined pass): scores title + summary, falls back to body."""

    def _get_text(self, content: Content) -> str:
        return f"{content.title} {content.summary or content.body}"
