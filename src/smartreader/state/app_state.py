from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .._types import AppStateCallback, Callback
from ..types.app_state import AppStateData, SourceStateEntry
from ..types.content import Content

if TYPE_CHECKING:
    from . import State
    from ..config import Config
    from ..input import Input
    from ..pipeline.adapter import PipelineAdapter

logger = logging.getLogger(__name__)


class AppState:
    """Typed wrapper on top of the raw State key-value store.

    Also holds module references and runtime (non-persisted) fields so that
    command objects can access everything they need through a single object.
    """

    def __init__(
        self,
        state: "State",
        config: "Config | None" = None,
        pipeline: "PipelineAdapter | None" = None,
        input: "Input | None" = None,
    ) -> None:
        self._state = state
        self.config = config
        self.pipeline = pipeline
        self.input = input
        # Runtime (non-persisted) fields populated during pipeline execution
        self.categories: list[str] = []
        self.active_source_ids: list[str] = []
        self.successful_source_ids: list[str] = []
        self.shown_items: list[Content] = []
        self.trigger_category: str | None = None
        self.initial_days_interval: int = 7

    def read_all_typed(self, callback: AppStateCallback) -> None:
        self._state.read_all(
            lambda ok, err, raw: self._on_raw_state(ok, err, raw, callback)
        )

    def _on_raw_state(
        self,
        ok: bool,
        err: str,
        raw: dict,
        callback: AppStateCallback,
    ) -> None:
        if not ok:
            callback(False, err, AppStateData([], {}, {}))
            return

        # Parse source states
        source_ids_raw = raw.get("sourceStates", {})
        if isinstance(source_ids_raw, dict):
            source_ids: list[str] = source_ids_raw.get("ids", [])
        elif isinstance(source_ids_raw, list):
            source_ids = source_ids_raw
        else:
            source_ids = []

        source_states: list[SourceStateEntry] = []
        for sid in sorted(source_ids):
            entry_raw = raw.get(f"source_{sid}", {})
            if isinstance(entry_raw, dict):
                active = bool(entry_raw.get("active", True))
                last_ts = entry_raw.get("lastReadTs")
                last_read_ts: float | None = float(last_ts) if last_ts else None
            else:
                active = True
                last_read_ts = None
            source_states.append(SourceStateEntry(
                source_id=sid,
                active=active,
                last_read_ts=last_read_ts,
            ))

        # Parse common_keyword_interests
        common_raw = raw.get("common_keyword_interests", {})
        common_interests: dict[str, float] = {}
        if isinstance(common_raw, dict):
            common_interests = dict(
                sorted(common_raw.items(), key=lambda x: x[1], reverse=True)
            )

        # Parse category_interests
        cat_raw = raw.get("category_interests", {})
        category_interests: dict[str, dict[str, float]] = {}
        if isinstance(cat_raw, dict):
            for cat, keywords in sorted(cat_raw.items()):
                if isinstance(keywords, dict):
                    category_interests[cat] = dict(
                        sorted(keywords.items(), key=lambda x: x[1], reverse=True)
                    )

        callback(True, "", AppStateData(
            source_states=source_states,
            common_interests=common_interests,
            category_interests=category_interests,
        ))

    def remove_keyword(self, word: str, callback: Callback) -> None:
        self._state.read_value(
            "common_keyword_interests",
            lambda ok, err, val: self._on_common_for_remove(ok, err, val, word, callback),
        )

    def _on_common_for_remove(
        self, ok: bool, err: str, val: dict, word: str, callback: Callback
    ) -> None:
        common: dict = val if ok and isinstance(val, dict) else {}
        common.pop(word, None)
        self._state.write_value(
            "common_keyword_interests",
            common,
            lambda ok2, err2: self._on_common_written(ok2, err2, word, callback),
        )

    def _on_common_written(
        self, ok: bool, err: str, word: str, callback: Callback
    ) -> None:
        if not ok:
            logger.error("remove_keyword: write common error: %s", err)
        self._state.read_value(
            "category_interests",
            lambda ok2, err2, val: self._on_category_for_remove(ok2, err2, val, word, callback),
        )

    def _on_category_for_remove(
        self, ok: bool, err: str, val: dict, word: str, callback: Callback
    ) -> None:
        cats: dict = val if ok and isinstance(val, dict) else {}
        for cat_keywords in cats.values():
            if isinstance(cat_keywords, dict):
                cat_keywords.pop(word, None)
        self._state.write_value(
            "category_interests",
            cats,
            callback,
        )
