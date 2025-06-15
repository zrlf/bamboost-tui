# Bamboost terminal interface

Complementary TUI for [bamboost](https://gitlab.com/cmbm-ethz/bamboost).

## Key bindings

To override key bindings, specify them in the bamboost config file like this:

> [!note]
> Below we maintain a list all modifieable bindings (they need to have an "id" assigned).

```toml
[tui.keys]
"app.command_palette" = "ctrl+p"
"app.help" = "question_mark"

"collection.toggle_picker" = "ctrl+m,p"
"collection.cycle_tabs" = "t"
"collection.sync" = "c>s"

"index.scan" = "alt+ctrl+s"
"index.clean" = "alt+ctrl+j"
```

## Custom commands

Custom commands/plugins are written in Python an can be loaded from the bamboost config file like this:

```toml
[tui]
plugins = [
    "path/to/plugin.py",
]
```

A very simple example of a custom command is:

```python
from bamboost_tui.plugins import CustomBinding, get_app

def greet():
    get_app().notify("Hello, world!")

BINDINGS = [
    CustomBinding(
        key="ctrl+l",
        action=greet,
        description="Say hello very loudly",
        id="custom.greeting",
    )
]
```

The keybinds in `BINDINGS` will be added to the app on the app level.
