from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table
from textual.widget import Widget
from textual.widgets import Static, Tab

from bamboost_tui.utils import get_index

if TYPE_CHECKING:
    from textual.app import ComposeResult, RenderResult

    from bamboost_tui.screens.collections import ScreenCollection


class CollectionHeader(Widget, can_focus=False):
    DEFAULT_CSS = """
    CollectionHeader {
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
        found_path = get_index()._get_collection_path(uid) if uid else None
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
    screen: "ScreenCollection"

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
