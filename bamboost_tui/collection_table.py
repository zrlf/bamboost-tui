from __future__ import annotations

from datetime import datetime
from itertools import chain, cycle
from textwrap import dedent
from typing import TYPE_CHECKING

import pandas as pd
from bamboost.index import DEFAULT_INDEX
from rich.highlighter import ReprHighlighter
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.color import Color
from textual.containers import Center, Container, Horizontal, Right
from textual.coordinate import Coordinate
from textual.geometry import Offset, Region
from textual.reactive import reactive, var
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static, Tab
from textual.widgets.data_table import ColumnKey
from typing_extensions import Self

from bamboost_tui._datatable import ModifiedDataTable, SortOrder
from bamboost_tui.collection_picker import CollectionHit, CollectionPicker
from bamboost_tui.commandline import CommandLine, CommandMessage
from bamboost_tui.hdfview import HDFViewer
from bamboost_tui.utils import KeySubgroupsMixin

if TYPE_CHECKING:
    from textual.app import ComposeResult, RenderResult


class Header(Widget, can_focus=False):
    DEFAULT_CSS = """
    Header {
        height: auto;
        width: auto;
    }
    """
    COMPONENT_CLASSES = Static.COMPONENT_CLASSES | {
        "--uid",
        "--path",
    }

    def __init__(self, uid: str | None = None, path: str | None = None) -> None:
        uid = uid or ""
        self.uid = uid
        self.path = self._get_path(uid)
        super().__init__(id="collection-header")

    def render(self) -> RenderResult:
        tab = Table.grid("key", "value", padding=(0, 3))
        if self.uid:
            tab.add_row(
                "UID:",
                self.uid,
                style=self.get_component_rich_style("--uid", partial=True),
            )
            tab.add_row(
                "Path:",
                self.path or "[collection not found]",
                style=self.get_component_rich_style("--path", partial=True),
            )
        return tab

    def _get_path(self, uid: str | None) -> str:
        found_path = DEFAULT_INDEX._get_collection_path(uid) if uid else None
        return found_path.as_posix() if found_path else "[Collection location found]"

    def on_mount(self):
        self.watch(self.screen, "current_uid", self._watch_current_uid, init=False)

    def _watch_current_uid(self, _old, _new: str | None) -> None:
        self.uid = _new
        self.path = self._get_path(_new)
        self.refresh(layout=True)


class OpenCollectionsTabs(Widget):
    DEFAULT_CSS = """
    OpenCollectionsTabs {
        height: 1;
        layout: horizontal;

        Tab {
            padding: 0 1;
            height: 1;
            width: auto;
            color: $panel;
        }
        Tab.-active {
            background: $surface;
            text-style: bold;
        }
    }
    """
    tabs: set[str]
    screen: ScreenCollection

    def __init__(self):
        super().__init__(id="collections-tabs")
        self.tabs = set()

    def on_mount(self):
        self.watch(self.screen, "current_uid", self._watch_current_uid, init=False)

    def _watch_current_uid(self, _old, _new: str | None) -> None:
        self.tabs = set(self.screen._open_collections.keys())
        self.refresh(recompose=True)
        self.call_after_refresh(self.set_active, _new)

    def set_active(self, new: str | None) -> None:
        if new is None:
            return
        self.query("Tab.-active").remove_class("-active")
        self.query(f"Tab#tab-{new}").add_class("-active")

    def compose(self) -> ComposeResult:
        yield from (Tab(key, id=f"tab-{key}") for key in self.tabs)


class Placeholder(Static):
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
        with Center():
            val = self.app.theme_variables.get("secondary")
            c = Color.parse(val).rich_color.name
            yield Static(
                f"No collection selected. Press [bold {c}]Ctrl+M[/bold {c}] to open the collection picker.",
            )
        with Center():
            val = self.app.theme_variables.get("panel")
            c = Color.parse(val).rich_color.name
            yield Static(Text("A creation of florez/zrlf ♥", style=f"italic {c}"))


class TableContainer(Container):
    _widget: reactive[CollectionTable | Placeholder] = reactive(
        Placeholder, recompose=True
    )
    DEFAULT_CLASSES = "placeholder"

    def __init__(self, id: str | None = None):
        super().__init__(id=id)
        self.set_reactive(TableContainer._widget, Placeholder())

    def watch__widget(self, old: Widget, new: Widget) -> None:
        if isinstance(new, Placeholder):
            self.add_class("placeholder")
        else:
            self.remove_class("placeholder")

    def compose(self) -> ComposeResult:
        yield self._widget

    def focus(self, scroll_visible: bool = True) -> CollectionTable | Placeholder:
        return self._widget.focus(scroll_visible)


