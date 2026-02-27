"""TrimSummarize — decorator that trims the summary produced by an inner Summarize impl.

Enabled by ``[summarize.trim] active = true`` in config.toml.
When active it calls the inner summarizer and then truncates the resulting
``content.summary`` (or ``content.body`` if no summary) to the configured
line / character limits, storing the result back in ``content.summary``.
When inactive it is a transparent pass-through.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .._types import Callback, ContentCallback
from ..types.content import Content
from . import Summarize

if TYPE_CHECKING:
    from ..config import Config

logger = logging.getLogger(__name__)


class TrimSummarize(Summarize):
    """Wraps another Summarize and trims its output according to [summarize.trim] config."""

    def __init__(self, inner: Summarize, config: Config) -> None:
        self._inner = inner
        self._config = config
        self._active = False
        self._lines: int = 0
        self._chars: int | None = None

    def initialize(self, callback: Callback) -> None:
        self._inner.initialize(lambda ok, err: self._on_inner_init(ok, err, callback))

    def _on_inner_init(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, err)
            return
        self._config.read_value(
            "summarize",
            lambda ok2, err2, val: self._on_config(ok2, err2, val, callback),
        )

    def _on_config(self, ok: bool, err: str, val: dict, callback: Callback) -> None:
        if ok and isinstance(val, dict):
            trim = val.get("trim", {})
            if isinstance(trim, dict):
                self._active = bool(trim.get("active", False))
                self._lines = int(trim.get("lines", 0))
                raw_chars = trim.get("chars")
                self._chars = int(raw_chars) if raw_chars is not None else None
        if self._active:
            logger.info(
                "summarize.trim: active, lines=%d chars=%s",
                self._lines, self._chars,
            )
        else:
            logger.info("summarize.trim: inactive (pass-through)")
        callback(True, "")

    def summarize(self, content: Content, callback: ContentCallback) -> None:
        self._inner.summarize(
            content,
            lambda ok, err, result: self._on_summarized(ok, err, result, callback),
        )

    def _on_summarized(
        self, ok: bool, err: str, result: Content, callback: ContentCallback
    ) -> None:
        if not ok or not self._active:
            callback(ok, err, result)
            return
        text = result.summary or result.body
        result.summary = _trim(text, self._lines, self._chars)
        callback(True, "", result)


def _trim(text: str, max_lines: int, max_chars: int | None) -> str:
    lines = text.strip().splitlines()
    if max_lines > 0:
        lines = lines[:max_lines]
    result = "\n".join(lines)
    if max_chars and len(result) > max_chars:
        result = result[:max_chars].rstrip() + "…"
    return result
