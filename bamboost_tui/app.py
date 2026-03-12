# pyright: reportUnusedImport=false
from __future__ import annotations

from types import ModuleType
from typing import TypedDict

from bamboost import config
from textual import work
from textual.app import App
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import HelpPanel

from bamboost_tui.plugins import CustomBinding
from bamboost_tui.screens.collections import ScreenCollection
from bamboost_tui.screens.keybind_palette import KeybindPalette
from bamboost_tui.theme import ANSI_THEME
from bamboost_tui.utils import get_index, import_module_from_path


class Config(TypedDict):
    keys: dict[str, str]
    plugins: list[str]


config_tui: Config = config._remainder.get("tui", {})


class BamboostApp(App):
    CSS_PATH = "bamboost.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True, show=False),
        Binding("ctrl+z", "suspend_process", "suspend application", show=False),
        Binding("q", "pop_screen_or_exit", "quit screen"),
        Binding("Q", "quit", "exit"),
        Binding("?", "toggle_help_panel", "Show help", id="app.help"),
        Binding(
            "ctrl+p", "command_palette", "Keybind picker", id="app.command_palette"
        ),
        Binding(
            "alt+ctrl+j",
            "clean_index",
            "Clean the collection database",
            id="index.clean",
            system=True,
            show=False,
        ),
        Binding(
            "alt+ctrl+s",
            "scan_collections",
            "Scan for collections",
            id="index.scan",
            system=True,
            show=False,
        ),
    ]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, initial_collection_path: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial_collection_path = initial_collection_path
        self.plugins: list[ModuleType] = []

        # set the keymap from the config
        self.set_keymap(config_tui.get("keys", {}))

        # load plugins from the config
        for path in config_tui.get("plugins", []):
            mod = import_module_from_path(path)
            self.plugins.append(mod)

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

        screen = ScreenCollection(path=self.initial_collection_path)
        self.push_screen(screen)

        # bind keybinds from plugins here
        for plugin in self.plugins:
            if hasattr(plugin, "BINDINGS"):
                for binding in plugin.BINDINGS:
                    binding: CustomBinding
                    # set an action method (textual requires this)
                    action_name = binding.action_name()
                    setattr(
                        self,
                        "action_" + action_name,
                        lambda b=binding: b.action(),
                    )
                    # add the binding to the app
                    all_keys = [key.strip() for key in binding.key.split(",")]
                    for key in all_keys:
                        self._bindings.key_to_bindings.setdefault(key, []).append(
                            binding.to_textual_binding()
                        )

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
        self.push_screen(KeybindPalette())

    def action_scan_collections(self) -> None:
        """Scan for collections."""
        get_index().scan_for_collections()
        self.notify("✔️ Scanned for collections")

    def action_clean_index(self) -> None:
        get_index().check_integrity()
        self.notify("⚪ Cleaned index")


if __name__ == "__main__":
    result = BamboostApp(watch_css=False, ansi_color=True).run()

    if result:
        print(result, end="")
