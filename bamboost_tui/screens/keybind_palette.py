from __future__ import annotations

from rich.table import Column, Table
from textual._context import active_app
from textual.app import App
from textual.binding import Binding
from textual.command import Hit, Hits, Matcher, Provider
from textual.message import Message
from textual.screen import Screen
from textual.system_commands import SystemCommandsProvider
from textual.visual import VisualType

from bamboost_tui.command_palette import CommandPalette


class KeyHit(Hit):
    def __init__(
        self,
        score: float,
        binding: Binding,
        command,
        matcher: Matcher | None = None,
    ) -> None:
        super().__init__(score, self._render(binding, matcher), command)

    def _render(self, binding: Binding, matcher: Matcher | None = None) -> VisualType:
        from rich.text import Text

        app = active_app.get()
        key_style = app.screen.get_component_rich_style(
            "command-palette--key", partial=True
        )
        help_style = app.screen.get_component_rich_style(
            "command-palette--help-text", partial=True
        )

        # Highlight description if matcher is provided
        # I need to replace the ansi_ prefix in the markup for rich to render it (?)
        # Fine for now
        description = Text.from_markup(
            matcher.highlight(binding.description).markup.replace("ansi_", "")
            if matcher is not None
            else binding.description
        )
        description = description.append(
            f" [{binding.id}]" if binding.id else "", style=help_style
        )

        # Create a table with two columns: description (left), key (right)
        table = Table.grid(
            Column(ratio=2),
            Column(ratio=1, justify="right"),
            padding=(0, 2),
            expand=True,
            pad_edge=False,
        )
        table.add_row(description, Text(binding.key, style=key_style))
        return table


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
                yield KeyHit(
                    score,
                    binding,
                    lambda b=binding: self.app.simulate_key(b.key),
                    self.matcher(query),
                )

    async def discover(self) -> Hits:
        screen = self.app.screen_stack[-2]
        for active_binding in self.get_all_bindings(screen):
            binding = active_binding.binding
            yield KeyHit(
                1,
                binding,
                lambda b=binding: self.app.simulate_key(b.key),
            )


class KeybindPalette(CommandPalette):
    COMPONENT_CLASSES = CommandPalette.COMPONENT_CLASSES | {
        "command-palette--key",
        "command-palette--help-text",
    }
    DEFAULT_CSS = """
    KeybindPalette > .command-palette--key {
        color: $accent;
    }
    KeybindPalette > .command-palette--help-text {
    }
    """

    def __init__(self) -> None:
        super().__init__(
            [BindingsProvider, SystemCommandsProvider],
            placeholder="Find bindings",
            id="keybind-palette",
        )
