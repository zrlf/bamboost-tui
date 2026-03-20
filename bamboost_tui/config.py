from typing import TypedDict

from bamboost import config


class Config(TypedDict):
    keys: dict[str, str]
    plugins: list[str]
    floatPrecision: int
    maxCellWidth: int


default_config: Config = {
    "floatPrecision": 4,
    "maxCellWidth": 50,
    "keys": {},
    "plugins": [],
}
config_tui: Config = default_config | (config._remainder.get("tui", {}))
