from pathlib import Path

from smartreader.state.sqlite import SQLiteState
from smartreader.types.params import ConfigParams

_MEMORY = Path(":memory:")


# ── helpers ───────────────────────────────────────────────────────────────────

def load(state: SQLiteState) -> tuple[bool, str]:
    result: list = []
    state.load(ConfigParams(), lambda *a: result.extend(a))
    ok, err = result
    return ok, err


def read(state: SQLiteState, key: str) -> tuple[bool, str, dict]:
    result: list = []
    state.read_value(key, lambda *a: result.extend(a))
    ok, err, val = result
    return ok, err, val


def write(state: SQLiteState, key: str, value: dict) -> tuple[bool, str]:
    result: list = []
    state.write_value(key, value, lambda *a: result.extend(a))
    ok, err = result
    return ok, err


def save(state: SQLiteState) -> tuple[bool, str]:
    result: list = []
    state.save(lambda *a: result.extend(a))
    ok, err = result
    return ok, err


# ── tests ─────────────────────────────────────────────────────────────────────

def test_load_succeeds() -> None:
    state = SQLiteState(path=_MEMORY)
    ok, err = load(state)
    assert ok, err


def test_read_missing_key_returns_empty_dict() -> None:
    state = SQLiteState(path=_MEMORY)
    load(state)

    ok, err, val = read(state, "nonexistent")
    assert ok, err
    assert val == {}


def test_write_and_read_dict() -> None:
    state = SQLiteState(path=_MEMORY)
    load(state)

    ok, err = write(state, "common_keyword_interests", {"python": 0.9, "rust": 0.7})
    assert ok, err

    ok, err, val = read(state, "common_keyword_interests")
    assert ok, err
    assert val == {"python": 0.9, "rust": 0.7}


def test_write_and_read_list() -> None:
    state = SQLiteState(path=_MEMORY)
    load(state)

    ok, err = write(state, "sourceStates", ["src1", "src2", "src3"])
    assert ok, err

    ok, err, val = read(state, "sourceStates")
    assert ok, err
    assert val == ["src1", "src2", "src3"]


def test_write_overwrites_previous_value() -> None:
    state = SQLiteState(path=_MEMORY)
    load(state)

    write(state, "source_bbc_world", {"active": True, "lastReadTs": 1000.0})
    write(state, "source_bbc_world", {"active": True, "lastReadTs": 2000.0})

    _, _, val = read(state, "source_bbc_world")
    assert val == {"active": True, "lastReadTs": 2000.0}


def test_write_nested_dict() -> None:
    state = SQLiteState(path=_MEMORY)
    load(state)

    category_interests = {"tech": {"python": 0.8}, "news": {"politics": 0.5}}
    write(state, "category_interests", category_interests)

    _, _, val = read(state, "category_interests")
    assert val == category_interests


def test_save_is_noop() -> None:
    state = SQLiteState(path=_MEMORY)
    load(state)
    write(state, "key", {"v": 1})

    ok, err = save(state)
    assert ok, err

    _, _, val = read(state, "key")
    assert val == {"v": 1}
