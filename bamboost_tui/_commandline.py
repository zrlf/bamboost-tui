from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, List, Type

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, Label, RichLog
from typing_extensions import TypeAlias

from bamboost_tui._cmp import (
    AutoComplete,
    DropdownItem,
    TargetState,
)

if TYPE_CHECKING:
    from bamboost_tui.collection_table import CollectionTable


@dataclass
class Argument:
    name: str
    type: Type = str
    choices: Iterable[str] = field(default_factory=list)


@dataclass
class Option:
    name: str
    type: Type = str
    choices: Iterable[str] = field(default_factory=list)


@dataclass
class Command:
    name: str
    arguments: list[Argument] = field(default_factory=list)
    options: dict[str, Option] = field(default_factory=dict)
    callback: Callable = lambda: None


CommandList: TypeAlias = List[Command]
"""A list of commands."""


class Parser:
    def __init__(self, commands: CommandList, *, target: Input):
        self._commands: dict[str, Command] = {cmd.name: cmd for cmd in commands}
        self._target = target

    def candidates(self, state: TargetState) -> list[DropdownItem]:
        text = state.text
        main_command_list = [
            DropdownItem(cmd, "function", "func") for cmd in self._commands.keys()
        ]
        if not text:
            return main_command_list

        if text[-1] == " ":
            tokens = state.text.split()
        else:
            tokens = state.text.split()[:-1]

        return self._get_current_options(tokens) or main_command_list

    def _get_current_options(self, tokens: list[str]) -> list[DropdownItem] | None:
        if not tokens:
            return None

        command = self._commands[tokens[0]]
        options = []
        arg_count = 0

        for token in tokens[1:]:
            if token.startswith("-"):
                options.append(token)
            else:
                arg_count += 1

        try:
            current_arg = command.arguments[arg_count]
            return [
                DropdownItem(choice, "object", "column")
                for choice in current_arg.choices
            ]
        except IndexError:
            return None

    def execute(self, text: str) -> None:
        tokens = text.split()
        command = self._commands[tokens[0]]
        args = tokens[1:]

        # if len(args) != len(command.arguments):
        #     return

        command.callback(*args)


class CommandLine(Input):
    _cmp: AutoComplete
    """The autocomplete component of this input widget."""
    BINDINGS = [
        Binding("enter", "execute"),
    ]

    def __init__(self, collection_table: "CollectionTable"):
        super().__init__(placeholder="command line", id="command-line-input")

        self._table = collection_table
        self.df = collection_table.df

        def goto(column: str):
            self._table.move_cursor(column=self._table.get_column_index(column))

        commands = [
            Command(
                "sort",
                arguments=[Argument("column_key", type=str, choices=self.df.columns)],
            ),
            Command(
                "goto",
                arguments=[Argument("column_key", type=str, choices=self.df.columns)],
                callback=goto,
            ),
            Command(
                "filter",
                arguments=[Argument("column_key", type=str, choices=self.df.columns)],
            ),
            Command(
                "filter2",
                arguments=[Argument("column_key", type=str, choices=self.df.columns)],
            ),
        ]
        self.parser = Parser(commands, target=self)

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

    def action_execute(self) -> None:
        """Function that will be called when the enter key is pressed."""
        self.parser.execute(self.value)
        self.value = ""
        self.app.pop_screen()

    def _complete(self, text: str, state: TargetState) -> None:
        """The function that will be called when a completion is selected. It will replace
        the last word with the selected completion.
        """
        # delete the last word
        try:
            *_, hit = re.finditer(self._WORD_START, self.value[: self.cursor_position])
        except ValueError:
            target = 0
        else:
            target = hit.start()

        self.delete(target, self.cursor_position)

        # add the new word
        self.insert_text_at_cursor(text)

    def _search_string(self, state: TargetState) -> str:
        """Function that extracts the search string from the current state."""
        try:
            return state.text.split()[-1]
        except IndexError:
            return ""


class CmdLineScreen(ModalScreen):
    BINDINGS = [Binding("escape", "app.pop_screen")]

    def __init__(self, collection_table: "CollectionTable", *_args, **_kwargs):
        self._table = collection_table

        super().__init__(*_args, **_kwargs)

    def compose(self) -> ComposeResult:
        yield Horizontal(Label(":"), CommandLine(self._table), id="command-line")
        # yield RichLog()
