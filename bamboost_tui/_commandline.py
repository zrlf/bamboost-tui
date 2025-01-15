from __future__ import annotations

import argparse
import re
from argparse import Namespace
from dataclasses import dataclass, field
from operator import itemgetter
from typing import TYPE_CHECKING, Any, Callable, Iterable, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, Label
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
    choices: Iterable[str] | None = None

    argparse_args: dict[str, Any] | None = None
    """Any arguments to pass to argparse for this command/argument."""


@dataclass
class Option:
    name: str
    choices: Iterable[str] = field(default_factory=list)
    bool_flag: bool = False
    aliases: list[str] = field(default_factory=list)

    argparse_args: dict[str, Any] | None = None
    """Any arguments to pass to argparse for this command/argument."""


@dataclass
class Command:
    name: str
    arguments: list[Argument] = field(default_factory=list)
    options: dict[str, Option] = field(default_factory=dict)
    callback: Callable = lambda: None

    argparse_args: dict[str, Any] | None = None
    """Any arguments to pass to argparse for this command/argument."""


CommandList: TypeAlias = List[Command]
"""A list of commands."""


class Parser:
    def __init__(self, commands: CommandList, *, target: Input):
        self._commands: dict[str, Command] = {cmd.name: cmd for cmd in commands}
        self._target = target
        self._argparse_parser = self._create_argparse_parser(commands)

    def candidates(self, state: TargetState) -> list[DropdownItem]:
        text = state.text
        main_command_list = [
            DropdownItem(cmd, "function", "func") for cmd in self._commands.keys()
        ]
        if not text:
            return main_command_list

        if text.endswith(" "):
            tokens = state.text.split()
        else:
            tokens = state.text.split()[:-1]

        return self._get_current_options(tokens) or main_command_list

    def _get_current_options(self, tokens: list[str]) -> list[DropdownItem] | None:
        if not tokens:
            return None

        command_token, last_token = tokens[0], tokens[-1]
        if command_token not in self._commands:
            return None

        command = self._commands[command_token]
        consumed_options = set()  # the options that have been consumed before
        arg_count = 0  # number of arguments consumed
        options: list[DropdownItem] = []

        for token in tokens[1:]:
            if token.startswith("-"):
                consumed_options.add(token)
            else:
                arg_count += 1

        if last_token.startswith("-") and (
            choices := getattr(command.options.get(last_token), "choices", None)
        ):
            return [DropdownItem(opt, "variable", "choice") for opt in choices]

        options.extend(
            {
                DropdownItem(c, "variable", "option")
                for c in (command.options.keys() - consumed_options)
            }
        )

        try:
            current_arg = command.arguments[arg_count]
            if current_arg.choices is not None:
                options.extend(
                    [
                        DropdownItem(choice, "object", "column")
                        for choice in current_arg.choices
                    ]
                )
        except IndexError:
            pass

        return options

    def execute(self, text: str) -> None:
        try:
            args = self.parse(text.split())
            self._commands[args.command].callback(args)
        except Exception as e:
            self._target.notify(f"Invalid command: {e}", severity="error")

    def parse(self, args: list[str]) -> Namespace:
        parser = self._argparse_parser
        return parser.parse_args(args)

    def _create_argparse_parser(self, commands: CommandList) -> argparse.ArgumentParser:
        """Create the argparse parser for the given commands."""
        parser = argparse.ArgumentParser(exit_on_error=False)
        subparsers = parser.add_subparsers(dest="command")
        for command in commands:
            subparser = subparsers.add_parser(command.name, exit_on_error=False)
            for arg in command.arguments:
                subparser.add_argument(
                    arg.name, choices=arg.choices, **(arg.argparse_args or {})
                )
            for flag, opt in command.options.items():
                if opt.bool_flag:
                    subparser.add_argument(
                        flag,
                        action="store_true",
                        **(opt.argparse_args or {}),
                    )
                else:
                    subparser.add_argument(
                        flag,
                        choices=opt.choices,
                        **(opt.argparse_args or {}),
                    )

        return parser


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


class CmdLineScreen(ModalScreen):
    BINDINGS = [Binding("escape", "app.pop_screen")]

    def __init__(self, collection_table: "CollectionTable", *_args, **_kwargs):
        self._table = collection_table

        super().__init__(*_args, **_kwargs)

    def compose(self) -> ComposeResult:
        yield Horizontal(Label(":"), CommandLine(self._table), id="command-line")
        # yield RichLog()
