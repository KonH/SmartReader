import logging
import tomllib
from pathlib import Path

import tomli_w

from .._types import Callback, StateValueCallback
from ..types.params import ConfigParams
from ..types.values import StateValue
from . import Config

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path("config.toml")

_DEFAULTS: dict = {
    "scoring": {
        "top_n": 10,
        "keyword": {
            "common_weight": 1.0,
            "category_weight": 1.5,
        },
    },
}


class TOMLConfig(Config):
    def __init__(self, path: Path = _CONFIG_PATH) -> None:
        self._path = path
        self._data: dict = {}

    def load(self, params: ConfigParams, callback: Callback) -> None:
        if not self._path.exists():
            logger.info("config.toml not found, creating with defaults")
            self._data = dict(_DEFAULTS)
            try:
                _write(self._path, self._data)
            except Exception as e:
                callback(False, f"failed to create config.toml: {e}")
                return
        else:
            try:
                with open(self._path, "rb") as f:
                    self._data = tomllib.load(f)
                sources = self._data.get("sources", {})
                source_count = sum(
                    len(v) if isinstance(v, list) else 1
                    for v in sources.values()
                ) if isinstance(sources, dict) else 0
                logger.info(
                    "config loaded from %s: %d top-level key(s), %d source(s)",
                    _CONFIG_PATH, len(self._data), source_count,
                )
            except Exception as e:
                callback(False, f"failed to load config.toml: {e}")
                return
        callback(True, "")

    def read_value(self, key: str, callback: StateValueCallback) -> None:
        val = self._data.get(key, {})
        # Wrap scalar values in a dict so callers can uniformly use .get()
        if not isinstance(val, dict):
            val = {key: val}
        callback(True, "", val)

    def write_value(self, key: str, value: StateValue, callback: Callback) -> None:
        self._data[key] = value
        callback(True, "")

    def save(self, callback: Callback) -> None:
        try:
            _write(self._path, self._data)
            callback(True, "")
        except Exception as e:
            callback(False, str(e))


def _write(path: Path, data: dict) -> None:
    with open(path, "wb") as f:
        tomli_w.dump(data, f)
