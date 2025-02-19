from pathlib import Path

import click

from ews_fem_pipeline import __version__
from ews_fem_pipeline.convert_simulation import feb_to_blender
from ews_fem_pipeline.prepare_simulation import (
    Settings,
    generate_mesh,
    load_settings_from_toml,
    write_settings_to_toml,
    write_to_feb,
)
from ews_fem_pipeline.run_simulation import FEBioRunner


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=False,
)
@click.version_option(
    version=__version__,
    prog_name="ews_fem_pipeline",
)
def cli_main():
    click.echo("EWS FEM pipeline")
    click.echo(f"version = {__version__}")


@cli_main.command()
@click.argument(
    "input_files",
    nargs=-1,
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
        executable=False,
    ),
)
def generate(input_files: tuple[Path, ...]):
    """
    Generates the mesh and writes them to the input .feb file.
    This file is written in the same directory as the input file.

    The .feb file generation is run on the provided input file(s).
    Each input file should be of the .toml format.
    Multiple input files can be specified (space separated), in which case these are all generated.
    The path to the input will be created, if it does not exist. The .feb file will be placed in the same
    directory as the input .toml file.

    All provided settings will overwrite the default values, which means that only settings that differ from their
    default value need to be written to the input .toml file.
    The code then writes another .toml file containing all settings that ultimately run the simulation; this is
    for reproducing purposes. This .toml is placed in the subdirectory "/output".
    """

    feb_files = []
    for filepath in input_files:
        # Load all non-default settings. Settings that are not parsed, are set to their default value.
        settings = load_settings_from_toml(filepath=filepath)

        # Write a .toml file that contains all settings for reproduction purposes. This will be put in the subdirectory
        # "/output" with name "<filename>_all_settings.toml".
        name_toml = filepath.stem + "_all_settings" + filepath.suffix
        output_directory = filepath.parent / "output"
        Path(output_directory).mkdir(parents=True, exist_ok=True)

        write_settings_to_toml(filepath=Path(output_directory / name_toml), settings=settings)

        mesh = generate_mesh(
            settings=settings
        )
        write_to_feb(
            filepath=filepath,
            mesh=mesh,
            settings=settings,
        )

        feb_file = filepath.with_suffix(".feb")
        feb_files.append(feb_file)
    return tuple(feb_files)


@cli_main.command()
@click.argument(
    "input-files",
    nargs=-1,
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
        executable=False,
    ),
)
@click.option(
    "-j", "--jobs",
    type=click.IntRange(min=0),
    default=0,
    help="Control parallelization; switches between (j>1) external (running multiple FEBio "
         "instances, at max j parallel instances) and (j=1) internal parallelization (allowing "
         "FEBio to use multiple threads). If j=0 (default), parallelization depends on the number "
         "of provided feb files: if 1 it chooses internal parallelization, if more than 1 external "
         "(maximum 4 instances).",
)
def fem(input_files: tuple[Path, ...], jobs: int):
    """ Run FEBio simulation(s).

    The simulation is run on the provided input file(s).
    Each input file should be of the .feb format.
    Multiple input files can be specified (space separated), in which case these are all simulated.
    """

    for filepath in input_files:
        assert filepath.suffix == ".feb", "The input file does not have the correct file extension. Must be .feb"

    if jobs == 0:
        # automatically determine how many parallel jobs to use
        jobs = 1 if len(input_files) == 1 else 4

    output_files = FEBioRunner().run(input_files, jobs)

    return output_files


@cli_main.command()
@click.argument(
    "input_files",
    nargs=-1,
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
        executable=False,
    ),
)
def convert(input_files: tuple[Path, ...]):
    """
    Converts the output .vtk files from the FEBio simulation(s) into a Blender compatible files to run the simulation
    from.

    Conversion is done on one or multiple input file(s)
    Each input file should be of the .feb format
    Multiple input files can be specified (space separated), in which case these are all converted.
    """
    for filepath in input_files:
        feb_to_blender(filepath)


@cli_main.command()
@click.argument(
    "filepath",
    nargs=1,
    type=click.Path(
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
        executable=False,
    ),
)
def write_default_settings(filepath: Path):
    """ Generates input .toml file with default settings.

    The single input is the path to where the settings file must be written.
    Input should be of .toml format.

    Changing default values can be done by opening the .toml file with a text editor and manually changing the values.
    """
    write_settings_to_toml(filepath=Path(filepath), settings=Settings())


@cli_main.command()
@click.argument(
    "input_files",
    nargs=-1,
    type=click.Path(
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
        executable=False,
    ),
)
@click.option(
    "-j", "--jobs",
    type=click.IntRange(min=0),
    default=0,
    help="Control parallelization; switches between (j>1) external (running multiple FEBio "
         "instances, at max j parallel instances) and (j=1) internal parallelization (allowing "
         "FEBio to use multiple threads). If j=0 (default), parallelization depends on the number "
         "of provided feb files: if 1 it chooses internal parallelization, if more than 1 external "
         "(maximum 4 instances).",
)
def run(input_files: tuple[Path, ...], jobs: int):
    """
    Runs the full FEM pipeline.

    The pipeline is run on the provided input file(s).
    Each input file should be of the .toml format.
    Multiple input files can be specified (space separated), in which all simulations are run for these input files.
    The path to the input will be created, if it does not exist.

    [1]: Generate
    Generates the mesh and writes them to the input .feb file for FEBio to run from.
    This file is written in the same directory as the input file.

    All provided settings in the .toml will overwrite the default values, which means that only settings
    that differ from their default value need to be written to the input .toml file.
    The code then writes another .toml file containing all settings that ultimately run the simulation; this is
    for reproducing purposes. This .toml is placed in the subdirectory "/output".

    [2]: FEM
    Run FEBio simulation(s).

    The simulation is run on the generated FEBio input .feb files
    For each .toml file, all output files are written in the subdirectory /output of where the .toml file is written

    [3]: Convert
    Converts the output .vtk files from the FEBio simulation(s) into a Blender compatible files to run the simulation
    from.

    """
    feb_files = generate.callback(input_files)
    output_files = fem.callback(feb_files, jobs)
    convert.callback(output_files)
