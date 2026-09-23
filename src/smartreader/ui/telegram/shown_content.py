"""Persistent cache of content shown in Telegram, so inline votes keep working
on older messages — after a later Show or an app restart."""
from __future__ import annotations

import logging

from ...state import State
from ...types.content import Content
from ...types.values import StateValue
from .state import TelegramSharedUIState

logger = logging.getLogger(__name__)

SHOWN_CONTENT_KEY = "telegram_shown_content"
MAX_SHOWN_CONTENT = 200


def content_to_dict(c: Content) -> StateValue:
    return {
        "id": c.id,
        "title": c.title,
        "body": c.body,
        "source_id": c.source_id,
        "source_type": c.source_type,
        "published_ts": c.published_ts,
        "summary": c.summary,
        "category": c.category,
        "url": c.url,
        "related_ids": list(c.related_ids),
    }


def content_from_dict(d: StateValue) -> Content | None:
    try:
        summary = d.get("summary")
        category = d.get("category")
        url = d.get("url")
        related = d.get("related_ids")
        return Content(
            id=str(d["id"]),
            title=str(d.get("title", "")),
            body=str(d.get("body", "")),
            source_id=str(d.get("source_id", "")),
            source_type=str(d.get("source_type", "")),
            published_ts=float(d.get("published_ts", 0.0)),
            summary=str(summary) if summary is not None else None,
            category=str(category) if category is not None else None,
            url=str(url) if url is not None else None,
            related_ids=[str(r) for r in related] if isinstance(related, list) else [],
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("shown_content: skipping malformed entry: %s", e)
        return None


def load_shown_content(state: State) -> dict[str, Content]:
    """Read persisted shown content, oldest first."""
    result: dict[str, Content] = {}

    def on_read(ok: bool, err: str, val: StateValue) -> None:
        if not ok:
            logger.error("shown_content: read error: %s", err)
            return
        items = val.get("items", [])
        for raw in items if isinstance(items, list) else []:
            if isinstance(raw, dict):
                content = content_from_dict(raw)
                if content is not None:
                    result[content.id] = content

    state.read_value(SHOWN_CONTENT_KEY, on_read)
    return result


def remember_shown_content(
    s: TelegramSharedUIState,
    state: State,
    items: list[Content],
) -> None:
    """Add *items* to the vote lookup (newest last), trim to the cap and persist."""
    if not items:
        return
    merged = dict(s.content_by_id)
    for item in items:
        merged.pop(item.id, None)
        merged[item.id] = item
    if len(merged) > MAX_SHOWN_CONTENT:
        merged = dict(list(merged.items())[-MAX_SHOWN_CONTENT:])
    # Replace (not mutate) — the vote handler reads this dict from the asyncio thread
    s.content_by_id = merged
    state.write_value(
        SHOWN_CONTENT_KEY,
        {"items": [content_to_dict(c) for c in merged.values()]},
        lambda ok, err: logger.error("shown_content: write error: %s", err) if not ok else None,
    )
