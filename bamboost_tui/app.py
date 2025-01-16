from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Generator

from rich.columns import Columns
from rich.console import RenderableType
from rich.spinner import Spinner
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Container
from textual.css.query import NoMatches
from textual.geometry import Size
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.theme import BUILTIN_THEMES, Theme
from textual.widget import Widget
from textual.widgets import Footer, HelpPanel, Label, Static

from bamboost_tui.collection_picker import CollectionHit, CollectionPicker
from bamboost_tui.collection_table import ScreenCollection

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
        "border": "ansi_bright_black",
        "border-focus": "ansi_white",
        # "block-hover-background": "$surface",
    },
)

ASCII_LOGO = r"""
              ▓▓▓▓▓▓▓▓▓▓▓▓              
          ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓          
       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓       
     ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓     
    ▓▓▓▓▓▓▓▓▓▓     ██▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓    
   ▓▓▓▓▓▓▓▓▓▓▓▓    ███    █▓▓▓▓▓▓▓▓▓▓   
  ▓▓▓▓▓▓▓▓▓▓▓▓▓    ███   ███░▒▓▓▓▓▓▓▓▓  
 ▓▓▓▓▓▓▓▓▓▒░░▓▓    ███   ▓░░░███▓▓▓▓▓▓▓ 
▓▓▓▓▓▓▓▓▓▓▓▓░░█    ███   ░░██████▓▓▓▓▓▓▓
▓▓▓▓▓▓▓▓▓▓▓▓▓░     ███   ░░░░██████▓▓▓▓▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓   ░░███    ███████████▓▓▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ░░███  ░░█████████████▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ░░███  ░███████████████
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ░░███  ░███████████████
 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ░░███  ░██████████████ 
  ▓▓▓▓▓▓▓▓▓▓▓▓▓  ░░███  ░▓████████████  
   ▓▓▓▓▓▓▓▓▓▓▓   ░░██▓  ░░███████████   
    ▓▓▓▓▓▓▓▓▓▓▓░▒█████▓▒▓███████████    
     ▓▓▓▓▓▓▓▓▓▓▓ ██████ ███████████     
       ▓▓▓▓▓▓▓▓▓▓▓▓██████████████       
          ▓▓▓▓▓▓▓▓▓▓▓█████████          
              ▓▓▓▓▓▓▓▓████              
"""


class KeybindsIntro(Static):
    def __init__(self) -> None:
        key_bindings = [
            "q / Quit current screen",
            "? / Toggle help panel",
            "ctrl+o / Open command palette",
            "ctrl+c / Quit application",
            "ctrl+z / Suspend process",
        ]
        content = [
            Text("Key Bindings:", style="italic dim"),
            Columns(
                key_bindings, align="center", expand=False, equal=True, padding=(0, 3)
            ),
        ]
        super().__init__(Columns(content, align="center", expand=True))


