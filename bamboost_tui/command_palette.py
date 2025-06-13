from __future__ import annotations


from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import CommandInput, CommandList
from textual.command import CommandPalette as BaseCommandPalette
from textual.command import DiscoveryHit, Hit, Hits, Provider, SearchIcon
from textual.containers import Horizontal, Vertical
from textual.system_commands import SystemCommandsProvider
from textual.widgets import Button, LoadingIndicator

from bamboost_tui.command_registry import command_registry, Command


class AppCommands(Provider):
    """A command provider for the command palette."""

    def get_commands(self) -> list[Command]:
        return command_registry

    async def startup(self) -> None:
        """Called once when the command palette is opened, prior to searching."""
        pass

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for cmd in self.get_commands():
            score = matcher.match(cmd.label)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(cmd.label),
                    lambda cmd=cmd: cmd.func(self.app),
                    help=rf"{cmd.name} \[{cmd.key}] / {cmd.help}",
                )

    async def discover(self) -> Hits:
        """Called when the command palette is opened, prior to searching."""
        for cmd in self.get_commands():
            yield DiscoveryHit(
                cmd.label,
                lambda cmd=cmd: cmd.func(self.app),
                text=cmd.label,
                help=rf"{cmd.name} \[{cmd.key}] / {cmd.help}",
            )


class CommandPalette(BaseCommandPalette):
    BINDINGS = [
        Binding("ctrl+n", "cursor_down", "move cursor down", show=False),
        Binding("ctrl+p", "command_list('cursor_up')", "move cursor up", show=False),
    ]
    COMPONENT_CLASSES = BaseCommandPalette.COMPONENT_CLASSES | {
        "collection-list--uid",
        "collection-list--path",
        "collection-list--count",
    }

    def __init__(self):
        super().__init__(
            providers=[SystemCommandsProvider, AppCommands],
            placeholder="Search commands...",
        )

    def compose(self) -> ComposeResult:
        """Compose the command palette.

        Returns:
            The content of the screen.
        """
        with Vertical(id="--container"):
            with Horizontal(id="--input") as container:
                container.border_title = "Command Palette"
                yield SearchIcon()
                yield CommandInput(placeholder=self._placeholder)
                if not self.run_on_select:
                    yield Button("\u25b6")
            with Vertical(id="--results"):
                yield CommandList()
                yield LoadingIndicator()
