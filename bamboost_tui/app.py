from __future__ import annotations

from bamboost import config
from rich.console import RenderableType
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.css.query import NoMatches
from textual.events import Event
from textual.geometry import Size
from textual.reactive import reactive
from textual.screen import Screen
from textual.theme import BUILTIN_THEMES, Theme
from textual.widget import Widget
from textual.widgets import Footer, HelpPanel, Label, OptionList, Static
from textual.widgets.option_list import Option

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


from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text


class KeybindsIntro(Static):
    def render(self) -> RenderResult:
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

        return Columns(content, align="center", expand=True)


class MultiColumnOption(Static):
    is_highlighted = reactive(False)

    def __init__(
        self,
        option_list: MultiColumnOptionList,
        columns: tuple[str, ...],
        styles: tuple[str, ...] = (),
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.option_list = option_list
        if styles:
            self.columns = tuple(
                Text(column, style=styles[i]) for i, column in enumerate(columns)
            )
        else:
            self.columns = tuple(Text(column) for column in columns)

    def render(self) -> RenderableType:
        chevron = Text("❯", style="blue") if self.is_highlighted else " "
        tab = Table.grid(padding=(0, 2), pad_edge=True)
        tab.add_column("chevron", width=1)  # chevron
        for i, column in enumerate(self.columns):
            tab.add_column(column, width=self.option_list.column_widths[i])
        tab.add_row(
            chevron,
            *self.columns,
            style=Style(bgcolor="black", bold=True) if self.is_highlighted else None,
        )
        return tab


class MultiColumnOptionList(Widget, can_focus=True):
    """A custom option list widget with three columns."""

    BINDINGS = [
        Binding("ctrl+n,j,down", "cursor_down", "Move cursor down"),
        Binding("ctrl+p,k,up", "cursor_up", "Move cursor up"),
    ]

    highlighted_index = reactive(0)

    def __init__(self, *options: tuple[str, ...], styles: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.options = [
            MultiColumnOption(self, option, styles=styles) for option in options
        ]

        col_lengths = [len(column) for column in options[0]]
        for option in options[1:]:
            for i, column in enumerate(option):
                col_lengths[i] = max(col_lengths[i], len(column))
        self.column_widths = col_lengths

    def compose(self) -> ComposeResult:
        """Compose the options as children widgets."""
        for option in self.options:
            yield option

    def on_mount(self) -> None:
        """Highlight the first option on mount."""
        self.update_highlight()

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

    class OptionSelected(Event):
        """An event that is emitted when an option is selected."""
        # TODO
        

    def action_select(self) -> None:
        """Select the highlighted option."""
        # self.options[self.highlighted_index].action_select()
        # TODO


class ScreenWelcome(Screen):
    def compose(self) -> ComposeResult:
        yield Container(Label(ASCII_LOGO), classes="logo")
        yield Container(
            MultiColumnOptionList(
                ("Index", "Pick a collection from all known collections"),
                ("Remote", "Show known remote collections"),
                ("Scan paths", "Scan paths for new collections"),
                ("Open config", "Open the config file"),
                ("Exit", "Quit the app"),
                styles=("blue", "dim"),
            ),
            KeybindsIntro(),
            classes="information",
        )
        yield Footer()


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


if __name__ == "__main__":
    Bamboost(watch_css=True, ansi_color=False).run()
