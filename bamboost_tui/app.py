from __future__ import annotations

import asyncio
import time

from textual import work
from textual.app import App
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.theme import BUILTIN_THEMES, Theme
from textual.widgets import HelpPanel

from bamboost_tui.collection_table import ScreenCollection

ansi_theme = Theme(
    name="ansi",
    primary="ansi_blue",
    secondary="ansi_magenta",
    accent="ansi_yellow",
    foreground="ansi_bright_white",
    background="ansi_default",
    success="ansi_bright_green",
    warning=BUILTIN_THEMES["textual-dark"].warning,
    error="ansi_red",
    surface="ansi_black",
    panel="ansi_bright_black",
    boost="ansi_bright_green",
    dark=True,
    variables={
        "foreground-muted": "ansi_white",
        "input-cursor-background": "ansi_black",
        "input-cursor-foreground": "ansi_white",
        "block-cursor-background": "ansi_black",
        "block-cursor-foreground": "ansi_white",
        "border": "ansi_bright_black",
        "border-focus": "ansi_blue",
        "footer-background": "ansi_black",
    },
)


class BamboostApp(App):
    CSS_PATH = "bamboost.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True, show=False),
        Binding("ctrl+z", "suspend_process", "suspend application", show=False),
        Binding("q", "pop_screen_or_exit", "quit screen"),
        Binding("Q", "quit", "exit"),
        Binding("?", "toggle_help_panel", "Show help"),
    ]
    COMMAND_PALETTE_BINDING = "ctrl+o"
    BINDING_GROUP_TITLE = "App commands"

    def on_mount(self) -> None:
        if ansi_colors_set := self.ansi_color:
            self.register_theme(ansi_theme)
            self.theme = "ansi"
            self.ansi_color = ansi_colors_set
        else:
            self.theme = "gruvbox"

        # This fixes the bug that the screen is empty after resuming the app
        self.app_resume_signal.subscribe(self, lambda *_args, **_kwargs: self.refresh())

        self._preload_modules()
        self.push_screen(ScreenCollection())

    @work(thread=True)
    async def _preload_modules(self) -> None:
        # Import in a thread to avoid blocking the event loop
        import bamboost.core.hdf5.attrsdict
        import bamboost.core.hdf5.file
        import bamboost.core.simulation
        import bamboost.index
        import h5py
        import pandas

    async def action_toggle_help_panel(self):
        try:
            await self.query_one(HelpPanel).remove()
        except NoMatches:
            self.action_show_help_panel()

    def action_pop_screen_or_exit(self) -> None:
        self.pop_screen()

        # if only the default screen is left, exit the app
        if len(self.screen_stack) <= 1 and self.screen_stack[0].id == "_default":
            self.exit()


if __name__ == "__main__":
    BamboostApp(watch_css=False, ansi_color=True).run()
