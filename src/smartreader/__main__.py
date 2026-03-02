"""Entry point: python -m smartreader (or via run.sh)."""
from __future__ import annotations

import logging
import sys
import tomllib
from pathlib import Path

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
from .ui.command import UICommand
from .ui.commands import (
    AddSourceCommand,
    SetInterestsPromptCommand,
    SetPromptCommand,
    ShowContentCommand,
    ShowLogsCommand,
    ShowStateCommand,
    SkipWordCommand,
)
from .ui.telegram import TelegramUI
from .ui.telegram.state import TelegramSharedUIState
from .ui.terminal import TerminalUI
from .ui.terminal.state import TerminalSharedUIState

setup_logging()

logger = logging.getLogger(__name__)

# Ordered list of known abstract command types (defines what this app supports)
_KNOWN_COMMAND_TYPES: list[type[UICommand]] = [
    ShowContentCommand,
    AddSourceCommand,
    ShowLogsCommand,
    ShowStateCommand,
    SkipWordCommand,
    SetPromptCommand,
    SetInterestsPromptCommand,
]


def _make_shared_ui_state_and_ui() -> tuple[object, UI]:
    """Read config.toml early to decide which UI/shared state to create."""
    try:
        with open("config.toml", "rb") as f:
            cfg = tomllib.load(f)
    except Exception:
        cfg = {}

    if cfg.get("telegram_ui", {}).get("active"):
        logger.info("using TelegramUI")
        shared = TelegramSharedUIState()
        ui: UI = TelegramUI(shared)
    else:
        shared = TerminalSharedUIState()
        ui = TerminalUI(shared)

    return shared, ui


def main() -> None:
    state_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("state.sqlite")

    config = TOMLConfig()
    state = SQLiteState(path=state_path)

    shared_common: dict[str, float] = {}
    shared_category: dict[str, dict[str, float]] = {}

    secrets = EnvSecrets()
    scoring = ScoringAdapter(config, state, shared_common, shared_category, secrets=secrets)
    summarize = TrimSummarize(MockSummarize(), config)
    source_reader = SourceReader(
        config=config,
        readers={"rss": RSSReader(), "telegram": TelegramReader()},
    )

    app_state = AppState(
        state=state,
        config=config,
        scoring=scoring,
        summarize=summarize,
        input=source_reader,
    )

    shared_ui_state, ui = _make_shared_ui_state_and_ui()

    # Instantiate only commands that the UI supports and that are in our known set
    ui_cmd_types = ui.get_commands()
    commands: list[UICommand] = [
        cmd_type(app_state, shared_ui_state)
        for cmd_type in ui_cmd_types
        if any(issubclass(cmd_type, k) for k in _KNOWN_COMMAND_TYPES)
    ]

    coordinator = Coordinator(
        ui=ui,
        input=source_reader,
        config=config,
        state=state,
        scoring=scoring,
        summarize=summarize,
        secrets=secrets,
        app_state=app_state,
    )

    def on_init(ok: bool, err: str) -> None:
        if not ok:
            logger.error("init failed: %s", err)
            sys.exit(1)
        coordinator.run(commands)

    try:
        coordinator.initialize(on_init)
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
