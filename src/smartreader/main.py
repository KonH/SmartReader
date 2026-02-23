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
from .ui import UI

logger = logging.getLogger(__name__)

_EFFORT_L1 = 1
_EFFORT_L2 = 2
_TOP_N_DEFAULT = 10


class Coordinator:
    """
    Initializes all modules in dependency order and runs the pipeline loop:

        wait_trigger
            → read per-source states
            → read sources (per-source, using lastReadTs)
            → score L1 (keyword pass)
            → select top N
            → summarize
            → score L2 (refined pass)
            → show + collect feedback
            → update per-source state
            → process feedback (update interests)
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
        self._active_source_ids: list[str] = []
        self._shown_items: list[Content] = []
        self._trigger_category: str | None = None
        self._initial_days_interval: int = 7

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
            self._config.read_value("sources", self._on_sources_for_wait)

    def stop(self) -> None:
        """Signal the loop to exit and terminate the UI."""
        logger.info("coordinator stopping")
        self._running = False
        self._ui.terminate()

    # ── Trigger → per-source reads ────────────────────────────────────────────

    def _on_sources_for_wait(self, ok: bool, err: str, val: dict) -> None:
        categories = _extract_categories(val) if ok and isinstance(val, dict) else []
        self._ui.wait_trigger(categories, self._on_trigger)

    def _on_trigger(self, ok: bool, err: str, params: TriggerParams) -> None:
        if not ok:
            logger.error("trigger: %s", err)
            return
        self._trigger_category = params.category
        logger.info("trigger received: mode=%s category=%s", params.mode, params.category)
        self._config.read_value(
            "common",
            lambda ok2, err2, val: self._on_common_config(ok2, err2, val),
        )

    def _on_common_config(self, ok: bool, err: str, val: dict) -> None:
        if ok and isinstance(val, dict):
            self._initial_days_interval = int(val.get("initial_days_scan_interval", 7))
        self._config.read_value(
            "sources",
            lambda ok2, err2, val: self._on_sources_config(ok2, err2, val),
        )

    def _on_sources_config(self, ok: bool, err: str, val: dict) -> None:
        if not ok or not isinstance(val, dict):
            logger.info("no sources configured")
            return
        source_ids = _filter_by_category(val, self._trigger_category)
        if not source_ids:
            logger.info("no sources match category=%s", self._trigger_category)
            return
        self._active_source_ids = source_ids
        self._collect_source_states(source_ids, {})

    def _collect_source_states(self, remaining: list[str], states: dict[str, float]) -> None:
        """Read source_<id> state for each source to get its lastReadTs."""
        if not remaining:
            self._gather_source_content(
                [(sid, ts) for sid, ts in states.items()], []
            )
            return
        sid, *rest = remaining
        self._state.read_value(
            f"source_{sid}",
            lambda ok, err, val: self._on_source_state(ok, err, val, sid, rest, states),
        )

    def _on_source_state(
        self, ok: bool, err: str, val: dict, sid: str,
        remaining: list[str], states: dict[str, float],
    ) -> None:
        raw_ts = float(val.get("lastReadTs", 0.0)) if ok and isinstance(val, dict) else 0.0
        if raw_ts == 0.0:
            last_ts = time.time() - self._initial_days_interval * 86400
            logger.info("source %r: first run, scanning last %d day(s)", sid, self._initial_days_interval)
        else:
            last_ts = raw_ts
        self._collect_source_states(remaining, {**states, sid: last_ts})

    # ── Step 1: read sources ──────────────────────────────────────────────────

    def _gather_source_content(
        self, remaining: list[tuple[str, float]], all_items: list[Content]
    ) -> None:
        """Call read_sources per source with its specific lastReadTs; combine results."""
        if not remaining:
            self._on_sources_read(True, "", all_items)
            return
        (sid, last_ts), *rest = remaining
        logger.info("reading source %r since ts=%.0f", sid, last_ts)
        self._input.read_sources(
            last_ts, "", sid,
            lambda ok, err, items: self._on_one_source(ok, err, items, sid, rest, all_items),
        )

    def _on_one_source(
        self, ok: bool, err: str, items: list[Content],
        sid: str, remaining: list[tuple[str, float]], all_items: list[Content],
    ) -> None:
        if not ok:
            logger.warning("source %r read failed: %s", sid, err)
        self._gather_source_content(remaining, all_items + (items if ok else []))

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

    def _on_top_n(self, ok: bool, err: str, val: dict, items: list[Content]) -> None:
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

    # ── Step 6: show + collect feedback ───────────────────────────────────────

    def _show(self, items: list[Content]) -> None:
        final = sorted(items, key=lambda c: c.published_ts)
        self._shown_items = final
        logger.info("showing %d item(s) to ui", len(final))
        self._ui.show_content_list(final, self._on_shown)

    def _on_shown(self, ok: bool, err: str, feedback: list[tuple[str, bool]]) -> None:
        if not ok:
            logger.error("show: %s", err)
            return
        logger.info("pipeline complete, updating per-source state")
        now = time.time()
        self._update_source_states(list(self._active_source_ids), now)
        if feedback:
            logger.info("processing %d feedback item(s)", len(feedback))
            self._process_feedback(feedback, self._shown_items, 0)

    # ── Step 7: update per-source state ───────────────────────────────────────

    def _update_source_states(self, remaining: list[str], now: float) -> None:
        if not remaining:
            self._state.write_value(
                "sourceStates",
                {"ids": self._active_source_ids},
                lambda ok, err: logger.error("state write sourceStates: %s", err) if not ok else None,
            )
            return
        sid, *rest = remaining
        self._state.write_value(
            f"source_{sid}",
            {"active": True, "lastReadTs": now},
            lambda ok, err: self._update_source_states(rest, now),
        )

    # ── Step 8: process feedback ──────────────────────────────────────────────

    def _process_feedback(
        self, feedback: list[tuple[str, bool]], items: list[Content], idx: int
    ) -> None:
        if idx >= len(feedback):
            logger.info("feedback processing done")
            return
        item_id, upvote = feedback[idx]
        content = next((c for c in items if c.id == item_id), None)
        if content is None:
            logger.warning("feedback for unknown item id: %s", item_id)
            self._process_feedback(feedback, items, idx + 1)
            return
        logger.info("updating interests for %r: upvote=%s", item_id, upvote)

        def on_updated(ok: bool, err: str) -> None:
            if not ok:
                logger.error("update_score error for %s: %s", item_id, err)
            self._process_feedback(feedback, items, idx + 1)

        self._scoring.update_score(content, upvote, on_updated)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_categories(sources_val: dict) -> list[str]:
    """Return sorted list of unique non-empty categories from sources config."""
    cats: set[str] = set()
    for entries in sources_val.values():
        for entry in (entries if isinstance(entries, list) else [entries]):
            cat = entry.get("category") if isinstance(entry, dict) else None
            if cat:
                cats.add(cat)
    return sorted(cats)


def _filter_by_category(sources_val: dict, category: str | None) -> list[str]:
    """Return source IDs that have at least one entry matching category (None = ALL)."""
    if category is None:
        return list(sources_val.keys())
    result: list[str] = []
    for sid, entries in sources_val.items():
        for entry in (entries if isinstance(entries, list) else [entries]):
            if isinstance(entry, dict) and entry.get("category") == category:
                result.append(sid)
                break
    return result