class ListOption(Static):
    is_highlighted = reactive(False)
    """A reactive boolean to determine if the option is highlighted."""
    option_key: str
    """The first column of the option is used as it's key."""
    columns: tuple[RenderableType, ...]
    description: reactive[RenderableType] = reactive("", init=False)

    def __init__(
        self,
        main: str,
        description: Text | str,
        option_list: MenuList,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.option_list = option_list
        self.option_key = main

        styles = option_list._styles
        self.main = Text(main, style=styles[0])
        self.description = (
            Text(description, style=styles[1])
            if isinstance(description, str)
            else description
        )

    def _update_self(self) -> None:
        tab = Table.grid(padding=(0, 2), pad_edge=True)
        tab.add_column("chevron", width=1)
        tab.add_column(width=self.option_list.column_widths[0])
        tab.add_column(width=self.option_list.column_widths[1])
        tab.add_row(
            Text("❯", style="blue") if self.is_highlighted else " ",
            self.main,
            self.description,
            style=Style(bgcolor="black", bold=True) if self.is_highlighted else None,
        )
        self.update(tab)

    def watch_is_highlighted(self) -> None:
        """Watch the is_highlighted reactive and update the renderable."""
        self._update_self()

    def watch_description(self) -> None:
        """Watch the description reactive and update the renderable."""
        self._update_self()

    @contextmanager
    def process_indicator(
        self,
        attr: str,
        renderable: RenderableType,
        interval: float = 0.5,
        success: str = "✓",
        timeout: float = 2,
    ) -> Generator[None, None, None]:
        """Context manager to show a process indicator in a widget.

        Args:
            attr (str): The attribute to update with the renderable.
            renderable (RenderableType): The renderable to show.
            interval (float, optional): The interval to update the renderable. Defaults to 0.5.
            success (str, optional): The success indicator. Defaults to "✓".
            timeout (float, optional): The timeout to stop the process indicator. Defaults to 2.
        """
        original = getattr(self, attr)
        setattr(self, attr, renderable)
        timer = self.set_interval(interval, self.refresh)
        try:
            yield
        finally:
            timer.stop()
            del timer
            setattr(self, attr, Text.from_markup(success))
            self.set_timer(timeout, lambda: setattr(self, attr, original))


class MenuList(Static, can_focus=True):
    """A custom option list widget with three columns."""

    BINDINGS = [
        Binding("ctrl+n,j,down", "cursor_down", "Move cursor down"),
        Binding("ctrl+p,k,up", "cursor_up", "Move cursor up"),
        Binding("enter", "select", "Select the highlighted option"),
    ]

    highlighted_index = reactive(0)

    def __init__(self, *options: tuple[str, ...], styles: tuple[str, ...] = ()) -> None:
        super().__init__()

        # compute necessary column widths
        col_lengths = [len(column) for column in options[0]]
        for option in options[1:]:
            for i, column in enumerate(option):
                col_lengths[i] = max(col_lengths[i], len(column))
        self.column_widths = col_lengths

        self._styles = styles
        self._options = options
        self.options = [ListOption(*option, option_list=self) for option in options]

    def compose(self) -> ComposeResult:
        """Compose the options as children widgets."""
        for option in self.options:
            yield option

    def on_mount(self) -> None:
        """Highlight the first option on mount."""
        self.update_highlight()

    def get_content_width(self, container: Size, viewport: Size) -> int:
        return sum(self.column_widths) + 10

    def update_highlight(self) -> None:
        """Update the highlighting of the options."""
        for i, option in enumerate(self.options):
            option.is_highlighted = i == self.highlighted_index

    def action_cursor_down(self) -> None:
        """Move the highlight down."""
        self.highlighted_index = min(self.highlighted_index + 1, len(self.options) - 1)
        self.update_highlight()

    def action_cursor_up(self) -> None:
        """Move the highlight up."""
        self.highlighted_index = max(self.highlighted_index - 1, 0)
        self.update_highlight()

    class OptionSelected(Message):
        """Option selected message."""

        def __init__(self, option: ListOption) -> None:
            self.option = option
            super().__init__()

    def action_select(self) -> None:
        """Select the highlighted option."""
        self.post_message(self.OptionSelected(self.options[self.highlighted_index]))


def variable_to_color(app: App, variable: str) -> str:
    val = app.theme_variables.get(variable)
    return Color.parse(val).rich_color.name


class ScreenWelcome(Screen):
    def compose(self) -> ComposeResult:
        yield Container(Label(ASCII_LOGO), classes="logo")
        yield Container(
            MenuList(
                ("Index", "Pick a collection from all known collections"),
                ("Remote", "Show known remote collections"),
                ("Scan paths", "Scan paths for new collections"),
                ("Open config", "Open the config file"),
                ("Exit", variable_to_color(self.app, "foreground")),
                styles=("cyan", variable_to_color(self.app, "foreground")),
            ),
            classes="menu",
        )
        yield KeybindsIntro()
        yield Footer()

    @on(MenuList.OptionSelected)
    async def on_selection(self, message: MenuList.OptionSelected) -> None:
        option = message.option
        desc = option.description

        if option.option_key == "Index":
            self.app.push_screen(CollectionPicker())
        elif option.option_key == "Remote":
            pass
        elif option.option_key == "Scan paths":

            async def scan_paths(option: ListOption):
                # replace the description with the spinner and set interval refresh
                with option.process_indicator(
                    "description",
                    Spinner("dots", text="Scanning paths..."),
                    1 / 20,
                    "[green][not bold]:heavy_check_mark:[/not bold] Index scanned.",
                    timeout=3,
                ):
                    from bamboost.index import DEFAULT_INDEX

                    DEFAULT_INDEX.scan_for_collections()
                    await asyncio.sleep(0.5)

            self.run_worker(scan_paths(option))
        elif option.option_key == "Open config":
            import os

            from bamboost._config import CONFIG_FILE

            with self.app.suspend():
                os.system(f"${{EDITOR:-vim}} {CONFIG_FILE}")

        elif option.option_key == "Exit":
            self.app.exit()


class IntervalUpdater(Static):
    _renderable_object: RenderableType

    def __init__(
        self, renderable: RenderableType, interval: float = 1.0, id: str | None = None
    ) -> None:
        super().__init__(renderable, id=id)
        self.interval = interval

    def on_mount(self) -> None:
        self.interval_update = self.set_interval(self.interval, self.refresh)


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

        self.install_screen(ScreenWelcome(), "welcome")
        self.push_screen("welcome")
        # self.push_screen(ScreenCollection())

    def action_toggle_help_panel(self):
        try:
            self.query_one(HelpPanel).remove()
        except NoMatches:
            self.action_show_help_panel()

    @on(CollectionHit.CollectionSelected)
    def _open_collection(self, message: CollectionHit.CollectionSelected) -> None:
        self.app.push_screen(ScreenCollection(uid=message.uid))


if __name__ == "__main__":
    Bamboost(watch_css=True, ansi_color=False).run()
