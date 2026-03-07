import dataclasses
import logging
from typing import Callable

import openai

from .._types import Callback, ContentCallback
from ..llm.client import LLMClient
from ..secrets import Secrets
from ..types.content import Content
from . import Summarize

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = """\
You are a news article summarizer. Summarize the following article in 2-3 concise sentences.
Reply with ONLY the summary text."""


class OpenAISummarize(Summarize):
    def __init__(
        self,
        secrets: Secrets,
        prompt: str = _DEFAULT_PROMPT,
        model: str = "gpt-4o-mini",
        max_repeat_count: int = 3,
        on_circuit_trip: Callable[[str], None] | None = None,
    ) -> None:
        self._secrets = secrets
        self._prompt = prompt or _DEFAULT_PROMPT
        self._model = model
        self._max_repeat_count = max_repeat_count
        self._on_circuit_trip = on_circuit_trip
        self._llm: LLMClient | None = None

    def initialize(self, callback: Callback) -> None:
        def on_key(ok: bool, err: str, key: str = "") -> None:
            if not ok:
                callback(False, f"OpenAISummarize: OPENAI_API_KEY not available: {err}")
                return
            self._llm = LLMClient(
                client=openai.OpenAI(api_key=key),
                name="openai_summarize",
                max_repeat_count=self._max_repeat_count,
                on_circuit_trip=self._on_circuit_trip,
            )
            callback(True, "")

        self._secrets.read_value("OPENAI_API_KEY", on_key)

    def reset_run(self) -> None:
        if self._llm is not None:
            self._llm.reset_run()

    def summarize(self, content: Content, callback: ContentCallback) -> None:
        text = content.title + "\n\n" + (content.body or "")
        messages = [
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": text},
        ]

        assert self._llm is not None

        def on_resp(ok: bool, err: str, summary: str) -> None:
            if not ok:
                logger.warning("OpenAISummarize: summarize failed: %s", err)
                callback(False, err, content)
                return
            updated = dataclasses.replace(content, summary=summary)
            callback(True, "", updated)

        self._llm.call(self._model, messages, on_resp)
