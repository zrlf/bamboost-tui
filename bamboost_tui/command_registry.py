import sys
from typing import Optional
from typing import Callable
from typing import List

from textual.app import App
from bamboost_tui.utils import get_index
from dataclasses import dataclass
from bamboost import config


@dataclass
class Command:
    name: str
    label: str
    help: Optional[str]
    key: Optional[str]
    func: Callable


command_registry: List[Command] = []


def register_command(name, label, help=None, key=None):
    def decorator(func):
        command_registry.append(
            Command(
                name,
                label,
                help,
                config._remainder.get("tui", {}).get("keys", {}).get(name, key),
                func,
            )
        )
        return func

    return decorator


@register_command("index.clean", label="Clean the collection index", key="ctrl+shift+i")
def clean_index(app: App) -> None:
    get_index().check_integrity()
    app.notify("⚪ Cleaned index")


@register_command(
    "index.scan", label="Scan for collections", help="search", key="ctrl+s"
)
def scan_collections(app: App) -> None:
    """Scan for collections."""
    get_index().scan_for_collections()
    app.notify("✔️ Scanned for collections")
