from __future__ import annotations

import argparse
import re
from argparse import Namespace
from dataclasses import field
from functools import partial
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Iterable,
    Type,
    TypeVar,
    Union,
    overload,
)

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Input, Label
from textual.widgets.data_table import ColumnKey
from typing_extensions import Self

from bamboost_tui.widgets import (
    AutoComplete,
    DropdownItem,
    TargetState,
)

if TYPE_CHECKING:
    from bamboost_tui.collection_table import CollectionTable

    ChoicesType = Union[Iterable[str], Callable[["CommandLine"], Iterable[str]], None]
    ChoicesResolvedType = Iterable[str]

T = TypeVar("T")


class Argument(Generic[T]):
    def __init__(
        self,
        name: str,
        choices: ChoicesType = None,
        argparse_args: dict[str, Any] | None = None,
    ):
        self.name = name
        self._choices = choices
        self.argparse_args = argparse_args
        self._value: T | None = None

    def _resolve(self, command_line: CommandLine) -> Self:
        choices = self._choices
        if callable(choices):
            self._resolved_choices = choices(command_line)
        else:
            self._resolved_choices = choices or []

        return self

    @property
    def choices(self) -> ChoicesResolvedType:
        try:
            return self._resolved_choices
        except AttributeError:
            raise ValueError("Choices have not been resolved yet.")

    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...
    @overload
    def __get__(self, instance: object, owner: type) -> T: ...
    def __get__(self, instance, owner):
        """Allows access to the default value directly when used in a class."""
        if instance is None:
            return self  # Allow class-level access
        return self._value  # Return the actual value when accessed

    def __set__(self, instance: CommandMessage, value: T) -> None:
        self._value = value

    def set_value(self, value: T) -> None:
        self._value = value


class Option(Argument[T]):
    bool_flag: bool = False
    aliases: list[str] = field(default_factory=list)

    def __init__(
        self,
        name: str,
        choices: ChoicesType = None,
        bool_flag: bool = False,
        aliases: list[str] | None = None,
        argparse_args: dict[str, Any] | None = None,
    ):
        super().__init__(name, choices, argparse_args)
        self.aliases = aliases or []
        self.bool_flag = bool_flag


class CommandMessage(Message):
    _arguments: list[Argument]
    """The arguments for this command tied to the command line."""
    _options: dict[str, Option]
    """The options for this command tied to the command line."""

    def __init__(self, target: CommandLine):
        super().__init__()
        self._target = target
        self._arguments = []
        self._options = {}

        # Check all class variables that are Arguments or Options
        for name, attr in self.__class__.__dict__.items():
            if isinstance(attr, Argument):
                resolved_attr = attr._resolve(target)
                setattr(self, name, resolved_attr)
                if isinstance(attr, Option):
                    self._options[attr.name] = resolved_attr  # type: ignore
                else:
                    self._arguments.append(resolved_attr)

    @classmethod
    def name(cls) -> str:
        return cls.__name__.lower()

    def set_parsed_values(self, args: Namespace) -> Self:
        for arg in chain(self._arguments, self._options.values()):
            # strip any leading dashes from the argument name
            arg_name = arg.name.lstrip("-")
            setattr(self, arg_name, getattr(args, arg_name))
        return self


