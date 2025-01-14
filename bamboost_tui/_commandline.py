from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Type

import pandas as pd
from rich.text import Text, TextType
from textual.app import ComposeResult
from textual.binding import Binding
from textual.geometry import Offset
from textual.screen import ModalScreen
from textual.widgets import Input, RichLog, TextArea
from textual_autocomplete import (
    AutoComplete,
    DropdownItem,
    MatcherFactoryType,
    TargetState,
)
from typing_extensions import TypeAlias


class CMP(AutoComplete):
    absolute_offset = Offset(0, 0)

    def __init__(
        self,
        target: Input | TextArea | str,
        candidates: list[DropdownItem] | Callable[[TargetState], list[DropdownItem]],
        matcher_factory: MatcherFactoryType | None = None,
        completion_strategy: (
            Callable[[str, TargetState], TargetState | None] | None
        ) = None,
        search_string: Callable[[TargetState], str] | None = None,
        prevent_default_enter: bool = True,
        prevent_default_tab: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            target,
            candidates,
            matcher_factory,
            completion_strategy,
            search_string,
            prevent_default_enter,
            prevent_default_tab,
            name,
            id,
            classes,
            disabled,
        )
        self.absolute_offset = Offset(0, 0)


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


CommandList: TypeAlias = List[Command]
"""A list of commands."""


class Parser:
    def __init__(self, commands: CommandList, *, target: Input):
        self._commands: dict[str, Command] = {cmd.name: cmd for cmd in commands}
        self._target = target

    def candidates(self, state: TargetState) -> list[DropdownItem]:
        text = state.text
        main_command_list = [
            DropdownItem(cmd, Text("󰊕", "blue")) for cmd in self._commands.keys()
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
                DropdownItem(choice, Text("", "red")) for choice in current_arg.choices
            ]
        except IndexError:
            return None


class CommandLine(Input):
    _cmp: CMP
    """The autocomplete component of this input widget."""

    def __init__(self, df: pd.DataFrame):
        self.df = df

        commands = [
            Command(
                "sort", arguments=[Argument("column_key", type=str, choices=df.columns)]
            ),
            Command(
                "goto", arguments=[Argument("column_key", type=str, choices=df.columns)]
            ),
            Command(
                "filter",
                arguments=[Argument("column_key", type=str, choices=df.columns)],
            ),
            Command(
                "filter2",
                arguments=[Argument("column_key", type=str, choices=df.columns)],
            ),
        ]
        self.parser = Parser(commands, target=self)

        super().__init__(placeholder="command line")
        self.id = "command-line"

    def get_new_state(self, text: str, state: TargetState) -> None:
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

    def on_mount(self):
        self._cmp = CMP(
            self,
            candidates=self.parser.candidates,
            search_string=get_last_word,
            completion_strategy=self.get_new_state,
            id="cmp",
        )
        self.screen.mount(self._cmp)


def get_last_word(state: TargetState) -> str:
    try:
        return state.text.split()[-1]
    except IndexError:
        return ""


class CmdLineScreen(ModalScreen):
    BINDINGS = [Binding("escape", "app.pop_screen")]

    def __init__(self, collection: pd.DataFrame, *_args, **_kwargs):
        self.collection = collection

        super().__init__(*_args, **_kwargs)

    def compose(self) -> ComposeResult:
        yield CommandLine(self.collection)
        yield RichLog()
