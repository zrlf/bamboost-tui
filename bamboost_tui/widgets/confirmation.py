from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ModalPrompt(ModalScreen[bool]):
    """Modal to prompt the user for confirmation."""

    BINDINGS = [
        Binding("l, right", "app.focus_next", "Focus Next", show=False),
        Binding("h, left", "app.focus_previous", "Focus Previous", show=False),
        Binding("escape", "dismiss", "Dismiss", show=False),
    ]

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-prompt"):
            yield Label(self.label, id="modal-prompt-label")
            with Horizontal():
                yield Button("Yes", variant="error", id="modal-prompt-yes")
                yield Button("No", variant="primary", id="modal-prompt-no")

    def on_mount(self) -> None:
        self.query_exactly_one("#modal-prompt-no").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-prompt-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)
