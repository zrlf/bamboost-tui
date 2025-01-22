# ------------------------------------------------------------------------------
# Mostly copied from darrenburns/textual-autocomplete
#
# MIT License
#
# Copyright (c) 2023 Darren Burns
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ------------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import dataclass, field
from operator import itemgetter
from re import IGNORECASE, compile, escape
from typing import (
    Callable,
    ClassVar,
    Iterator,
    Literal,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    cast,
)

import rich.repr
from rich.measure import Measurement
from rich.padding import Padding
from rich.style import Style
from rich.text import Text, TextType
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.cache import LRUCache
from textual.css.query import NoMatches
from textual.geometry import Offset, Region, Spacing
from textual.widget import Widget
from textual.widgets import Input, Label, OptionList, TextArea
from textual.widgets.option_list import Option
from textual.widgets.text_area import Selection


@rich.repr.auto
class Matcher:
    """A fuzzy matcher."""

    def __init__(
        self,
        query: str,
        match_style: Style | None = None,
        case_sensitive: bool = False,
    ) -> None:
        """Initialise the fuzzy matching object.

        Args:
            query: A query as typed in by the user.
            match_style: The style to use to highlight matched portions of a string.
            case_sensitive: Should matching be case sensitive?
        """
        self._query = query
        self._match_style = Style(reverse=True) if match_style is None else match_style
        self._query_regex = compile(
            ".*?".join(f"({escape(character)})" for character in query),
            flags=0 if case_sensitive else IGNORECASE,
        )
        self._cache: LRUCache[str, float] = LRUCache(1024 * 4)

    @property
    def query(self) -> str:
        """The query string to look for."""
        return self._query

    @property
    def match_style(self) -> Style:
        """The style that will be used to highlight hits in the matched text."""
        return self._match_style

    @property
    def query_pattern(self) -> str:
        """The regular expression pattern built from the query."""
        return self._query_regex.pattern

    @property
    def case_sensitive(self) -> bool:
        """Is this matcher case sensitive?"""
        return not bool(self._query_regex.flags & IGNORECASE)

    def match(self, candidate: str) -> float:
        """Match the candidate against the query.

        Args:
            candidate: Candidate string to match against the query.

        Returns:
            Strength of the match from 0 to 1.
        """
        cached = self._cache.get(candidate)
        if cached is not None:
            return cached
        match = self._query_regex.search(candidate)
        if match is None:
            score = 0.0
        else:
            assert match.lastindex is not None
            offsets = [
                match.span(group_no)[0] for group_no in range(1, match.lastindex + 1)
            ]
            group_count = 0
            last_offset = -2
            for offset in offsets:
                if offset > last_offset + 1:
                    group_count += 1
                last_offset = offset

            score = 1.0 - ((group_count - 1) / len(candidate))
        self._cache[candidate] = score
        return score

    def highlight(self, candidate: str) -> Text:
        return Text(candidate)

    def _highlight(self, candidate: str) -> Text:
        """Highlight the candidate with the fuzzy match.

        Args:
            candidate: The candidate string to match against the query.

        Returns:
            A [rich.text.Text][`Text`] object with highlighted matches.
        """
        match = self._query_regex.search(candidate)
        text = Text(candidate)
        if match is None:
            return text
        offsets = [
            match.span(group_no)[0] for group_no in range(1, match.lastindex + 1)
        ]
        for offset in offsets:
            text.stylize(self._match_style, offset, offset + 1)

        return text


@dataclass
class TargetState:
    text: str
    """The content in the target widget."""

    selection: Selection
    """The selection of the target widget."""


class SearchString(NamedTuple):
    start_location: int
    value: str


class InvalidTarget(Exception):
    """Raised if the target is invalid, i.e. not something which can
    be autocompleted."""


