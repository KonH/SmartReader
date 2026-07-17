from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..types.content import Content

logger = logging.getLogger(__name__)

_REPORT_DIR = Path(".tmp/reports")


def _content_to_dict(c: Content) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "body": c.body,
        "source_id": c.source_id,
        "source_type": c.source_type,
        "published_ts": c.published_ts,
        "summary": c.summary,
        "score": c.score,
        "category": c.category,
        "url": c.url,
        "related_ids": list(c.related_ids),
    }


@dataclass
class _StageRecord:
    type: str
    config: dict
    output: list[dict]


class PipelineLogger:
    def __init__(self) -> None:
        self._run_ts: datetime = datetime.now().astimezone()
        self._input: list[dict] = []
        self._stages: list[_StageRecord] = []

    def start(self, items: list[Content]) -> None:
        self._run_ts = datetime.now().astimezone()
        self._input = [_content_to_dict(c) for c in items]
        self._stages = []

    def record_stage(self, stage_type: str, config: dict, output: list[Content]) -> None:
        self._stages.append(_StageRecord(
            type=stage_type,
            config=config,
            output=[_content_to_dict(c) for c in output],
        ))

    def save(self) -> None:
        try:
            _REPORT_DIR.mkdir(parents=True, exist_ok=True)
            filename = self._run_ts.strftime("%Y_%m_%d_%H_%M_data.json")
            path = _REPORT_DIR / filename
            report = {
                "run_ts": self._run_ts.isoformat(),
                "input": self._input,
                "stages": [
                    {"type": s.type, "config": s.config, "output": s.output}
                    for s in self._stages
                ],
            }
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            logger.info("pipeline report written to %s", path)
        except Exception as exc:
            logger.warning("pipeline logger: failed to write report: %s", exc)
