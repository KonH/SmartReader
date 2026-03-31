"""Background cron scheduler — fires a callback at times specified by a cron expression."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class CronScheduler:
    """Daemon thread that fires *callback* each time the cron expression matches."""

    def __init__(self, expr: str, callback: Callable[[], None]) -> None:
        self._expr = expr
        self._callback = callback
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="cron-scheduler"
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            from croniter import croniter  # type: ignore[import-untyped]
        except ImportError:
            logger.error("cron scheduler: croniter is not installed (pip install croniter)")
            return

        import datetime
        cron = croniter(self._expr, datetime.datetime.now(datetime.timezone.utc))
        logger.info("cron: scheduler started with expression %r", self._expr)

        while not self._stop.is_set():
            next_ts: float = cron.get_next(float)
            delay = next_ts - time.time()
            logger.info(
                "cron: next trigger at %s (in %.0f s)",
                time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(next_ts)),
                max(delay, 0),
            )
            if self._stop.wait(max(delay, 0.0)):
                break
            if not self._stop.is_set():
                logger.info("cron: triggering scheduled show")
                try:
                    self._callback()
                except Exception as exc:
                    logger.error("cron: callback error: %s", exc)
