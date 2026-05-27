from textual.widgets import Static
from textual.reactive import reactive

from rich.console import RenderableType


class StatusFooter(Static):
    """A Footer that also displays status update messages."""
    has_content: reactive[bool] = reactive(False)

    def on_mount(self) -> None:
        self.visible = False

    def display_status(self, content: RenderableType) -> None:
        self.update(content)
        self.has_content = True

    def clear(self) -> None:
        self.update("")
        self.has_content = False

    def watch_has_content(self, has_content: bool) -> None:
        self.visible = has_content