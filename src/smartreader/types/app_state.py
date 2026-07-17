from dataclasses import dataclass, field


@dataclass
class SourceStateEntry:
    source_id: str
    active: bool
    last_read_ts: float | None  # None = never read


@dataclass
class AppStateData:
    source_states: list[SourceStateEntry]            # sorted by source_id
    common_interests: dict[str, float]               # sorted by score desc
    category_interests: dict[str, dict[str, float]]  # category → keywords sorted by score desc
    skip_words: list[str] = field(default_factory=list)
    ban_words: list[str] = field(default_factory=list)
    openai_pending_count: int = 0
    openai_user_summary: str = ""
