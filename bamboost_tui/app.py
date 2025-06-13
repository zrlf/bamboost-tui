# pyright: reportUnusedImport=false
from __future__ import annotations

from textual import work
from textual.app import App
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import HelpPanel

from bamboost_tui.screens.collection import ScreenCollection
from bamboost_tui.command_palette import CommandPalette
from bamboost_tui.command_registry import command_registry
from bamboost_tui.theme import ANSI_THEME


class BamboostApp(App):
    CSS_PATH = "bamboost.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True, show=False),
        Binding("ctrl+z", "suspend_process", "suspend application", show=False),
        Binding("q", "pop_screen_or_exit", "quit screen"),
        Binding("Q", "quit", "exit"),
        Binding("?", "toggle_help_panel", "Show help"),
        Binding("ctrl+o", "command_palette", "Command palette"),
    ]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # bind the keys from the command_registry

        for cmd in command_registry:
            if cmd.key:

                def _action_func(self=self, cmd=cmd) -> None:
                    return cmd.func(self)

                func_name = cmd.name.replace(".", "_")
                self.__setattr__(f"action_{func_name}", _action_func)
                self.bind(cmd.key, func_name, description=cmd.label, show=False)

    def on_mount(self) -> None:
        if ansi_colors_set := self.ansi_color:
            self.register_theme(ANSI_THEME)
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
        import bamboost.core.hdf5.attrsdict  # noqa: F401
        import bamboost.core.hdf5.file  # noqa: F401
        import bamboost.core.simulation  # noqa: F401
        import bamboost.index  # noqa: F401
        import h5py  # noqa: F401
        import pandas  # noqa: F401

    async def action_toggle_help_panel(self):
        try:
            await self.screen.query_one(HelpPanel).remove()
        except NoMatches:
            self.action_show_help_panel()

    def action_pop_screen_or_exit(self) -> None:
        self.pop_screen()

        # if only the default screen is left, exit the app
        if len(self.screen_stack) <= 1 and self.screen_stack[0].id == "_default":
            self.exit()

    def action_command_palette(self) -> None:
        self.push_screen(CommandPalette())


if __name__ == "__main__":
    BamboostApp(watch_css=False, ansi_color=True).run()
