"""Main Coordinator — wires all modules and drives the processing pipeline."""
from __future__ import annotations

import logging
import time

from ._types import Callback
from .config import Config
from .input import Input
from .scoring import Scoring
from .secrets import Secrets
from .state import State
from .summarize import Summarize
from .types.content import Content
from .types.params import ConfigParams, SecretsParams, TriggerParams, UIParams
from .types.values import StateValue
from .ui import UI

logger = logging.getLogger(__name__)

_EFFORT_L1 = 1
_EFFORT_L2 = 2
_TOP_N_DEFAULT = 10
_LAST_RUN_KEY = "last_run_ts"


class Coordinator:
    """
    Initializes all modules in dependency order and runs the pipeline loop:

        wait_trigger
            → read sources
            → score L1 (keyword pass)
            → select top N
            → summarize
            → score L2 (refined pass)
            → show
            → update state
            ↺ (loop)
    """

    def __init__(
        self,
        ui: UI,
        input: Input,
        config: Config,
        state: State,
        scoring: Scoring,
        summarize: Summarize,
        secrets: Secrets,
    ) -> None:
        self._ui = ui
        self._input = input
        self._config = config
        self._state = state
        self._scoring = scoring
        self._summarize = summarize
        self._secrets = secrets
        self._running = False

    # ── Initialization ────────────────────────────────────────────────────────

    def initialize(self, callback: Callback) -> None:
        """Initialize all modules in dependency order: secrets → config → state → scoring → summarize → ui."""
        logger.info("initializing secrets")
        self._secrets.initialize(
            SecretsParams(),
            lambda ok, err: self._init_config(ok, err, callback),
        )

    def _init_config(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"secrets: {err}")
            return
        logger.info("initializing config")
        self._config.load(ConfigParams(), lambda ok2, err2: self._init_state(ok2, err2, callback))

    def _init_state(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"config: {err}")
            return
        logger.info("initializing state")
        self._state.load(ConfigParams(), lambda ok2, err2: self._init_scoring(ok2, err2, callback))

    def _init_scoring(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"state: {err}")
            return
        logger.info("initializing scoring")
        self._scoring.initialize(lambda ok2, err2: self._init_summarize(ok2, err2, callback))

    def _init_summarize(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"scoring: {err}")
            return
        logger.info("initializing summarize")
        self._summarize.initialize(lambda ok2, err2: self._init_ui(ok2, err2, callback))

    def _init_ui(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"summarize: {err}")
            return
        logger.info("initializing ui")
        self._ui.initialize(UIParams(), callback)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Block and drive the trigger → pipeline loop until stop() is called."""
        logger.info("coordinator running, waiting for trigger")
        self._running = True
        while self._running:
            self._ui.wait_trigger(self._on_trigger)

    def stop(self) -> None:
        """Signal the loop to exit and terminate the UI."""
        logger.info("coordinator stopping")
        self._running = False
        self._ui.terminate()

    # ── Trigger ───────────────────────────────────────────────────────────────

    def _on_trigger(self, ok: bool, err: str, params: TriggerParams) -> None:
        if not ok:
            logger.error("trigger: %s", err)
            return
        logger.info("trigger received: mode=%s", params.mode)
        self._state.read_value(
            _LAST_RUN_KEY,
            lambda ok2, err2, val: self._on_last_ts(ok2, err2, val),
        )

    def _on_last_ts(self, ok: bool, err: str, val: StateValue) -> None:
        last_ts: float = float(val.get(_LAST_RUN_KEY, 0.0)) if ok and isinstance(val, dict) else 0.0
        logger.info("reading sources since ts=%.0f", last_ts)
        self._input.read_sources(
            last_ts, "", "",
            lambda ok2, err2, items: self._on_sources_read(ok2, err2, items),
        )

    # ── Step 1: read sources ──────────────────────────────────────────────────

    def _on_sources_read(self, ok: bool, err: str, items: list[Content]) -> None:
        if not ok:
            logger.error("read sources: %s", err)
            return
        if not items:
            logger.info("no new content")
            return
        logger.info("read %d item(s), starting L1 scoring", len(items))
        self._score_l1(items, [])

    # ── Step 2: L1 scoring ────────────────────────────────────────────────────

    def _score_l1(self, remaining: list[Content], scored: list[Content]) -> None:
        if not remaining:
            logger.info("L1 scoring done: %d item(s) scored", len(scored))
            self._select_top_n(scored)
            return
        item, *rest = remaining

        def on_score(ok: bool, err: str, score: float) -> None:
            if ok:
                item.score = score
                logger.info("L1 scored %r: %.3f", item.id, score)
            else:
                logger.warning("l1 score error for %s: %s", item.id, err)
            self._score_l1(rest, scored + [item])

        self._scoring.score(item, _EFFORT_L1, on_score)

    # ── Step 3: select top N ──────────────────────────────────────────────────

    def _select_top_n(self, items: list[Content]) -> None:
        self._config.read_value(
            "scoring",
            lambda ok, err, val: self._on_top_n(ok, err, val, items),
        )

    def _on_top_n(self, ok: bool, err: str, val: StateValue, items: list[Content]) -> None:
        n: int = int(val.get("top_n", _TOP_N_DEFAULT)) if ok and isinstance(val, dict) else _TOP_N_DEFAULT
        top = sorted(items, key=lambda c: c.score or 0.0, reverse=True)[:n]
        logger.info("selected top %d/%d item(s) for summarization", len(top), len(items))
        self._summarize_all(top, [])

    # ── Step 4: summarize ─────────────────────────────────────────────────────

    def _summarize_all(self, remaining: list[Content], done: list[Content]) -> None:
        if not remaining:
            logger.info("summarization done: %d item(s), starting L2 scoring", len(done))
            self._score_l2(done, [])
            return
        item, *rest = remaining
        logger.info("summarizing %r (%d remaining)", item.id, len(remaining))

        def on_summary(ok: bool, err: str, result: Content) -> None:
            if not ok:
                logger.warning("summarize error for %s: %s", item.id, err)
            self._summarize_all(rest, done + [result if ok else item])

        self._summarize.summarize(item, on_summary)

    # ── Step 5: L2 scoring ────────────────────────────────────────────────────

    def _score_l2(self, remaining: list[Content], scored: list[Content]) -> None:
        if not remaining:
            logger.info("L2 scoring done: %d item(s) scored", len(scored))
            self._show(scored)
            return
        item, *rest = remaining

        def on_score(ok: bool, err: str, score: float) -> None:
            if ok:
                item.score = score
                logger.info("L2 scored %r: %.3f", item.id, score)
            else:
                logger.warning("l2 score error for %s: %s", item.id, err)
            self._score_l2(rest, scored + [item])

        self._scoring.score(item, _EFFORT_L2, on_score)

    # ── Step 6: show ──────────────────────────────────────────────────────────

    def _show(self, items: list[Content]) -> None:
        final = sorted(items, key=lambda c: c.score or 0.0, reverse=True)
        logger.info("showing %d item(s) to ui", len(final))
        self._ui.show_content_list(final, self._on_shown)

    def _on_shown(self, ok: bool, err: str) -> None:
        if not ok:
            logger.error("show: %s", err)
            return
        logger.info("pipeline complete, updating last_run_ts")
        self._state.write_value(
            _LAST_RUN_KEY,
            {_LAST_RUN_KEY: time.time()},
            lambda ok2, err2: logger.error("state write: %s", err2) if not ok2 else None,
        )
