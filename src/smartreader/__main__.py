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
    BanWordCommand,
    ExplainCommand,
    RestartCommand,
    SetCronCommand,
    SetPromptGroupCommand,
    ShowConfigCommand,
    ShowContentCommand,
    ShowLogsCommand,
    ShowStateCommand,
    SkipWordCommand,
    SourcesGroupCommand,
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
    SourcesGroupCommand,
    AddSourceCommand,
    BanWordCommand,
    ExplainCommand,
    RestartCommand,
    ShowLogsCommand,
    ShowStateCommand,
    ShowConfigCommand,
    SkipWordCommand,
    SetPromptGroupCommand,
    SetCronCommand,
]

_DEFAULT_PIPELINE: list[dict] = [
    {"type": "keyword_score", "common_weight": 1.0, "category_weight": 1.5},
    {"type": "normalize_score"},
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

    def _prompt_map(raw: object) -> dict[str, str]:
        if not isinstance(raw, dict):
            return {}
        return {str(k): str(v) for k, v in raw.items() if str(v).strip()}

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
        category_prompts=_prompt_map(scoring_cfg.get("category_prompts")),
        channel_prompts=_prompt_map(scoring_cfg.get("channel_prompts")),
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
            category_prompts=_prompt_map(scoring.get("category_prompts")),
            channel_prompts=_prompt_map(scoring.get("channel_prompts")),
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
    # One CronScheduler per schedule (global ALL + optional per-category).
    _active_schedulers: list[CronScheduler] = []

    def _make_cron_callback(category: str | None) -> Callable[[], None]:
        label = category if category is not None else "ALL"
        if isinstance(shared, TelegramSharedUIState):
            _tg = shared

            def _cron_cb() -> None:
                from .ui.telegram.common import load_last_chat
                last = load_last_chat()
                logger.info("cron[%s]: fired, last_chat=%s", label, last)
                if last is None:
                    logger.warning(
                        "cron[%s]: no saved chat id — trigger skipped "
                        "(send any message to the bot first)",
                        label,
                    )
                    return
                logger.info(
                    "cron[%s]: queuing trigger for chat_id=%s mode=run category=%r",
                    label, last, category,
                )
                _tg.trigger_queue.put({
                    "sender_id": last,
                    "mode": "run",
                    "category": category,
                })
                logger.info("cron[%s]: trigger queued (~%d items)", label, _tg.trigger_queue.qsize())

            return _cron_cb

        if isinstance(shared, TerminalSharedUIState):
            _term = shared

            def _cron_cb() -> None:
                logger.info("cron[%s]: fired, queuing terminal trigger category=%r", label, category)
                _term.trigger_queue.put(category)
                logger.info("cron[%s]: terminal trigger queued", label)

            return _cron_cb

        def _cron_cb() -> None:
            logger.warning("cron[%s]: unrecognized UI state type, trigger ignored", label)

        return _cron_cb

    def _collect_cron_schedules(common: dict) -> list[tuple[str | None, str]]:
        """Return (category_or_None, expr) pairs from the common config section."""
        schedules: list[tuple[str | None, str]] = []
        global_expr = str(common.get("cron_schedule", "") or "").strip()
        if global_expr:
            schedules.append((None, global_expr))
        cat_sched = common.get("category_schedules", {})
        if isinstance(cat_sched, dict):
            for cat, expr in cat_sched.items():
                expr_s = str(expr or "").strip()
                if cat and expr_s:
                    schedules.append((str(cat), expr_s))
        return schedules

    def _cron_updater() -> None:
        """Stop all running schedulers and restart from current config."""
        for old in _active_schedulers:
            old.stop()
        _active_schedulers.clear()

        common: dict = {}
        if app_state.config is not None:
            def on_common(ok: bool, err: str, val: object) -> None:
                nonlocal common
                if ok and isinstance(val, dict):
                    common = val

            app_state.config.read_value("common", on_common)
        else:
            common = dict(raw_cfg.get("common", {}))

        schedules = _collect_cron_schedules(common)
        if not schedules:
            logger.info("cron: all schedulers stopped (no schedules configured)")
            return

        for category, expr in schedules:
            label = category if category is not None else "ALL"
            sched = CronScheduler(expr, _make_cron_callback(category), label=label)
            sched.start()
            _active_schedulers.append(sched)
            logger.info("cron: started scheduler label=%s expr=%r", label, expr)

    app_state.cron_updater = _cron_updater

    def on_init(ok: bool, err: str) -> None:
        if not ok:
            logger.error("init failed: %s", err)
            sys.exit(1)
        logger.info("init: cron update starting")
        app_state.update_cron()
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
