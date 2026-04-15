from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING, Iterable, Self

from bamboost import Simulation
from bamboost.constants import UID_SEPARATOR
from rich.highlighter import ReprHighlighter
from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.geometry import Offset, Region
from textual.reactive import var
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from bamboost_tui.commandline import CommandLine, CommandMessage
from bamboost_tui.config import config_tui
from bamboost_tui.utils import KeySubgroupsMixin, get_index
from bamboost_tui.widgets import CellContentScreen, ModifiedDataTable, SortOrder, ExpDesignInfoScreen
from bamboost_tui.widgets.confirmation import ModalPrompt
from bamboost_tui.widgets.status_footer import StatusFooter

if TYPE_CHECKING:
    import pandas as pd
    from bamboost.core.remote import Remote

REPR_HIGHLIGHTER = ReprHighlighter()

MAX_CELL_WIDTH = config_tui["maxCellWidth"]
FLOAT_PRECISION = config_tui["floatPrecision"]


def _format_iterable(obj: object) -> str:
    if isinstance(obj, Iterable) and not isinstance(obj, str):
        return _format_iterable("[" + ", ".join(map(_format_iterable, obj)) + "]")
    if isinstance(obj, float):
        return str(round(obj, FLOAT_PRECISION))
    return str(obj)


def cell_highlighter(cell: object) -> Text:
    if isinstance(cell, datetime):
        cell = cell.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(cell, float):
        cell = str(round(cell, FLOAT_PRECISION))
    elif isinstance(cell, Iterable) and not isinstance(cell, str):
        cell = _format_iterable(cell)

    cell_str = str(cell)
    if len(cell_str) > MAX_CELL_WIDTH:
        cell_str = cell_str[: MAX_CELL_WIDTH - 3] + "..."

    highlighted = REPR_HIGHLIGHTER(
        Text(
            cell_str,
            justify="right" if cell_str.isdecimal() else "left",
        )
    )
    return highlighted