class Parser:
    def __init__(
        self, *commands: Type[CommandMessage], target: CommandLine, prefix: str = ""
    ):
        self._target = target
        self._commands: dict[str, CommandMessage] = {
            cmd.__name__.lower(): cmd(target) for cmd in commands
        }
        self._argparse_parser = self._create_argparse_parser(
            [cmd(target) for cmd in commands]
        )
        self._prefix = prefix

    def candidates(self, state: TargetState) -> list[DropdownItem]:
        text = self._prefix + " " + state.text
        main_command_list = [
            DropdownItem(cmd, "function", "func") for cmd in self._commands.keys()
        ]
        if not text:
            return main_command_list

        if text.endswith(" "):
            tokens = text.split()
        else:
            tokens = text.split()[:-1]

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
            choices := getattr(command._options.get(last_token), "choices", None)
        ):
            return [DropdownItem(opt, "variable", "choice") for opt in choices]

        options.extend(
            {
                DropdownItem(c, "variable", "option")
                for c in (command._options.keys() - consumed_options)
            }
        )

        try:
            current_arg = command._arguments[arg_count]
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

    def _create_argparse_parser(
        self, commands: Iterable[CommandMessage]
    ) -> argparse.ArgumentParser:
        """Create the argparse parser for the given commands."""
        parser = argparse.ArgumentParser(exit_on_error=False)
        subparsers = parser.add_subparsers(dest="command")
        for command in commands:
            subparser = subparsers.add_parser(command.name(), exit_on_error=False)
            for arg in command._arguments:
                subparser.add_argument(
                    arg.name, choices=arg.choices, **(arg.argparse_args or {})
                )
            for flag, opt in command._options.items():
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

    def parse(self, text: str) -> CommandMessage:
        text = self._prefix + " " + text
        parser = self._argparse_parser
        args = parser.parse_args(text.split())
        return self._commands[args.command].set_parsed_values(args)


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
    cmp: AutoComplete
    """The autocomplete component of this command line."""

    class Sort(CommandMessage):
        column_key = Argument[str](
            "column_key", lambda command_line: command_line.collection.df.columns
        )
        reverse = Option[bool]("--reverse", bool_flag=True, aliases=["-r"])

    class GoTo(CommandMessage):
        column_key = Argument[ColumnKey](
            "column_key", lambda command_line: command_line.collection.df.columns
        )

    def __init__(
        self,
        collection: CollectionTable,
        prefix: str = "",
        label: str = ":",
        placeholder: str = "command line",
    ):
        super().__init__()

        self.collection = collection
        self.prefix = prefix
        self.label = label
        self.placeholder = placeholder
        self.parser = Parser(
            CommandLine.Sort,
            CommandLine.GoTo,
            target=self,
            prefix=prefix,
        )

    def compose(self) -> ComposeResult:
        with Horizontal(id="command-line"):
            yield Label(self.label)
            yield CommandLineInput(placeholder=self.placeholder)

    def on_mount(self) -> None:
        # here we mount the autocompletion widget
        input_widget = self.query_one(CommandLineInput)
        self.mount(
            AutoComplete(
                input_widget,
                candidates=self.parser.candidates if self.parser else [],
                search_string=_search_string,
                completion_strategy=partial(_complete, input_widget),
                prevent_default_enter=False,
            )
        )

    @on(Input.Submitted)
    def _input_submitted(self, message: Input.Submitted) -> None:
        """Function that will be called when the enter key is pressed."""
        try:
            command_message = self.parser.parse(message.value)
            self.dismiss(command_message)
        except argparse.ArgumentError as e:
            self.dismiss()
            self.notify(str(e), severity="error")


class CommandLineInput(Input, can_focus=True):
    """The autocomplete component of this input widget."""

    DEFAULT_CSS = """
    CommandLineInput {
    }
    """
    BINDINGS = [
        Binding("alt+backspace", "delete_left_word"),
    ]

    async def action_submit(self) -> None:
        await super().action_submit()
        self.clear()


def _complete(input_widget: Input, text: str, state: TargetState) -> None:
    """The function that will be called when a completion is selected. It will replace
    the last word with the selected completion.
    """
    WHITESPACE_BEFORE = re.compile(r"(?<=\s)\S")

    # delete the last word to the last whitespace
    try:
        *_, hit = re.finditer(
            WHITESPACE_BEFORE, input_widget.value[: input_widget.cursor_position]
        )
    except ValueError:
        target = 0
    else:
        target = hit.start()

    if not input_widget.value.endswith(" "):
        input_widget.delete(target, input_widget.cursor_position)

    # add the new word
    input_widget.insert_text_at_cursor(text + " ")


def _search_string(state: TargetState) -> str:
    """Function that extracts the search string from the current state."""
    text = state.text
    if not text or text.endswith(" "):
        return ""
    return text.split()[-1]
