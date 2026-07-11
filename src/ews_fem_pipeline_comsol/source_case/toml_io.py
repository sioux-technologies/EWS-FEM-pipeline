"""TOML I/O helpers for source-case pydantic settings."""

import math
import tomllib
from pathlib import Path

from ews_fem_pipeline_comsol.source_case.source_case_settings import Settings


def _is_list_of_tables(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def _format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite floats are not supported in TOML output.")
        return repr(value)
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        return "[ " + ", ".join(_format_value(item) for item in value) + ",]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _write_table(lines: list[str], prefix: str, table: dict, array_item: bool = False) -> None:
    scalars = []
    subtables = []
    array_tables = []

    for key, value in table.items():
        if value is None:
            continue
        if isinstance(value, dict):
            subtables.append((key, value))
        elif _is_list_of_tables(value):
            array_tables.append((key, value))
        else:
            scalars.append((key, value))

    if prefix:
        header = f"[[{prefix}]]" if array_item else f"[{prefix}]"
        lines.append(header)

    for key, value in scalars:
        lines.append(f"{key} = {_format_value(value)}")

    if scalars and (subtables or array_tables):
        lines.append("")

    for index, (key, value) in enumerate(subtables):
        child_prefix = f"{prefix}.{key}" if prefix else key
        _write_table(lines, child_prefix, value)
        if index != len(subtables) - 1 or array_tables:
            lines.append("")

    for table_index, (key, tables) in enumerate(array_tables):
        child_prefix = f"{prefix}.{key}" if prefix else key
        for item_index, item in enumerate(tables):
            _write_table(lines, child_prefix, item, array_item=True)
            if item_index != len(tables) - 1:
                lines.append("")
        if table_index != len(array_tables) - 1:
            lines.append("")


def write_settings_to_toml(filepath: Path, settings):
    """Write all source-case settings to a TOML file."""
    assert filepath.suffix == ".toml", "The input file does not have the correct file extension. Must be .toml"

    parent_path = filepath.parent
    parent_path.mkdir(parents=True, exist_ok=True)

    settings_dict = settings.model_dump()
    lines: list[str] = []
    _write_table(lines, "", settings_dict)

    with open(filepath, "w", encoding="utf-8") as toml_file:
        toml_file.write("\n".join(line for line in lines if line is not None).rstrip() + "\n")


def load_settings_from_toml(filepath: Path):
    """Load source-case settings from TOML and fill omitted values with defaults."""
    assert filepath.suffix == ".toml", "The input file does not have the correct file extension. Must be .toml"

    with open(filepath, "rb") as f:
        settings = tomllib.load(f)
    settings = Settings.model_validate(settings)

    return settings