REPR_HIGHLIGHTER = ReprHighlighter()


def cell_highlighter(cell: object) -> Text:
    if isinstance(cell, datetime):
        cell = cell.strftime("%Y-%m-%d %H:%M:%S")

    highlighted = REPR_HIGHLIGHTER(
        Text(
            str(cell),
            justify="right" if str(cell).isdecimal() else "left",
        )
    )
    return highlighted


class CollectionTable(ModifiedDataTable, KeySubgroupsMixin, inherit_bindings=False):
    BINDINGS = [
        Binding("j,down", "cursor_down", "move cursor down", show=False),
        Binding("k,up", "cursor_up", "move cursor up", show=False),
        Binding("l,right", "cursor_right", "move cursor right", show=False),
        Binding("h,left", "cursor_left", "move cursor left", show=False),
        Binding("s", "sort_column", "sort column"),
        Binding("G", "cursor_to_end", "move cursor to end", show=False),
        Binding("g>g", "cursor_to_home", "move cursor to start", show=False),
        Binding("enter", "select_cursor", "show simulation", show=False),
        Binding("ctrl+d,pagedown", "page_down", "scroll page down", show=False),
        Binding("ctrl+u,pageup", "page_up", "scroll page up", show=False),
        Binding(":", "command_line", "enter command mode", show=True),
        Binding("/", 'command_line("goto", "")', "jump to column", show=True),
    ]
    BINDING_GROUP_TITLE = "Collection commands"
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {
        "datatable--label",
    }
    HELP = """
    Explore your simulations in this collection. Enter to view the respective HDF file.
    """
    DEFAULT_CSS = """
    CollectionTable {
        layers: bottom top;
    }
    """

    df: var[pd.DataFrame | None] = var(None, init=False, always_update=True)
    """The pandas DataFrame from which the table is built."""

    def __init__(self, uid: str):
        super().__init__(
            header_height=2,
            cursor_type="cell",
            cell_highlighter=cell_highlighter,
            cursor_foreground_priority="renderable",
            cursor_background_priority="css",
            id=f"table-{uid}",
        )

        self.uid: str = uid
        """The collection uid to display."""

        self._create_subgroup_mapping()

    def on_mount(self):
        if self.df is None:
            self.loading = True
            self._load_data()
        self.focus()

    @work(exclusive=True)
    async def _load_data(self):
        sims = DEFAULT_INDEX.collection(self.uid).simulations
        tab = [i.as_dict(standalone=False) for i in sims]
        self.df = pd.DataFrame.from_records(tab)
        """The DataFrame that holds the data for the table."""
        self.loading = False
        self.focus()

    async def watch_df(self, _old, _new: pd.DataFrame | None) -> None:
        if _new is None:
            return

        await self._create_table()
        self.refresh(layout=True)

    async def _create_table(self) -> Self:
        # clear the current table
        self.clear(True)

        # build columns and rows from dataframe
        for col in self.df.columns:
            self.add_column(str(col), key=str(col))
        try:
            names = self.df["name"]
        except KeyError:
            names = self.df.index
        for row, name in zip(self.df.values, names):
            self.add_row(*row, key=str(name))

        self.fixed_columns = 1
        return self

    def watch_cursor_coordinate(
        self, old_coordinate: Coordinate, new_coordinate: Coordinate
    ) -> None:
        old_region = self._get_cell_region(old_coordinate)
        new_region = self._get_cell_region(new_coordinate)

        if new_coordinate.column != old_coordinate.column:
            # Refresh header cell
            old_region_h = Region(old_region.x, 0, old_region.width, self.header_height)
            new_region_h = Region(new_region.x, 0, new_region.width, self.header_height)
            self.refresh(
                old_region_h.translate(-Offset(self.scroll_offset.x, 0)),
                new_region_h.translate(-Offset(self.scroll_offset.x, 0)),
            )
            self._header_cell_render_cache.clear()
        else:
            # Refresh entire row highlighting
            old = Region(old_region.x, old_region.y, self.size.width, old_region.height)
            self._refresh_region(old)
            new = Region(new_region.x, new_region.y, self.size.width, new_region.height)
            self._refresh_region(new)

        # TODO: This may be remmoved
        super().watch_cursor_coordinate(old_coordinate, new_coordinate)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_sort_column(
        self, column_key: ColumnKey | str | None = None, reverse: bool | None = None
    ):
        if not column_key:
            key = self._column_locations.get_key(self.cursor_column)
            if key is None:
                return
        else:
            key = ColumnKey(column_key) if isinstance(column_key, str) else column_key

        if reverse is None:
            sort_order = (
                SortOrder(not self._sort_column_order.value)
                if self._sort_column == key
                else SortOrder.DESC
            )
        else:
            sort_order = SortOrder(not reverse)

        self.sort(key, reverse=sort_order.value)
        self._sort_column = key
        self._sort_column_order = sort_order

    def action_select_cursor(self):
        name = self._row_locations.get_key(self.cursor_row).value
        self.app.push_screen(HDFViewer(self.uid, name))  # type: ignore

    def action_cursor_to_end(self):
        self.cursor_coordinate = Coordinate(
            self.row_count - 1, self.cursor_coordinate.column
        )

    def action_cursor_to_home(self):
        self.cursor_coordinate = Coordinate(0, self.cursor_coordinate.column)

    @work
    async def action_command_line(self, prefix: str = "", label: str = ":"):
        cmd: CommandMessage = await self.app.push_screen_wait(
            CommandLine(self, prefix=prefix, label=label)
        )
        self._handle_command(cmd)

    def _handle_command(self, cmd: CommandMessage):
        if isinstance(cmd, CommandLine.GoTo):
            self.move_cursor(column=self._column_locations.get(cmd.column_key))


