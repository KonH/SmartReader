"""Logging configuration — sets up console + rotating file handlers under .tmp/logs/."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(".tmp/logs")
_FILE_FMT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_CONSOLE_FMT = "%(levelname)s %(name)s: %(message)s"

_SCOPES = ("input", "scoring", "summarize")

_current_log_file: Path | None = None


def get_log_file() -> Path | None:
    """Return the path to the current INFO-level log file, or None if not yet set."""
    return _current_log_file


def setup(log_dir: Path = _LOG_DIR) -> None:
    """Create timestamped log files and attach handlers to the root and scope loggers."""
    global _current_log_file
    log_dir.mkdir(parents=True, exist_ok=True)

    prefix = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_")

    file_fmt = logging.Formatter(_FILE_FMT)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console — INFO+
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_CONSOLE_FMT))
    root.addHandler(console)

    # logs.log — INFO+ from all loggers
    log_path = log_dir / f"{prefix}logs.log"
    _current_log_file = log_path
    _file_handler(log_path, logging.INFO, file_fmt, root)

    # logs.errors.log — ERROR+ from all loggers
    _file_handler(log_dir / f"{prefix}logs.errors.log", logging.ERROR, file_fmt, root)

    # Scope-specific — DEBUG+ (detailed), attached to their own logger
    for scope in _SCOPES:
        logger = logging.getLogger(f"smartreader.{scope}")
        _file_handler(log_dir / f"{prefix}logs.{scope}.log", logging.DEBUG, file_fmt, logger)


def _file_handler(
    path: Path,
    level: int,
    formatter: logging.Formatter,
    logger: logging.Logger,
) -> None:
    handler = logging.FileHandler(path)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
