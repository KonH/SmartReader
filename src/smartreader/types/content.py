from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Content:
    id: str
    title: str
    body: str
    source_id: str
    source_type: str        # "rss" | "telegram" | "merged"
    published_ts: float
    summary: str | None = None
    score: float | None = None
    category: str | None = None
    url: str | None = None
    related_ids: list[str] = field(default_factory=list)
    # In-memory only — holds original items for feedback propagation, never serialized
    related_contents: list[Content] = field(default_factory=list, repr=False, compare=False)
