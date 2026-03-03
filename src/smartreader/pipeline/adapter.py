import logging
from typing import TYPE_CHECKING

from .._types import Callback
from ..config import Config
from ..secrets import Secrets
from ..state import State
from ..types.content import Content
from . import PipelineStage, UpdatablePipelineStage

if TYPE_CHECKING:
    from ..summarize import Summarize

logger = logging.getLogger(__name__)


class PipelineAdapter:
    """Runs a pre-built list of pipeline stages sequentially."""

    def __init__(self, stages: list[PipelineStage]) -> None:
        self._stages = stages

    def initialize(self, callback: Callback) -> None:
        self._init_stages(0, callback)

    def _init_stages(self, idx: int, callback: Callback) -> None:
        if idx >= len(self._stages):
            callback(True, "")
            return
        self._stages[idx].initialize(
            lambda ok, err, _i=idx: (
                self._init_stages(_i + 1, callback) if ok else callback(False, err)
            )
        )

    def process(self, items: list[Content]) -> list[Content]:
        result = items
        for stage in self._stages:
            label = type(stage).__name__
            before = len(result)
            result = stage.process(result)
            after = len(result)
            if before != after:
                logger.info("pipeline %s: %d/%d selected", label, after, before)
        return result

    def update_score(self, content: Content, upvote: bool, callback: Callback) -> None:
        updatable = [s for s in self._stages if isinstance(s, UpdatablePipelineStage)]

        def _chain(idx: int) -> None:
            if idx >= len(updatable):
                callback(True, "")
                return

            def on_done(ok: bool, err: str) -> None:
                if not ok:
                    logger.warning("stage %d update_score error: %s", idx, err)
                _chain(idx + 1)

            updatable[idx].update_score(content, upvote, on_done)

        if not updatable:
            callback(True, "")
            return
        _chain(0)


def build_pipeline(
    entries: list[dict],
    state: State,
    config: Config,
    secrets: Secrets | None = None,
    summarize: "Summarize | None" = None,
    global_prompt: str = "",
    global_interests_prompt: str = "",
) -> PipelineAdapter:
    """Build a PipelineAdapter from a list of stage entry dicts."""
    from .stages.keyword_score import KeywordScoreStage
    from .stages.openai_score import OpenAIScoreStage
    from .stages.shuffle import ShuffleStage
    from .stages.summarize import SummarizeStage
    from .stages.top_n import TopNStage
    from .stages.trim import TrimStage

    shared_common: dict[str, float] = {}
    shared_category: dict[str, dict[str, float]] = {}

    stages: list[PipelineStage] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        t = entry.get("type", "")
        if t == "keyword_score":
            common_weight = float(entry.get("common_weight", 1.0))
            category_weight = float(entry.get("category_weight", 1.5))
            stages.append(KeywordScoreStage(
                state, config,
                shared_common, shared_category,
                common_weight, category_weight,
            ))
        elif t == "openai_score":
            if secrets is None:
                logger.warning("openai_score stage requires secrets; skipping (no secrets provided)")
            else:
                effective_entry = dict(entry)
                if "prompt" not in effective_entry and global_prompt:
                    effective_entry["prompt"] = global_prompt
                if "interests_prompt" not in effective_entry and global_interests_prompt:
                    effective_entry["interests_prompt"] = global_interests_prompt
                stages.append(OpenAIScoreStage(state, secrets, effective_entry))
        elif t == "shuffle":
            noise_factor = float(entry.get("noise_factor", 1.0))
            stages.append(ShuffleStage(noise_factor))
        elif t == "summarize":
            if summarize is None:
                logger.warning("summarize stage: no Summarize impl provided; skipping")
            else:
                stages.append(SummarizeStage(summarize))
        elif t == "trim":
            lines = int(entry.get("lines", 0))
            raw_chars = entry.get("chars")
            chars = int(raw_chars) if raw_chars is not None else None
            stages.append(TrimStage(lines, chars))
        elif t == "top_n":
            n = int(entry.get("n", 10))
            stages.append(TopNStage(n))
        else:
            logger.warning("unknown pipeline stage type %r; skipping", t)

    logger.info("pipeline: %d stage(s) configured", len(stages))
    return PipelineAdapter(stages)
