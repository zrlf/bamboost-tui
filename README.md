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
"collection.reload" = "r"
"collection.sort" = "s"
"collection.delete" = "d"
"collection.open_paraview" = "o>p"
"collection.open_directory" = "o>d"
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
from bamboost_tui.plugins import CustomBinding, get_app, get_uid


def greet():
    get_app().notify("Hello, world!")


def print_uid_to_console():
    """This function demonstrates how to get the UID of the currently selected item, and
    print it to stdout for a pipe or something."""
    app = get_app()

    # Giving the app as an argument is optional, you can also call get_uid() without an argument
    # uid is the full UID of the currently selected item, e.g. "ABCD1234:my-simulation"
    uid = get_uid(app)

    # We can output the UID to the console by giving the apps exit function a string argument!
    app.exit(uid)


BINDINGS = [
    CustomBinding(
        key="ctrl+l",
        action=greet,
        description="Say hello very loudly",
        id="custom.greeting",
    ),
    CustomBinding(
        "ctrl+y",
        print_uid_to_console,
        "Print my UID to the console",
        "custom.print_uid",
    ),
]
```

The keybinds in `BINDINGS` will be added to the app on the app level.
