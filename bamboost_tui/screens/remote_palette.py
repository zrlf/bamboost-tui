from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.style import Style as RichStyle
from rich.table import Column, Table
from rich.text import Text
from textual._context import active_app
from textual.command import Hit, Hits, Provider
from textual.message import Message
from textual.style import Style

from bamboost_tui.command_palette import CommandPalette

if TYPE_CHECKING:
    from bamboost.core.remote import Remote


class RemoteHit(Hit):
    class RemoteSelected(Message):
        def __init__(self, remote: Remote) -> None:
            self.remote = remote
            super().__init__()

    def __init__(
        self,
        score: float,
        remote: Remote,
        picker: RemoteProvider,
    ) -> None:
        self.remote = remote
        self._picker = picker
        super().__init__(
            score,
            self._render(),
            lambda: self._picker.screen.post_message(
                RemoteHit.RemoteSelected(self.remote)
            ),
        )

    def _render(self):
        tab = Table.grid(
            *(Column(width=w) for w in self._picker._widths),
            padding=(0, 2),
            expand=True,
            pad_edge=False,
        )
        styles = self._picker.styles
        tab.add_row(
            Text(self.remote._remote_url, styles["url"]),
            Text(self.remote._workspace_name or "", styles["workspace"]),
        )
        return Group(tab, Text("remote database", styles["help"]))


class RemoteProvider(Provider):
    """A command provider to select remotes."""

    def __init__(self, screen, match_style: Style | None = None) -> None:
        super().__init__(screen, match_style)
        self.styles: dict[str, RichStyle] = {}

    async def startup(self) -> None:
        from bamboost.core.remote import Remote

        app = active_app.get()
        self.styles["url"] = app.screen.get_component_rich_style(
            "remote-list--url", partial=True
        )
        self.styles["workspace"] = app.screen.get_component_rich_style(
            "remote-list--workspace", partial=True
        )
        self.styles["help"] = app.screen.get_component_rich_style(
            "command-palette--help-text", partial=True
        )
        try:
            self.remotes = Remote.list()
        except Exception:
            self.remotes = []

        widths = (0, 0)
        for r in self.remotes:
            widths = tuple(
                max(width, len(str(cell)))
                for width, cell in zip(widths, (r._remote_url, r._workspace_name or ""))
            )
        self._widths = widths

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for r in self.remotes:
            text = r._remote_url + (r._workspace_name or "")
            score = matcher.match(text)
            if score > 0:
                yield RemoteHit(score, r, self)

    async def discover(self) -> Hits:
        for r in self.remotes:
            yield RemoteHit(1.0, r, self)


class RemotePalette(CommandPalette):
    COMPONENT_CLASSES = CommandPalette.COMPONENT_CLASSES | {
        "remote-list--url",
        "remote-list--workspace",
    }

    def __init__(self):
        super().__init__(
            providers=[RemoteProvider],
            placeholder="Search remotes (or type a new remote URL)",
            id="remote-picker",
        )
