from __future__ import annotations

import importlib.util
from types import ModuleType
from typing import TYPE_CHECKING, MutableMapping, TypeVar, cast

from textual import events
from textual.app import App
from textual.binding import Binding, BindingType
from textual.color import Color
from textual.widget import Widget

if TYPE_CHECKING:
    from bamboost.index import Index


def get_index() -> Index:
    from bamboost.index import Index

    return Index.default


def import_module_from_path(path: str, module_name: str | None = None) -> ModuleType:
    """Import a module from a given file path."""
    if module_name is None:
        # Derive a module name from the path (not required, but helps in sys.modules)
        module_name = f"plugin_{hash(path)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)  # pyright: ignore[reportArgumentType]
    spec.loader.exec_module(module)
    return module


Subgroup = MutableMapping[str, "Binding  | Subgroup"]  # recursive
SelfWidgetMixin = TypeVar("SelfWidgetMixin", bound="Widget | KeySubgroupsMixin")


class KeySubgroupsMixin:
    """A mixin for widgets that handle hierarchical key bindings."""

    BINDINGS: list[BindingType]
    SUBGROUPS: dict[str, Subgroup]
    _active_subgroup: Subgroup | None = None

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.SUBGROUPS = {}

        def insert(subgroup: Subgroup, path: list[str], binding: Binding) -> None:
            *chain, final = path
            for key in chain:
                next_sub = subgroup.setdefault(key, {})
                if isinstance(next_sub, Binding):
                    raise ValueError(f"Key '{key}' already bound to an action.")
                subgroup = next_sub
            if final in subgroup:
                raise ValueError(f"Duplicate key: '{final}'")
            subgroup[final] = binding

        for binding in Binding.make_bindings(cls.BINDINGS):
            keys = binding.key.split(">")
            if len(keys) > 1:
                insert(cls.SUBGROUPS.setdefault(keys[0], {}), keys[1:], binding)

    def _enter_subgroup(self, event: events.Key) -> bool:
        subgroup = self.SUBGROUPS.get(event.key)
        if isinstance(subgroup, dict):
            self._active_subgroup = subgroup
            return True
        return False

    async def _resolve_binding(self, subgroup: Subgroup, event: events.Key) -> bool:
        try:
            item = subgroup[event.key]
        except KeyError:
            return False

        if isinstance(item, Binding):
            event.prevent_default()
            event.stop()
            self._active_subgroup = None
            await cast("Widget", self).run_action(item.action)
            return True

        self._active_subgroup = item
        return True

    async def on_key(self, event: events.Key) -> None:
        # Active subgroup resolution
        if self._active_subgroup:
            if await self._resolve_binding(self._active_subgroup, event):
                return
            # Invalid key: exit subgroup
            self._active_subgroup = None
            return

        # Top-level subgroup entry
        self._enter_subgroup(event)


def variable_to_color(app: App, variable: str) -> str:
    val = app.theme_variables.get(variable)
    return Color.parse(val).rich_color.name
