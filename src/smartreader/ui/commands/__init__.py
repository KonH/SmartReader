"""Abstract command classes — WHAT-logic only, no execute().

Each class encapsulates the pipeline / state logic for one command,
leaving the HOW (terminal prompts vs Telegram messages) to concrete subclasses.
"""
from __future__ import annotations

import logging
import sys
import time
from abc import ABC
from typing import TYPE_CHECKING

from ..command import SharedUIState, UICommand
from ...types.app_state import AppStateData
from ...types.content import Content
from ...types.params import NewSourceParams

if TYPE_CHECKING:
    from ...state.app_state import AppState

logger = logging.getLogger(__name__)

_EFFORT_L1 = 1
_EFFORT_L2 = 2
_TOP_N_L1_DEFAULT = 10
_TOP_N_L2_DEFAULT = 5


# ── ShowContentCommand ─────────────────────────────────────────────────────────

class ShowContentCommand(UICommand, ABC):
    """Full read → L1 → summarize → L2 → show pipeline."""

    def __init__(self, app_state: "AppState", shared_ui_state: SharedUIState) -> None:
        self._app_state = app_state
        self._shared = shared_ui_state

    # ── Pipeline helpers ───────────────────────────────────────────────────────

    def _run_pipeline(self, category: str | None) -> list[Content]:
        """Execute the read→score→summarize pipeline and return items to show."""
        assert self._app_state.config is not None
        assert self._app_state.input is not None
        assert self._app_state.scoring is not None
        assert self._app_state.summarize is not None

        # Read common config
        initial_days: list[int] = [7]

        def on_common(ok: bool, err: str, val: object) -> None:
            if ok and isinstance(val, dict):
                initial_days[0] = int(val.get("initial_days_scan_interval", 7))

        self._app_state.config.read_value("common", on_common)
        self._app_state.initial_days_interval = initial_days[0]

        # Read sources config
        sources_val: list[dict] = [{}]

        def on_sources_cfg(ok: bool, err: str, val: object) -> None:
            if ok and isinstance(val, dict):
                sources_val[0] = val

        self._app_state.config.read_value("sources", on_sources_cfg)
        sources = sources_val[0]

        if not sources:
            logger.info("no sources configured")
            return []

        source_ids = _filter_by_category(sources, category)
        if not source_ids:
            logger.info("no sources match category=%s", category)
            return []

        self._app_state.active_source_ids = source_ids
        self._app_state.successful_source_ids = []

        # Collect per-source lastReadTs from state
        assert self._app_state._state is not None
        source_ts: dict[str, float] = {}
        for sid in source_ids:
            state_val: list[object] = [{}]

            def on_state(ok: bool, err: str, val: object, _sid: str = sid) -> None:
                state_val[0] = val if ok and isinstance(val, dict) else {}

            self._app_state._state.read_value(f"source_{sid}", on_state)
            raw_ts = float(state_val[0].get("lastReadTs", 0.0)) if isinstance(state_val[0], dict) else 0.0  # type: ignore[union-attr]
            if raw_ts == 0.0:
                source_ts[sid] = time.time() - self._app_state.initial_days_interval * 86400
                logger.info("source %r: first run, scanning last %d day(s)", sid, self._app_state.initial_days_interval)
            else:
                source_ts[sid] = raw_ts

        # Read sources
        all_items: list[Content] = []
        for sid, last_ts in source_ts.items():
            logger.info("reading source %r since ts=%.0f", sid, last_ts)
            items_result: list[list[Content]] = [[]]

            def on_read(ok: bool, err: str, items: list[Content], _sid: str = sid, _r: list[list[Content]] = items_result) -> None:
                if ok:
                    self._app_state.successful_source_ids.append(_sid)
                    _r[0] = items
                else:
                    logger.warning("source %r read failed: %s", _sid, err)

            self._app_state.input.read_sources(last_ts, "", sid, on_read)
            all_items.extend(items_result[0])

        if not all_items:
            logger.info("no new content")
            return []

        # L1 scoring
        logger.info("read %d item(s), starting L1 scoring", len(all_items))
        for item in all_items:
            def on_l1(ok: bool, err: str, score: float, _item: Content = item) -> None:
                if ok:
                    _item.score = score
                    logger.info("L1 scored %r: %.3f", _item.id, score)
                else:
                    logger.warning("l1 score error for %s: %s", _item.id, err)
            self._app_state.scoring.score(item, _EFFORT_L1, on_l1)

        # Select top N L1
        top_n_l1_val: list[int] = [_TOP_N_L1_DEFAULT]

        def on_scoring_cfg_l1(ok: bool, err: str, val: object) -> None:
            if ok and isinstance(val, dict):
                top_n_l1_val[0] = int(val.get("top_n_l1", _TOP_N_L1_DEFAULT))

        self._app_state.config.read_value("scoring", on_scoring_cfg_l1)
        top_l1 = sorted(all_items, key=lambda c: c.score or 0.0, reverse=True)[:top_n_l1_val[0]]
        logger.info("selected top %d/%d item(s) for summarization", len(top_l1), len(all_items))

        # Summarize
        summarized: list[Content] = []
        for item in top_l1:
            result: list[Content] = []

            def on_summary(ok: bool, err: str, s: Content, _r: list[Content] = result, _item: Content = item) -> None:
                if not ok:
                    logger.warning("summarize error for %s: %s", _item.id, err)
                _r.append(s if ok else _item)

            logger.info("summarizing %r", item.id)
            self._app_state.summarize.summarize(item, on_summary)
            summarized.append(result[0] if result else item)

        logger.info("summarization done: %d item(s)", len(summarized))

        # L2 scoring
        for item in summarized:
            def on_l2(ok: bool, err: str, score: float, _item: Content = item) -> None:
                if ok:
                    _item.score = score
                    logger.info("L2 scored %r: %.3f", _item.id, score)
                else:
                    logger.warning("l2 score error for %s: %s", _item.id, err)
            self._app_state.scoring.score(item, _EFFORT_L2, on_l2)

        # Select top N L2
        top_n_l2_val: list[int] = [_TOP_N_L2_DEFAULT]

        def on_scoring_cfg_l2(ok: bool, err: str, val: object) -> None:
            if ok and isinstance(val, dict):
                top_n_l2_val[0] = int(val.get("top_n_l2", _TOP_N_L2_DEFAULT))

        self._app_state.config.read_value("scoring", on_scoring_cfg_l2)
        top_l2 = sorted(summarized, key=lambda c: c.score or 0.0, reverse=True)[:top_n_l2_val[0]]
        logger.info("selected top %d/%d item(s) for display", len(top_l2), len(summarized))

        final = sorted(top_l2, key=lambda c: c.published_ts)
        self._app_state.shown_items = final
        return final

    def _update_source_states(self) -> None:
        """Write lastReadTs for all successfully-read sources."""
        assert self._app_state._state is not None
        now = time.time()
        for sid in self._app_state.successful_source_ids:
            self._app_state._state.write_value(
                f"source_{sid}",
                {"active": True, "lastReadTs": now},
                lambda ok, err: logger.error("state write error: %s", err) if not ok else None,
            )
        self._app_state._state.write_value(
            "sourceStates",
            {"ids": self._app_state.active_source_ids},
            lambda ok, err: logger.error("state write sourceStates: %s", err) if not ok else None,
        )

    def _process_feedback(self, feedback: list[tuple[str, bool]]) -> None:
        """Update interest scores based on user feedback."""
        assert self._app_state.scoring is not None
        if not feedback:
            return
        logger.info("processing %d feedback item(s)", len(feedback))
        for item_id, upvote in feedback:
            content = next((c for c in self._app_state.shown_items if c.id == item_id), None)
            if content is None:
                logger.warning("feedback for unknown item id: %s", item_id)
                continue
            logger.info("updating interests for %r: upvote=%s", item_id, upvote)
            self._app_state.scoring.update_score(
                content, upvote,
                lambda ok, err, _id=item_id: (
                    logger.error("update_score error for %s: %s", _id, err) if not ok else None
                ),
            )


