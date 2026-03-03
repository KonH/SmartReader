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
from .pipeline.adapter import build_pipeline
from .scheduler import CronScheduler
from .secrets.env import EnvSecrets
from .state.app_state import AppState
from .state.sqlite import SQLiteState
from .summarize.mock import MockSummarize
from .ui import UI
from .ui.command import UICommand
from .ui.commands import (
    AddSourceCommand,
    SetCronCommand,
    SetPromptGroupCommand,
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
    SetPromptGroupCommand,
    SetCronCommand,
]

_DEFAULT_PIPELINE: list[dict] = [
    {"type": "keyword_score", "common_weight": 1.0, "category_weight": 1.5},
    {"type": "top_n", "n": 10},
    {"type": "summarize"},
    {"type": "keyword_score", "common_weight": 1.0, "category_weight": 1.5},
    {"type": "top_n", "n": 5},
]


def main() -> None:
    state_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("state.sqlite")

    try:
        with open("config.toml", "rb") as f:
            raw_cfg = tomllib.load(f)
    except Exception:
        raw_cfg = {}

    config = TOMLConfig()
    state = SQLiteState(path=state_path)
    secrets = EnvSecrets()

    scoring_cfg = raw_cfg.get("scoring", {})

    pipeline = build_pipeline(
        raw_cfg.get("pipeline", _DEFAULT_PIPELINE),
        state, config, secrets, MockSummarize(),
        global_prompt=scoring_cfg.get("openai_prompt", ""),
        global_interests_prompt=scoring_cfg.get("openai_interests_prompt", ""),
        global_merge_prompt=scoring_cfg.get("openai_merge_prompt", ""),
        global_cluster_prompt=scoring_cfg.get("openai_cluster_prompt", ""),
        global_summarize_prompt=scoring_cfg.get("openai_summarize_prompt", ""),
    )

    source_reader = SourceReader(
        config=config,
        readers={"rss": RSSReader(), "telegram": TelegramReader()},
    )

    app_state = AppState(
        state=state,
        config=config,
        pipeline=pipeline,
        input=source_reader,
    )

    if raw_cfg.get("telegram_ui", {}).get("active"):
        logger.info("using TelegramUI")
        shared: object = TelegramSharedUIState()
        ui: UI = TelegramUI(shared)
    else:
        shared = TerminalSharedUIState()
        ui = TerminalUI(shared)

    # Instantiate only commands that the UI supports and that are in our known set
    ui_cmd_types = ui.get_commands()
    commands: list[UICommand] = [
        cmd_type(app_state, shared)
        for cmd_type in ui_cmd_types
        if any(issubclass(cmd_type, k) for k in _KNOWN_COMMAND_TYPES)
    ]

    coordinator = Coordinator(
        ui=ui,
        input=source_reader,
        config=config,
        state=state,
        pipeline=pipeline,
        secrets=secrets,
        app_state=app_state,
    )

    def on_init(ok: bool, err: str) -> None:
        if not ok:
            logger.error("init failed: %s", err)
            sys.exit(1)
        cron_expr: str = raw_cfg.get("common", {}).get("cron_schedule", "")
        if cron_expr:
            if isinstance(shared, TelegramSharedUIState):
                tg = shared

                def _tg_cron_callback() -> None:
                    from .ui.telegram.common import load_last_chat
                    last = load_last_chat()
                    logger.info("cron: _tg_cron_callback fired, last_chat=%s", last)
                    if last is None:
                        logger.warning("cron: no saved chat id — trigger skipped (send any message to the bot first)")
                        return
                    logger.info("cron: putting trigger on queue for chat_id=%s mode=run", last)
                    tg.trigger_queue.put({"sender_id": last, "mode": "run"})
                    logger.info("cron: trigger queued (queue size now ~%d)", tg.trigger_queue.qsize())

                CronScheduler(cron_expr, _tg_cron_callback).start()
            elif isinstance(shared, TerminalSharedUIState):
                term = shared

                def _term_cron_callback() -> None:
                    logger.info("cron: _term_cron_callback fired, queuing terminal trigger")
                    term.trigger_queue.put(True)
                    logger.info("cron: terminal trigger queued")

                CronScheduler(cron_expr, _term_cron_callback).start()
        coordinator.run(commands)

    try:
        coordinator.initialize(on_init)
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
