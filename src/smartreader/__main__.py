"""Entry point: python -m smartreader (or via run.sh)."""
from __future__ import annotations

import logging
import sys

from ._logging import setup as setup_logging
from .config.toml import TOMLConfig
from .input.mock import MockInput
from .main import Coordinator
from .scoring.mock import MockScoring
from .secrets.mock import MockSecrets
from .state.sqlite import SQLiteState
from .summarize.mock import MockSummarize
from .ui.terminal import TerminalUI

setup_logging()

logger = logging.getLogger(__name__)


def main() -> None:
    coordinator = Coordinator(
        ui=TerminalUI(),
        input=MockInput(),
        config=TOMLConfig(),
        state=SQLiteState(),
        scoring=MockScoring(),
        summarize=MockSummarize(),
        secrets=MockSecrets(),
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
