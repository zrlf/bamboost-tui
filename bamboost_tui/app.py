from rich.console import RenderableType
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.css.query import NoMatches
from textual.geometry import Offset
from textual.reactive import reactive
from textual.theme import BUILTIN_THEMES, Theme
from textual.widgets import Footer, HelpPanel, RichLog, Rule, Static

from bamboost_tui._commandline import CommandLine
from bamboost_tui.collection_table import CollectionTable

ansi_theme = Theme(
    name="ansi",
    primary="ansi_blue",
    secondary="ansi_magenta",
    accent="ansi_yellow",
    foreground="ansi_white",
    background="ansi_default",
    success="ansi_green",
    warning=BUILTIN_THEMES["textual-dark"].warning,
    error="ansi_red",
    surface="ansi_black",
    panel="ansi_bright_black",
    boost="ansi_green",
    dark=True,
)


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
        Binding("ctrl+q", "pop_screen", "quit screen"),
        Binding("?", "toggle_help_panel", "Show help"),
    ]
    COMMAND_PALETTE_BINDING = "ctrl+o"

    def compose(self) -> ComposeResult:
        yield Container(
            CollectionTable(),
            id="table-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        if ansi_colors_set := self.ansi_color:
            self.register_theme(ansi_theme)
            self.ansi_theme.ansi_colors
            self.theme = "ansi"
            self.ansi_color = ansi_colors_set

        def refresh(self, *_args, **_kwargs):
            self.refresh()

        self.app_resume_signal.subscribe(self, refresh)

    def action_toggle_help_panel(self):
        try:
            self.query_one(HelpPanel).remove()
        except NoMatches:
            self.action_show_help_panel()


if __name__ == "__main__":
    Bamboost(watch_css=True, ansi_color=False).run()
