"""Entry point: python -m smartreader (or via run.sh)."""
from __future__ import annotations

import logging
import sys
import tomllib
from pathlib import Path
from typing import Callable

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
    ExplainCommand,
    RestartCommand,
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
    ExplainCommand,
    RestartCommand,
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
    common_cfg = raw_cfg.get("common", {})
    enable_pipeline_logging: bool = bool(common_cfg.get("pipeline_logging", True))
    max_openai_request_repeat_count: int = int(common_cfg.get("max_openai_request_repeat_count", 3))

    if raw_cfg.get("telegram_ui", {}).get("active"):
        logger.info("using TelegramUI")
        shared: object = TelegramSharedUIState()
        ui: UI = TelegramUI(shared)
    else:
        shared = TerminalSharedUIState()
        ui = TerminalUI(shared)

    def _on_circuit_trip(message: str) -> None:
        logger.error("LLM circuit trip: %s", message)
        if isinstance(shared, TelegramSharedUIState):
            from .ui.telegram.common import load_last_chat, run_async, async_send_text
            last_chat = load_last_chat()
            if last_chat:
                run_async(shared, async_send_text(shared, last_chat, f"⚠️ Safety shutdown: {message}"))
        else:
            print(f"Safety shutdown: {message}", file=sys.stderr)
        sys.exit(1)

    pipeline = build_pipeline(
        raw_cfg.get("pipeline", _DEFAULT_PIPELINE),
        state, config, secrets, MockSummarize(),
        global_prompt=scoring_cfg.get("openai_prompt", ""),
        global_interests_prompt=scoring_cfg.get("openai_interests_prompt", ""),
        global_merge_prompt=scoring_cfg.get("openai_merge_prompt", ""),
        global_cluster_prompt=scoring_cfg.get("openai_cluster_prompt", ""),
        global_summarize_prompt=scoring_cfg.get("openai_summarize_prompt", ""),
        enable_logging=enable_pipeline_logging,
        on_circuit_trip=_on_circuit_trip,
        max_openai_request_repeat_count=max_openai_request_repeat_count,
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

    # ── Hot-reload: pipeline factory ───────────────────────────────────────────
    def _pipeline_factory(callback: Callable[[bool, str], None]) -> None:
        """Re-read config.toml, rebuild and initialize a fresh pipeline in-place."""
        try:
            with open("config.toml", "rb") as f:
                new_raw = tomllib.load(f)
        except Exception:
            new_raw = {}
        scoring = new_raw.get("scoring", {})
        new_pipeline = build_pipeline(
            new_raw.get("pipeline", _DEFAULT_PIPELINE),
            state, config, secrets, MockSummarize(),
            global_prompt=scoring.get("openai_prompt", ""),
            global_interests_prompt=scoring.get("openai_interests_prompt", ""),
            global_merge_prompt=scoring.get("openai_merge_prompt", ""),
            global_cluster_prompt=scoring.get("openai_cluster_prompt", ""),
            global_summarize_prompt=scoring.get("openai_summarize_prompt", ""),
            enable_logging=bool(new_raw.get("common", {}).get("pipeline_logging", True)),
            on_circuit_trip=_on_circuit_trip,
            max_openai_request_repeat_count=int(new_raw.get("common", {}).get("max_openai_request_repeat_count", 3)),
        )

        def _on_pipeline_init(ok: bool, err: str) -> None:
            if ok:
                app_state.pipeline = new_pipeline
                logger.info("pipeline reloaded successfully")
            else:
                logger.error("pipeline reload failed: %s", err)
            callback(ok, err)

        new_pipeline.initialize(_on_pipeline_init)

    app_state.pipeline_factory = _pipeline_factory

    # ── Hot-reload: cron scheduler updater ────────────────────────────────────
    # Build the trigger callback once based on UI type; reuse it on every reload.
    _active_scheduler: list[CronScheduler | None] = [None]

    if isinstance(shared, TelegramSharedUIState):
        _tg = shared

        def _cron_cb() -> None:
            from .ui.telegram.common import load_last_chat
            last = load_last_chat()
            logger.info("cron: fired, last_chat=%s", last)
            if last is None:
                logger.warning("cron: no saved chat id — trigger skipped (send any message to the bot first)")
                return
            logger.info("cron: queuing trigger for chat_id=%s mode=run", last)
            _tg.trigger_queue.put({"sender_id": last, "mode": "run"})
            logger.info("cron: trigger queued (~%d items)", _tg.trigger_queue.qsize())

    elif isinstance(shared, TerminalSharedUIState):
        _term = shared

        def _cron_cb() -> None:  # type: ignore[no-redef]
            logger.info("cron: fired, queuing terminal trigger")
            _term.trigger_queue.put(True)
            logger.info("cron: terminal trigger queued")

    else:
        def _cron_cb() -> None:  # type: ignore[no-redef]
            logger.warning("cron: unrecognized UI state type, trigger ignored")

    def _cron_updater(expr: str) -> None:
        """Stop the current scheduler (if any) and start a new one for *expr*.

        Pass an empty string to stop the scheduler without starting a new one.
        """
        old = _active_scheduler[0]
        if old is not None:
            old.stop()
            _active_scheduler[0] = None
        if expr:
            sched = CronScheduler(expr, _cron_cb)
            sched.start()
            _active_scheduler[0] = sched
            logger.info("cron scheduler reloaded with expression %r", expr)
        else:
            logger.info("cron scheduler stopped")

    app_state.cron_updater = _cron_updater

    def on_init(ok: bool, err: str) -> None:
        if not ok:
            logger.error("init failed: %s", err)
            sys.exit(1)
        logger.info("init: cron update starting")
        cron_expr: str = raw_cfg.get("common", {}).get("cron_schedule", "")
        if cron_expr:
            app_state.update_cron(cron_expr)
        logger.info("init: cron updated")
        logger.info("init: coordinator run starting")
        coordinator.run(commands)
        logger.info("init: coordinator run finished")

    try:
        logger.info("init: coordinator initialize starting")
        coordinator.initialize(on_init)
        logger.info("init: coordinator initialize finished")
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
