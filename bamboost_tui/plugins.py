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
