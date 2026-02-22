from smartreader.config import Config
from smartreader.input.source_reader import SourceEntry, SourceReader, TypeReader
from smartreader.types.content import Content
from smartreader.types.params import ConfigParams
from smartreader.types.values import StateValue


# ── stubs ─────────────────────────────────────────────────────────────────────

class StubConfig(Config):
    def __init__(self, sources: dict) -> None:
        self._sources = sources

    def load(self, params: ConfigParams, callback) -> None: callback(True, "")
    def read_value(self, key: str, callback) -> None:
        callback(True, "", self._sources if key == "sources" else {})
    def write_value(self, key: str, value: StateValue, callback) -> None: callback(True, "")
    def save(self, callback) -> None: callback(True, "")


class StubTypeReader:
    def __init__(self, items: list[Content] | None = None, fail: bool = False) -> None:
        self._items = items or []
        self._fail = fail
        self.calls: list[tuple[SourceEntry, float]] = []

    def read(self, source: SourceEntry, start_ts: float, callback) -> None:
        self.calls.append((source, start_ts))
        if self._fail:
            callback(False, "stub error", [])
        else:
            callback(True, "", self._items)


def _make_content(id: str = "c1") -> Content:
    return Content(id=id, title="T", body="B", source_id="s", source_type="rss", published_ts=1.0)


def _read(reader: SourceReader, start_ts=0.0, type_filter="", id_filter=""):
    result: list = []
    reader.read_sources(start_ts, type_filter, id_filter, lambda *a: result.extend(a))
    return result[0], result[1], result[2]


# ── tests ─────────────────────────────────────────────────────────────────────

def test_reads_from_single_source() -> None:
    item = _make_content()
    stub = StubTypeReader(items=[item])
    config = StubConfig({"feed1": [{"type": "rss", "externalId": "http://x", "category": "tech"}]})
    reader = SourceReader(config=config, readers={"rss": stub})

    ok, _, items = _read(reader)

    assert ok
    assert items == [item]
    assert len(stub.calls) == 1
    assert stub.calls[0][0].id == "feed1"
    assert stub.calls[0][0].category == "tech"


def test_aggregates_multiple_sources() -> None:
    a = _make_content("a")
    b = _make_content("b")
    config = StubConfig({
        "feed1": [{"type": "rss", "externalId": "http://1", "category": ""}],
        "feed2": [{"type": "rss", "externalId": "http://2", "category": ""}],
    })
    reader = SourceReader(config=config, readers={"rss": StubTypeReader([a, b])})

    _, _, items = _read(reader)
    assert len(items) == 4  # 2 items × 2 sources


def test_type_filter_skips_non_matching_sources() -> None:
    stub = StubTypeReader(items=[_make_content()])
    config = StubConfig({
        "rss_feed": [{"type": "rss", "externalId": "", "category": ""}],
        "tg_feed":  [{"type": "telegram", "externalId": "", "category": ""}],
    })
    reader = SourceReader(config=config, readers={"rss": stub, "telegram": StubTypeReader()})

    _, _, items = _read(reader, type_filter="rss")
    assert len(stub.calls) == 1


def test_id_filter_skips_non_matching_sources() -> None:
    stub_a = StubTypeReader(items=[_make_content()])
    stub_b = StubTypeReader(items=[_make_content()])
    config = StubConfig({
        "feed_a": [{"type": "rss", "externalId": "", "category": ""}],
        "feed_b": [{"type": "rss", "externalId": "", "category": ""}],
    })
    reader = SourceReader(config=config, readers={"rss": stub_a})

    _, _, items = _read(reader, id_filter="feed_a")
    assert len(stub_a.calls) == 1


def test_unknown_type_is_skipped() -> None:
    config = StubConfig({"feed": [{"type": "unknown_type", "externalId": "", "category": ""}]})
    reader = SourceReader(config=config, readers={})

    ok, _, items = _read(reader)
    assert ok
    assert items == []


def test_failing_reader_is_skipped_others_still_returned() -> None:
    good_item = _make_content("good")
    config = StubConfig({
        "bad":  [{"type": "rss", "externalId": "bad",  "category": ""}],
        "good": [{"type": "rss", "externalId": "good", "category": ""}],
    })
    readers = {
        "rss": StubTypeReader(),  # replaced per-call below
    }

    calls = []
    def dispatch_read(source: SourceEntry, start_ts: float, callback) -> None:
        calls.append(source.id)
        if source.id == "bad":
            callback(False, "err", [])
        else:
            callback(True, "", [good_item])

    reader = SourceReader(config=config, readers={"rss": type("R", (), {"read": staticmethod(dispatch_read)})()})
    _, _, items = _read(reader)

    assert good_item in items
    assert len(items) == 1


def test_empty_sources_returns_empty_list() -> None:
    config = StubConfig({})
    reader = SourceReader(config=config, readers={})

    ok, _, items = _read(reader)
    assert ok
    assert items == []
