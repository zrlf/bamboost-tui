from __future__ import annotations

import re

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Input, Label

from bamboost_tui.commandline._cmp import (
    AutoComplete,
    TargetState,
)
from bamboost_tui.commandline.parser import Parser


class CommandLine(Screen):
    BINDINGS = [
        Binding("escape", "dismiss"),
        Binding("enter", "execute", "do this thing"),
    ]
    DEFAULT_CSS = """
    CommandLine {
        background: transparent;

        & > Horizontal {
            width: 100%;
            height: 1;
            background: $surface;
        }
    }
    """

    def __init__(self, parser: Parser | None, label: str = ":", *_args, **_kwargs):
        super().__init__(*_args, **_kwargs)
        self.label = label
        self.display = False
        self.parser: Parser | None = parser
        self.has_parser = bool(parser)

    def compose(self) -> ComposeResult:
        with Horizontal(id="command-line"):
            yield Label(self.label)
            yield CommandLineInput(parser=self.parser)

    def action_show(self):
        self.query_one(CommandLineInput).focus()

    @on(Input.Submitted)
    def _input_submitted(self, message: Input.Submitted) -> None:
        """Function that will be called when the enter key is pressed."""
        self.dismiss()
        self.parser.execute(message.value)


class CommandLineInput(Input, can_focus=True):
    """The autocomplete component of this input widget."""

    DEFAULT_CSS = """
    CommandLineInput {
    }
    """
    BINDINGS = [
        Binding("alt+backspace", "delete_left_word"),
    ]
    cmp: AutoComplete | None
    parser: Parser | None

    def __init__(self, parser: Parser | None = None):
        super().__init__(placeholder="command line", id="command-line-input")
        self.parser = parser

    async def action_submit(self) -> None:
        await super().action_submit()
        self.clear()

    def on_mount(self) -> None:
        self.cmp = AutoComplete(
            self,
            candidates=self.parser.candidates if self.parser else [],
            search_string=self._search_string,
            completion_strategy=self._complete,
            prevent_default_enter=False,
        )
        self.screen.mount(self.cmp)

    def _on_unmount(self) -> None:
        self.cmp.remove()
        super()._on_unmount()

    _WHITESPACE_BEFORE = re.compile(r"(?<=\s)\S")

    def _complete(self, text: str, state: TargetState) -> None:
        """The function that will be called when a completion is selected. It will replace
        the last word with the selected completion.
        """
        # delete the last word to the last whitespace
        try:
            *_, hit = re.finditer(
                self._WHITESPACE_BEFORE, self.value[: self.cursor_position]
            )
        except ValueError:
            target = 0
        else:
            target = hit.start()

        if not self.value.endswith(" "):
            self.delete(target, self.cursor_position)

        # add the new word
        self.insert_text_at_cursor(text + " ")

    def _search_string(self, state: TargetState) -> str:
        """Function that extracts the search string from the current state."""
        text = state.text
        if not text or text.endswith(" "):
            return ""
        return text.split()[-1]
