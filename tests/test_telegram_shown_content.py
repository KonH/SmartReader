from pathlib import Path

from smartreader.state.sqlite import SQLiteState
from smartreader.types.content import Content
from smartreader.types.params import ConfigParams
from smartreader.ui.telegram import shown_content
from smartreader.ui.telegram.shown_content import (
    SHOWN_CONTENT_KEY,
    content_from_dict,
    content_to_dict,
    load_shown_content,
    remember_shown_content,
)
from smartreader.ui.telegram.state import TelegramSharedUIState


# ── helpers ───────────────────────────────────────────────────────────────────

def make_state(path: Path) -> SQLiteState:
    state = SQLiteState(path)
    state.load(ConfigParams(), lambda ok, err: None)
    return state


def make_content(cid: str, **kw: object) -> Content:
    return Content(
        id=cid,
        title=f"title {cid}",
        body=f"body {cid}",
        source_id="src",
        source_type="rss",
        published_ts=1.0,
        **kw,  # type: ignore[arg-type]
    )


# ── serialization ─────────────────────────────────────────────────────────────

def test_roundtrip_keeps_feedback_fields() -> None:
    c = make_content("a", summary="sum", category="tech", url="http://x", related_ids=["r1"])
    restored = content_from_dict(content_to_dict(c))
    assert restored == c


def test_malformed_entry_is_skipped() -> None:
    assert content_from_dict({"title": "no id"}) is None


# ── persistence ───────────────────────────────────────────────────────────────

def test_votes_on_earlier_show_still_resolve() -> None:
    s = TelegramSharedUIState()
    state = make_state(Path(":memory:"))
    remember_shown_content(s, state, [make_content("old")])
    remember_shown_content(s, state, [make_content("new")])
    assert set(s.content_by_id) == {"old", "new"}


def test_survives_restart(tmp_path: Path) -> None:
    db = tmp_path / "state.sqlite"
    s = TelegramSharedUIState()
    remember_shown_content(s, make_state(db), [make_content("a", category="tech")])

    restored = load_shown_content(make_state(db))
    assert list(restored) == ["a"]
    assert restored["a"].category == "tech"


def test_capped_to_most_recent(monkeypatch: object) -> None:
    monkeypatch.setattr(shown_content, "MAX_SHOWN_CONTENT", 3)  # type: ignore[attr-defined]
    s = TelegramSharedUIState()
    state = make_state(Path(":memory:"))
    remember_shown_content(s, state, [make_content(str(i)) for i in range(5)])
    assert list(s.content_by_id) == ["2", "3", "4"]
    assert list(load_shown_content(state)) == ["2", "3", "4"]


def test_reshown_item_moves_to_newest() -> None:
    s = TelegramSharedUIState()
    state = make_state(Path(":memory:"))
    remember_shown_content(s, state, [make_content("a"), make_content("b")])
    remember_shown_content(s, state, [make_content("a")])
    assert list(s.content_by_id) == ["b", "a"]


def test_empty_state_loads_nothing() -> None:
    assert load_shown_content(make_state(Path(":memory:"))) == {}


def test_state_key_name() -> None:
    state = make_state(Path(":memory:"))
    remember_shown_content(TelegramSharedUIState(), state, [make_content("a")])
    got: list = []
    state.read_value(SHOWN_CONTENT_KEY, lambda ok, err, val: got.append(val))
    assert [i["id"] for i in got[0]["items"]] == ["a"]
