from __future__ import annotations

from typing import TYPE_CHECKING

from ...commands import SetPromptCommand
from ..state import TerminalSharedUIState

if TYPE_CHECKING:
    from ....state.app_state import AppState


class TerminalSetPromptCommand(SetPromptCommand):
    def __init__(self, app_state: "AppState", shared_ui_state: TerminalSharedUIState) -> None:
        super().__init__(app_state, shared_ui_state)
        self._terminal = shared_ui_state

    @property
    def control_title(self) -> str:
        return "prompt"

    def execute(self) -> None:
        console = self._terminal.console
        console.print(
            "[bold]EVAL prompt scope[/bold] "
            "[dim](stage > channel > category > global)[/dim]"
        )
        console.print("  1. Global")
        console.print("  2. Category")
        console.print("  3. Channel")
        try:
            choice = console.input("Select (1-3, Enter to cancel): ").strip()
        except EOFError:
            return
        if choice == "1":
            self._edit_global()
        elif choice == "2":
            self._edit_mapped("category_prompts", "category", self._list_categories())
        elif choice == "3":
            self._edit_mapped("channel_prompts", "channel", self._list_channels())

    def _edit_global(self) -> None:
        console = self._terminal.console
        current = self._read_current_prompt()
        if current:
            console.print("[dim]Current global scoring prompt:[/dim]")
            console.print(current)
            console.print()
        try:
            prompt = console.input("New global scoring prompt (Enter to keep current): ").strip()
        except EOFError:
            return
        if prompt:
            self._set_prompt_and_restart(prompt)

    def _edit_mapped(self, map_key: str, label: str, keys: list[str]) -> None:
        console = self._terminal.console
        prompts = self._read_prompt_map(map_key)
        if keys:
            console.print(f"[bold]Select {label}:[/bold]")
            for i, key in enumerate(keys, start=1):
                mark = " [green]✓[/green]" if key in prompts else ""
                console.print(f"  {i}. {key}{mark}")
            console.print(f"  0. Enter new {label} name")
        else:
            console.print(f"[dim]No {label} entries yet — enter a new name.[/dim]")
        try:
            raw = console.input(f"{label.capitalize()} number or name (Enter to cancel): ").strip()
        except EOFError:
            return
        if not raw:
            return
        entry_key = ""
        if raw.isdigit():
            idx = int(raw)
            if idx == 0 or not keys:
                try:
                    entry_key = console.input(f"New {label} name: ").strip()
                except EOFError:
                    return
            elif 1 <= idx <= len(keys):
                entry_key = keys[idx - 1]
            else:
                console.print("[red]Invalid selection[/red]")
                return
        else:
            entry_key = raw
        if not entry_key:
            return

        current = prompts.get(entry_key, "")
        if current:
            console.print(f"[dim]Current {label} prompt for {entry_key}:[/dim]")
            console.print(current)
            console.print()
        else:
            console.print(f"[dim]No custom {label} prompt for {entry_key} yet.[/dim]")
        try:
            prompt = console.input(
                f"New {label} scoring prompt (Enter to keep, '-' to clear): "
            ).strip()
        except EOFError:
            return
        if prompt == "-":
            self._set_mapped_prompt_and_restart(map_key, entry_key, "")
            console.print(f"[green]Cleared {label} prompt for {entry_key}[/green]")
        elif prompt:
            self._set_mapped_prompt_and_restart(map_key, entry_key, prompt)
            console.print(f"[green]Updated {label} prompt for {entry_key}[/green]")
