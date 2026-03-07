import logging

import openai

from .._types import Callback, ScoreCallback
from ..secrets import Secrets
from ..state import State
from ..types.content import Content
from . import Scoring

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = """\
You are a news relevance scorer. Given an article, output a single number between -1.0 and 1.0:
  +1.0 = very important, high-quality news
   0.0 = neutral / borderline
  -1.0 = irrelevant, advertisement, spam, or low-quality content
Reply with ONLY the number, no explanation."""

_DEFAULT_INTERESTS_PROMPT = """\
You maintain a short user preference profile for a news reader.
Current profile: {current_profile}

Recent feedback actions:
{actions_text}

Write an updated profile in 3-5 short sentences describing what this user likes and dislikes.
Be concise and specific. Reply with ONLY the profile text."""

_SUMMARY_KEY = "openai_scoring_summary"
_PENDING_KEY = "openai_scoring_pending_actions"


class OpenAIScoring(Scoring):
    def __init__(self, state: State, secrets: Secrets, entry: dict) -> None:
        self._state = state
        self._secrets = secrets
        self._prompt: str = entry.get("prompt", _DEFAULT_PROMPT)
        self._interests_prompt: str = entry.get("interests_prompt", _DEFAULT_INTERESTS_PROMPT)
        self._score_factor: float = float(entry.get("score_factor", 1.0))
        self._model: str = entry.get("model", "gpt-4o-mini")
        self._summary: str = ""
        self._pending: list[dict] = []
        self._client: openai.OpenAI | None = None

    def initialize(self, callback: Callback) -> None:
        logger.info("OpenAIScoring initializing")
        def on_key(ok: bool, err: str, key: str = "") -> None:
            logger.info("OpenAIScoring initializing: on_key")
            if not ok:
                callback(False, f"OpenAI API key not available: {err}")
                return
            logger.info("OpenAIScoring initializing: on_key: success")
            self._client = openai.OpenAI(api_key=key)
            logger.info("OpenAIScoring initializing: on_key: client created")   
            self._state.read_value(
                _SUMMARY_KEY,
                lambda ok2, err2, val2: _on_summary(ok2, val2),
            )

        def _on_summary(ok: bool, val: object) -> None:
            logger.info("OpenAIScoring initializing: on_summary")
            if isinstance(val, dict):
                self._summary = str(val.get("text", ""))
            logger.info("OpenAIScoring initializing: on_summary: summary read")
            self._state.read_value(
                _PENDING_KEY,
                lambda ok3, err3, val3: _on_pending(ok3, val3),
            )

        def _on_pending(ok: bool, val: object) -> None:
            logger.info("OpenAIScoring initializing: on_pending")
            if isinstance(val, dict):
                actions = val.get("actions", [])
                self._pending = actions if isinstance(actions, list) else []
            logger.info("OpenAIScoring initializing: on_pending: pending read")
            if self._pending:
                logger.info("OpenAIScoring initializing: on_pending: updating summary")
                self._update_summary(callback)
            else:
                logger.info("OpenAIScoring initializing: on_pending: no pending actions")
                callback(True, "")

        self._secrets.read_value("OPENAI_API_KEY", on_key)

    def _update_summary(self, callback: Callback) -> None:
        logger.info("OpenAIScoring _update_summary")
        lines = []
        logger.info("OpenAIScoring _update_summary: pending actions length: %s", len(self._pending))
        for a in self._pending:
            mark = "✓ liked" if a.get("upvote") else "✗ disliked"
            cat = a.get("category") or "no category"
            title = a.get("title", "")
            lines.append(f"{mark}: {title} ({cat})")
        actions_text = "\n".join(lines)
        logger.info("OpenAIScoring _update_summary: actions text length: %s", len(actions_text))
        current = self._summary or "none"
        logger.info("OpenAIScoring _update_summary: current profile length: %s", len(current))
        prompt = self._interests_prompt.format(current_profile=current, actions_text=actions_text)
        logger.info("OpenAIScoring _update_summary: prompt length: %s", len(prompt))
        try:
            assert self._client is not None
            logger.info("OpenAIScoring _update_summary: calling chat.completions.create")
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            logger.info("OpenAIScoring _update_summary: chat.completions.create: response received")
            new_summary = (resp.choices[0].message.content or "").strip()
            logger.info("OpenAIScoring _update_summary: chat.completions.create: new summary length: %s", len(new_summary))
        except Exception as e:
            logger.warning("OpenAI summary update failed: %s", e)
            callback(True, "")
            return

        self._summary = new_summary
        logger.info("OpenAI preference summary updated")

        def _on_pending_cleared(ok: bool, err: str) -> None:
            logger.info("OpenAIScoring _update_summary: on_pending_cleared")
            if not ok:
                logger.warning("failed to clear OpenAI pending actions: %s", err)
            self._pending = []
            logger.info("OpenAIScoring _update_summary: on_pending_cleared: pending actions cleared")
            callback(True, "")

        def _on_summary_saved(ok: bool, err: str) -> None:
            logger.info("OpenAIScoring _update_summary: on_summary_saved")
            if not ok:
                logger.warning("failed to save OpenAI summary: %s", err)
            logger.info("OpenAIScoring _update_summary: on_summary_saved: clearing pending actions")
            self._state.write_value(
                _PENDING_KEY,
                {"actions": []},
                _on_pending_cleared,
            )

        self._state.write_value(
            _SUMMARY_KEY,
            {"text": new_summary},
            _on_summary_saved,
        )

    def score(self, content: Content, effort_level: int, callback: ScoreCallback) -> None:
        if effort_level >= 2:
            text = content.title + "\n" + (content.summary or content.body)
        else:
            text = content.title + "\n" + content.body

        system = self._prompt
        if self._summary:
            system += f"\n\nUser preferences:\n{self._summary}"

        try:
            assert self._client is not None
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
            )
            raw = (resp.choices[0].message.content or "").strip()
            value = float(raw)
            value = max(-1.0, min(1.0, value))
            score = value * self._score_factor
        except Exception as e:
            callback(False, str(e))
            return

        callback(True, "", score)

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        action = {
            "title": content.title,
            "upvote": upvote,
            "category": content.category,
        }
        self._pending.append(action)
        self._state.write_value(
            _PENDING_KEY,
            {"actions": self._pending},
            callback,
        )
