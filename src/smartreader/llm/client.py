import hashlib
import json
import logging
from typing import Callable

import openai

logger = logging.getLogger(__name__)


class LLMClient:
    """Wraps openai.OpenAI with per-run repeat detection to catch pipeline bugs."""

    def __init__(
        self,
        client: openai.OpenAI,
        name: str,
        max_repeat_count: int = 3,
        on_circuit_trip: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._name = name
        self._max_repeat_count = max_repeat_count
        self._on_circuit_trip = on_circuit_trip
        self._run_counts: dict[str, int] = {}

    def reset_run(self) -> None:
        """Call at the start of each pipeline run to reset per-run counters."""
        self._run_counts.clear()

    def call(
        self,
        model: str,
        messages: list[dict],
        callback: Callable[[bool, str, str], None],
    ) -> None:
        h = hashlib.sha256(
            (model + json.dumps(messages, ensure_ascii=False)).encode()
        ).hexdigest()[:16]

        self._run_counts[h] = self._run_counts.get(h, 0) + 1
        if self._run_counts[h] > self._max_repeat_count:
            msg = (
                f"[{self._name}] circuit trip: identical request hash {h} "
                f"sent {self._run_counts[h]} times in one run "
                f"(max_openai_request_repeat_count={self._max_repeat_count})"
            )
            self._trip(msg, callback)
            return

        try:
            resp = self._client.chat.completions.create(model=model, messages=messages)
            text = (resp.choices[0].message.content or "").strip()
            callback(True, "", text)
        except Exception as e:
            callback(False, str(e), "")

    def _trip(self, msg: str, callback: Callable[[bool, str, str], None]) -> None:
        logger.error("LLM circuit trip: %s", msg)
        if self._on_circuit_trip is not None:
            self._on_circuit_trip(msg)
        callback(False, msg, "")
