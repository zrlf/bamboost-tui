from __future__ import annotations

import re
from argparse import Namespace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from bamboost_tui.commandline._cmp import (
    AutoComplete,
    TargetState,
)
from bamboost_tui.commandline.parser import Argument, Command, Option, Parser

if TYPE_CHECKING:
    from bamboost_tui.collection_table import CollectionTable


class CommandLine(ModalScreen):
    BINDINGS = [Binding("escape", "app.pop_screen")]

    def __init__(self, collection_table: "CollectionTable", *_args, **_kwargs):
        self._table = collection_table

        super().__init__(*_args, **_kwargs)

    def compose(self) -> ComposeResult:
        yield Horizontal(Label(":"), CommandLineInput(self._table), id="command-line")
        # yield RichLog()


class CommandLineInput(Input):
    _cmp: AutoComplete
    """The autocomplete component of this input widget."""
    BINDINGS = [
        Binding("enter", "execute"),
    ]

    def __init__(self, collection_table: "CollectionTable"):
        super().__init__(placeholder="command line", id="command-line-input")

        self._table = collection_table
        self.df = collection_table.df
        self.parser = Parser(
            [
                self.command_sort,
                self.command_go_to,
                self.command_filter,
            ],
            target=self,
        )

    def on_mount(self):
        """Mount the CMP component."""
        self._cmp = AutoComplete(
            self,
            candidates=self.parser.candidates,
            search_string=self._search_string,
            completion_strategy=self._complete,
            prevent_default_enter=False,
            id="cmp",
        )
        self.screen.mount(self._cmp)

    @property
    def command_sort(self) -> Command:
        def _cb(args: Namespace):
            self._table.action_sort_column(args.column_key, reverse=args.reverse)

        return Command(
            "sort",
            [Argument("column_key", choices=self.df.columns)],
            options={
                "--reverse": Option("reverse", bool_flag=True, aliases=["-r"]),
            },
            callback=_cb,
        )

    @property
    def command_go_to(self) -> Command:
        def _cb(args: Namespace):
            self._table.move_cursor(
                column=self._table.get_column_index(args.column_key)
            )

        return Command(
            "go_to",
            [Argument("column_key", choices=self.df.columns)],
            callback=_cb,
        )

    @property
    def command_filter(self) -> Command:
        def _cb(args: Namespace):
            # self._table.filter(args.column_key)
            pass

        return Command(
            "filter",
            [Argument("column_key", choices=self.df.columns)],
            callback=_cb,
        )

    def action_execute(self) -> None:
        """Function that will be called when the enter key is pressed."""
        self.parser.execute(self.value)
        self.value = ""
        self.app.pop_screen()

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
        self.insert_text_at_cursor(text)

    def _search_string(self, state: TargetState) -> str:
        """Function that extracts the search string from the current state."""
        text = state.text
        if not text or text.endswith(" "):
            return ""
        return text.split()[-1]
