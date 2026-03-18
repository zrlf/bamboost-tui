from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table
from textual.widget import Widget
from textual.widgets import Static, Tab

from bamboost_tui.utils import get_index

if TYPE_CHECKING:
    from textual.app import ComposeResult, RenderResult

    from bamboost.core.remote import Remote
    from bamboost_tui.screens.collections import ScreenCollection


class CollectionHeader(Static, can_focus=False):
    DEFAULT_CSS = """
    CollectionHeader {
        height: auto;
        width: auto;
    }
    """
    COMPONENT_CLASSES = Static.COMPONENT_CLASSES | {
        "--uid",
        "--path",
        "--remote",
    }

    def __init__(self, uid: str | None = None, path: str | None = None) -> None:
        uid = uid or ""
        path = self._get_path(uid)
        super().__init__(
            content=self._get_rich_table(uid, path), id="collection-header"
        )

    def _get_rich_table(
        self, uid: str, path: str, remote: Remote | None = None
    ) -> RenderResult:
        tab = Table.grid("key", "value", padding=(0, 3))
        if uid:
            tab.add_row(
                "UID:", uid, style=self.get_component_rich_style("--uid", partial=True)
            )
            tab.add_row(
                "Path:",
                path or "[collection not found]",
                style=self.get_component_rich_style("--path", partial=True),
            )
            if remote is not None:
                tab.add_row(
                    "Remote:",
                    remote._remote_url,
                    style=self.get_component_rich_style("--remote", partial=True),
                )
        return tab

    def _get_path(self, uid: str | None, remote: Remote | None = None) -> str:
        if remote is not None:
            found_path = remote._get_collection_path(uid) if uid else None
        else:
            found_path = get_index()._get_collection_path(uid) if uid else None
        return found_path.as_posix() if found_path else "[Collection not found]"

    def update_uid(self, uid: str | None, remote: Remote | None = None) -> None:
        """Update the UID and path in the header."""
        self.update(
            content=self._get_rich_table(uid or "", self._get_path(uid, remote), remote)
        )


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

    def update_uid(self, uid: str | None) -> None:
        self.tabs = set(self.screen._open_collections.keys())
        self.refresh(recompose=True)
        self.call_after_refresh(self.set_active, uid)

    def set_active(self, new: str | None) -> None:
        if new is None:
            return
        self.query("Tab.-active").remove_class("-active")
        self.query(f"Tab#tab-{new}").add_class("-active")

    def compose(self) -> ComposeResult:
        yield from (Tab(key, id=f"tab-{key}") for key in self.tabs)