class CollectionTable(ModifiedDataTable, KeySubgroupsMixin, inherit_bindings=False):
    BINDINGS = [  # noqa: RUF012
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
        Binding(
            "space",
            "toggle_selection",
            "toggle selection",
            show=False,
            id="collection.toggle_select",
        ),
        Binding(
            "v",
            "toggle_visual_mode",
            "visual mode",
            show=False,
            id="collection.visual_mode",
        ),
        Binding(
            "escape",
            "cancel_visual_mode",
            "cancel visual mode",
            show=False,
            id="collection.cancel_visual",
        ),
        Binding(
            "y", "copy_uids", "copy selected UIDs", show=True, id="collection.copy_uids"
        ),
        Binding("r", "reload", "reload data", show=False, id="collection.reload"),
        Binding("s", "sort_column", "sort column", show=False, id="collection.sort"),
        Binding("d", "delete", "delete simulation", show=False, id="collection.delete"),
        Binding("i", "show_full_cell", "show full cell content", show=True),
        Binding("e>d", "show_exp_design_info", "show experiment design of collection", show=True),
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
        Binding(
            "c>r",
            "rsync",
            "rsync simulation from remote",
            show=False,
            id="collection.rsync",
        ),
    ]
    BINDING_GROUP_TITLE = "Collection commands"
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {
        "datatable--label",
    }
    DEFAULT_CSS = """
    $row-selected-background: $accent 30%;
    $row-selected-color: $accent;

    CollectionTable {
        layers: bottom top;
    }
    CollectionTable > .datatable--row-selected {
        background: $row-selected-background;
        color: $row-selected-color;
        text-style: bold italic;
    }
    """

    df: var[pd.DataFrame | None] = var(None, init=False, always_update=True)
    """The pandas DataFrame from which the table is built."""

    def __init__(self, uid: str, remote: Remote | None = None):
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

        self.remote: Remote | None = remote
        """Optional remote index for remote collections."""

    def on_mount(self):
        if self.df is None:
            self.loading = True
            self._load_data()
        self.focus()

    @work(thread=True, exclusive=True)
    async def _load_data(self):
        from bamboost import config

        if self.remote is not None:
            df = self.remote[self.uid].df
        else:
            df = get_index().collection(self.uid).to_pandas()

        if not df.empty:
            sort_key = config.options.sortTableKey
            try:
                df.sort_values(
                    sort_key,
                    inplace=True,
                    ascending=config.options.sortTableOrder == "asc",
                    ignore_index=True,
                )
                self._sort_column = ColumnKey(sort_key)
                self._sort_column_order = (
                    SortOrder.DESC
                    if config.options.sortTableOrder == "desc"
                    else SortOrder.ASC
                )
            except KeyError:
                self.notify(
                    f"Column [bold]{config.options.sortTableKey}[/bold] not found for sorting.",
                    severity="information",
                    timeout=4.0,
                )

        def finalize():
            self.df = df
            self.loading = False
            self.focus()

        self.app.call_from_thread(finalize)

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
        if self.visual_start_row is not None:
            r_min = min(old_coordinate.row, new_coordinate.row)
            r_max = max(old_coordinate.row, new_coordinate.row)
            for r in range(r_min, r_max + 1):
                self.refresh_row(r)
            super().watch_cursor_coordinate(old_coordinate, new_coordinate)
            return

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

    def watch_visual_start_row(self, old: int | None, new: int | None) -> None:
        if new is not None:
            self.screen.add_class("visual-mode")
        else:
            self.screen.remove_class("visual-mode")

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_toggle_selection(self) -> None:
        if self.visual_start_row is not None:
            start, end = sorted([self.visual_start_row, self.cursor_row])
            for i in range(start, end + 1):
                key = self._row_locations.get_key(i)
                if key is not None:
                    if key in self.selected_rows:
                        self.selected_rows.remove(key)
                    else:
                        self.selected_rows.add(key)
                    self.refresh_row(i)
            self.visual_start_row = None
            self._selection_update_count += 1
            self.refresh()
        else:
            row_key = self._row_locations.get_key(self.cursor_row)
            if row_key is not None:
                if row_key in self.selected_rows:
                    self.selected_rows.remove(row_key)
                else:
                    self.selected_rows.add(row_key)
                self.refresh_row(self.cursor_row)
            self.action_cursor_down()
            self._selection_update_count += 1
            self.refresh()

    def action_toggle_visual_mode(self) -> None:
        if self.visual_start_row is None:
            self.visual_start_row = self.cursor_row
            self.refresh_row(self.cursor_row)
        else:
            self._selection_update_count += 1
            self.refresh_row(self.cursor_row)
            self.visual_start_row = None

    def action_cancel_visual_mode(self) -> None:
        if self.visual_start_row is not None:
            r_min = min(self.visual_start_row, self.cursor_row)
            r_max = max(self.visual_start_row, self.cursor_row)
            self.visual_start_row = None
            self._selection_update_count += 1
            for r in range(r_min, r_max + 1):
                self.refresh_row(r)

    def action_copy_uids(self) -> None:
        if self.selected_rows:
            target_keys = list(self.selected_rows)
        else:
            current_key = self._row_locations.get_key(self.cursor_row)
            if current_key is None:
                self.notify("No row selected", severity="warning")
                return
            target_keys = [current_key]

        uids = [f"{self.uid}{UID_SEPARATOR}{key.value}" for key in target_keys]
        text = "\n".join(uids)
        self.app.copy_to_clipboard(text)
        self.notify(f"Copied {len(uids)} UID(s) to clipboard")

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

    def action_show_full_cell(self):
        status_bar = self.screen.query_one(StatusFooter)
        status_bar.display("Showing full cell content.")
        coordinate = self.cursor_coordinate
        cell_data = self.get_cell_at(coordinate)
        column_key = self._column_locations.get_key(coordinate.column)
        column_name = str(column_key.value) if column_key else "Unknown"

        self.app.push_screen(CellContentScreen(cell_data, column_name))

    def action_show_exp_design_info(self):
        if self.df is not None:
            metadata_keys = list(get_index().collection(self.uid)._fields)
            exclude_keys = [*metadata_keys, "name", "status", "submitted"]
            self.app.push_screen(ExpDesignInfoScreen(df=self.df, exclude_keys=exclude_keys))

    def action_select_cursor(self):
        name = self._row_locations.get_key(self.cursor_row).value
        assert name is not None, "No simulation selected."

        from bamboost_tui.screens.hdfview import HDFViewer

        if self.remote is not None:
            simulation = self.remote[self.uid][name]
        else:
            simulation = Simulation.from_uid(f"{self.uid}{UID_SEPARATOR}{name}")

        self.app.push_screen(HDFViewer(simulation))

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
            get_index().drop_simulation(self.uid, name)
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
        if self.remote is not None:
            self.set_reactive(CollectionTable.df, self.remote[self.uid].df)
        else:
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

    @work(thread=True, exclusive=True)
    async def action_sync(self):
        import time

        if self.remote is not None:
            self.notify(
                "Sync not supported for remote collections. For remote collections, use rsync (c>r)",
                severity="warning",
                timeout=2.0,
            )
            return
        
        bar = self.screen.query_one(StatusFooter)

        def display_sync_progress(current: int, total: int) -> None:
            def update():
                if bar.is_mounted: # check if widget is still mounted to avoid crashes on exit
                    bar.display(f"Syncing collection: {current}/{total}")
            self.app.call_from_thread(update)
            # Make sure that the sync progress is visible for a minimum time
            min_time = 1
            time.sleep(min_time / total)

        try:
            self.app.call_from_thread(bar.display, content="Getting the index instance...")
            index = get_index()
            # check if the path is correct
            index.resolve_path(self.uid)
            # sync the collection
            index.sync_collection(self.uid, progress_callback=display_sync_progress)
            self.notify("✔️ Synced collection", timeout=1.0)
        finally:
            self.app.call_from_thread(bar.clear)
            # reload the collection
            self.app.call_from_thread(self.action_reload)

    @work(thread=True)
    async def action_rsync(self):
        if self.remote is None:
            self.notify("Not a remote collection", severity="warning", timeout=2.0)
            return
        row_key = self._row_locations.get_key(self.cursor_row)
        assert row_key is not None, "No simulation selected."
        name = row_key.value
        assert name is not None, "No simulation selected."

        self.notify(f"⏳ Syncing simulation [bold]{name}[/bold]…", timeout=2.0)
        self.remote[self.uid].rsync(name)
        self.notify(f"✔️ Synced simulation [bold]{name}[/bold]", timeout=2.0)
        self.app.call_from_thread(self.action_reload)
