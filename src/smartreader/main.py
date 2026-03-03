"""Main Coordinator — initializes all modules in dependency order."""
from __future__ import annotations

import logging

from ._types import Callback, LiveFeedbackHandler
from .config import Config
from .input import Input
from .pipeline.adapter import PipelineAdapter
from .secrets import Secrets
from .state import State
from .state.app_state import AppState
from .types.content import Content
from .types.params import ConfigParams, SecretsParams, UIParams
from .ui import UI
from .ui.command import UICommand

logger = logging.getLogger(__name__)


class Coordinator:
    """Initializes all modules in dependency order and delegates the loop to the UI."""

    def __init__(
        self,
        ui: UI,
        input: Input,
        config: Config,
        state: State,
        pipeline: PipelineAdapter,
        secrets: Secrets,
        app_state: AppState,
    ) -> None:
        self._ui = ui
        self._input = input
        self._config = config
        self._state = state
        self._pipeline = pipeline
        self._secrets = secrets
        self._app_state = app_state

    # ── Initialization ────────────────────────────────────────────────────────

    def initialize(self, callback: Callback) -> None:
        """Initialize all modules: secrets → config → state → pipeline → ui → input."""
        logger.info("initializing secrets")
        self._secrets.initialize(
            SecretsParams(),
            lambda ok, err: self._init_config(ok, err, callback),
        )

    def _init_config(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"secrets: {err}")
            return
        logger.info("initializing config")
        self._config.load(ConfigParams(), lambda ok2, err2: self._init_state(ok2, err2, callback))

    def _init_state(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"config: {err}")
            return
        logger.info("initializing state")
        self._state.load(ConfigParams(), lambda ok2, err2: self._init_pipeline(ok2, err2, callback))

    def _init_pipeline(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"state: {err}")
            return
        logger.info("initializing pipeline")
        self._pipeline.initialize(lambda ok2, err2: self._init_ui(ok2, err2, callback))

    def _live_feedback(self, content: Content, upvote: bool) -> None:
        """Handle asynchronous inline vote from TelegramUI."""
        logger.info("live feedback for %r: upvote=%s", content.id, upvote)
        self._pipeline.update_score(content, upvote, lambda ok, err: (
            logger.error("live feedback update_score error for %s: %s", content.id, err) if not ok else None
        ))

    def _init_ui(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"pipeline: {err}")
            return
        logger.info("initializing ui")
        self._ui.initialize(
            UIParams(live_feedback=self._live_feedback),
            lambda ok2, err2: self._init_input(ok2, err2, callback),
        )

    def _init_input(self, ok: bool, err: str, callback: Callback) -> None:
        if not ok:
            callback(False, f"ui: {err}")
            return
        logger.info("initializing input")
        self._input.initialize(self._secrets, self._config, callback)

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, commands: list[UICommand]) -> None:
        """Hand off to the UI's loop with the pre-built command list."""
        logger.info("coordinator: starting ui loop")
        self._ui.loop(commands)

    def stop(self) -> None:
        """Terminate the UI."""
        logger.info("coordinator stopping")
        self._ui.terminate()
