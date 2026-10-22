"""Tracks an in-flight Show run so a restart mid-pipeline resumes it — at most MAX_RESUMES times."""
from __future__ import annotations

import logging
from pathlib import Path

from ..._logging import get_log_file
from ...state import State
from ...types.values import StateValue

logger = logging.getLogger(__name__)

PENDING_RUN_KEY = "telegram_pending_run"
MAX_RESUMES = 2
_LOG_TAIL_CHARS = 3000
_LOG_TAIL_LINES = 40


def mark_run_started(state: State, sender_id: int, category: str | None, resumes: int) -> None:
    _write(state, {"sender_id": sender_id, "category": category, "resumes": resumes})


def mark_run_finished(state: State) -> None:
    _write(state, {})


def load_pending_run(state: State) -> StateValue:
    result: list[StateValue] = [{}]

    def on_read(ok: bool, err: str, val: StateValue) -> None:
        if ok:
            result[0] = val
        else:
            logger.error("pending_run: read error: %s", err)

    state.read_value(PENDING_RUN_KEY, on_read)
    return result[0]


def previous_log_tail() -> str:
    """Tail of the log of the process before this one, i.e. the run that was interrupted."""
    current = get_log_file()
    if current is None:
        return ""
    previous = sorted(p for p in current.parent.glob("*_logs.log") if p != current)
    if not previous:
        return ""
    lines = previous[-1].read_text(errors="replace").splitlines()[-_LOG_TAIL_LINES:]
    return "\n".join(lines)[-_LOG_TAIL_CHARS:]


def give_up_message(pending: StateValue) -> str:
    return (
        f"⚠️ Interrupted run (category={pending.get('category') or 'ALL'}) was resumed "
        f"{MAX_RESUMES} times and the app restarted again each time. Not retrying; "
        f"send a new request when ready.\n\nLast log lines before the restart:\n"
        f"```\n{previous_log_tail() or 'No log available.'}\n```"
    )


def _write(state: State, value: StateValue) -> None:
    state.write_value(
        PENDING_RUN_KEY, value,
        lambda ok, err: logger.error("pending_run: write error: %s", err) if not ok else None,
    )
