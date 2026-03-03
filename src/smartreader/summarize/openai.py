import logging

import openai

from .._types import Callback, ContentCallback
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
    ) -> None:
        self._secrets = secrets
        self._prompt = prompt or _DEFAULT_PROMPT
        self._model = model
        self._client: openai.OpenAI | None = None

    def initialize(self, callback: Callback) -> None:
        def on_key(ok: bool, err: str, key: str = "") -> None:
            if not ok:
                callback(False, f"OpenAISummarize: OPENAI_API_KEY not available: {err}")
                return
            self._client = openai.OpenAI(api_key=key)
            callback(True, "")

        self._secrets.read_value("OPENAI_API_KEY", on_key)

    def summarize(self, content: Content, callback: ContentCallback) -> None:
        text = content.title + "\n\n" + (content.body or "")
        try:
            assert self._client is not None
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._prompt},
                    {"role": "user", "content": text},
                ],
            )
            summary = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("OpenAISummarize: summarize failed: %s", e)
            callback(False, str(e), content)
            return

        import dataclasses
        updated = dataclasses.replace(content, summary=summary)
        callback(True, "", updated)