# ── AddSourceCommand ───────────────────────────────────────────────────────────

class AddSourceCommand(UICommand, ABC):
    """Prompt for new source params, write to config, and restart."""

    def __init__(self, app_state: "AppState", shared_ui_state: SharedUIState) -> None:
        self._app_state = app_state
        self._shared = shared_ui_state

    def _write_source_and_restart(self, params: NewSourceParams) -> None:
        """Append source entry to config and call sys.exit(0)."""
        assert self._app_state.config is not None
        sources_val: list[object] = [{}]

        def on_sources(ok: bool, err: str, val: object) -> None:
            sources_val[0] = val if ok and isinstance(val, dict) else {}

        self._app_state.config.read_value("sources", on_sources)
        data: dict = sources_val[0] if isinstance(sources_val[0], dict) else {}  # type: ignore[assignment]
        entry: dict = {"type": params.source_type, "externalId": params.external_id}
        if params.category:
            entry["category"] = params.category
        data.setdefault(params.name, []).append(entry)

        self._app_state.config.write_value(
            "sources", data,
            lambda ok, err: logger.error("add_source: write_value error: %s", err) if not ok else None,
        )
        self._app_state.config.save(
            lambda ok, err: logger.error("add_source: config save error: %s", err) if not ok else None,
        )
        logger.info("config saved with new source, restarting")
        sys.exit(0)


