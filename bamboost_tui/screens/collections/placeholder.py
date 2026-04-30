from textwrap import dedent

from rich.text import Text
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Center
from textual.widgets import Static
from textual.reactive import reactive


class Placeholder(Static):
    binding_text = reactive("???")

    def compose(self) -> ComposeResult:
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
        yield Center(Static(id="message-label"))
        with Center():
            val = self.app.theme_variables.get("panel")
            c = Color.parse(val).rich_color.name
            yield Static(Text("A creation of florez/zrlf ♥", style=f"italic {c}"))

    def _get_instruction_text(self) -> Text:
        val = self.app.theme_variables.get("secondary")
        c = Color.parse(val).rich_color.name
        return Text.from_markup(
            f"No collection selected. Press [bold {c}]{self.binding_text}[/bold {c}] to open the collection picker."
        )

    def on_mount(self) -> None:
        picker_binding = next(
            (
                b.binding
                for b in self.app.active_bindings.values()
                if b.binding.action == "toggle_picker"
            ),
            None,
        )
        if picker_binding:
            self.binding_text = picker_binding.key_display or picker_binding.key

        self._update_display()

    def _update_display(self) -> None:
        try:
            self.query_one("#message-label", Static).update(self._get_instruction_text())
        finally:
            pass

    def watch_binding_text(self, _) -> None: self._update_display()