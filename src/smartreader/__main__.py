"""Entry point: python -m smartreader (or via run.sh)."""
from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)


def main() -> None:
    # Wire concrete implementations here once available, e.g.:
    #
    #   from smartreader.impl.ui_terminal import TerminalUI
    #   from smartreader.impl.input_rss import RSSInput
    #   from smartreader.impl.config_toml import TOMLConfig
    #   from smartreader.impl.state_sqlite import SQLiteState
    #   from smartreader.impl.scoring_keyword import KeywordScoring
    #   from smartreader.impl.summarize_openai import OpenAISummarize
    #   from smartreader.impl.secrets_env import EnvSecrets
    #   from smartreader.main import Coordinator
    #
    #   coordinator = Coordinator(
    #       ui=TerminalUI(),
    #       input=RSSInput(),
    #       config=TOMLConfig(),
    #       state=SQLiteState(),
    #       scoring=KeywordScoring(),
    #       summarize=OpenAISummarize(),
    #       secrets=EnvSecrets(),
    #   )
    #
    #   def on_init(ok: bool, err: str) -> None:
    #       if not ok:
    #           logger.error("init failed: %s", err)
    #           sys.exit(1)
    #       coordinator.run()
    #
    #   coordinator.initialize(on_init)

    print("No concrete implementations wired yet. See src/smartreader/__main__.py.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
