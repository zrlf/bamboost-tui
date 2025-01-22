from __future__ import annotations

import argparse
from argparse import Namespace
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Iterable, List

from textual.widget import Widget
from textual.widgets import Input
from typing_extensions import Self, TypeAlias

from bamboost_tui.commandline._cmp import (
    DropdownItem,
    TargetState,
)

if TYPE_CHECKING:
    pass


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


CommandList: TypeAlias = Iterable[Command]
"""A list of commands."""


class Parser:
    def __init__(self, *commands: Command, prefix: str = ""):
        self._commands_raw = commands
        self._commands: dict[str, Command] = {cmd.name: cmd for cmd in commands}
        self._argparse_parser = self._create_argparse_parser(commands)
        self._prefix = prefix

    def set_prefix(self, prefix: str) -> Parser:
        return Parser(*self._commands_raw, prefix=prefix)

    def candidates(self, state: TargetState) -> list[DropdownItem]:
        text = f"{self._prefix} {state.text}"
        main_command_list = [
            DropdownItem(cmd, "function", "func") for cmd in self._commands.keys()
        ]
        if not text:
            return main_command_list

        if text.endswith(" "):
            tokens = state.text.split()
        else:
            tokens = state.text.split()[:-1]

        if (res := self._get_current_options(tokens)) is not None:
            return res
        else:
            return main_command_list

    def _get_current_options(self, tokens: list[str]) -> list[DropdownItem] | None:
        if not tokens:
            return None

        command_token, last_token = tokens[0], tokens[-1]
        if command_token not in self._commands:
            return []

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
        text = self._prefix + " " + text
        try:
            args = self.parse(text.split())
            self._commands[args.command].callback(args)
        except Exception as e:
            from textual._context import active_app

            active_app.get().notify(f"Invalid command: {e}", severity="error")

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
