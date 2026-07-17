from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from typing import Callable

import openai

from ..._types import Callback
from ...llm.client import LLMClient
from ...secrets import Secrets
from ...types.content import Content
from .. import PipelineStage

logger = logging.getLogger(__name__)

_DEFAULT_MERGE_PROMPT = """\
You are a news event summarizer. Given related articles, write:
Line 1: Short event headline (one sentence).
Remaining lines: 2-3 sentence summary of the event.
Reply with ONLY the headline and summary."""

_CLUSTER_PROMPT = """\
Group these articles by the news event they cover.
Return a JSON array of groups, e.g. [[0,2],[1,4]].
Include only groups with 2 or more articles. Omit ungrouped articles.
Reply ONLY with the JSON array."""


class MergeContentStage(PipelineStage):
    def __init__(
        self,
        secrets: Secrets,
        entry: dict,
        global_merge_prompt: str = "",
        global_cluster_prompt: str = "",
        max_repeat_count: int = 3,
        on_circuit_trip: Callable[[str], None] | None = None,
    ) -> None:
        self._secrets = secrets
        self._model: str = entry.get("model", "gpt-4o-mini")
        self._merge_prompt: str = entry.get("prompt", "") or global_merge_prompt or _DEFAULT_MERGE_PROMPT
        self._cluster_prompt: str = entry.get("cluster_prompt", "") or global_cluster_prompt or _CLUSTER_PROMPT
        self._max_repeat_count = max_repeat_count
        self._on_circuit_trip = on_circuit_trip
        self._llm: LLMClient | None = None

    def initialize(self, callback: Callback) -> None:
        def on_key(ok: bool, err: str, key: str = "") -> None:
            if not ok:
                callback(False, f"MergeContentStage: OPENAI_API_KEY not available: {err}")
                return
            self._llm = LLMClient(
                client=openai.OpenAI(api_key=key),
                name="openai_merge",
                max_repeat_count=self._max_repeat_count,
                on_circuit_trip=self._on_circuit_trip,
            )
            callback(True, "")

        self._secrets.read_value("OPENAI_API_KEY", on_key)

    def process(self, items: list[Content]) -> list[Content]:
        if len(items) < 2:
            return items

        assert self._llm is not None
        self._llm.reset_run()

        clusters = self._cluster_articles(items)
        if not clusters:
            return items

        clustered_indices: set[int] = set()
        for group in clusters:
            for idx in group:
                clustered_indices.add(idx)

        merged_items: list[Content] = []
        for group in clusters:
            cluster_items = [items[i] for i in group]
            merged = self._merge_cluster(cluster_items)
            if merged is not None:
                merged_items.append(merged)

        singles = [item for i, item in enumerate(items) if i not in clustered_indices]
        return merged_items + singles

    def _cluster_articles(self, items: list[Content]) -> list[list[int]]:
        titles_text = "\n".join(
            f"{i}. {item.title}" for i, item in enumerate(items)
        )
        result: list[list[int]] = []

        assert self._llm is not None

        def on_resp(ok: bool, err: str, text: str) -> None:
            if not ok:
                logger.warning("MergeContentStage: clustering failed: %s", err)
                return
            try:
                groups = json.loads(text)
                if not isinstance(groups, list):
                    return
                n = len(items)
                for group in groups:
                    if isinstance(group, list) and len(group) >= 2:
                        valid = [int(i) for i in group if isinstance(i, int) and 0 <= i < n]
                        if len(valid) >= 2:
                            result.append(valid)
            except Exception as e:
                logger.warning("MergeContentStage: clustering parse failed: %s", e)

        self._llm.call(
            self._model,
            [
                {"role": "system", "content": self._cluster_prompt},
                {"role": "user", "content": titles_text},
            ],
            on_resp,
        )
        return result

    def _merge_cluster(self, items: list[Content]) -> Content | None:
        combined = "\n\n---\n\n".join(
            f"Title: {item.title}\n{item.body or item.summary or ''}" for item in items
        )
        result: list[str | None] = [None]

        assert self._llm is not None

        def on_resp(ok: bool, err: str, text: str) -> None:
            if not ok:
                logger.warning("MergeContentStage: merge failed: %s", err)
                return
            result[0] = text

        self._llm.call(
            self._model,
            [
                {"role": "system", "content": self._merge_prompt},
                {"role": "user", "content": combined},
            ],
            on_resp,
        )

        raw = result[0]
        if raw is None:
            return None

        lines = raw.splitlines()
        if not lines:
            return None
        title = lines[0].strip()
        summary = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        sorted_ids = sorted(item.id for item in items)
        merge_hash = hashlib.md5("|".join(sorted_ids).encode()).hexdigest()[:8]
        merge_id = f"merge-{merge_hash}"

        published_ts = max(item.published_ts for item in items)
        avg_score: float | None = None
        scores = [item.score for item in items if item.score is not None]
        if scores:
            avg_score = sum(scores) / len(scores)

        cats = [item.category for item in items if item.category]
        category: str | None = Counter(cats).most_common(1)[0][0] if cats else None

        body = "\n\n---\n\n".join(item.body for item in items)

        return Content(
            id=merge_id,
            title=title,
            body=body,
            source_id="merged",
            source_type="merged",
            published_ts=published_ts,
            summary=summary or None,
            score=avg_score,
            category=category,
            related_ids=sorted_ids,
            related_contents=list(items),
        )
