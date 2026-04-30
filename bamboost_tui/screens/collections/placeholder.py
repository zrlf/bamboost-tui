from textwrap import dedent

from rich.text import Text
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Center
from textual.widgets import Static


class Placeholder(Static):
    def compose(self) -> ComposeResult:
        picker_binding = next(
            (
                b.binding
                for b in self.app.active_bindings.values()
                if b.binding.action == "toggle_picker"
            ),
            None,
        )
        key_name = (
            picker_binding.key_display or picker_binding.key
            if picker_binding
            else "???"
        )
        with Center():
            yield Static(
                dedent("""
                            dP                           dP                                    dP
                            88                           88                                    88
                            88d888b. .d8888b. 88d8b.d8b. 88d888b. .d8888b. .d8888b. .d8888b. d8888P
                            88'  `88 88'  `88 88'`88'`88 88'  `88 88'  `88 88'  `88 Y8ooooo.   88
                            88.  .88 88.  .88 88  88  88 88.  .88 88.  .88 88.  .88       88   88
                            88Y8888' `88888P8 dP  dP  dP 88Y8888' `88888P' `88888P' `88888P'   dP
                        """),
                classes="logo",
            )
        with Center():
            val = self.app.theme_variables.get("secondary")
            c = Color.parse(val).rich_color.name
            yield Static(
                Text.from_markup(
                    f"No collection selected. Press [bold {c}]{key_name}[/bold {c}] to open the collection picker."
                )
            )
        with Center():
            val = self.app.theme_variables.get("panel")
            c = Color.parse(val).rich_color.name
            yield Static(Text("A creation of florez/zrlf ♥", style=f"italic {c}"))
