import calendar
import time
from unittest.mock import MagicMock, patch

from smartreader.input.rss import RSSReader
from smartreader.input.source_reader import SourceEntry

_SOURCE = SourceEntry(id="test_feed", type="rss", external_id="http://example.com/rss",
                      category="tech", custom={})


def _make_entry(id: str, title: str, summary: str, ts: float) -> MagicMock:
    published = time.gmtime(ts)
    entry = MagicMock()
    entry.get = lambda k, default=None: {
        "id": id, "title": title, "summary": summary,
        "published_parsed": published,
    }.get(k, default)
    entry.title = title
    entry.published_parsed = published
    entry.updated_parsed = None
    return entry


def _make_feed(*entries: MagicMock) -> MagicMock:
    feed = MagicMock()
    feed.entries = list(entries)
    return feed


def _read(source: SourceEntry = _SOURCE, start_ts: float = 0.0) -> tuple[bool, str, list]:
    result: list = []
    RSSReader().read(source, start_ts, lambda *a: result.extend(a))
    return result[0], result[1], result[2]


# ── tests ─────────────────────────────────────────────────────────────────────

def test_returns_items_from_feed() -> None:
    ts = calendar.timegm(time.gmtime(1_000_000))
    feed = _make_feed(_make_entry("e1", "Title One", "Body one", ts))

    with patch("feedparser.parse", return_value=feed):
        ok, err, items = _read()

    assert ok, err
    assert len(items) == 1
    assert items[0].title == "Title One"
    assert items[0].body == "Body one"
    assert items[0].source_id == "test_feed"
    assert items[0].source_type == "rss"
    assert items[0].category == "tech"


def test_filters_items_older_than_start_ts() -> None:
    old_ts = 1_000_000.0
    new_ts = 2_000_000.0
    feed = _make_feed(
        _make_entry("old", "Old", "", old_ts),
        _make_entry("new", "New", "", new_ts),
    )

    with patch("feedparser.parse", return_value=feed):
        ok, _, items = _read(start_ts=old_ts)  # strictly greater than

    assert ok
    assert len(items) == 1
    assert items[0].id == "new"


def test_empty_feed_returns_empty_list() -> None:
    with patch("feedparser.parse", return_value=_make_feed()):
        ok, _, items = _read()

    assert ok
    assert items == []


def test_entry_without_published_ts_uses_zero() -> None:
    entry = MagicMock()
    entry.get = lambda k, default=None: {"id": "x", "title": "T", "summary": ""}.get(k, default)
    entry.title = "T"
    entry.published_parsed = None
    entry.updated_parsed = None
    feed = _make_feed(entry)

    with patch("feedparser.parse", return_value=feed):
        ok, _, items = _read(start_ts=0.0)

    assert ok
    assert len(items) == 0  # ts=0.0 is not > start_ts=0.0


def test_parse_exception_returns_failure() -> None:
    with patch("feedparser.parse", side_effect=RuntimeError("network error")):
        ok, err, items = _read()

    assert not ok
    assert "network error" in err
    assert items == []
