import logging

from .._types import Callback, ScoreCallback
from ..config import Config
from ..state import State
from ..types.content import Content
from . import Scoring
from .keyword import L1KeywordScoring, L2KeywordScoring
from .noise import NoiseScoring

logger = logging.getLogger(__name__)


class ScoringAdapter(Scoring):
    """
    Builds L1 and L2 scorer lists from config and delegates scoring accordingly.

    Config format (under [scoring]):
        [[scoring.l1]]
        type = "keyword"
        common_weight = 1.0
        category_weight = 1.5

        [[scoring.l2]]
        type = "keyword"
        common_weight = 1.0
        category_weight = 1.5

        [[scoring.l1]]   # optional noise entry
        type = "noise"
        noise_factor = 0.5
    """

    def __init__(
        self,
        config: Config,
        state: State,
        shared_common: dict[str, float],
        shared_category: dict[str, dict[str, float]],
    ) -> None:
        self._config = config
        self._state = state
        self._shared_common = shared_common
        self._shared_category = shared_category
        self._l1: list[Scoring] = []
        self._l2: list[Scoring] = []

    def initialize(self, callback: Callback) -> None:
        self._config.read_value(
            "scoring",
            lambda ok, err, val: self._on_config(ok, err, val, callback),
        )

    def _on_config(self, ok: bool, err: str, val: dict, callback: Callback) -> None:
        cfg = val if isinstance(val, dict) else {}
        self._l1 = self._build_scorers(cfg.get("l1", []), "l1")
        self._l2 = self._build_scorers(cfg.get("l2", []), "l2")
        all_scorers = self._l1 + self._l2
        self._init_scorers(all_scorers, 0, callback)

    def _build_scorers(self, entries: list, stage: str) -> list[Scoring]:
        scorers: list[Scoring] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            t = entry.get("type", "")
            if t == "keyword":
                common_weight = float(entry.get("common_weight", 1.0))
                category_weight = float(entry.get("category_weight", 1.5))
                cls = L1KeywordScoring if stage == "l1" else L2KeywordScoring
                scorers.append(cls(
                    self._state, self._config,
                    self._shared_common, self._shared_category,
                    common_weight, category_weight,
                ))
            elif t == "noise":
                noise_factor = float(entry.get("noise_factor", 1.0))
                scorers.append(NoiseScoring(noise_factor))
            else:
                logger.warning("unknown scorer type %r in %s, skipping", t, stage)
        return scorers

    def _init_scorers(self, scorers: list[Scoring], idx: int, callback: Callback) -> None:
        if idx >= len(scorers):
            callback(True, "")
            return
        scorers[idx].initialize(
            lambda ok, err, _i=idx, _s=scorers: (
                self._init_scorers(_s, _i + 1, callback) if ok else callback(False, err)
            )
        )

    def score(self, content: Content, effort_level: int, callback: ScoreCallback) -> None:
        scorers = self._l2 if effort_level >= 2 else self._l1
        stage = "L2" if effort_level >= 2 else "L1"

        def _chain(idx: int, total: float) -> None:
            if idx >= len(scorers):
                callback(True, "", total)
                return

            scorer = scorers[idx]
            label = _scorer_label(scorer)

            def on_score(ok: bool, err: str, s: float = 0.0) -> None:
                if not ok:
                    logger.warning("%s (%s) score error for %s: %s", stage, label, content.id, err)
                else:
                    logger.info("%s (%s) scored %r: %.3f", stage, label, content.id, s)
                _chain(idx + 1, total + (s if ok else 0.0))

            scorer.score(content, effort_level, on_score)

        if not scorers:
            callback(True, "", 0.0)
            return
        _chain(0, 0.0)

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        all_scorers = self._l1 + self._l2

        def _chain(idx: int) -> None:
            if idx >= len(all_scorers):
                callback(True, "")
                return

            def on_done(ok: bool, err: str) -> None:
                if not ok:
                    logger.warning("scorer %d update_score error: %s", idx, err)
                _chain(idx + 1)

            all_scorers[idx].update_score(content, upvote, on_done)

        if not all_scorers:
            callback(True, "")
            return
        _chain(0)


def _scorer_label(scorer: Scoring) -> str:
    if isinstance(scorer, (L1KeywordScoring, L2KeywordScoring)):
        return "keyword"
    if isinstance(scorer, NoiseScoring):
        return "noise"
    return type(scorer).__name__
