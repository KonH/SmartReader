import logging
from dataclasses import dataclass
from typing import Protocol

from .._types import ContentListCallback
from ..config import Config
from ..types.content import Content
from . import Input

logger = logging.getLogger(__name__)


@dataclass
class SourceEntry:
    id: str
    type: str
    external_id: str
    category: str
    custom: dict


class TypeReader(Protocol):
    def read(self, source: SourceEntry, start_ts: float, callback: ContentListCallback) -> None: ...


class SourceReader(Input):
    """Reads all configured sources, dispatching to a TypeReader per source type."""

    def __init__(self, config: Config, readers: dict[str, TypeReader]) -> None:
        self._config = config
        self._readers = readers

    def read_sources(
        self, start_ts: float, type: str, id: str, callback: ContentListCallback
    ) -> None:
        self._config.read_value(
            "sources",
            lambda ok, err, val: self._on_sources(ok, err, val, start_ts, type, id, callback),
        )

    def _on_sources(
        self,
        ok: bool,
        err: str,
        val: dict,
        start_ts: float,
        type_filter: str,
        id_filter: str,
        callback: ContentListCallback,
    ) -> None:
        if not ok:
            callback(False, f"failed to read sources config: {err}", [])
            return

        all_items: list[Content] = []

        for source_name, entries in val.items():
            for entry in (entries if isinstance(entries, list) else [entries]):
                source_type = entry.get("type", "")
                external_id = entry.get("externalId", "")
                category = entry.get("category", "")

                if type_filter and source_type != type_filter:
                    continue
                if id_filter and source_name != id_filter:
                    continue

                reader = self._readers.get(source_type)
                if reader is None:
                    logger.warning("no reader registered for source type %r (source: %s)", source_type, source_name)
                    continue

                source = SourceEntry(
                    id=source_name,
                    type=source_type,
                    external_id=external_id,
                    category=category,
                    custom=entry.get("custom", {}),
                )

                def on_items(ok2: bool, err2: str, items: list[Content], _src: SourceEntry = source) -> None:
                    if ok2:
                        logger.info("source %r: %d item(s) read", _src.id, len(items))
                        all_items.extend(items)
                    else:
                        logger.warning("source %r read failed: %s", _src.id, err2)

                reader.read(source, start_ts, on_items)

        callback(True, "", all_items)
