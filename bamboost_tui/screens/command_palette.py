from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import CommandInput, CommandList
from textual.command import CommandPalette as BaseCommandPalette
from textual.command import DiscoveryHit, Hit, Hits, Provider, SearchIcon
from textual.containers import Horizontal, Vertical
from textual.system_commands import SystemCommandsProvider
from textual.widgets import Button, LoadingIndicator

from bamboost_tui.utils import get_index

if TYPE_CHECKING:
    pass


class GlobalCommands(Provider):
    """A command provider for the command palette."""

    @dataclass
    class CustomCommand:
        name: str
        command: Callable[[], Any]
        help: Optional[str] = None

    COMMANDS: list[CustomCommand] = []

    def scan_collections(self) -> None:
        """Scan for collections."""
        get_index().scan_for_collections()
        self.app.notify("✔️ Scanned for collections")

    async def startup(self) -> None:
        """Called once when the command palette is opened, prior to searching."""
        self.COMMANDS = [
            GlobalCommands.CustomCommand(
                "Scan for collections",
                self.scan_collections,
                "The config is based on the current working directory.",
            ),
        ]

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for cmd in self.COMMANDS:
            score = matcher.match(cmd.name)
            if score > 0:
                yield Hit(
                    score, matcher.highlight(cmd.name), cmd.command, help=cmd.help
                )

    async def discover(self) -> Hits:
        """Called when the command palette is opened, prior to searching."""
        for cmd in self.COMMANDS:
            yield DiscoveryHit(
                cmd.name,
                cmd.command,
                help=cmd.help,
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
            providers=[SystemCommandsProvider, GlobalCommands],
            placeholder="Search collections",
        )

    def compose(self) -> ComposeResult:
        """Compose the command palette.

        Returns:
            The content of the screen.
        """
        with Vertical(id="--container"):
            with Horizontal(id="--input") as container:
                container.border_title = "Collection Picker"
                yield SearchIcon()
                yield CommandInput(placeholder=self._placeholder)
                if not self.run_on_select:
                    yield Button("\u25b6")
            with Vertical(id="--results"):
                yield CommandList()
                yield LoadingIndicator()
