"""Terminal (stdout/stdin) UI implementation."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from ..._types import Callback
from ...types.params import UIParams
from ..command import UICommand
from ..commands import ShowContentCommand
from .commands import (
    TerminalAddSourceCommand,
    TerminalSetInterestsPromptCommand,
    TerminalSetPromptCommand,
    TerminalShowContentCommand,
    TerminalShowLogsCommand,
    TerminalShowStateCommand,
    TerminalSkipWordCommand,
)
from .state import TerminalSharedUIState
from .. import UI

if TYPE_CHECKING:
    from ...state.app_state import AppState

logger = logging.getLogger(__name__)

_COMMAND_TYPES: list[type[UICommand]] = [
    TerminalShowContentCommand,
    TerminalAddSourceCommand,
    TerminalShowLogsCommand,
    TerminalShowStateCommand,
    TerminalSkipWordCommand,
    TerminalSetPromptCommand,
    TerminalSetInterestsPromptCommand,
]


class TerminalUI(UI):
    def __init__(self, shared_ui_state: TerminalSharedUIState) -> None:
        self._shared = shared_ui_state
        self._running = False

    def initialize(self, params: UIParams, callback: Callback) -> None:
        self._shared.console.print(
            Panel.fit("[bold cyan]SmartReader[/bold cyan]", border_style="cyan")
        )
        callback(True, "")

    def get_commands(self) -> list[type[UICommand]]:
        return list(_COMMAND_TYPES)

    def loop(self, commands: list[UICommand]) -> None:
        # Retrieve app_state from the ShowContent command (always present)
        app_state: AppState | None = None
        for cmd in commands:
            if isinstance(cmd, ShowContentCommand):
                app_state = cmd._app_state
                break

        cmd_by_title = {cmd.control_title.lower(): cmd for cmd in commands}
        show_cmd = cmd_by_title.get("show")
        skip_cmd = cmd_by_title.get("skip")

        self._running = True
        while self._running:
            # Refresh categories from config
            categories: list[str] = []
            if app_state is not None and app_state.config is not None:
                cats_result: list[list[str]] = [[]]

                def on_sources(ok: bool, err: str, val: object) -> None:
                    if ok and isinstance(val, dict):
                        cats_result[0] = _extract_categories(val)

                app_state.config.read_value("sources", on_sources)
                categories = cats_result[0]
                if app_state is not None:
                    app_state.categories = categories

            titles = " / ".join(
                cmd.control_title for cmd in commands if cmd.control_title != "show"
            )
            try:
                raw = self._shared.console.input(
                    f"\n[bold]Press Enter to run[/bold], "
                    f"[dim]'{titles}' or 'skip <word>'[/dim] "
                    f"[dim](Ctrl+C to quit)[/dim]: "
                ).strip().lower()
            except EOFError:
                break

            if not raw:
                # Category selection then show
                category = _pick_category(categories, self._shared.console)
                if app_state is not None:
                    app_state.trigger_category = category
                if show_cmd is not None:
                    show_cmd.execute()
                continue

            # "skip <word>" shorthand (bypasses the prompt inside SkipWordCommand)
            if raw.startswith("skip "):
                word = raw[5:].strip()
                if word and skip_cmd is not None:
                    skip_cmd._add_skip_and_restart(word)  # type: ignore[attr-defined]
                continue

            if raw in cmd_by_title:
                cmd_by_title[raw].execute()
            else:
                self._shared.console.print(f"[yellow]Unknown command '{raw}'[/yellow]")

    def terminate(self) -> None:
        self._running = False
        self._shared.console.print("\n[dim]Bye.[/dim]")


def _pick_category(categories: list[str], console: Console) -> str | None:
    if not categories:
        return None
    options = ["ALL"] + categories
    console.print("\n[bold]Categories:[/bold]")
    for i, cat in enumerate(options):
        hint = " [dim](default)[/dim]" if i == 0 else ""
        console.print(f"  [dim]{i}.[/dim] {cat}{hint}")
    try:
        raw = console.input(
            "[bold]Select category (number), then Enter to run[/bold] "
            "[dim](Ctrl+C to quit)[/dim]: "
        ).strip()
    except EOFError:
        return None
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx < len(options):
            return options[idx]
    return None


def _extract_categories(sources_val: dict) -> list[str]:
    cats: set[str] = set()
    for entries in sources_val.values():
        for entry in (entries if isinstance(entries, list) else [entries]):
            cat = entry.get("category") if isinstance(entry, dict) else None
            if cat:
                cats.add(cat)
    return sorted(cats)
