from textual.widgets import Static

from rich.console import RenderableType


class StatusFooter(Static):
    """A Footer that also displays status update messages."""

    def display(self, content: RenderableType) -> None:
        self.update(content)

    def clear(self) -> None:
        self.update("")