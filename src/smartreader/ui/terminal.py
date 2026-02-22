import logging

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .._types import Callback, TriggerCallback
from ..types.content import Content
from ..types.params import TriggerParams, UIParams
from . import UI

logger = logging.getLogger(__name__)


class TerminalUI(UI):
    def __init__(self) -> None:
        self._console = Console()

    def initialize(self, params: UIParams, callback: Callback) -> None:
        self._console.print(Panel.fit("[bold cyan]SmartReader[/bold cyan]", border_style="cyan"))
        callback(True, "")

    def wait_trigger(self, callback: TriggerCallback) -> None:
        try:
            self._console.input("\n[bold]Press Enter to run[/bold] [dim](Ctrl+C to quit)[/dim]")
        except EOFError:
            return
        callback(True, "", TriggerParams(mode="ask"))

    def show_content_list(self, content: list[Content], callback: Callback) -> None:
        if not content:
            self._console.print("[dim]No content to show.[/dim]")
            callback(True, "")
            return

        table = Table(
            title="Results",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("#", style="dim", justify="right", width=3)
        table.add_column("Score", justify="right", width=6)
        table.add_column("Title", ratio=2, no_wrap=False)
        table.add_column("Source", width=18)
        table.add_column("Summary", ratio=3, no_wrap=False)

        for i, item in enumerate(content, 1):
            score_str = f"{item.score:.2f}" if item.score is not None else "—"
            text = item.summary or item.body
            summary_str = text[:200].rstrip() + "…" if len(text) > 200 else text
            table.add_row(str(i), score_str, item.title, item.source_id, summary_str)

        self._console.print(table)
        callback(True, "")

    def receive_score(self, id: str, score: float) -> None:
        pass

    def terminate(self) -> None:
        self._console.print("\n[dim]Bye.[/dim]")
