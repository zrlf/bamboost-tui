from textual.app import App
from textual.color import Color


def variable_to_color(app: App, variable: str) -> str:
    val = app.theme_variables.get(variable)
    return Color.parse(val).rich_color.name
