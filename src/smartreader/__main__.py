"""Entry point: python -m smartreader (or via run.sh)."""
from __future__ import annotations

import logging
import sys

from ._logging import setup as setup_logging
from .config.toml import TOMLConfig
from .input.rss import RSSReader
from .input.source_reader import SourceReader
from .main import Coordinator
from .scoring.adapter import ScoringAdapter
from .scoring.keyword import L1KeywordScoring, L2KeywordScoring
from .secrets.mock import MockSecrets
from .state.sqlite import SQLiteState
from .summarize.mock import MockSummarize
from .ui.terminal import TerminalUI

setup_logging()

logger = logging.getLogger(__name__)


def main() -> None:
    config = TOMLConfig()
    state = SQLiteState()

    shared_common: dict[str, float] = {}
    shared_category: dict[str, dict[str, float]] = {}

    coordinator = Coordinator(
        ui=TerminalUI(),
        input=SourceReader(config=config, readers={"rss": RSSReader()}),
        config=config,
        state=state,
        scoring=ScoringAdapter(
            l1=L1KeywordScoring(state, config, shared_common, shared_category),
            l2=L2KeywordScoring(state, config, shared_common, shared_category),
        ),
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
