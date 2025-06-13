from __future__ import annotations

from rich.table import Column, Table
from textual._context import active_app
from textual.app import App
from textual.binding import Binding
from textual.command import Hit, Hits, Matcher, Provider
from textual.screen import Screen
from textual.visual import VisualType

from bamboost_tui.command_palette import CommandPalette


class KeyHit(Hit):
    def __init__(
        self,
        score: float,
        binding: Binding,
        matcher: Matcher | None = None,
    ) -> None:
        app = active_app.get()
        super().__init__(
            score,
            self._render(app, binding, matcher),
            lambda b=binding: app.simulate_key(binding.key),
        )

    def _render(
        self, app: App, binding: Binding, matcher: Matcher | None = None
    ) -> VisualType:
        from rich.text import Text

        key_style = app.screen.get_component_rich_style(
            "command-palette--key", partial=True
        )
        help_style = app.screen.get_component_rich_style(
            "command-palette--help-text", partial=True
        )

        # Highlight description if matcher is provided
        description = (
            matcher.highlight(binding.description)
            if matcher is not None
            else Text(binding.description)
        )
        description = Text.from_markup(
            " ".join(
                (
                    description.markup,
                    Text(f"[{binding.id}]" if binding.id else "", help_style).markup,
                )
            )
        )

        key_text = Text(binding.key, style=key_style)

        # Create a table with two columns: description (left), key (right)
        table = Table.grid(
            Column(ratio=2),
            Column(ratio=1, justify="right"),
            padding=(0, 2),
            expand=True,
            pad_edge=False,
        )
        table.add_row(description, key_text)
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
                yield KeyHit(score, binding, self.matcher(query))

    async def discover(self) -> Hits:
        screen = self.app.screen_stack[-2]
        for active_binding in self.get_all_bindings(screen):
            binding = active_binding.binding
            yield KeyHit(1, binding)


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
            [BindingsProvider], placeholder="Find bindings", id="keybind-palette"
        )
