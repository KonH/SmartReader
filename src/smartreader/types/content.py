from dataclasses import dataclass


@dataclass
class Content:
    id: str
    title: str
    body: str
    source_id: str
    source_type: str        # "rss" | "telegram"
    published_ts: float
    summary: str | None = None
    score: float | None = None
    category: str | None = None
