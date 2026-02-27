import calendar
import logging

import feedparser

from .._types import ContentListCallback
from ..types.content import Content
from .source_reader import SourceEntry

logger = logging.getLogger(__name__)


class RSSReader:
    """Fetches and parses an RSS/Atom feed, returning Content items newer than start_ts."""

    def read(self, source: SourceEntry, start_ts: float, callback: ContentListCallback) -> None:
        try:
            feed = feedparser.parse(source.external_id)
        except Exception as e:
            callback(False, str(e), [])
            return

        items: list[Content] = []
        for entry in feed.entries:
            published_ts = _parse_ts(entry)
            if published_ts <= start_ts:
                continue
            items.append(Content(
                id=entry.get("id") or entry.get("link", ""),
                title=entry.get("title", ""),
                body=entry.get("summary", ""),
                source_id=source.id,
                source_type="rss",
                published_ts=published_ts,
                category=source.category,
                url=entry.get("link"),
            ))

        logger.info("rss %r: %d new item(s) since ts=%.0f", source.external_id, len(items), start_ts)
        callback(True, "", items)


def _parse_ts(entry: feedparser.util.FeedParserDict) -> float:
    for attr in ("published_parsed", "updated_parsed"):
        val = entry.get(attr)
        if val is not None:
            return float(calendar.timegm(val))
    return 0.0
