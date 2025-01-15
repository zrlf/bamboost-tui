from bamboost import config
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.css.query import NoMatches
from textual.theme import BUILTIN_THEMES, Theme
from textual.widgets import Footer, HelpPanel

from bamboost_tui.collection_table import CollectionTable, ScreenCollection

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
    variables={
        "input-cursor-background": "ansi_black",
        "input-cursor-foreground": "ansi_white",
        "block-cursor-background": "ansi_black",
        "block-cursor-foreground": "ansi_white",
        # "block-hover-background": "$surface",
    },
)


class Bamboost(App):
    CSS_PATH = "bamboost.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True, show=False),
        Binding("ctrl+z", "suspend_process"),
        Binding("q", "pop_screen", "quit screen"),
        Binding("?", "toggle_help_panel", "Show help"),
    ]
    COMMAND_PALETTE_BINDING = "ctrl+o"

    def on_mount(self) -> None:
        if ansi_colors_set := self.ansi_color:
            self.register_theme(ansi_theme)
            self.ansi_theme.ansi_colors
            self.theme = "ansi"
            self.ansi_color = ansi_colors_set

        # This fixes the bug that the screen is empty after resuming the app
        self.app_resume_signal.subscribe(self, lambda *_args, **_kwargs: self.refresh())

        self.push_screen(ScreenCollection())

    def action_toggle_help_panel(self):
        try:
            self.query_one(HelpPanel).remove()
        except NoMatches:
            self.action_show_help_panel()


if __name__ == "__main__":
    Bamboost(watch_css=True, ansi_color=False).run()
