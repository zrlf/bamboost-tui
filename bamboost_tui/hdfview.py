"""The HDF5 viewer screen for bamboost.

This module contains the HDF5 viewer screen for bamboost. It allows you to navigate
through the HDF5 file of a simulation and view the attributes of groups and datasets.

The screen is divided into three main parts:
    - The navigation widget, which shows the groups and datasets in the current group, and
          a small preview window to the right.
    - The attributes view of the current group.
    - The attributes view of the highlighted group.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Sequence, cast

import rich
from bamboost import constants
from bamboost._typing import StrPath
from bamboost.core.hdf5.attrs_dict import AttrsDict
from bamboost.core.hdf5.file import HDF5Path
from bamboost.core.hdf5.ref import Dataset, Group
from bamboost.core.simulation import Simulation
from rich.highlighter import ReprHighlighter
from rich.rule import Rule
from rich.segment import Segment
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Region, Size
from textual.message import Message
from textual.reactive import reactive, var
from textual.screen import Screen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Footer, Static


class Header(Static, can_focus=False):
    DEFAULT_CSS = """
    Header {
        height: auto;
        width: auto;
    }
    .--uid {
        color: $accent;
    }
    .--path {
        color: $primary;
    }
    """
    COMPONENT_CLASSES = {
        "--uid",
        "--path",
    }
    path: str

    def __init__(self, uid: str, path: StrPath) -> None:
        self.uid = uid
        self.path = path if isinstance(path, str) else path.as_posix()
        super().__init__(id="nav-header")

    def render(self) -> RenderResult:
        tab = Table.grid("key", "value", padding=(0, 2))
        tab.add_row(
            "UID:",
            self.uid,
            style=self.get_component_rich_style("--uid", partial=True),
        )
        tab.add_row(
            "Path:",
            self.path,
            style=self.get_component_rich_style("--path", partial=True),
        )
        return tab


class AttrsView(VerticalScroll, can_focus=True):
    DEFAULT_CSS = """
    AttrsView {
        background: $background;
        border: round $border;

        &:focus-within {
            border: round $accent;
        }
    }
    AttrsView > .--key {
        color: $accent;
    }
    AttrsView > .--value {
        color: $primary;
    }
    """
    COMPONENT_CLASSES = {
        "--key",
        "--value",
    }
    attrs: var[AttrsDict | None] = var(None)

    def __init__(
        self,
        border_title: str = "",
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.border_title = border_title

    def compose(self) -> ComposeResult:
        yield Static()

    def watch_attrs(self, _old: AttrsDict | None, new: AttrsDict | None) -> None:
        if new is None:
            return

        tab = Table.grid("key", "value", padding=(0, 2))
        for key, value in self.attrs.items():
            text = Text(str(value))
            ReprHighlighter().highlight(text)
            tab.add_row(
                key,
                text,
                style=self.get_component_rich_style("--key", partial=True),
            )
        inner_widget = self.query_one(Static)
        inner_widget.update(tab)


@dataclass
class GroupData:
    path: HDF5Path
    groups: Sequence[str]
    datasets: Sequence[str]
    attrs: AttrsDict

    @property
    def length(self) -> int:
        return len(self.groups) + len(self.datasets)

    def get_item_at(self, index: int) -> str:
        try:
            return self.groups[index]
        except IndexError:
            return self.datasets[index - len(self.groups)]


@dataclass
class NavigationState:
    cursor_row: int
    level: int
    group_data: GroupData | None
    scroll_offset_y: float = 0


class NavigationStatic(ScrollView, can_focus=False):
    COMPONENT_CLASSES = {
        "--cursor",
        "--group",
        "--dataset",
        "--hovered",
    }
    DEFAULT_CSS = """
    NavigationStatic {
        scrollbar-size-vertical: 0;
        background: $background;
        height: 100%;

        & > .--cursor {
            text-style: reverse bold;
        }
        & > .--group {
            color: $accent;
        }
        & > .--dataset {
            color: $primary;
        }
        & > .--hovered {
            background: $surface;
        }
    }
    """
    cursor_row: var[int] = var(0)
    """The row index of the cursor."""
    _hovered_row: var[int | None] = var(None)
    """The row index of the hovered item."""
    level: var[int] = var(0)
    """The depth level of the navigation. If 0, the layout has only one Navigation widget."""
    _group_data: var[GroupData | None] = var(None)  # type: ignore
    """The group data of the currently shown group."""

    @dataclass
    class GroupHighlighted(Message):
        """Message to indicate that a group has been highlighted."""

        obj: NavigationStatic
        highlighted_path: HDF5Path

    @dataclass
    class GroupChanged(Message):
        """Message to indicate that the group needs to be changed."""

        path: HDF5Path
        direction: Literal["up", "down"] = "down"

    def render_line(self, y: int) -> Strip:
        hover_style = (
            self.get_component_rich_style("--hovered", partial=True)
            if y == self._hovered_row
            else Style.null()
        )

        _, scroll_y = self.scroll_offset
        y += scroll_y

        cursor = Style.combine(
            (
                self.get_component_rich_style("--cursor", partial=True)
                if y == self.cursor_row
                else Style.null(),
                hover_style,
            )
        )

        group_data = self._group_data
        if group_data is None:
            return Strip([])

        try:
            item = group_data.groups[y]
            style = Style.combine(
                (cursor, self.get_component_rich_style("--group", partial=True))
            )
        except IndexError:
            try:
                item = group_data.datasets[y - len(group_data.groups)]
                style = Style.combine(
                    (cursor, self.get_component_rich_style("--dataset", partial=True))
                )
            except IndexError:
                return Strip([])

        strip = Strip([Segment(item, style=style)])
        return strip.crop_pad(
            strip.cell_length, 1, self.size.width - strip.cell_length, style
        )

    def get_navigation_state(self) -> NavigationState:
        """Get the current navigation state."""
        return NavigationState(
            cursor_row=self.cursor_row,
            level=self.level,
            group_data=self._group_data,
            scroll_offset_y=self.scroll_y,
        )

    def set_navigation_state(self, state: NavigationState | None) -> None:
        """Set the navigation state.

        Args:
            state: The navigation state to set.
        """
        if state is None:
            state = NavigationState(0, 0, None)

        with self.prevent(Message):
            self.level = state.level
            self._group_data = state.group_data

        self.scroll_y = state.scroll_offset_y
        self.cursor_row = state.cursor_row

    def watch__group_data(self, _old: GroupData, new: GroupData | None) -> None:
        if new is not None:
            self.virtual_size = Size(1, new.length)
            self.cursor_row = 0

        self.refresh(layout=True)

    def watch__hovered_row(self, old: int | None, new: int | None) -> None:
        if old is not None:
            self.refresh_line(old)
        if new is not None:
            self.refresh_line(new)


class Navigation(NavigationStatic, can_focus=True):
    BINDINGS = [
        Binding("j,down", "cursor_down"),
        Binding("k,up", "cursor_up"),
        Binding("l,right,enter", "cursor_right"),
        Binding("h,left,escape", "cursor_left"),
    ]

    def action_cursor_down(self) -> None:
        y = min(self.cursor_row + 1, self._group_data.length - 1)
        self.scroll_to_region(Region(0, y, 1, 1), animate=False)
        self.cursor_row = y

    def action_cursor_up(self) -> None:
        y = max(self.cursor_row - 1, 0)
        self.scroll_to_region(Region(0, y, 1, 1), animate=False)
        self.cursor_row = y

    def action_cursor_right(self) -> None:
        try:
            highlighted = self._group_data.get_item_at(self.cursor_row)
            highlighted_path = self._group_data.path.joinpath(highlighted)
        except IndexError:
            return

        if highlighted not in self._group_data.groups:
            return

        self.post_message(Navigation.GroupChanged(highlighted_path, "down"))

    def action_cursor_left(self) -> None:
        if self.level == 0:
            return
        self.post_message(Navigation.GroupChanged(self._group_data.path.parent, "up"))

    def set_navigation_state(self, state: NavigationState | None) -> None:
        super().set_navigation_state(state)
        self._highlight_row(self.cursor_row)

    def _highlight_row(self, y: int) -> None:
        try:
            highlighted_path = self._group_data.path.joinpath(
                self._group_data.get_item_at(y)
            )
            self.post_message(Navigation.GroupHighlighted(self, highlighted_path))
        except (IndexError, AttributeError):
            return

    def watch_cursor_row(self, old: int, new: int) -> None:
        if new < 0:
            return
        scroll_y = self.scroll_offset[1]
        old_region = Region(0, old - scroll_y, self.size.width, 1)
        new_region = Region(0, new - scroll_y, self.size.width, 1)

        self._highlight_row(new)
        self.refresh(old_region, new_region)

    def on_mouse_move(self, message: events.MouseMove) -> None:
        self._hovered_row = message.y

    def on_click(self, message: events.Click) -> None:
        if message.y is None:
            return
        self.cursor_row = message.y


class NavigationPreview(Static):
    """The preview widget on the right side to show the content of the highlighted
    object.
    """

    path: reactive[HDF5Path | None] = reactive(None, layout=True)

    def __init__(self, root_group: Group, **kwargs) -> None:
        super().__init__(**kwargs)
        self._root = root_group
        """The root bamboost group of the simulation hdf5 file."""

    def render(self) -> RenderResult:
        if self.path is None:
            return ""

        obj = self._root[self.path]
        if isinstance(obj, Dataset):
            return rich.console.Group(
                Text(str(obj), style="blue"),
                Rule(style="black"),
                Text(str(obj[()])),
            )

        return rich.console.Group(
            Text(str(obj), style="blue"),
            Rule(style="black"),
            Text("An HDF5 Group"),
        )


class HDFViewer(Screen):
    DEFAULT_CSS = """
    HDFViewer > Vertical {
        layout: grid;
        grid-rows: 3fr 2fr;
    }

    #nav-container {
        border: round $border;

        &:focus-within {
            border: round $accent;
        }
    }
    #nav-center {
        width: 2fr;
        border-right: vkey $border;
    }
    #nav-static {
        display: none;
        width: 1fr;
        border-right: vkey $border;
    }
    #nav-preview {
        width: 2fr;
        padding: 0 1;
    }
    """

    def __init__(self, collection_uid: str, simulation_name: str) -> None:
        super().__init__("hfive")
        self.collection_uid = collection_uid
        self.simulation_name = simulation_name
        self.simulation = Simulation.from_uid(
            f"{collection_uid}{constants.UID_SEPARATOR}{simulation_name}"
        )
        self._root = self.simulation.root
        with self.simulation._file.open() as f:
            f.file_map.populate(exclude_numeric=False)
        self._stack: list[NavigationState] = []

    def on_mount(self) -> None:
        self.query_one(Navigation).set_navigation_state(
            NavigationState(0, 0, self._get_group_data(HDF5Path("/")))
        )
        self.query_one("#current-group-attrs").attrs = self.simulation.root.attrs  # type: ignore[reportAttributeAccessIssue]

    def compose(self) -> ComposeResult:
        yield Header(self.simulation.uid, self.simulation.path)
        with Vertical() as v:
            with Horizontal(id="nav-container"):
                yield NavigationStatic(id="nav-static")
                yield Navigation(id="nav-center")
                yield NavigationPreview(self._root, id="nav-preview")
            with Horizontal() as h:
                yield AttrsView(
                    id="current-group-attrs",
                    border_title="Current Group Attributes",
                )
                yield AttrsView(
                    id="highlighted-attrs", border_title="Highlighted Group Attributes"
                )
        yield Footer()

    @lru_cache(100)
    def _get_group_data(self, path: HDF5Path) -> GroupData:
        group = self._root[path, Group]
        return GroupData(path, group.groups(), group.datasets(), group.attrs)

    @on(Navigation.GroupHighlighted)
    def _on_group_highlighted(self, message: Navigation.GroupHighlighted) -> None:
        w = cast(AttrsView, self.query_one("#highlighted-attrs"))
        w.attrs = self._get_group_data(message.highlighted_path).attrs

        preview_widget = self.query_one(NavigationPreview)
        preview_widget.path = message.highlighted_path

    @on(Navigation.GroupChanged)
    def _on_group_changed(self, message: Navigation.GroupChanged) -> None:
        w = cast(AttrsView, self.query_one("#current-group-attrs"))
        w.attrs = self._get_group_data(message.path).attrs

        navigation_widget = self.query_one(Navigation)
        static_widget = self.query_one(NavigationStatic)

        if message.direction == "up":
            previous_state = self._stack.pop()
            navigation_widget.set_navigation_state(previous_state)
            if not self._stack:
                static_widget.styles.display = "none"

        else:
            self._stack.append(navigation_widget.get_navigation_state())
            new_state = NavigationState(
                0, navigation_widget.level + 1, self._get_group_data(message.path)
            )
            navigation_widget.set_navigation_state(new_state)
            static_widget.styles.display = "block"

        static_state = self._stack[-1] if self._stack else None
        static_widget.set_navigation_state(static_state)
