from ...types.content import Content
from .. import PipelineStage


def _trim(text: str, max_lines: int, max_chars: int | None) -> str:
    lines = text.strip().splitlines()
    if max_lines > 0:
        lines = lines[:max_lines]
    result = "\n".join(lines)
    if max_chars and len(result) > max_chars:
        result = result[:max_chars].rstrip() + "…"
    return result


class TrimStage(PipelineStage):
    """Trims item.summary in-place to a maximum number of lines/characters."""

    def __init__(self, lines: int, chars: int | None = None) -> None:
        self._lines = lines
        self._chars = chars

    def process(self, items: list[Content]) -> list[Content]:
        for item in items:
            if item.summary:
                item.summary = _trim(item.summary, self._lines, self._chars)
        return items
