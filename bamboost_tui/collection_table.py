from __future__ import annotations

import weakref
from datetime import datetime
from textwrap import dedent
from typing import TYPE_CHECKING, Mapping

import pandas as pd
from bamboost.index import DEFAULT_INDEX
from rich.highlighter import ReprHighlighter
from rich.table import Table
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult, RenderResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Center, Container, Horizontal, Right, Vertical
from textual.coordinate import Coordinate
from textual.geometry import Offset, Region
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static, Tab, Tabs
from textual.widgets.data_table import ColumnKey
from typing_extensions import Self

from bamboost_tui._datatable import ModifiedDataTable, SortOrder
from bamboost_tui.collection_picker import CollectionHit, CollectionPicker
from bamboost_tui.commandline import CommandLine

if TYPE_CHECKING:
    pass


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

    def _get_path(self, uid: str) -> str:
        found_path = DEFAULT_INDEX._get_collection_path(uid)
        return found_path.as_posix() if found_path else "[Collection location found]"

    def on_mount(self):
        self.watch(self.screen, "current_uid", self._watch_current_uid, init=False)

    def _watch_current_uid(self, _old, _new: str | None) -> None:
        if _new is None:
            return
        self.uid = _new
        self.path = self._get_path(_new)
        self.refresh()


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
    _tabs: dict[str, Tab]
    active: reactive[str | None] = reactive(None, init=False)

    def __init__(self, open_collections: Mapping):
        self._open_collections = open_collections
        self._tabs = {}
        super().__init__(id="collections-tabs")

    def on_mount(self):
        self.watch(self.screen, "current_uid", self._update, init=True)

    def watch_active(self, _old, _new: str | None) -> None:
        if _new is None:
            return
        self.query("Tab.-active").remove_class("-active")
        self._tabs[_new].add_class("-active")

    def _update(self, _old, new: str) -> None:
        if new is None:
            return
        if new not in self._tabs:
            self._tabs[new] = Tab(new)
        self.active = new
        self.refresh(recompose=True)

    def compose(self) -> ComposeResult:
        yield from self._tabs.values()


class ScreenCollection(Screen):
    BINDINGS = [
        Binding("ctrl+m", "toggle_picker", "toggle the collection picker"),
        Binding("ctrl+a", "log_tabs", "log the tabs"),
    ]
    _open_collections: weakref.WeakValueDictionary[str, CollectionTable] = (
        weakref.WeakValueDictionary()
    )
    current_uid: reactive[str | None] = reactive(None)

    def __init__(self, uid: str | None = None) -> None:
        super().__init__(uid)
        self.set_reactive(ScreenCollection.current_uid, uid)
        self._table_container = TableContainer(id="table-container")
        self._tabs = OpenCollectionsTabs(self._open_collections)

    def action_log_tabs(self):
        self.log.error(self._tabs)

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Header()
            with Right():
                yield self._tabs
        yield self._table_container
        yield Footer()

    def action_toggle_picker(self):
        self.app.push_screen(CollectionPicker())

    @on(CollectionHit.CollectionSelected)
    def _open_collection(self, message: CollectionHit.CollectionSelected) -> None:
        new_uid = message.uid
        if new_uid in self._open_collections:
            table_widget = self._open_collections[new_uid]
        else:
            table_widget = CollectionTable(new_uid)
            self._open_collections[new_uid] = table_widget

        self._table_container._widget = table_widget
        self.current_uid = new_uid

        # we check if the collection is already open
        # try:
        #     new_screen = self._open_collections[collection_uid]
        # except KeyError:
        #     new_screen = CollectionTable(uid=collection_uid)
        #     self._open_collections[collection_uid] = new_screen


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


class TableContainer(Container):
    _widget: reactive[Widget] = reactive(Placeholder, recompose=True)
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


class CollectionTable(ModifiedDataTable):
    BINDINGS = [
        Binding("j", "cursor_down", "move cursor down", show=False),
        Binding("k", "cursor_up", "move cursor up", show=False),
        Binding("l", "cursor_right", "move cursor right", show=False),
        Binding("h", "cursor_left", "move cursor left", show=False),
        Binding("s", "sort_column", "sort column"),
        Binding("G", "cursor_to_end", "move cursor to end"),
        Binding("g>g", "cursor_to_home", "move cursor to home"),
        Binding(":", "enter_command_mode", "enter command mode", show=False),
    ]
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {
        "datatable--label",
    }
    HELP = """
    # Collection table

    Explore your simulations in this collection. Enter to view the respective HDF file.
    """

    def __init__(self, uid: str):
        super().__init__(
            header_height=2,
            cursor_type="cell",
            cell_highlighter=cell_highlighter,
            cursor_foreground_priority="renderable",
            cursor_background_priority="css",
        )

        self.uid: str = uid
        """The collection uid to display."""

        self._SUBGROUPS: dict[str, dict[str, Binding]] = {}
        """Mapping of subgroup keys to a dictionary of bindings."""
        self._subgroup: dict[str, Binding] | None = None
        """The current subgroup of bindings."""
        self._create_subgroup_mapping()

        self.df: pd.DataFrame | None = None
        """The DataFrame that holds the data for the table."""

    def on_mount(self):
        """Load the data, create columns and rows."""
        sims = DEFAULT_INDEX.collection(self.uid).simulations
        tab = [i.as_dict(standalone=False) for i in sims]
        self.df = pd.DataFrame.from_records(tab)

        self.recreate_table()
        self.focus()

    def recreate_table(self) -> Self:
        # clear the current table
        self.clear(True)

        # build columns and rows from dataframe
        for col in self.df.columns:
            self.add_column(str(col), key=str(col))
        for row in self.df.values:
            self.add_row(*row)

        self.fixed_columns = 1
        return self

    def _create_subgroup_mapping(self):
        for binding in Binding.make_bindings(self.BINDINGS):
            if len(binding.key.split(">")) > 1:
                subgroup_key, key = binding.key.split(">")
                self._SUBGROUPS[subgroup_key] = {
                    key: Binding(
                        key,
                        binding.action,
                        binding.description,
                        binding.show,
                        binding.key_display,
                        binding.priority,
                        binding.tooltip,
                        binding.id,
                        binding.system,
                    )
                }

    def _enter_subgroup(self, key: events.Key) -> None:
        self._subgroup = self._SUBGROUPS.get(key.key)

    def _resolve_subgroup(self, subgroup: dict[str, Binding], key: events.Key) -> None:
        action = subgroup[key.key].action
        key.prevent_default()
        key.stop()
        self._subgroup = None
        # call the action for the binding
        getattr(self, "action_" + action)()

    def on_key(self, event: events.Key) -> None:
        # if we're in a subgroup, check group specific binding
        if self._subgroup is not None:
            if event.key in self._subgroup:
                return self._resolve_subgroup(self._subgroup, event)
            else:
                self._subgroup = None
                return

        # if the key leads to a subgroup, enter it
        if event.key in self._SUBGROUPS:
            self._enter_subgroup(event)

    def _create_command_line_for_collection(self):
        assert self.df is not None
        self.app.install_screen(CommandLine(collection_table=self), name="command_line")

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
        super().action_select_cursor()

    def action_cursor_to_end(self):
        self.cursor_coordinate = Coordinate(
            self.row_count - 1, self.cursor_coordinate.column
        )

    def action_cursor_to_home(self):
        self.cursor_coordinate = Coordinate(0, self.cursor_coordinate.column)

    def action_enter_command_mode(self):
        if "command_line" in self.app._installed_screens:
            self.app.push_screen("command_line")
        else:
            self._create_command_line_for_collection()
            self.app.push_screen("command_line")
