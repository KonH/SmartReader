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
    "common": {
        "initial_days_scan_interval": 7,
    },
    "telegram": {
        "active": False,
        "read_source_min_interval": 1000,
        "read_source_max_interval": 3000,
    },
    "scoring": {
        "top_n": 10,
        "upvote_power": 1.5,
        "downvote_power": -1.0,
        "keyword": {
            "common_weight": 1.0,
            "category_weight": 1.5,
            "skip": [
                "a", "an", "the", "this", "that", "these", "those",
                "i", "me", "my", "we", "our", "you", "your",
                "he", "his", "she", "her", "it", "its", "they", "their",
                "is", "are", "was", "were", "be", "been", "being", "am",
                "have", "has", "had", "do", "does", "did",
                "will", "would", "could", "should", "may", "might", "shall", "can", "must",
                "to", "of", "in", "on", "at", "by", "for", "with", "from", "into", "onto",
                "and", "or", "but", "not", "no", "nor", "so", "yet",
                "as", "if", "then", "than", "so", "up", "out", "about",
                "all", "also", "just", "more", "new", "now", "one", "other", "over", "said", "such",
            ],
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
