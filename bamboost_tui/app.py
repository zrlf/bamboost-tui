from __future__ import annotations

import weakref

from textual import on
from textual.app import App
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.theme import BUILTIN_THEMES, Theme
from textual.widgets import HelpPanel

from bamboost_tui.collection_picker import CollectionHit
from bamboost_tui.collection_table import ScreenCollection, ScreenCollectionPlaceholder

ansi_theme = Theme(
    name="ansi",
    primary="ansi_blue",
    secondary="ansi_cyan",
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
        "border": "ansi_bright_black",
        "border-focus": "ansi_white",
        # "block-hover-background": "$surface",
    },
)


class Bamboost(App):
    CSS_PATH = "bamboost.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True, show=False),
        Binding("ctrl+z", "suspend_process"),
        Binding("q", "pop_screen_or_exit", "quit screen"),
        Binding("?", "toggle_help_panel", "Show help"),
    ]
    COMMAND_PALETTE_BINDING = "ctrl+o"

    _open_collections: weakref.WeakValueDictionary[str, ScreenCollection] = (
        weakref.WeakValueDictionary()
    )

    def on_mount(self) -> None:
        if ansi_colors_set := self.ansi_color:
            self.register_theme(ansi_theme)
            self.ansi_theme.ansi_colors
            self.theme = "ansi"
            self.ansi_color = ansi_colors_set

        # This fixes the bug that the screen is empty after resuming the app
        self.app_resume_signal.subscribe(self, lambda *_args, **_kwargs: self.refresh())

        self.push_screen(ScreenCollectionPlaceholder())

    def action_toggle_help_panel(self):
        try:
            self.query_one(HelpPanel).remove()
        except NoMatches:
            self.action_show_help_panel()

    def action_pop_screen_or_exit(self) -> None:
        self.pop_screen()

        # if only the default screen is left, exit the app
        if len(self.screen_stack) <= 1 and self.screen_stack[0].id == "_default":
            self.exit()

    @on(CollectionHit.CollectionSelected)
    def _open_collection(self, message: CollectionHit.CollectionSelected) -> None:
        collection_uid = message.uid

        # if we try to open the same collection again, we do nothing
        if self.screen.name == collection_uid:
            return

        # we check if the collection is already open
        try:
            new_screen = self._open_collections[collection_uid]
        except KeyError:
            new_screen = ScreenCollection(uid=collection_uid)
            self._open_collections[collection_uid] = new_screen

        if isinstance(self.screen, ScreenCollectionPlaceholder):
            self.pop_screen()

        self.push_screen(new_screen)


if __name__ == "__main__":
    Bamboost(watch_css=True, ansi_color=False).run()
