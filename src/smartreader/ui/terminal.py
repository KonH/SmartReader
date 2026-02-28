import logging
from datetime import datetime

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .._types import Callback, FeedbackListCallback, NewSourceCallback, TriggerCallback
from ..types.content import Content
from ..types.params import NewSourceParams, TriggerParams, UIParams
from ..types.values import StateValue
from . import UI

logger = logging.getLogger(__name__)


class TerminalUI(UI):
    def __init__(self) -> None:
        self._console = Console()

    def initialize(self, params: UIParams, callback: Callback) -> None:
        self._console.print(Panel.fit("[bold cyan]SmartReader[/bold cyan]", border_style="cyan"))
        callback(True, "")

    def wait_trigger(self, categories: list[str], callback: TriggerCallback) -> None:
        try:
            cmd = self._console.input(
                "\n[bold]Press Enter to run[/bold], "
                "[dim]'add' to add a source, 'logs' to view logs, 'state' to view state[/dim] "
                "[dim](Ctrl+C to quit)[/dim]: "
            ).strip().lower()
        except EOFError:
            return

        if cmd == "add":
            callback(True, "", TriggerParams(mode="add", category=None))
            return
        if cmd == "logs":
            callback(True, "", TriggerParams(mode="logs", category=None))
            return
        if cmd == "state":
            callback(True, "", TriggerParams(mode="state", category=None))
            return

        category: str | None = None
        if categories:
            options = ["ALL"] + categories
            self._console.print("\n[bold]Categories:[/bold]")
            for i, cat in enumerate(options):
                hint = " [dim](default)[/dim]" if i == 0 else ""
                self._console.print(f"  [dim]{i}.[/dim] {cat}{hint}")
            try:
                raw = self._console.input(
                    "[bold]Select category (number), then Enter to run[/bold] [dim](Ctrl+C to quit)[/dim]: "
                ).strip()
            except EOFError:
                return
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx < len(options):
                    category = options[idx]
        callback(True, "", TriggerParams(mode="ask", category=category))

    def prompt_new_source(self, callback: NewSourceCallback) -> None:
        try:
            source_type = self._console.input(
                "[bold]Source type[/bold] [dim](rss/telegram)[/dim]: "
            ).strip().lower()
            if source_type not in ("rss", "telegram"):
                self._console.print("[yellow]Invalid type; expected 'rss' or 'telegram'[/yellow]")
                callback(True, "", None)
                return

            external_id = self._console.input(
                "[bold]Source URL or channel ID:[/bold] "
            ).strip()
            if not external_id:
                self._console.print("[yellow]External ID cannot be empty[/yellow]")
                callback(True, "", None)
                return

            name = self._console.input(
                "[bold]Source name[/bold] [dim](config key, no spaces)[/dim]: "
            ).strip()
            if not name or " " in name:
                self._console.print("[yellow]Name must be non-empty and have no spaces[/yellow]")
                callback(True, "", None)
                return

            category_raw = self._console.input(
                "[bold]Category[/bold] [dim](optional, Enter to skip)[/dim]: "
            ).strip()
            category: str | None = category_raw if category_raw else None
        except EOFError:
            callback(True, "", None)
            return

        callback(True, "", NewSourceParams(
            name=name,
            source_type=source_type,
            external_id=external_id,
            category=category,
        ))

    def show_logs(self, lines: list[str], callback: Callback) -> None:
        for line in lines:
            self._console.print(line)
        callback(True, "")

    def show_state(self, data: dict[str, StateValue], callback: Callback) -> None:
        import json
        if not data:
            self._console.print("[dim]State is empty.[/dim]")
        else:
            for key in sorted(data):
                self._console.print(f"\n[bold cyan]{key}[/bold cyan]")
                self._console.print(json.dumps(data[key], indent=2, ensure_ascii=False))
        callback(True, "")

    def show_content_list(self, content: list[Content], callback: FeedbackListCallback) -> None:
        if not content:
            self._console.print("[dim]No content to show.[/dim]")
            callback(True, "", [])
            return

        table = Table(
            title="Results",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("#", style="dim", justify="right", width=3)
        table.add_column("Date", width=12)
        table.add_column("Score", justify="right", width=6)
        table.add_column("Title", ratio=2, no_wrap=False)
        table.add_column("Source", width=18)
        table.add_column("Summary", ratio=3, no_wrap=False)

        for i, item in enumerate(content, 1):
            score_str = f"{item.score:.2f}" if item.score is not None else "—"
            date_str = datetime.fromtimestamp(item.published_ts).strftime("%b %d %H:%M")
            text = item.summary or item.body
            summary_str = text[:200].rstrip() + "…" if len(text) > 200 else text
            table.add_row(str(i), date_str, score_str, item.title, item.source_id, summary_str)

        self._console.print(table)

        feedback = self._collect_feedback(content)
        callback(True, "", feedback)

    def _collect_feedback(self, content: list[Content]) -> list[tuple[str, bool]]:
        """Prompt user for upvote/downvote on displayed items."""
        self._console.print(
            "\n[dim]Rate items: [bold]u[/bold]<n> upvote · [bold]d[/bold]<n> downvote · "
            "[bold]Enter[/bold] to finish[/dim]"
        )
        idx_to_id = {str(i): item.id for i, item in enumerate(content, 1)}
        feedback: list[tuple[str, bool]] = []

        while True:
            try:
                raw = self._console.input("[dim]>[/dim] ").strip()
            except EOFError:
                break
            if not raw:
                break
            action, num_str = raw[0].lower(), raw[1:]
            if action not in ("u", "d") or not num_str.isdigit():
                self._console.print("[yellow]Use u<n> or d<n>, e.g. u3 to upvote #3[/yellow]")
                continue
            item_id = idx_to_id.get(num_str)
            if item_id is None:
                self._console.print(f"[yellow]No item #{num_str}[/yellow]")
                continue
            upvote = action == "u"
            feedback.append((item_id, upvote))
            verb = "[green]Upvoted[/green]" if upvote else "[red]Downvoted[/red]"
            self._console.print(f"{verb} #{num_str}")

        return feedback

    def receive_score(self, id: str, score: float) -> None:
        pass

    def terminate(self) -> None:
        self._console.print("\n[dim]Bye.[/dim]")
