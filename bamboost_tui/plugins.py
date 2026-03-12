from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from textual.binding import Binding

if TYPE_CHECKING:
    from bamboost_tui.app import BamboostApp


@dataclass(frozen=True)
class CustomBinding:
    key: str
    action: Callable
    description: str = ""
    id: str | None = None
    show: bool = False

    def action_name(self) -> str:
        """Generate a unique action name based on the binding's key and description."""
        return f"{abs(hash(self.action))}"

    def to_textual_binding(self) -> Binding:
        """Convert this custom binding to a Textual Binding."""
        return Binding(
            self.key,
            self.action_name(),
            description=self.description,
            id=self.id,
            show=self.show,
        )


# Some API for plugins to use
def get_app() -> "BamboostApp":
    """Get the current Textual app instance."""
    from textual._context import active_app

    return active_app.get()  # pyright: ignore[reportReturnType]


def get_uid(app: "BamboostApp | None" = None) -> str | None:
    """Get the uid of the selected collection."""
    from bamboost_tui.screens.collections import ScreenCollection
    from bamboost_tui.screens.collections.placeholder import Placeholder

    if app is None:
        app = get_app()
    screen = app.screen

    if not isinstance(screen, ScreenCollection):
        raise RuntimeError("Not on a collection screen")

    table = screen._table_container._active_widget
    if isinstance(table, Placeholder):
        get_app().notify(
            "No collection table available. Doing nothing.", severity="information"
        )
        return

    name = table._row_locations.get_key(table.cursor_row).value
    return f"{table.uid}:{name}"
