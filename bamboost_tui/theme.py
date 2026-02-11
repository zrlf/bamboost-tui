from textual.theme import BUILTIN_THEMES, Theme


ANSI_THEME = Theme(
    name="ansi",
    primary="ansi_blue",
    secondary="ansi_magenta",
    accent="ansi_yellow",
    foreground="ansi_bright_white",
    background="ansi_default",
    success="ansi_bright_green",
    warning=BUILTIN_THEMES["textual-dark"].warning,
    error="ansi_red",
    surface="ansi_bright_black",
    panel="ansi_bright_black",
    boost="ansi_bright_green",
    dark=True,
    variables={
        "foreground-muted": "ansi_white",
        "input-cursor-background": "ansi_black",
        "input-cursor-foreground": "ansi_white",
        "block-cursor-background": "ansi_black",
        "block-cursor-foreground": "ansi_white",
        "border": "ansi_bright_black",
        "border-focus": "ansi_blue",
        "footer-background": "ansi_black",
    },
)