class DropdownItem(Option):
    _option_type_symbols = {
        "function": Text("󰊕", "blue dim", no_wrap=True),
        "variable": Text("󰊖", "yellow dim", no_wrap=True),
        # "object": "󰊗",
        "object": Text("", "red dim", no_wrap=True),
    }

    def __init__(
        self,
        main: TextType,
        # left_meta: TextType | None = None,
        option_type: Literal["function", "variable", "object"] | None = None,
        right_meta: TextType | None = None,
        # popup: TextType | None = None,
        id: str | None = None,
        disabled: bool = False,
    ) -> None:
        """A single option appearing in the autocompletion dropdown. Each option has up to 3 columns.
        Note that this is not a widget, it's simply a data structure for describing dropdown items.

        Args:
            left: The left column will often contain an icon/symbol, the main (middle)
                column contains the text that represents this option.
            main: The main text representing this option - this will be highlighted by default.
                In an IDE, the `main` (middle) column might contain the name of a function or method.
            search_string: The string that is being used for matching.
            highlight_ranges: Custom ranges to highlight. By default, the value is None,
                meaning textual-autocomplete will highlight substrings in the dropdown.
                That is, if the value you've typed into the Input is a substring of the candidates
                `main` attribute, then that substring will be highlighted. If you supply your own
                implementation of `items` which uses a more complex process to decide what to
                display in the dropdown, then you can customise the highlighting of the returned
                candidates by supplying index ranges to highlight.
        """
        self.main = Text(main, no_wrap=True) if isinstance(main, str) else main
        self.left_meta = (
            self._option_type_symbols[option_type] if option_type is not None else None
        )

        self.right_meta = (
            Text(right_meta, no_wrap=True, style="dim", justify="right")
            if isinstance(right_meta, str)
            else right_meta
        )
        # self.popup = (
        #     Text(popup, no_wrap=True, style="dim") if isinstance(popup, str) else popup
        # )
        left = self.left_meta
        prompt = self.main
        if left:
            prompt = Padding(Text.assemble(left, "  ", self.main), pad=(0, 1))
        # if self.right_meta:
        #     prompt = Text.assemble(prompt, " ", self.right_meta)

        super().__init__(prompt, id, disabled)


class AutoCompleteList(OptionList):
    DEFAULT_CSS = """
    AutoCompleteList {
        max-height: 20;
    }
    """

    def get_content_width(
        self, container: events.Resize, viewport: events.Resize
    ) -> int:
        """Get maximum width of options."""
        console = self.app.console
        options = console.options
        max_width = max(
            (
                Measurement.get(console, options, option.prompt).maximum  # pyright: ignore[reportArgumentType]
                for option in self._options
            ),
            default=1,
        )
        max_width += self.scrollbar_size_vertical
        return max_width


MatcherFactoryType = Callable[[str, Optional[Style], bool], Matcher]

TargetType = TypeVar("TargetType", bound=Union[Input, TextArea])


@dataclass
class CmpKeybinds:
    """The keys that are intercepted from the input widget and used to control the
    autocomplete dropdown.
    """

    down: set[str] = field(default_factory=lambda: {"down", "ctrl+n"})
    up: set[str] = field(default_factory=lambda: {"up", "ctrl+p"})
    select: set[str] = field(default_factory=lambda: {"tab"})
    toggle: set[str] = field(default_factory=lambda: {"ctrl+space"})


