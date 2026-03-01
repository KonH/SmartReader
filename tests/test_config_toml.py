from pathlib import Path

import pytest

from smartreader.config.toml import TOMLConfig, _DEFAULTS
from smartreader.types.params import ConfigParams


# ── helpers ───────────────────────────────────────────────────────────────────

def load(config: TOMLConfig) -> tuple[bool, str]:
    result: list = []
    config.load(ConfigParams(), lambda *a: result.extend(a))
    ok, err = result
    return ok, err


def read(config: TOMLConfig, key: str) -> tuple[bool, str, dict]:
    result: list = []
    config.read_value(key, lambda *a: result.extend(a))
    ok, err, val = result
    return ok, err, val


def write(config: TOMLConfig, key: str, value: dict) -> tuple[bool, str]:
    result: list = []
    config.write_value(key, value, lambda *a: result.extend(a))
    ok, err = result
    return ok, err


def save(config: TOMLConfig) -> tuple[bool, str]:
    result: list = []
    config.save(lambda *a: result.extend(a))
    ok, err = result
    return ok, err


# ── tests ─────────────────────────────────────────────────────────────────────

def test_load_creates_file_with_defaults_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    assert not path.exists()

    config = TOMLConfig(path=path)
    ok, err = load(config)

    assert ok, err
    assert path.exists()


def test_load_defaults_contain_scoring_section(tmp_path: Path) -> None:
    config = TOMLConfig(path=tmp_path / "config.toml")
    load(config)

    ok, err, val = read(config, "scoring")
    assert ok, err
    assert "top_n_l1" in val
    assert "l1" in val
    assert "skip" in val


def test_load_reads_existing_toml(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_bytes(b"[scoring]\ntop_n = 5\n")

    config = TOMLConfig(path=path)
    ok, err = load(config)
    assert ok, err

    _, _, val = read(config, "scoring")
    assert val["top_n"] == 5


def test_read_value_missing_key_returns_empty_dict(tmp_path: Path) -> None:
    config = TOMLConfig(path=tmp_path / "config.toml")
    load(config)

    ok, err, val = read(config, "nonexistent")
    assert ok, err
    assert val == {}


def test_read_value_wraps_scalar_in_dict(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_bytes(b"answer = 42\n")

    config = TOMLConfig(path=path)
    load(config)

    ok, err, val = read(config, "answer")
    assert ok, err
    assert isinstance(val, dict)
    assert val["answer"] == 42


def test_write_value_visible_via_read(tmp_path: Path) -> None:
    config = TOMLConfig(path=tmp_path / "config.toml")
    load(config)

    ok, err = write(config, "custom", {"x": 1})
    assert ok, err

    _, _, val = read(config, "custom")
    assert val == {"x": 1}


def test_save_persists_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    config = TOMLConfig(path=path)
    load(config)
    write(config, "custom", {"persisted": True})

    ok, err = save(config)
    assert ok, err

    config2 = TOMLConfig(path=path)
    load(config2)
    _, _, val = read(config2, "custom")
    assert val == {"persisted": True}
