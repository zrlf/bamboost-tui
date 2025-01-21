from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.app import App
from textual.binding import Binding, BindingType
from textual.color import Color

if TYPE_CHECKING:
    from typing import Protocol

    class WidgetProtocol(Protocol):
        BINDINGS: list[BindingType]
        _SUBGROUPS: dict[str, dict[str, Binding]]
        _subgroup: dict[str, Binding] | None


class KeySubgroupsMixin:
    """A mixin for widgets that need to handle key subgroups."""

    def _create_subgroup_mapping(self: WidgetProtocol) -> None:
        self._SUBGROUPS = {}
        """Mapping of subgroup keys to a dictionary of bindings."""
        self._subgroup = None
        """The current subgroup of bindings."""
        for binding in Binding.make_bindings(self.BINDINGS):
            if len(binding.key.split(">")) > 1:
                subgroup_key, key = binding.key.split(">")
                self._SUBGROUPS.setdefault(subgroup_key, {})[key] = Binding(
                    key,
                    binding.action,
                    binding.description,
                    binding.show,
                    binding.key_display,
                    binding.priority,
                    binding.tooltip,
                    binding.id,
                    binding.system,
                )

    def _enter_subgroup(self, key: events.Key) -> None:
        self._subgroup = self._SUBGROUPS.get(key.key)

    def _resolve_subgroup(self, subgroup: dict[str, Binding], key: events.Key) -> None:
        action = subgroup[key.key].action
        key.prevent_default()
        key.stop()
        self._subgroup = None
        # call the action for the binding
        getattr(self, "action_" + action)()

    def on_key(self, event: events.Key) -> None:
        # if we're in a subgroup, check group specific binding
        if self._subgroup is not None:
            if event.key in self._subgroup:
                return self._resolve_subgroup(self._subgroup, event)
            else:
                self._subgroup = None
                return

        # if the key leads to a subgroup, enter it
        if event.key in self._SUBGROUPS:
            self._enter_subgroup(event)


def variable_to_color(app: App, variable: str) -> str:
    val = app.theme_variables.get(variable)
    return Color.parse(val).rich_color.name