class AutoComplete(Widget):
    BINDINGS = [
        Binding("escape", "hide", "Hide dropdown", show=False),
    ]
    DEFAULT_CSS = """\
    AutoComplete {
        position: absolute;
        layer: textual-autocomplete;
        height: auto;
        width: auto;
        max-height: 12;
        display: none;
        background: $surface-lighten-1;

        & AutoCompleteList {
            width: auto;
            height: auto;
            border: none;
            padding: 0;
            margin: 0;
            scrollbar-size-vertical: 1;
            scrollbar-size-horizontal: 0;
            &:focus {
                border: none;
                padding: 0;
                margin: 0;
            }
            & > .option-list--option-highlighted, & > .option-list--option-hover-highlighted {
                color: $text;
                background: $surface-lighten-3 60%;
            }
            
        }

        & .autocomplete--highlight-match {
            color: $text;
            background: $primary-lighten-1;
        }
    }
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "autocomplete--highlight-match",
    }

    def __init__(
        self,
        target: Input | str,
        candidates: list[DropdownItem] | Callable[[TargetState], list[DropdownItem]],
        matcher_factory: MatcherFactoryType | None = None,
        completion_strategy: (
            Callable[[str, TargetState], TargetState | None] | None
        ) = None,
        search_string: Callable[[TargetState], str] | None = None,
        prevent_default_enter: bool = True,
        prevent_default_tab: bool = True,
        keybinds: CmpKeybinds | None = None,
        position: Literal["top", "bottom"] = "top",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        self._position: Literal["top", "bottom"] = position

        self._target = target
        """An Input instance, TextArea instance, or a selector string used to query an Input/TextArea instance.
        
        Must be on the same screen as the dropdown instance."""

        self.completion_strategy = completion_strategy
        """A function which modifies the state of the target widget 
        to perform the completion.
        If None, the default behavior will be used.
        """

        self.candidates = candidates
        """The candidates to match on, or a function which returns the candidates to match on."""

        self.matcher_factory = Matcher if matcher_factory is None else matcher_factory
        """A factory function that returns the Matcher to use for matching and highlighting."""

        self.search_string = search_string
        """A function that returns the search string to match on.
        
        This is the string that will be passed into the matcher.

        If None, the default the default behavior will be used.

        For Input widgets, the default behavior is to use the entire value 
        as the search string.

        For TextArea widgets, the default behavior is to use the text before the cursor 
        as the search string, up until the last whitespace.
        """

        self.prevent_default_enter = prevent_default_enter
        """Prevent the default enter behavior."""

        self.prevent_default_tab = prevent_default_tab
        """Prevent the default tab behavior."""

        self._keybinds = keybinds or CmpKeybinds()

        self.last_action_was_completion = False
        """Used to filter duplicate performing an action twice on a character insertion.
        An insertion/deletion moves the cursor and creates a "changed" event, so we end up
        with two events for the same action.
        """

        self._target_state = TargetState("", Selection.cursor((0, 0)))
        """Cached state of the target Input/TextArea."""

    def compose(self) -> ComposeResult:
        option_list = AutoCompleteList(wrap=False)
        option_list.can_focus = False
        yield option_list

    def on_mount(self) -> None:
        # Subscribe to the target widget's reactive attributes.
        self.target.message_signal.subscribe(self, self._listen_to_messages)  # type: ignore
        # self.screen.screen_layout_refresh_signal.subscribe(  # type: ignore
        #     self,
        #     lambda _event: self._align_to_target(),  # type: ignore
        # )
        self._subscribe_to_target()
        self._handle_target_update()

    def _listen_to_messages(self, event: events.Event) -> None:
        """Listen to some events of the target widget."""

        try:
            option_list = self.option_list
        except NoMatches:
            # This can happen if the event is an Unmount event
            # during application shutdown.
            return

        if isinstance(event, events.Key) and option_list.option_count:
            displayed = self.display
            highlighted = option_list.highlighted or 0
            keybinds = self._keybinds
            if event.key in keybinds.down:
                # Check if there's only one item and it matches the search string
                if option_list.option_count == 1:
                    search_string = self.get_search_string(self._get_target_state())
                    first_option = option_list.get_option_at_index(0).prompt
                    text_from_option = (
                        first_option.plain
                        if isinstance(first_option, Text)
                        else first_option
                    )
                    if text_from_option == search_string:
                        # Don't prevent default behavior in this case
                        return

                event.stop()
                event.prevent_default()
                # If you press `down` while in an Input and the autocomplete is currently
                # hidden, then we should show the dropdown.
                if isinstance(self.target, Input):
                    if not displayed:
                        self.display = True
                        highlighted = 0
                    else:
                        highlighted = (highlighted + 1) % option_list.option_count
                else:
                    if displayed:
                        highlighted = (highlighted + 1) % option_list.option_count

                option_list.highlighted = highlighted

            elif event.key in keybinds.up:
                if displayed:
                    event.stop()
                    event.prevent_default()
                    highlighted = (highlighted - 1) % option_list.option_count
                    option_list.highlighted = highlighted

            elif event.key in keybinds.select:
                if self.prevent_default_tab and displayed:
                    event.stop()
                    event.prevent_default()
                self._complete(option_index=highlighted)

            elif event.key in keybinds.toggle:
                self.action_toggle_visibility()

        if isinstance(event, (Input.Changed, TextArea.Changed)):
            self._handle_target_update()

    def action_hide(self) -> None:
        self.styles.display = "none"

    def action_show(self) -> None:
        self.styles.display = "block"

    def action_toggle_visibility(self) -> None:
        if self.display:
            self.action_hide()
        else:
            height = min(
                self.option_list.option_count, self.option_list.styles.max_height.value
            )
            self._align_to_target(height, 0)  # pyright: ignore[reportArgumentType]
            self.action_show()

    def _complete(self, option_index: int) -> None:
        """Do the completion (i.e. insert the selected item into the target input/textarea).

        This is when the user highlights an option in the dropdown and presses tab or enter.
        """
        if not self.display or self.option_list.option_count == 0:
            return

        target = self.target
        completion_strategy = self.completion_strategy
        option_list = self.option_list
        highlighted = option_index
        option = cast(DropdownItem, option_list.get_option_at_index(highlighted))
        highlighted_value = option.main.plain

        if completion_strategy is None:
            target.value = ""
            target.insert_text_at_cursor(highlighted_value)
        elif callable(completion_strategy):
            completion_strategy(
                highlighted_value,
                self._get_target_state(),
            )

        # Set a flag indicating that the last action that was performed
        # was a completion. This is so that when the target posts a Changed message
        # as a result of this completion, we can opt to ignore it in `handle_target_updated`
        self.last_action_was_completion = True
        self.action_hide()

    def yield_characters_before_cursor(
        self, target: Input
    ) -> Iterator[tuple[str, int]]:
        column = target.cursor_position

        start = 0
        text = target.value[start:column]
        for char in reversed(text):
            column -= 1
            yield char, column

    def get_text_area_word_bounds_before_cursor(self, target: Input) -> tuple[int, int]:
        """Get the bounds of the word before the cursor in a TextArea.

        A word is defined as a sequence of alphanumeric characters or underscores,
        bounded by the start of the line, a space, or a non-alphanumeric character.

        Returns:
            A tuple containing the start and end positions of the word as (row, column) tuples.
        """
        cursor_location = target.cursor_position
        for char, column in self.yield_characters_before_cursor(target):
            if not char.isalnum() and char not in "$_-":
                return column + 1, cursor_location
            elif column == 0:
                return column, cursor_location

        return cursor_location, cursor_location

    @property
    def target(self) -> Input:
        """The resolved target widget."""
        if isinstance(self._target, Input):
            return self._target
        else:
            target = self.screen.query_one(self._target)
            assert isinstance(target, Input)
            return target

    def _subscribe_to_target(self) -> None:
        """Attempt to subscribe to the target widget, if it's available."""
        target = self.target
        self.watch(target, "has_focus", self._handle_focus_change)
        self.watch(target, "cursor_position", self._align_to_target)

    def _handle_target_message(self, message: events.Event) -> None:
        if isinstance(message, Input.Changed):
            self._handle_target_update()

    def _align_to_target(
        self, height: int | None = None, width: int | None = None
    ) -> None:
        cursor_x, cursor_y = self.target.cursor_screen_offset
        dropdown = self.query_one(OptionList)
        if height is None or width is None:
            width, height = dropdown.size
        x, y, _width, _height = Region(
            cursor_x,
            cursor_y + 1,
            width,
            height,
        ).constrain("inside", "none", Spacing.all(0), self.screen.region)
        self.styles.offset = self._get_necessary_offset(x, y, _width, _height)

    def _get_necessary_offset(self, x, y, width, height) -> tuple[int, int]:
        if self._position == "top":
            return max(x - 1, 0), max(y - height - 1, 0)
        else:
            return max(x - 1, 0), y

    def _get_target_state(self) -> TargetState:
        """Get the state of the target widget."""
        target = self.target
        return TargetState(
            text=target.value,
            selection=Selection.cursor((0, target.cursor_position)),  # type: ignore
        )

    def _handle_focus_change(self, has_focus: bool) -> None:
        """Called when the focus of the target widget changes."""
        if not has_focus:
            self.action_hide()
        else:
            search_string = self.get_search_string(self._target_state)
            self._rebuild_options(
                self._compute_matches(self._target_state, search_string)
            )

    def _handle_target_update(self) -> None:
        """Called when the state (text or selection) of the target is updated.

        Here we align the dropdown to the target, determine if it should be visible,
        and rebuild the options in it.
        """
        self._target_state = self._get_target_state()
        search_string = self.get_search_string(self._target_state)

        # Determine visibility after the user makes a change in the
        # target widget (e.g. typing in a character in the Input).
        matches = self._compute_matches(self._target_state, search_string)
        # first align, then rebuild the optionlist
        height = min(len(matches), self.option_list.styles.max_height.value)  # pyright: ignore[reportArgumentType]
        self._align_to_target(height, 0)  # pyright: ignore[reportArgumentType]
        self._rebuild_options(matches)

        if self.should_show_dropdown(search_string):
            self.action_show()
        else:
            self.action_hide()

        # We've rebuilt the options based on the latest change,
        # however, if the user made that change via selecting a completion
        # from the dropdown, then we always want to hide the dropdown.
        if self.last_action_was_completion:
            self.last_action_was_completion = False
            self.action_hide()
            return

    def should_show_dropdown(self, search_string: str) -> bool:
        """
        Determine whether to show or hide the dropdown based on the current state.

        This method can be overridden to customize the visibility behavior.

        Args:
            search_string: The current search string.

        Returns:
            bool: True if the dropdown should be shown, False otherwise.
        """
        option_list = self.option_list
        option_count = option_list.option_count

        if option_count == 0:
            return False
        elif option_count == 1:
            first_option = option_list.get_option_at_index(0).prompt
            text_from_option = (
                first_option.plain if isinstance(first_option, Text) else first_option
            )
            return text_from_option != search_string
        else:
            return True

    def _rebuild_options(self, matches: list[DropdownItem] | None) -> None:
        """Rebuild the options in the dropdown.

        Args:
            target_state: The state of the target widget.
        """
        option_list = self.option_list
        option_list.clear_options()
        if self.target.has_focus:
            if matches:
                option_list.add_options(matches)
                option_list.highlighted = 0

    def get_search_string(self, target_state: TargetState) -> str:
        """This value will be passed to the matcher.

        This could be, for example, the text in the target widget, or a substring of that text.

        For Input widgets the default is to use the text in the input, and for TextArea widgets
        the default is to use the text in the TextArea before the cursor up to the most recent
        non-alphanumeric character.

        Subclassing AutoComplete to create a custom `get_search_string` method is a way to
        customise the behaviour of the autocomplete dropdown.

        Returns:
            The search string that will be used to filter the dropdown options.
        """
        if self.search_string is not None:
            search_string = self.search_string(target_state)
            return search_string

        return target_state.text

    def _compute_matches(
        self, target_state: TargetState, search_string: str
    ) -> list[DropdownItem]:
        """Compute the matches based on the target state.

        Args:
            target_state: The state of the target widget.

        Returns:
            The matches to display in the dropdown.
        """

        # If items is a callable, then it's a factory function that returns the candidates.
        # Otherwise, it's a list of candidates.
        candidates = self.get_candidates(target_state)
        return self.get_matches(target_state, candidates, search_string)

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """Get the candidates to match against."""
        candidates = self.candidates
        return candidates(target_state) if callable(candidates) else candidates

    def get_matches(
        self,
        target_state: TargetState,
        candidates: list[DropdownItem],
        search_string: str,
    ) -> list[DropdownItem]:
        """Given the state of the target widget, return the DropdownItems
        which match the query string and should be appear in the dropdown.

        Args:
            target_state: The state of the target widget.
            candidates: The candidates to match against.

        Returns:
            The matches to display in the dropdown.
        """
        if not search_string:
            return candidates

        match_style = self.get_component_rich_style("autocomplete--highlight-match")
        matcher = self.matcher_factory(search_string, match_style, False)

        matches_and_scores: list[tuple[DropdownItem, float]] = []
        append_score = matches_and_scores.append
        get_score = matcher.match
        get_highlighted = matcher.highlight

        for candidate in candidates:
            candidate_string = candidate.main.plain
            if (score := get_score(candidate_string)) > 0:
                # highlighted_text = get_highlighted(candidate_string)
                # highlighted_item = DropdownItem(
                #     main=highlighted_text,
                #     left_meta=candidate.left_meta,
                #     id=candidate.id,
                #     disabled=candidate.disabled,
                # )
                append_score((candidate, score))

        matches_and_scores.sort(key=itemgetter(1), reverse=True)
        matches = [match for match, _ in matches_and_scores]
        return matches

    @property
    def option_list(self) -> AutoCompleteList:
        return self.query_one(AutoCompleteList)

    @on(OptionList.OptionSelected, "AutoCompleteList")
    def _apply_completion(self, event: OptionList.OptionSelected) -> None:
        self._complete(event.option_index)
