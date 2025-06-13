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
