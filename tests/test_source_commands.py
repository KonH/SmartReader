"""Unit tests for Add / Edit / Remove source config helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from smartreader.config.toml import TOMLConfig
from smartreader.state.app_state import AppState
from smartreader.state.sqlite import SQLiteState
from smartreader.types.params import ConfigParams, NewSourceParams
from smartreader.ui.command import SharedUIState
from smartreader.ui.commands import AddSourceCommand, EditSourceCommand, RemoveSourceCommand


class _DummyShared(SharedUIState):
    pass


class _ConcreteAdd(AddSourceCommand):
    @property
    def control_title(self) -> str:
        return "add"

    def execute(self) -> None:
        return


class _ConcreteEdit(EditSourceCommand):
    @property
    def control_title(self) -> str:
        return "edit"

    def execute(self) -> None:
        return


class _ConcreteRemove(RemoveSourceCommand):
    @property
    def control_title(self) -> str:
        return "remove"

    def execute(self) -> None:
        return


def _load_config(path: Path, sources: dict) -> TOMLConfig:
    cfg = TOMLConfig(path=path)
    ok_box: list[bool] = [False]
    cfg.load(ConfigParams(), lambda ok, err: ok_box.__setitem__(0, ok))
    assert ok_box[0]
    cfg.write_value("sources", sources, lambda ok, err: None)
    cfg.save(lambda ok, err: None)
    return cfg


def _make_app(tmp_path: Path, sources: dict) -> AppState:
    cfg = _load_config(tmp_path / "config.toml", sources)
    state = SQLiteState(path=tmp_path / "state.sqlite")
    state.load(ConfigParams(), lambda ok, err: None)
    app = AppState(state, config=cfg)
    # rebuild_pipeline is a no-op for these unit tests
    app.pipeline_factory = lambda cb: cb(True, "")  # type: ignore[assignment]
    return app


def test_add_source_appends_entry(tmp_path: Path) -> None:
    app = _make_app(tmp_path, {"tech": [{"type": "rss", "externalId": "https://a.example/feed"}]})
    cmd = _ConcreteAdd(app, _DummyShared())
    cmd._write_source_and_restart(NewSourceParams(
        name="world", source_type="rss",
        external_id="https://b.example/feed", category="news",
    ))
    names = _ConcreteEdit(app, _DummyShared())._list_source_names()
    assert names == ["tech", "world"]
    entry = _ConcreteEdit(app, _DummyShared())._read_source_entry("world")
    assert entry == {
        "type": "rss",
        "externalId": "https://b.example/feed",
        "category": "news",
    }


def test_edit_source_updates_fields(tmp_path: Path) -> None:
    app = _make_app(tmp_path, {
        "tech": [{"type": "rss", "externalId": "https://old.example/feed", "category": "old"}],
    })
    cmd = _ConcreteEdit(app, _DummyShared())
    cmd._update_source_and_restart(NewSourceParams(
        name="tech", source_type="telegram",
        external_id="newchannel", category="tech",
    ))
    entry = cmd._read_source_entry("tech")
    assert entry == {
        "type": "telegram",
        "externalId": "newchannel",
        "category": "tech",
    }


def test_edit_source_clears_category(tmp_path: Path) -> None:
    app = _make_app(tmp_path, {
        "tech": [{"type": "rss", "externalId": "https://a.example/feed", "category": "tech"}],
    })
    cmd = _ConcreteEdit(app, _DummyShared())
    cmd._update_source_and_restart(NewSourceParams(
        name="tech", source_type="rss",
        external_id="https://a.example/feed", category=None,
    ))
    entry = cmd._read_source_entry("tech")
    assert entry is not None
    assert "category" not in entry


def test_remove_source_deletes_and_cleans_state(tmp_path: Path) -> None:
    app = _make_app(tmp_path, {
        "tech": [{"type": "rss", "externalId": "https://a.example/feed"}],
        "world": [{"type": "rss", "externalId": "https://b.example/feed"}],
    })
    app._state.write_value(
        "sourceStates", {"ids": ["tech", "world"]}, lambda ok, err: None,
    )
    app._state.write_value(
        "source_tech", {"active": True, "lastReadTs": 1.0}, lambda ok, err: None,
    )

    cmd = _ConcreteRemove(app, _DummyShared())
    cmd._remove_source_and_restart("tech")

    assert cmd._list_source_names() == ["world"]

    ids_box: list[list[str]] = [[]]

    def on_states(ok: bool, err: str, val: object) -> None:
        if ok and isinstance(val, dict):
            raw = val.get("ids", [])
            ids_box[0] = list(raw) if isinstance(raw, list) else []

    app._state.read_value("sourceStates", on_states)
    assert ids_box[0] == ["world"]
