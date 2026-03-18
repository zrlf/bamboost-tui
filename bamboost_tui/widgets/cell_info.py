from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class CellContentScreen(ModalScreen):
    """A modal screen to display full cell content."""

    BINDINGS = [
        Binding("escape,q,i", "dismiss", "Dismiss", show=False),
    ]

    def __init__(self, content: object, column_name: str):
        super().__init__()
        self.content = content
        self.column_name = column_name

    def compose(self) -> ComposeResult:
        with Vertical(id="cell-content-container"):
            yield Label(
                f"[bold]{self.column_name}[/bold] - [dim] q / i / esc to close again",
                id="cell-content-label",
            )
            with ScrollableContainer(id="cell-content-text-container"):
                yield Static(str(self.content), id="cell-content-text")
