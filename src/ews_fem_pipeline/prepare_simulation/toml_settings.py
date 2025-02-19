import tomllib
from pathlib import Path

import toml

from ews_fem_pipeline.prepare_simulation.simulation_settings import Settings


def write_settings_to_toml(filepath: Path, settings):
    """
    Writes all settings to a .toml file.
    """
    assert filepath.suffix == ".toml", "The input file does not have the correct file extension. Must be .toml"

    parent_path = filepath.parent
    parent_path.mkdir(parents=True, exist_ok=True)

    settings_dict = settings.model_dump()

    with open(filepath, "w") as toml_file:
        toml.dump(settings_dict, toml_file)


def load_settings_from_toml(filepath: Path):
    """
    Loads settings from a pre-written .toml file.
    Only non-default settings need to be provided.
    The remaining settings are set to their default value.
    """

    assert filepath.suffix == ".toml", "The input file does not have the correct file extension. Must be .toml"

    with open(filepath, "rb") as f:
        settings = tomllib.load(f)
    settings = Settings.model_validate(settings)

    return settings
