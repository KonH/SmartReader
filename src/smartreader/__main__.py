"""Entry point: python -m smartreader (or via run.sh)."""
from __future__ import annotations

import logging
import sys
import tomllib

from ._logging import setup as setup_logging
from .config.toml import TOMLConfig
from .input.rss import RSSReader
from .input.source_reader import SourceReader
from .input.telegram import TelegramReader
from .main import Coordinator
from .scoring.adapter import ScoringAdapter
from .secrets.env import EnvSecrets
from .state.app_state import AppState
from .state.sqlite import SQLiteState
from .summarize.mock import MockSummarize
from .summarize.trim import TrimSummarize
from .ui import UI
from .ui.telegram import TelegramUI
from .ui.terminal import TerminalUI

setup_logging()

logger = logging.getLogger(__name__)


def _pick_ui() -> UI:
    """Read config.toml early to decide which UI to instantiate."""
    try:
        with open("config.toml", "rb") as f:
            cfg = tomllib.load(f)
    except (FileNotFoundError, Exception):
        cfg = {}
    if cfg.get("telegram_ui", {}).get("active"):
        logger.info("using TelegramUI")
        return TelegramUI()
    return TerminalUI()


def main() -> None:
    from pathlib import Path as _Path
    state_path = _Path(sys.argv[1]) if len(sys.argv) > 1 else _Path("state.sqlite")
    config = TOMLConfig()
    state = SQLiteState(path=state_path)
    app_state = AppState(state)

    shared_common: dict[str, float] = {}
    shared_category: dict[str, dict[str, float]] = {}

    coordinator = Coordinator(
        ui=_pick_ui(),
        input=SourceReader(
            config=config,
            readers={
                "rss": RSSReader(),
                "telegram": TelegramReader(),
            },
        ),
        config=config,
        state=state,
        scoring=ScoringAdapter(config, state, shared_common, shared_category),
        summarize=TrimSummarize(MockSummarize(), config),
        secrets=EnvSecrets(),
        app_state=app_state,
    )

    def on_init(ok: bool, err: str) -> None:
        if not ok:
            logger.error("init failed: %s", err)
            sys.exit(1)
        coordinator.run()

    try:
        coordinator.initialize(on_init)
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
