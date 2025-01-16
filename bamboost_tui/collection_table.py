from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
import rich
from bamboost.index import DEFAULT_INDEX
from bamboost.index.sqlmodel import CollectionORM
from rich.columns import Columns
from rich.console import RenderableType
from rich.highlighter import ReprHighlighter
from rich.panel import Panel
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import CommandPalette, Hit, Hits, Matcher, Provider
from textual.containers import Container
from textual.content import Content
from textual.coordinate import Coordinate
from textual.geometry import Offset, Region
from textual.screen import ModalScreen, Screen
from textual.types import IgnoreReturnCallbackType
from textual.visual import Style, VisualType
from textual.widgets import DataTable, Footer, Label, Placeholder, Static
from textual.widgets.data_table import ColumnKey

from bamboost_tui._datatable import ModifiedDataTable, SortOrder
from bamboost_tui.collection_picker import CollectionPicker
from bamboost_tui.commandline import CommandLine

if TYPE_CHECKING:
    from rich.style import Style as RichStyle


class ScreenCollection(Screen):
    BINDINGS = [Binding("ctrl+m", "toggle_picker", "toggle the collection picker")]
    COMPONENT_CLASSES = Screen.COMPONENT_CLASSES | {
        "collection-list--uid",
    }

    def __init__(self, uid: str) -> None:
        self.uid = uid
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Container(
            CollectionTable(self.uid),
            id="table-container",
        )
        yield Footer()

    def action_toggle_picker(self):
        self.app.push_screen(CollectionPicker())


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

        for col in self.df.columns:
            self.add_column(str(col), key=str(col))
        for row in self.df.values:
            self.add_row(*row)

        self.fixed_columns = 1

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
