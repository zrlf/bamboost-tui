from __future__ import annotations


from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import CommandInput, CommandList
from textual.command import CommandPalette as BaseCommandPalette
from textual.command import Hit, Hits, Provider, SearchIcon
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.system_commands import SystemCommandsProvider
from textual.widgets import Button, LoadingIndicator


class BindingsProvider(Provider):
    """A command provider that exposes all Bindings from the app, screen, and widgets."""

    def get_all_bindings(self, screen: Screen):
        return screen.active_bindings.values()

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        screen = self.app.screen_stack[-2]
        for active_binding in self.get_all_bindings(screen):
            binding = active_binding.binding
            score = matcher.match(
                binding.description + binding.key + (binding.id or "")
            )
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(binding.description or binding.key),
                    lambda b=binding: self.app.simulate_key(b.key),
                    help=f"{binding.key} / {binding.description or binding.action}",
                )

    async def discover(self) -> Hits:
        screen = self.app.screen_stack[-2]
        for active_binding in self.get_all_bindings(screen):
            binding = active_binding.binding
            yield Hit(
                1,
                binding.description or binding.key,
                lambda b=binding: self.app.simulate_key(b.key),
                help=f"{binding.key} / {binding.description or binding.action}",
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
            providers=[SystemCommandsProvider, BindingsProvider],
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
