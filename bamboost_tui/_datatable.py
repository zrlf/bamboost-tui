from __future__ import annotations

from enum import Enum
from itertools import zip_longest
from typing import Callable, Literal, overload

from rich.console import RenderableType
from rich.padding import Padding
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual._types import SegmentLines
from textual.color import Color
from textual.coordinate import Coordinate
from textual.renderables.styled import Styled
from textual.widgets import DataTable
from textual.widgets._data_table import (
    _EMPTY_TEXT,
    ColumnKey,
    CursorType,
    RowKey,
    RowRenderables,
    default_cell_formatter,
)


class SortOrder(Enum):
    ASC = False
    DESC = True

    __symbols__ = {ASC: "", DESC: ""}

    def __not__(self) -> SortOrder:
        return SortOrder(not self.value)

    @property
    def symbol(self) -> str:
        return self.__symbols__[self.value]


class ModifiedDataTable(DataTable):
    def __init__(
        self,
        cell_highlighter: Callable[[object], Text] | None = None,
        *,
        show_header: bool = True,
        show_row_labels: bool = True,
        fixed_rows: int = 0,
        fixed_columns: int = 0,
        zebra_stripes: bool = False,
        header_height: int = 1,
        show_cursor: bool = True,
        cursor_foreground_priority: Literal["renderable", "css"] = "css",
        cursor_background_priority: Literal["renderable", "css"] = "renderable",
        cursor_type: CursorType = "cell",
        cell_padding: int = 1,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        self.highlighter = cell_highlighter or None
        self._header_cell_render_cache = {}
        self._sort_column: ColumnKey | None = None
        self._sort_column_order = SortOrder.DESC

        super().__init__(
            show_header=show_header,
            show_row_labels=show_row_labels,
            fixed_rows=fixed_rows,
            fixed_columns=fixed_columns,
            zebra_stripes=zebra_stripes,
            header_height=header_height,
            show_cursor=show_cursor,
            cursor_foreground_priority=cursor_foreground_priority,
            cursor_background_priority=cursor_background_priority,
            cursor_type=cursor_type,
            cell_padding=cell_padding,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )

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
        # cursor_type = self.cursor_type
        cursor_type = "row"
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
                    wrap=row_metadata.height != 1,
                    height=row_metadata.height,
                )
                if row_metadata.label
                else None
            )
        return RowRenderables(label, formatted_row_cells)

    def _render_cell(
        self,
        row_index: int,
        column_index: int,
        base_style: Style,
        width: int,
        cursor: bool = False,
        hover: bool = False,
    ) -> SegmentLines:
        """Render the given cell.

        Args:
            row_index: Index of the row.
            column_index: Index of the column.
            base_style: Style to apply.
            width: Width of the cell.
            cursor: Is this cell affected by cursor highlighting?
            hover: Is this cell affected by hover cursor highlighting?

        Returns:
            A list of segments per line.
        """
        is_header_cell = row_index == -1
        is_row_label_cell = column_index == -1

        is_fixed_style_cell = (
            not is_header_cell
            and not is_row_label_cell
            and (row_index < self.fixed_rows or column_index < self.fixed_columns)
        )

        if is_header_cell:
            row_key = self._header_row_key
        else:
            row_key = self._row_locations.get_key(row_index)

        column_key = self._column_locations.get_key(column_index)
        cell_cache_key: CellCacheKey = (
            row_key,
            column_key,
            base_style,
            cursor,
            hover,
            self._show_hover_cursor,
            self._update_count,
            self._pseudo_class_state,
        )

        if is_header_cell:
            if cell_cache_key in self._header_cell_render_cache:
                return self._header_cell_render_cache[cell_cache_key]

        if cell_cache_key in self._cell_render_cache and not is_header_cell:
            return self._cell_render_cache[cell_cache_key]

        base_style += Style.from_meta({"row": row_index, "column": column_index})
        row_label, row_cells = self._get_row_renderables(row_index)

        if is_row_label_cell:
            # cell = row_label if row_label is not None else ""
            cell = row_label or " " if row_index == self.cursor_row else " "
        else:
            cell = row_cells[column_index]

        component_style, post_style = self._get_styles_to_render_cell(
            is_header_cell,
            is_row_label_cell,
            is_fixed_style_cell,
            hover,
            cursor,
            self.show_cursor,
            self._show_hover_cursor,
            self.cursor_foreground_priority == "css",
            self.cursor_background_priority == "css",
        )

        if is_header_cell:
            row_height = self.header_height
            options = self.app.console.options.update_dimensions(width, row_height)
            if (
                self._sort_column
                and self._column_locations.get(self._sort_column) == column_index
            ):
                cell = str(cell) + "\n" + self._sort_column_order.symbol
            if self.cursor_column == column_index:
                component_style += self.get_component_styles(
                    "datatable--header-cursor"
                ).rich_style
        else:
            # If an auto-height row hasn't had its height calculated, we don't fix
            # the value for `height` so that we can measure the height of the cell.
            row = self.rows[row_key]
            if row.auto_height and row.height == 0:
                row_height = 0
                options = self.app.console.options.update_width(width)
            else:
                row_height = row.height
                options = self.app.console.options.update_dimensions(width, row_height)

        # If the row height is explicitly set to 1, then we don't wrap.
        if row_height == 1:
            options = options.update(no_wrap=True)

        lines = self.app.console.render_lines(
            Styled(
                Padding(cell, (0, self.cell_padding)),
                pre_style=base_style + component_style,
                post_style=post_style,
            ),
            options,
        )

        if is_header_cell:
            self._header_cell_render_cache[cell_cache_key] = lines
            return lines

        self._cell_render_cache[cell_cache_key] = lines
        return lines
