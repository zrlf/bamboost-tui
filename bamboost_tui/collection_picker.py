from __future__ import annotations

from time import monotonic

from bamboost.index import DEFAULT_INDEX
from bamboost.index.sqlmodel import CollectionORM
from rich.console import Group
from rich.style import Style as RichStyle
from rich.table import Column, Table
from rich.text import Text
from textual import work
from textual._context import active_app
from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import (
    Command,
    CommandInput,
    CommandList,
    CommandPalette,
    Hit,
    Hits,
    Matcher,
    Provider,
    SearchIcon,
)
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.visual import VisualType
from textual.widgets import Button, LoadingIndicator
from textual.worker import get_current_worker


class CollectionHit(Hit):
    class CollectionSelected(Message):
        def __init__(self, uid: str) -> None:
            self.uid = uid
            super().__init__()

    def __init__(
        self,
        score: float,
        collection: CollectionORM,
        picker: Picker,
        matcher: Matcher | None = None,
    ) -> None:
        self.collection = collection
        self._picker = picker
        super().__init__(
            score,
            self._render(matcher),
            lambda: self._picker.screen.post_message(
                CollectionHit.CollectionSelected(collection.uid)
            ),
        )

    def _render(self, matcher: Matcher | None = None) -> VisualType:
        coll = self.collection
        tab = Table.grid(
            *(Column(width=w) for w in self._picker._widths),
            padding=(0, 2),
            expand=True,
            pad_edge=False,
        )
        styles = self._picker.styles
        tab.add_row(
            Text(coll.uid, styles["uid"]),
            matcher.highlight(coll.path)
            if matcher
            else Text(coll.path, styles["path"]),
            Text(str(coll.simulations.__len__()), styles["count"]),
        )
        return Group(tab, Text("last modified: ", styles["help"]))


class Picker(Provider):
    """A command provider to select collections."""

    _table: Table

    def __init__(self, screen: Screen, match_style: RichStyle | None = None) -> None:
        super().__init__(screen, match_style)
        self.styles: dict[str, RichStyle] = {}

    async def startup(self) -> None:
        app = active_app.get()
        self.styles["uid"] = app.screen.get_component_rich_style(
            "collection-list--uid", partial=True
        )
        self.styles["path"] = app.screen.get_component_rich_style(
            "collection-list--path", partial=True
        )
        self.styles["count"] = app.screen.get_component_rich_style(
            "collection-list--count", partial=True
        )
        self.styles["help"] = app.screen.get_component_rich_style(
            "command-palette--help-text", partial=True
        )
        self.collections = DEFAULT_INDEX.all_collections
        widths = (0, 0, 0)
        for coll in self.collections:
            widths = tuple(
                max(width, len(str(cell)))
                for width, cell in zip(
                    widths, (coll.uid, coll.path, coll.simulations.__len__())
                )
            )
        self._widths = widths

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for coll in self.collections:
            score = matcher.match(coll.uid + coll.path)
            if score > 0:
                # yield Hit(score, self._render(coll, matcher), self.app.pop_screen)
                yield CollectionHit(score, coll, self, matcher)

    async def discover(self) -> Hits:
        for coll in self.collections:
            # yield Hit(1.0, self._render(coll), self.app.pop_screen)
            yield CollectionHit(1.0, coll, self)


class CollectionPicker(CommandPalette):
    BINDINGS = [
        Binding("ctrl+n", "cursor_down", "move cursor down", show=False),
        Binding("ctrl+p", "command_list('page_up')", "move cursor up", show=False),
    ]
    COMPONENT_CLASSES = CommandPalette.COMPONENT_CLASSES | {
        "collection-list--uid",
        "collection-list--path",
        "collection-list--count",
    }

    def __init__(self):
        super().__init__(providers=[Picker], placeholder="Search collections")

    def compose(self) -> ComposeResult:
        """Compose the command palette.

        Returns:
            The content of the screen.
        """
        with Vertical(id="--container"):
            with Horizontal(id="--input") as container:
                container.border_title = "Collection Picker"
                yield SearchIcon()
                yield CommandInput(placeholder=self._placeholder)
                if not self.run_on_select:
                    yield Button("\u25b6")
            with Vertical(id="--results"):
                yield CommandList()
                yield LoadingIndicator()

    @work(exclusive=True, group=CommandPalette._GATHER_COMMANDS_GROUP)
    async def _gather_commands(self, search_value: str) -> None:
        """Gather up all of the commands that match the search value.

        Args:
            search_value: The value to search for.
        """
        gathered_commands: list[Command] = []
        command_list = self.query_one(CommandList)
        if (
            command_list.option_count == 1
            and command_list.get_option_at_index(0).id == self._NO_MATCHES
        ):
            command_list.remove_option(self._NO_MATCHES)

        command_id = 0
        worker = get_current_worker()

        # Reset busy mode.
        self._show_busy = False
        clear_current = True
        last_update = monotonic()

        # Kick off the search, grabbing the iterator.
        search_routine = self._search_for(search_value)
        search_results = search_routine.__aiter__()

        # We're going to be doing the send/await dance in this code, so we
        # need to grab the first yielded command to start things off.
        try:
            hit = await search_results.__anext__()
        except StopAsyncIteration:
            hit = None

        while hit:
            # NEEDED TO CHANGE THIS LINE. RENDER THE PROMPT DIRECTLY
            prompt = hit.prompt

            gathered_commands.append(Command(prompt, hit, id=str(command_id)))

            if worker.is_cancelled:
                break

            now = monotonic()
            if (now - last_update) > self._RESULT_BATCH_TIME:
                self._refresh_command_list(
                    command_list, gathered_commands, clear_current
                )
                clear_current = False
                last_update = now

            command_id += 1

            try:
                hit = await search_routine.asend(worker.is_cancelled)
            except StopAsyncIteration:
                break

        if not worker.is_cancelled:
            self._refresh_command_list(command_list, gathered_commands, clear_current)

        # One way or another, we're not busy any more.
        self._show_busy = False

        if command_list.option_count == 0 and not worker.is_cancelled:
            self._hit_count = 0
            self._start_no_matches_countdown(search_value)

        self.add_class("-ready")
