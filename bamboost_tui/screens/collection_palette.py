from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.style import Style as RichStyle
from rich.table import Column, Table
from rich.text import Text
from textual._context import active_app
from textual.command import Hit, Hits, Matcher, Provider
from textual.message import Message
from textual.screen import Screen
from textual.style import Style
from textual.visual import VisualType

from bamboost_tui.command_palette import CommandPalette

if TYPE_CHECKING:
    from bamboost.index.sqlmodel import CollectionORM


class CollectionHit(Hit):
    class CollectionSelected(Message):
        def __init__(self, uid: str) -> None:
            self.uid = uid
            super().__init__()

    def __init__(
        self,
        score: float,
        collection: CollectionORM,
        picker: CollectionProvider,
        matcher: Matcher | None = None,
    ) -> None:
        self.collection = collection
        self._picker = picker
        super().__init__(
            score,
            self._render(matcher),
            lambda: self._picker.screen.post_message(
                CollectionHit.CollectionSelected(collection.uid)
            ),
        )

    def _render(self, matcher: Matcher | None = None) -> VisualType:
        coll = self.collection

        tab = Table.grid(
            *(Column(width=w) for w in self._picker._widths),
            padding=(0, 2),
            expand=True,
            pad_edge=False,
        )
        styles = self._picker.styles
        tab.add_row(
            Text(coll.uid, styles["uid"]),
            Text.from_markup(
                matcher.highlight(coll.path).markup.replace("ansi_", ""),
                style=styles["path"],
            )
            if matcher
            else Text(coll.path, styles["path"]),
            Text(str(coll.simulations.__len__()), styles["count"]),
        )
        return Group(tab, Text("last modified: ", styles["help"]))


class CollectionProvider(Provider):
    """A command provider to select collections."""

    _table: Table

    def __init__(self, screen: Screen, match_style: Style | None = None) -> None:
        super().__init__(screen, match_style)
        self.styles: dict[str, RichStyle] = {}

    async def startup(self) -> None:
        from bamboost.index import Index

        app = active_app.get()
        self.styles["uid"] = app.screen.get_component_rich_style(
            "collection-list--uid", partial=True
        )
        self.styles["path"] = app.screen.get_component_rich_style(
            "collection-list--path", partial=True
        )
        self.styles["count"] = app.screen.get_component_rich_style(
            "collection-list--count", partial=True
        )
        self.styles["help"] = app.screen.get_component_rich_style(
            "command-palette--help-text", partial=True
        )
        self.collections = Index.default.all_collections
        widths = (0, 0, 0)
        for coll in self.collections:
            widths = tuple(
                max(width, len(str(cell)))
                for width, cell in zip(
                    widths, (coll.uid, coll.path, coll.simulations.__len__())
                )
            )
        self._widths = widths

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for coll in self.collections:
            score = matcher.match(coll.uid + coll.path)
            if score > 0:
                yield CollectionHit(score, coll, self, matcher)

    async def discover(self) -> Hits:
        for coll in self.collections:
            # yield Hit(1.0, self._render(coll), self.app.pop_screen)
            yield CollectionHit(1.0, coll, self)


class RemoteCollectionProvider(CollectionProvider):
    async def startup(self) -> None:
        app = active_app.get()
        self.styles["uid"] = app.screen.get_component_rich_style(
            "collection-list--uid", partial=True
        )
        self.styles["path"] = app.screen.get_component_rich_style(
            "collection-list--path", partial=True
        )
        self.styles["count"] = app.screen.get_component_rich_style(
            "collection-list--count", partial=True
        )
        self.styles["help"] = app.screen.get_component_rich_style(
            "command-palette--help-text", partial=True
        )
        from bamboost.core.remote import Remote

        self.collections = Remote()
        widths = (0, 0, 0)
        for coll in self.collections:
            widths = tuple(
                max(width, len(str(cell)))
                for width, cell in zip(
                    widths, (coll.uid, coll.path, coll.simulations.__len__())
                )
            )
        self._widths = widths


class CollectionPalette(CommandPalette):
    COMPONENT_CLASSES = CommandPalette.COMPONENT_CLASSES | {
        "collection-list--uid",
        "collection-list--path",
        "collection-list--count",
    }

    def __init__(self):
        super().__init__(
            providers=[CollectionProvider],
            placeholder="Search collections",
            id="collection-picker",
        )
