from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING

from rich.highlighter import ReprHighlighter
from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.geometry import Offset, Region
from textual.reactive import var
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey
from typing_extensions import Self

from bamboost_tui.commandline import CommandLine, CommandMessage
from bamboost_tui.utils import KeySubgroupsMixin, get_index
from bamboost_tui.widgets import ModifiedDataTable, SortOrder
from bamboost_tui.widgets.confirmation import ModalPrompt

if TYPE_CHECKING:
    import pandas as pd
    from pandas import DataFrame

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
        # Navigation
        Binding("enter", "select_cursor", "show simulation", show=False),
        Binding("j,down", "cursor_down", "move cursor down", show=False),
        Binding("k,up", "cursor_up", "move cursor up", show=False),
        Binding("l,right", "cursor_right", "move cursor right", show=False),
        Binding("h,left", "cursor_left", "move cursor left", show=False),
        Binding("G", "cursor_to_end", "move cursor to end", show=False),
        Binding("g>g", "cursor_to_home", "move cursor to start", show=False),
        Binding("ctrl+d,pagedown", "page_down", "scroll page down", show=False),
        Binding("ctrl+u,pageup", "page_up", "scroll page up", show=False),
        Binding("$", "cursor_to_last_column", "move cursor to right end", show=False),
        Binding("0", "cursor_to_first_column", "move cursor to left end", show=False),
        # Commands
        Binding(":", "command_line", "enter command mode", show=True),
        Binding("/", 'command_line("goto", "")', "jump to column", show=False),
        Binding("r", "reload", "reload data", show=False, id="collection.reload"),
        Binding("s", "sort_column", "sort column", show=False, id="collection.sort"),
        Binding("d", "delete", "delete simulation", show=False, id="collection.delete"),
        Binding(
            "o>p",
            "open_paraview",
            "open paraview",
            show=False,
            id="collection.open_paraview",
        ),
        Binding(
            "o>d",
            "open_directory",
            "open directory in editor",
            show=False,
            id="collection.open_directory",
        ),
        Binding(
            "c>s", "sync", "sync collection with fs", show=False, id="collection.sync"
        ),
    ]
    BINDING_GROUP_TITLE = "Collection commands"
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {
        "datatable--label",
    }
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

    def on_mount(self):
        if self.df is None:
            self.loading = True
            self._load_data()
        self.focus()

    @work(exclusive=True)
    async def _load_data(self):
        from bamboost import config

        self.df: DataFrame = get_index().collection(self.uid).to_pandas()
        self.df.sort_values(
            config.options.sortTableKey,
            inplace=True,
            ascending=config.options.sortTableOrder == "asc",
            ignore_index=True,
        )
        self.loading = False
        self.focus()

    async def watch_df(self, _old, _new: pd.DataFrame | None) -> None:
        if _new is None:
            return

        await self._create_table()
        self.refresh(layout=False)

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
        assert name is not None, "No simulation selected."

        from bamboost_tui.screens.hdfview import HDFViewer

        self.app.push_screen(HDFViewer(self.uid, name))

    def action_cursor_to_end(self):
        self.cursor_coordinate = Coordinate(
            self.row_count - 1, self.cursor_coordinate.column
        )

    def action_cursor_to_home(self):
        self.cursor_coordinate = Coordinate(0, self.cursor_coordinate.column)

    def action_cursor_to_last_column(self):
        self.cursor_coordinate = Coordinate(
            self.cursor_coordinate.row, len(self.columns) - 1
        )

    def action_cursor_to_first_column(self):
        self.cursor_coordinate = Coordinate(self.cursor_coordinate.row, 0)

    @work(exclusive=True)
    async def action_command_line(self, prefix: str = "", label: str = ":"):
        cmd: CommandMessage = await self.app.push_screen_wait(
            CommandLine(self, prefix=prefix, label=label)
        )
        self._handle_command(cmd)

    def _handle_command(self, cmd: CommandMessage):
        if isinstance(cmd, CommandLine.GoTo):
            return self.move_cursor(column=self._column_locations.get(cmd.column_key))
        if isinstance(cmd, CommandLine.Sort):
            return self.action_sort_column(cmd.column_key, cmd.reverse)

    async def action_delete(self):
        row_key = self._row_locations.get_key(self.cursor_row)
        assert row_key is not None, "No simulation selected."
        name = row_key.value
        assert name is not None, "No simulation selected."

        def _delete(confirm: bool | None):
            if not confirm:
                return
            get_index()._drop_simulation(self.uid, name)
            import shutil

            path = get_index()._get_collection_path(self.uid).joinpath(name)  # pyright: ignore[reportArgumentType]
            shutil.rmtree(path)

            # refresh the table
            self.remove_row(row_key)

        self.app.push_screen(
            ModalPrompt(f"Really want to delete simulation [bold]{name}[/bold]"),
            _delete,
        )

    def action_open_paraview(self):
        row_key = self._row_locations.get_key(self.cursor_row)
        assert row_key is not None, "No simulation selected."
        name = row_key.value
        assert name is not None, "No simulation selected."

        path = get_index()._get_collection_path(self.uid).joinpath(name)  # pyright: ignore[reportArgumentType]
        path = path.joinpath("data.xdmf")
        subprocess.Popen(["paraview", path.as_posix()])

    def action_open_directory(self):
        row_key = self._row_locations.get_key(self.cursor_row)
        assert row_key is not None, "No simulation selected."
        name = row_key.value
        assert name is not None, "No simulation selected."

        path = get_index()._get_collection_path(self.uid).joinpath(name)
        with self.app.suspend():
            subprocess.run([os.getenv("EDITOR", "vi"), path.as_posix()])

    async def action_reload(self):
        previous_coordinate = self.cursor_coordinate

        # update df without triggering a watch
        self.set_reactive(
            CollectionTable.df, get_index().collection(self.uid).to_pandas()
        )
        await self._create_table()

        # sort the table as before
        if self._sort_column is not None:
            self.sort(self._sort_column, reverse=self._sort_column_order.value)

        # move cursor to previous position
        self.cursor_coordinate = previous_coordinate

        self.notify("✔️ Reloaded data", timeout=1.0)

    async def action_sync(self):
        index = get_index()
        # check if the path is correct
        index.resolve_path(self.uid)
        # sync the collection
        index.sync_collection(self.uid)
        self.notify("✔️ Synced collection", timeout=1.0)
        # reload the collection
        await self.action_reload()
