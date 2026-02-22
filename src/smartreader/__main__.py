"""Entry point: python -m smartreader (or via run.sh)."""
from __future__ import annotations

import logging
import sys

from ._logging import setup as setup_logging
from .config.mock import MockConfig
from .input.mock import MockInput
from .main import Coordinator
from .scoring.mock import MockScoring
from .secrets.mock import MockSecrets
from .state.mock import MockState
from .summarize.mock import MockSummarize
from .ui.mock import MockUI

setup_logging()

logger = logging.getLogger(__name__)


def main() -> None:
    coordinator = Coordinator(
        ui=MockUI(),
        input=MockInput(),
        config=MockConfig(),
        state=MockState(),
        scoring=MockScoring(),
        summarize=MockSummarize(),
        secrets=MockSecrets(),
    )

    def on_init(ok: bool, err: str) -> None:
        if not ok:
            logger.error("init failed: %s", err)
            sys.exit(1)
        coordinator.run()

    coordinator.initialize(on_init)


if __name__ == "__main__":
    main()
