from dataclasses import dataclass


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
