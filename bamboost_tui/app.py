from functools import partial
from rich.console import RenderableType
from rich.highlighter import ReprHighlighter
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.geometry import Offset
from textual.reactive import reactive
from textual.widgets import Footer, RichLog, Static

from bamboost_tui.collection_table import CollectionTable


class RowIndicator(Static):
    position = reactive(0)

    def render(self) -> RenderableType:
        table = self.screen.query_one(CollectionTable)
        self.offset = Offset(0, table.header_height)
        visible_rows = table.virtual_size.height

        lines = []
        for i in range(visible_rows):
            if i == self.position:
                lines.append("")
            else:
                lines.append(" ")

        return "\n".join(lines)

    def on_mount(self):
        table = self.screen.query_one(CollectionTable)
        self.watch(table, "cursor_coordinate", self.refresh_row)

    def refresh_row(self, coord: Coordinate):
        self.position = coord.row



class Bamboost(App):
    CSS_PATH = "bamboost.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True, show=False),
        Binding("ctrl+z", "suspend_process"),
        Binding("q", "quit", "quit"),
    ]

    def compose(self) -> ComposeResult:
        # RowIndicator(),
        yield Container(
            CollectionTable(
            ),
            id="table-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        def refresh(self, *_args, **_kwargs):
            self.refresh()
        self.app_resume_signal.subscribe(self, refresh)


if __name__ == "__main__":
    Bamboost(watch_css=True, ansi_color=False).run()
