import json
import logging
import sqlite3
from pathlib import Path

from .._types import AllStateCallback, Callback, StateValueCallback
from ..types.params import ConfigParams
from ..types.values import StateValue
from . import State

logger = logging.getLogger(__name__)

_STATE_PATH = Path("state.sqlite")
_TABLE = "state"


def _json_len(conn: sqlite3.Connection, key: str) -> int:
    """Return len() of the JSON value stored under key, or 0 if absent."""
    row = conn.execute(f"SELECT value FROM {_TABLE} WHERE key = ?", (key,)).fetchone()
    if not row:
        return 0
    val = json.loads(row[0])
    return len(val) if isinstance(val, (dict, list)) else 0


class SQLiteState(State):
    def __init__(self, path: Path = _STATE_PATH) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None

    def load(self, params: ConfigParams, callback: Callback) -> None:
        try:
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.execute(
                f"CREATE TABLE IF NOT EXISTS {_TABLE} "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._conn.commit()
            count = self._conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
            logger.info("state database opened: %s — %d entry/entries", self._path, count)
            logger.info(
                "state: sourceStates=%d id(s), common_keyword_interests=%d, category_interests=%d",
                _json_len(self._conn, "sourceStates"),
                _json_len(self._conn, "common_keyword_interests"),
                _json_len(self._conn, "category_interests"),
            )
            callback(True, "")
        except Exception as e:
            logger.error("SQLiteState load error: %s", e)
            callback(False, str(e))

    def read_value(self, key: str, callback: StateValueCallback) -> None:
        try:
            row = self._db().execute(
                f"SELECT value FROM {_TABLE} WHERE key = ?", (key,)
            ).fetchone()
            val: StateValue = json.loads(row[0]) if row else {}
            callback(True, "", val)
        except Exception as e:
            logger.error("SQLiteState read_value error: %s", e)
            callback(False, str(e), {})

    def write_value(self, key: str, value: StateValue, callback: Callback) -> None:
        try:
            self._db().execute(
                f"INSERT OR REPLACE INTO {_TABLE} (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
            self._conn.commit()  # type: ignore[union-attr]
            callback(True, "")
        except Exception as e:
            logger.error("SQLiteState write_value error: %s", e)
            callback(False, str(e))

    def read_all(self, callback: AllStateCallback) -> None:
        try:
            rows = self._db().execute(f"SELECT key, value FROM {_TABLE}").fetchall()
            result: dict[str, StateValue] = {key: json.loads(val) for key, val in rows}
            callback(True, "", result)
        except Exception as e:
            logger.error("SQLiteState read_all error: %s", e)
            callback(False, str(e), {})

    def save(self, callback: Callback) -> None:
        # write_value commits on every call; save is a no-op
        callback(True, "")

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteState not initialised; call load() first")
        return self._conn
