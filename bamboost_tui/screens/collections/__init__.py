from __future__ import annotations

from itertools import chain, cycle
from typing import TYPE_CHECKING

from bamboost.exceptions import InvalidCollectionError
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Right
from textual.reactive import reactive, var
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Tab

from bamboost_tui.commandline import CommandLine as CommandLine
from bamboost_tui.commandline import CommandMessage as CommandMessage
from bamboost_tui.screens.collection_palette import (
    CollectionHit,
    CollectionPalette,
    RemoteCollectionPalette,
)
from bamboost_tui.screens.collections.header import (
    CollectionHeader,
    OpenCollectionsTabs,
)
from bamboost_tui.screens.collections.placeholder import Placeholder
from bamboost_tui.screens.collections.table import CollectionTable
from bamboost_tui.screens.remote_palette import RemoteHit, RemotePalette
from bamboost_tui.utils import KeySubgroupsMixin as KeySubgroupsMixin
from bamboost_tui.utils import get_index as get_index
from bamboost_tui.widgets import ModifiedDataTable as ModifiedDataTable
from bamboost_tui.widgets import SortOrder as SortOrder
from bamboost_tui.widgets.confirmation import ModalPrompt as ModalPrompt

if TYPE_CHECKING:
    from bamboost.core.remote import Remote


class TableContainer(Container):
    _active_widget: reactive[CollectionTable | Placeholder] = reactive(
        Placeholder(), recompose=True
    )
    DEFAULT_CLASSES = "placeholder"

    def watch__active_widget(self, old: Widget, new: Widget) -> None:
        if isinstance(new, Placeholder):
            self.add_class("placeholder")
        else:
            self.remove_class("placeholder")

    def compose(self) -> ComposeResult:
        yield self._active_widget

    def focus(self, scroll_visible: bool = True) -> CollectionTable | Placeholder:
        return self._active_widget.focus(scroll_visible)


class ScreenCollection(Screen, inherit_bindings=False):
    BINDINGS = [
        Binding(
            "ctrl+m",
            "toggle_picker",
            "toggle the collection picker",
            id="collection.toggle_picker",
        ),
        Binding(
            "ctrl+r",
            "toggle_remote_picker",
            "select a remote",
            id="collection.toggle_remote_picker",
        ),
        Binding(
            "ctrl+t",
            "cycle_tabs",
            "cycle through collection tabs",
            show=False,
            id="collection.cycle_tabs",
        ),
        Binding("q", "close", "close collection", show=False),
    ]
    BINDING_GROUP_TITLE = "Screen commands"

    _open_collections: dict[str, CollectionTable]
    current_uid: var[str | None] = var(None)
    current_widget: CollectionTable | Placeholder
    _active_remote: Remote | None = None
    """The currently selected remote, or None for local collections."""

    def __init__(self, uid: str | None = None, path: str | None = None) -> None:
        super().__init__()
        self.uid, self.path = uid, path
        self.set_reactive(ScreenCollection.current_uid, uid)
        self._table_container = TableContainer(id="table-container")
        """The container holding the table widget."""
        self._tabs = OpenCollectionsTabs()
        """The container holding the tabs in the header."""
        self._open_collections = {}

    def on_mount(self) -> None:
        if not self.uid and self.path:
            self.loading = True
            self._startup_with_path(self.path)

    @work(thread=True)
    async def _startup_with_path(self, path: str) -> None:
        try:
            uid = get_index().resolve_uid(path)
            self.current_uid = uid
        except InvalidCollectionError:
            self.notify("[$error][/$error] Invalid collection path")
        self.loading = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield CollectionHeader()
            with Right():
                yield self._tabs
        yield self._table_container
        yield Footer(disabled=True)

    def watch_current_uid(self, _old, new: str | None) -> None:
        self.show_collection(uid=new)

    @work(exclusive=True)
    async def show_collection(
        self, uid: str | None = None, remote: Remote | None = None
    ) -> None:
        # if no uid, show placeholder
        if uid is None:
            self._table_container._active_widget = Placeholder()
        else:
            try:
                self._table_container._active_widget = self._open_collections[uid]
            except KeyError:
                new_table = CollectionTable(uid, remote=remote)
                self._open_collections[uid] = new_table
                self._table_container._active_widget = new_table

        # update header and tabs
        self.query_one(CollectionHeader).update_uid(uid, remote=remote)
        self._tabs.update_uid(uid)

    def action_toggle_picker(self):
        self.app.push_screen(CollectionPalette())

    def action_toggle_remote_picker(self):
        self.app.push_screen(RemotePalette())

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
                self._table_container._active_widget = Placeholder()
            else:
                self.current_uid = next(iter(self._open_collections.keys()))
        else:
            self.app.exit()

    @on(CollectionHit.CollectionSelected)
    def _open_collection(self, message: CollectionHit.CollectionSelected) -> None:
        if self._active_remote is not None:
            self.show_collection(uid=message.uid, remote=self._active_remote)
            self._active_remote = None
        else:
            self.current_uid = message.uid

    @on(RemoteHit.RemoteSelected)
    def _on_remote_selected(self, message: RemoteHit.RemoteSelected) -> None:
        self._active_remote = message.remote
        self._fetch_and_browse_remote(message.remote)

    @work(thread=True)
    async def _fetch_and_browse_remote(self, remote: "Remote") -> None:
        self.notify(
            f"⏳ Fetching remote database from [bold]{remote._remote_url}[/bold]…",
            timeout=3.0,
        )
        try:
            remote.fetch_remote_database()
        except Exception as e:
            self.notify(
                f"Failed to fetch remote database: {e}",
                severity="error",
                timeout=5.0,
            )
            return
        self.notify(
            f"✔️ Fetched database from [bold]{remote._remote_url}[/bold]",
            timeout=2.0,
        )
        self.app.call_from_thread(
            self.app.push_screen, RemoteCollectionPalette(remote)
        )

    @on(Tab.Clicked)
    def _on_tab_clicked(self, message: Tab.Clicked) -> None:
        self.current_uid = message.tab.label_text
