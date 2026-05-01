from __future__ import annotations
from typing import Any, Self, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, VerticalScroll
from textual.binding import Binding
from textual.widgets import Static
from textual.reactive import var

from rich.text import Text
from rich.table import Table
from rich.highlighter import ReprHighlighter

if TYPE_CHECKING:
    from pandas import DataFrame, Series
    import numpy as np


@dataclass
class EDParam:
    name: str
    dtype: Any
    unique_vals: np.ndarray
    group: str = "general"

    def __len__(self) -> int:
        return len(self.unique_vals)

    def __hash__(self) -> int:
        return hash(self.name)

    def render_row(self, highlighter: ReprHighlighter) -> tuple[Text, Text, Text]:
        """Returns the formatted cells for a table row."""
        
        # 1. Handle the Value Display
        if len(self.unique_vals) == 1:
            val = self.unique_vals[0]
            # Custom formatting for specific types
            if hasattr(val, "strftime"):
                val_str = val.strftime("%Y-%m-%d %H:%M")
            else:
                val_str = str(val)
        else:
            val_str = str(self.unique_vals)

        # 2. Create Rich Text objects
        name_text = Text(self.name, style="bold cyan")
        type_text = Text(str(self.dtype), style="italic dim")
        val_text = Text(val_str)
        
        # 3. Apply highlighting
        highlighter.highlight(val_text)
        
        return name_text, type_text, val_text


EDParamDict = dict[str, EDParam]


@dataclass
class ExperimentalDesignData:
    all_parameters: EDParamDict
    constants: EDParamDict
    variables: EDParamDict

    @classmethod
    def from_df(
        cls,
        df: DataFrame,
        exclude: list[str] | None = None,
    ) -> Self:
        import numpy as np

        param_keys = [k for k in df.columns if k not in (exclude or [])]

        def get_unique_vals(series: Series) -> np.ndarray:
            try:
                return np.asarray(series.unique())
            except TypeError:

                def make_hashable(x):
                    if isinstance(x, (list, np.ndarray)):
                        return tuple(make_hashable(item) for item in x)
                    return x
                
                hashable_vals = series.map(make_hashable)
                return np.asarray(hashable_vals.unique())
        
        all_params = {
            pkey: EDParam(
                name=pkey,
                dtype=df[pkey].dtype,
                unique_vals=get_unique_vals(df[pkey]),
                group=pkey.split(".")[0] if "." in pkey else "general",
            )
            for pkey in param_keys
        }

        const_params = {k: v for k, v in all_params.items() if len(v.unique_vals) == 1}
        var_params = {k: v for k, v in all_params.items() if len(v.unique_vals) > 1}

        return cls(
            all_parameters=all_params, constants=const_params, variables=var_params
        )


class ParamsView(VerticalScroll, can_focus=True):
    COMPONENT_CLASSES = {
        "--key",
        "--value",
    }
    BINDINGS = [
        Binding("j,down", "scroll_down", show=False),
        Binding("k,up", "scroll_up", show=False),
    ]
    params: var[EDParamDict | None] = var(None)

    def __init__(
        self,
        headers: tuple[str, ...],
        border_title: str = "",
        *,
        id: str | None = None,
        params: EDParamDict | None = None,
    ) -> None:
        super().__init__(id=id)
        self.headers = headers
        self.border_title = border_title
        self.params = params

    def compose(self) -> ComposeResult:
        yield Static()

    def update_params(self, params: EDParamDict) -> None:
        self.params = params
        table = Table.grid(*self.headers, padding=(0, 2))
        table.add_row(*self.headers, end_section=True)
        
        highlighter = ReprHighlighter()

        if self.params:
            for param in self.params.values():
                table.add_row(*param.render_row(highlighter))

        self.query_one(Static).update(table)


class ExpDesignInfoScreen(ModalScreen):
    """A modal screen to display the experimental design of the collection."""

    BINDINGS = [
        Binding("escape,q", "dismiss", "Dismiss", show=False),
    ]

    def __init__(self, df: DataFrame, exclude_keys: list[str]):
        super().__init__()
        self.ed_data: ExperimentalDesignData = ExperimentalDesignData.from_df(df=df, exclude=exclude_keys)

    def compose(self) -> ComposeResult:
        vc = Vertical(id="exp-design-container")
        vc.border_title = "Experimental Design"
        with vc:
            yield ParamsView(
                headers=("Name", "Type", "Value"),
                border_title="Constant Parameters", 
                id="const-params"
            )
            yield ParamsView(
                headers=("Name", "Type", "Values"),
                border_title="Variable Parameters", 
                id="var-params"
            )

    def on_mount(self) -> None:
        self.query_one("#const-params", ParamsView).update_params(
            params=self.ed_data.constants
        )
        self.query_one("#var-params", ParamsView).update_params(
            params=self.ed_data.variables
        )