class ScreenCollection(Screen, inherit_bindings=False):
    BINDINGS = [
        Binding("ctrl+m", "toggle_picker", "toggle the collection picker"),
        Binding("ctrl+t", "cycle_tabs", "cycle through tabs", show=False),
        Binding("q", "close", "close collection", show=False),
    ]
    BINDING_GROUP_TITLE = "Screen commands"
    DEFAULT_CSS = """
    ScreenCollection {
        layers: bottom top;
    }
    """

    _open_collections: dict[str, CollectionTable]
    current_uid: var[str | None] = var(None)
    current_widget: CollectionTable | Placeholder

    def __init__(self, uid: str | None = None) -> None:
        super().__init__(uid)
        self.set_reactive(ScreenCollection.current_uid, uid)
        self._table_container = TableContainer(id="table-container")
        """The container holding the table widget."""
        self._tabs = OpenCollectionsTabs()
        """The container holding the tabs in the header."""
        self._open_collections = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Header()
            with Right():
                yield self._tabs
        yield self._table_container
        yield Footer()

    def watch_current_uid(self, _old, new: str | None) -> None:
        if new is None:
            self._table_container._widget = Placeholder()
            return
        try:
            self._table_container._widget = self._open_collections[new]
        except KeyError:
            new_table = CollectionTable(new)
            self._open_collections[new] = new_table
            self._table_container._widget = new_table

    def action_toggle_picker(self):
        self.app.push_screen(CollectionPicker())

    @work(exclusive=True)
    async def action_cycle_tabs(self):
        if self.current_uid is None:
            return
        uid_list = list(self._open_collections.keys())
        start = uid_list.index(str(self.current_uid))
        uid_cycler_start_from_current = cycle(
            (i for i in chain(uid_list[start + 1 :], uid_list[: start + 1]))
        )
        # from the location of the current_uid, get the next tab, if at end, cycle to
        # start
        if next_tab := next(uid_cycler_start_from_current, None):
            self.current_uid = next_tab

    def action_close(self):
        uid = self.current_uid
        if uid is None:
            self.app.exit()
            return
        _open_collections = self._open_collections
        if _open_collections:
            collection = _open_collections.pop(uid)
            self.remove_children(f"#{collection.id}")
            if not _open_collections:
                self.current_uid = None
                self._table_container._widget = Placeholder()
            else:
                self.current_uid = next(iter(self._open_collections.keys()))
        else:
            self.app.exit()

    @on(CollectionHit.CollectionSelected)
    def _open_collection(self, message: CollectionHit.CollectionSelected) -> None:
        self.current_uid = message.uid

    @on(Tab.Clicked)
    def _on_tab_clicked(self, message: Tab.Clicked) -> None:
        self.current_uid = message.tab.label_text