# ── ShowLogsCommand ────────────────────────────────────────────────────────────

class ShowLogsCommand(UICommand, ABC):
    """Read the last N log lines."""

    def __init__(self, app_state: "AppState", shared_ui_state: SharedUIState) -> None:
        self._app_state = app_state
        self._shared = shared_ui_state

    def _read_log_lines(self, n: int = 100) -> list[str]:
        from ..._logging import get_log_file
        log_path = get_log_file()
        if log_path and log_path.exists():
            with open(log_path) as f:
                all_lines = f.readlines()
            return [ln.rstrip("\n") for ln in all_lines[-n:]]
        return ["No log file found."]


# ── ShowStateCommand ───────────────────────────────────────────────────────────

class ShowStateCommand(UICommand, ABC):
    """Read the typed AppStateData."""

    def __init__(self, app_state: "AppState", shared_ui_state: SharedUIState) -> None:
        self._app_state = app_state
        self._shared = shared_ui_state

    def _read_state_data(self) -> AppStateData:
        result: list[AppStateData] = [AppStateData([], {}, {})]

        def on_data(ok: bool, err: str, data: AppStateData) -> None:
            result[0] = data if ok else AppStateData([], {}, {})

        self._app_state.read_all_typed(on_data)
        return result[0]


# ── SkipWordCommand ────────────────────────────────────────────────────────────

class SkipWordCommand(UICommand, ABC):
    """Add word to scoring.skip config, remove from state interests, restart."""

    def __init__(self, app_state: "AppState", shared_ui_state: SharedUIState) -> None:
        self._app_state = app_state
        self._shared = shared_ui_state

    def _add_skip_and_restart(self, word: str) -> None:
        assert self._app_state.config is not None
        scoring_val: list[object] = [{}]

        def on_scoring(ok: bool, err: str, val: object) -> None:
            scoring_val[0] = val if ok and isinstance(val, dict) else {}

        self._app_state.config.read_value("scoring", on_scoring)
        scoring: dict = scoring_val[0] if isinstance(scoring_val[0], dict) else {}  # type: ignore[assignment]
        skip_list: list = list(scoring.get("skip", []))
        if word not in skip_list:
            skip_list.append(word)
        scoring["skip"] = skip_list

        def on_written(ok: bool, err: str) -> None:
            if not ok:
                logger.error("skip: write_value error: %s", err)
            self._app_state.remove_keyword(
                word,
                lambda ok2, err2: self._save_and_restart(ok2, err2),
            )

        self._app_state.config.write_value("scoring", scoring, on_written)

    def _save_and_restart(self, ok: bool, err: str) -> None:
        if not ok:
            logger.error("skip: state write error: %s", err)
        assert self._app_state.config is not None
        self._app_state.config.save(
            lambda ok2, err2: logger.error("skip: config save error: %s", err2) if not ok2 else None
        )
        logger.info("skip word added, restarting")
        sys.exit(0)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _filter_by_category(sources_val: dict, category: str | None) -> list[str]:
    if category is None:
        return list(sources_val.keys())
    result: list[str] = []
    for sid, entries in sources_val.items():
        for entry in (entries if isinstance(entries, list) else [entries]):
            if isinstance(entry, dict) and entry.get("category") == category:
                result.append(sid)
                break
    return result
