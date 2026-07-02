"""Small public settings API used by the CLI and external scripts."""

from pathlib import Path

from .settings import (
    Settings,
    default_settings as _default_settings,
    load_settings_from_toml,
    write_settings_to_toml,
)


def default_settings() -> Settings:
    return _default_settings()


def load_settings(filepath: Path) -> Settings:
    return load_settings_from_toml(filepath)


def write_settings(filepath: Path, settings: Settings) -> None:
    write_settings_to_toml(filepath, settings)
