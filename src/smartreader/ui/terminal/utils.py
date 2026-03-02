"""Rendering helpers for the Terminal UI."""
from __future__ import annotations

from datetime import datetime

from rich import box
from rich.console import Console
from rich.table import Table

from ...types.app_state import AppStateData
from ...types.content import Content


def render_content_table(content: list[Content], console: Console) -> None:
    if not content:
        console.print("[dim]No content to show.[/dim]")
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
        summary_str = text
        table.add_row(str(i), date_str, score_str, item.title, item.source_id, summary_str)

    console.print(table)


def render_state(data: AppStateData, console: Console) -> None:
    console.print(f"\n[bold]Sources ({len(data.source_states)}):[/bold]")
    if data.source_states:
        for entry in data.source_states:
            status = "active" if entry.active else "inactive"
            ts_str = (
                datetime.fromtimestamp(entry.last_read_ts).strftime("%b %d, %Y %H:%M")
                if entry.last_read_ts else "never"
            )
            console.print(f"  [{entry.source_id}]  {status}     last_read: {ts_str}")
    else:
        console.print("  [dim]No sources tracked yet.[/dim]")

    n_common = len(data.common_interests)
    console.print(f"\n[bold]Common interests ({n_common} keywords):[/bold]")
    if data.common_interests:
        for k, v in data.common_interests.items():
            console.print(f"  - {k}: {v:.1f}")
    else:
        console.print("  [dim]No interests yet.[/dim]")

    for cat, keywords in data.category_interests.items():
        console.print(f"\n[bold]Category: {cat} ({len(keywords)} keywords)[/bold]")
        for k, v in keywords.items():
            console.print(f"  - {k}: {v:.1f}")


def collect_feedback(content: list[Content], console: Console) -> list[tuple[str, bool]]:
    """Prompt user for upvote/downvote on displayed items."""
    console.print(
        "\n[dim]Rate items: [bold]u[/bold]<n> upvote · [bold]d[/bold]<n> downvote · "
        "[bold]Enter[/bold] to finish[/dim]"
    )
    idx_to_id = {str(i): item.id for i, item in enumerate(content, 1)}
    feedback: list[tuple[str, bool]] = []

    while True:
        try:
            raw = console.input("[dim]>[/dim] ").strip()
        except EOFError:
            break
        if not raw:
            break
        action, num_str = raw[0].lower(), raw[1:]
        if action not in ("u", "d") or not num_str.isdigit():
            console.print("[yellow]Use u<n> or d<n>, e.g. u3 to upvote #3[/yellow]")
            continue
        item_id = idx_to_id.get(num_str)
        if item_id is None:
            console.print(f"[yellow]No item #{num_str}[/yellow]")
            continue
        upvote = action == "u"
        feedback.append((item_id, upvote))
        verb = "[green]Upvoted[/green]" if upvote else "[red]Downvoted[/red]"
        console.print(f"{verb} #{num_str}")

    return feedback
