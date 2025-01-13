from __future__ import annotations

from itertools import zip_longest
from typing import Callable

import pandas as pd
from bamboost.index import DEFAULT_INDEX
from rich.console import RenderableType
from rich.highlighter import Highlighter, ReprHighlighter
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual._types import SegmentLines
from textual.binding import Binding
from textual.color import Color
from textual.coordinate import Coordinate
from textual.widgets import DataTable, RichLog
from textual.widgets._data_table import (
    _EMPTY_TEXT,
    RowKey,
    RowRenderables,
    default_cell_formatter,
)

highlighter = ReprHighlighter()


class CollectionTable(DataTable):
    BINDINGS = [
        Binding("j", "cursor_down", "move cursor down", show=False),
        Binding("k", "cursor_up", "move cursor up", show=False),
        Binding("l", "cursor_right", "move cursor right", show=False),
        Binding("h", "cursor_left", "move cursor left", show=False),
        Binding("s", "sort_column", "sort column"),
    ]
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {
        "datatable--label",
    }

    def __init__(self, cell_highlighter: Callable[[object], Text] | None = None, *args, **kwargs):
        self.highlighter = cell_highlighter
        super().__init__(*args, **kwargs)

    def on_mount(self):
        sims = DEFAULT_INDEX.collection("0FD8B0E3BE").simulations
        tab = [i.as_dict(standalone=False) for i in sims]
        df = pd.DataFrame.from_records(tab)
        self.add_columns(*(str(i) for i in df.columns))

        def cells(row):
            for cell in row:
                # hl = highlighter(str(cell))
                # hl.justify = "right" if str(cell).isnumeric() else "left"
                # yield hl
                yield cell

        for row in df.values:
            self.add_row(*cells(row))

        self.fixed_columns = 1

        self.logger = self.screen.query_one(RichLog)

    def action_sort_column(self):
        key = self._column_locations.get_key(self.cursor_column)
        if hasattr(self, "last_sort") and self.last_sort == key:
            sort_reverse = not self.last_sort_reverse
        else:
            sort_reverse = False

        self.sort(key, reverse=sort_reverse)
        self.last_sort = key
        self.last_sort_reverse = sort_reverse

    def action_select_cursor(self):
        super().action_select_cursor()
        self.logger.write(self.get_cell_at(self.cursor_coordinate))

    def _render_line_in_row(
        self,
        row_key: RowKey,
        line_no: int,
        base_style: Style,
        cursor_location: Coordinate,
        hover_location: Coordinate,
    ) -> tuple[SegmentLines, SegmentLines]:
        """Render a single line from a row in the DataTable.

        Args:
            row_key: The identifying key for this row.
            line_no: Line number (y-coordinate) within row. 0 is the first strip of
                cells in the row, line_no=1 is the next line in the row, and so on...
            base_style: Base style of row.
            cursor_location: The location of the cursor in the DataTable.
            hover_location: The location of the hover cursor in the DataTable.

        Returns:
            Lines for fixed cells, and Lines for scrollable cells.
        """
        cursor_type = self.cursor_type
        show_cursor = self.show_cursor

        cache_key = (
            row_key,
            line_no,
            base_style,
            cursor_location,
            hover_location,
            cursor_type,
            show_cursor,
            self._show_hover_cursor,
            self._update_count,
            self._pseudo_class_state,
        )

        if cache_key in self._row_render_cache:
            return self._row_render_cache[cache_key]

        should_highlight = self._should_highlight
        render_cell = self._render_cell
        header_style = self.get_component_styles("datatable--header").rich_style

        if row_key in self._row_locations:
            row_index = self._row_locations.get(row_key)
        else:
            row_index = -1

        # If the row has a label, add it to fixed_row here with correct style.
        fixed_row = []

        if self._labelled_row_exists and self.show_row_labels:
            # The width of the row label is updated again on idle
            cell_location = Coordinate(row_index, -1)
            label_cell_lines = render_cell(
                row_index,
                -1,
                header_style,
                width=self._row_label_column_width,
                cursor=should_highlight(cursor_location, cell_location, "row"),
                hover=should_highlight(hover_location, cell_location, cursor_type),
            )[line_no]
            fixed_row.append(label_cell_lines)

        if self.fixed_columns:
            if row_key is self._header_row_key:
                fixed_style = header_style  # We use the header style either way.
            else:
                fixed_style = self.get_component_styles("datatable--fixed").rich_style
                fixed_style += Style.from_meta({"fixed": True})
            for column_index, column in enumerate(
                self.ordered_columns[: self.fixed_columns]
            ):
                cell_location = Coordinate(row_index, column_index)
                fixed_cell_lines = render_cell(
                    row_index,
                    column_index,
                    fixed_style,
                    column.get_render_width(self),
                    cursor=should_highlight(cursor_location, cell_location, "row"),
                    hover=should_highlight(hover_location, cell_location, cursor_type),
                )[line_no]
                fixed_row.append(fixed_cell_lines)

        row_style = self._get_row_style(row_index, base_style)

        scrollable_row = []
        for column_index, column in enumerate(self.ordered_columns):
            cell_location = Coordinate(row_index, column_index)
            cell_lines = render_cell(
                row_index,
                column_index,
                row_style,
                column.get_render_width(self),
                cursor=should_highlight(cursor_location, cell_location, cursor_type),
                hover=should_highlight(hover_location, cell_location, cursor_type),
            )[line_no]
            scrollable_row.append(cell_lines)

        # Extending the styling out horizontally to fill the container
        widget_width = self.size.width
        table_width = (
            sum(
                column.get_render_width(self)
                for column in self.ordered_columns[self.fixed_columns :]
            )
            + self._row_label_column_width
        )
        remaining_space = max(0, widget_width - table_width)
        background_color = self.background_colors[1]
        if row_style.bgcolor is not None:
            # TODO: This should really be in a component class
            faded_color = Color.from_rich_color(row_style.bgcolor).blend(
                background_color, factor=0.25
            )
            faded_style = Style.from_color(
                color=row_style.color, bgcolor=faded_color.rich_color
            )
        else:
            faded_style = Style.from_color(row_style.color, row_style.bgcolor)
        scrollable_row.append([Segment(" " * remaining_space, faded_style)])

        row_pair = (fixed_row, scrollable_row)
        self._row_render_cache[cache_key] = row_pair
        return row_pair

    def _get_row_renderables(self, row_index: int) -> RowRenderables:
        """Get renderables for the row currently at the given row index. The renderables
        returned here have already been passed through the default_cell_formatter.

        Args:
            row_index: Index of the row.

        Returns:
            A RowRenderables containing the optional label and the rendered cells.
        """
        ordered_columns = self.ordered_columns
        if row_index == -1:
            header_row: list[RenderableType] = [
                column.label for column in ordered_columns
            ]
            # This is the cell where header and row labels intersect
            return RowRenderables(None, header_row)

        ordered_row = self.get_row_at(row_index)
        row_key = self._row_locations.get_key(row_index)
        if row_key is None:
            return RowRenderables(None, [])
        row_metadata = self.rows.get(row_key)
        if row_metadata is None:
            return RowRenderables(None, [])

        formatted_row_cells: list[RenderableType] = [
            (
                _EMPTY_TEXT
                if datum is None
                else default_cell_formatter(
                    self.highlighter(datum) if self.highlighter else datum,
                    wrap=row_metadata.height != 1,
                    height=row_metadata.height,
                )
                or _EMPTY_TEXT
            )
            for datum, _ in zip_longest(ordered_row, range(len(self.columns)))
        ]

        label = None
        if self._should_render_row_labels:
            label = (
                default_cell_formatter(
                    row_metadata.label,
                    # ">" if row_index == self.cursor_row else "",
                    wrap=row_metadata.height != 1,
                    height=row_metadata.height,
                )
                if row_metadata.label
                else None
            )
        return RowRenderables(label, formatted_row_cells)
