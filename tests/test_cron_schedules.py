"""Tests for cron schedule helpers and per-category schedule config persistence."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import tomllib

from smartreader.config.toml import TOMLConfig
from smartreader.state.app_state import AppState
from smartreader.types.params import ConfigParams
from smartreader.ui.commands import SetCronCommand
from smartreader.ui.command import SharedUIState


class _DummyShared(SharedUIState):
    pass


class _TestSetCron(SetCronCommand):
    @property
    def control_title(self) -> str:
        return "cron"

    def execute(self) -> None:
        pass


def _load_config(path: Path, contents: bytes | None = None) -> TOMLConfig:
    if contents is not None:
        path.write_bytes(contents)
    config = TOMLConfig(path=path)
    result: list = []
    config.load(ConfigParams(), lambda *a: result.extend(a))
    assert result[0], result[1]
    return config


def _make_cmd(config: TOMLConfig, categories: list[str] | None = None) -> _TestSetCron:
    state = MagicMock()
    app = AppState(state=state, config=config)
    if categories is not None:
        app.categories = categories
    reloads: list[int] = []
    app.cron_updater = lambda: reloads.append(1)
    cmd = _TestSetCron(app, _DummyShared())
    cmd._reloads = reloads  # type: ignore[attr-defined]
    return cmd


def test_set_global_cron_persists_and_reloads(tmp_path: Path) -> None:
    config = _load_config(tmp_path / "config.toml")
    cmd = _make_cmd(config)

    cmd._set_cron_and_restart("0 8 * * *")

    with open(tmp_path / "config.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["common"]["cron_schedule"] == "0 8 * * *"
    assert "category_schedules" not in data["common"]
    assert cmd._reloads == [1]  # type: ignore[attr-defined]


def test_set_category_cron_persists_nested_table(tmp_path: Path) -> None:
    config = _load_config(tmp_path / "config.toml")
    cmd = _make_cmd(config, categories=["tech", "world"])

    cmd._set_cron_and_restart("0 9 * * 1-5", category="tech")
    cmd._set_cron_and_restart("30 18 * * *", category="world")

    with open(tmp_path / "config.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["common"]["category_schedules"] == {
        "tech": "0 9 * * 1-5",
        "world": "30 18 * * *",
    }
    assert cmd._read_current_cron("tech") == "0 9 * * 1-5"
    assert cmd._read_current_cron("world") == "30 18 * * *"
    assert cmd._read_current_cron(None) == ""


def test_disable_category_cron_removes_entry(tmp_path: Path) -> None:
    contents = b"""
[common]
cron_schedule = "0 8 * * *"

[common.category_schedules]
tech = "0 9 * * *"
world = "0 18 * * *"
"""
    config = _load_config(tmp_path / "config.toml", contents)
    cmd = _make_cmd(config)

    cmd._set_cron_and_restart("", category="tech")

    with open(tmp_path / "config.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["common"]["cron_schedule"] == "0 8 * * *"
    assert data["common"]["category_schedules"] == {"world": "0 18 * * *"}


def test_disable_last_category_cron_drops_table(tmp_path: Path) -> None:
    contents = b"""
[common]
[common.category_schedules]
tech = "0 9 * * *"
"""
    config = _load_config(tmp_path / "config.toml", contents)
    cmd = _make_cmd(config)

    cmd._set_cron_and_restart("", category="tech")

    with open(tmp_path / "config.toml", "rb") as f:
        data = tomllib.load(f)
    assert "category_schedules" not in data.get("common", {})


def test_schedule_target_categories_includes_orphans(tmp_path: Path) -> None:
    contents = b"""
[common.category_schedules]
legacy = "0 7 * * *"
"""
    config = _load_config(tmp_path / "config.toml", contents)
    cmd = _make_cmd(config, categories=["tech"])

    assert cmd._schedule_target_categories() == ["legacy", "tech"]


def test_format_schedule_status_lines(tmp_path: Path) -> None:
    contents = b"""
[common]
cron_schedule = "0 8 * * *"

[common.category_schedules]
tech = "0 9 * * *"
"""
    config = _load_config(tmp_path / "config.toml", contents)
    cmd = _make_cmd(config)

    lines = cmd._format_schedule_status_lines()
    assert lines[0].startswith("ALL: 0 8 * * *")
    assert any(line.startswith("tech: 0 9 * * *") for line in lines)


def test_validate_cron() -> None:
    assert SetCronCommand._validate_cron("0 8 * * *") is True
    assert SetCronCommand._validate_cron("not a cron") is False


def test_collect_schedules_roundtrip_via_config(tmp_path: Path) -> None:
    """category_schedules nested table survives load/save intact."""
    path = tmp_path / "config.toml"
    path.write_bytes(b"""
[common]
cron_schedule = "0 8 * * *"
[common.category_schedules]
tech = "0 9 * * 1-5"
""")
    config = TOMLConfig(path=path)
    result: list = []
    config.load(ConfigParams(), lambda *a: result.extend(a))
    assert result[0]

    common_box: list[dict] = [{}]

    def on_common(ok: bool, err: str, val: object) -> None:
        assert ok
        assert isinstance(val, dict)
        common_box[0] = val

    config.read_value("common", on_common)
    common = common_box[0]
    assert common["cron_schedule"] == "0 8 * * *"
    assert common["category_schedules"]["tech"] == "0 9 * * 1-5"

    # mutate and save
    common["category_schedules"]["world"] = "0 18 * * *"
    write_ok: list = []
    config.write_value("common", common, lambda *a: write_ok.extend(a))
    save_ok: list = []
    config.save(lambda *a: save_ok.extend(a))
    assert write_ok[0] and save_ok[0]

    with open(path, "rb") as f:
        data = tomllib.load(f)
    assert data["common"]["category_schedules"] == {
        "tech": "0 9 * * 1-5",
        "world": "0 18 * * *",
    }
