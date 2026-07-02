"""Command-line interface for the EWS COMSOL FEM pipeline."""

import argparse
import logging
from pathlib import Path

from ews_fem_pipeline_comsol.__about__ import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ews_fem_pipeline_comsol",
        description="COMSOL pipeline scaffold for the EWS FEM project.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate COMSOL input JSON files from TOML settings.")
    generate_parser.add_argument("input_files", nargs="+", type=Path)

    solve_parser = subparsers.add_parser("solve", help="Run COMSOL batch for one or more generated JSON files.")
    solve_parser.add_argument("input_files", nargs="+", type=Path)

    build_parser = subparsers.add_parser("build-only", help="Generate and build the COMSOL MPH without starting the solve.")
    build_parser.add_argument("input_files", nargs="+", type=Path)

    postprocess_parser = subparsers.add_parser(
        "postprocess-only",
        help="Generate postprocess Java and rerun COMSOL metrics/plot export on an existing result MPH without solving.",
    )
    postprocess_parser.add_argument("input_files", nargs="+", type=Path)
    postprocess_parser.add_argument(
        "--mode",
        choices=["full", "global", "ews_surface", "internal_tumor", "none", "skip"],
        default=None,
        help="Override [comsol].postprocess_mode for this postprocess-only call.",
    )

    run_parser = subparsers.add_parser("run", help="Run generate and solve in sequence.")
    run_parser.add_argument("input_files", nargs="+", type=Path)

    sweep_parser = subparsers.add_parser("sweep", help="Batch run multiple TOML cases through COMSOL pipeline.")
    sweep_parser.add_argument("input_files", nargs="+", type=Path)

    compare_parser = subparsers.add_parser("compare-metrics", help="Compare COMSOL metrics across runs.")
    compare_parser.add_argument("input_files", nargs="+", type=Path)
    compare_parser.add_argument("--baseline", type=str, default=None, help="Case name to use as baseline.")

    extract_parser = subparsers.add_parser(
        "extract-source-case",
        help="Write the resolved inline/source case from a COMSOL TOML to a standalone source-case TOML.",
    )
    extract_parser.add_argument("input_file", type=Path)
    extract_parser.add_argument("--output", type=Path, default=None)

    defaults_parser = subparsers.add_parser("write-default-settings", help="Write a default COMSOL TOML settings file.")
    defaults_parser.add_argument("filepath", type=Path)

    license_parser = subparsers.add_parser("license-check", help="Check whether COMSOL license is reachable.")
    license_parser.add_argument("settings_file", type=Path)

    return parser


def cli_main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        from ews_fem_pipeline_comsol.pipeline import generate_cases

        generate_cases(tuple(args.input_files))
        return 0

    if args.command == "solve":
        from ews_fem_pipeline_comsol.pipeline import solve_cases

        solve_cases(tuple(args.input_files))
        return 0

    if args.command == "build-only":
        from ews_fem_pipeline_comsol.pipeline import build_only_pipeline

        build_only_pipeline(tuple(args.input_files))
        return 0

    if args.command == "postprocess-only":
        from ews_fem_pipeline_comsol.pipeline import postprocess_only_pipeline

        postprocess_only_pipeline(tuple(args.input_files), postprocess_mode=args.mode)
        return 0

    if args.command == "run":
        from ews_fem_pipeline_comsol.pipeline import run_full_pipeline

        run_full_pipeline(tuple(args.input_files))
        return 0

    if args.command == "sweep":
        from ews_fem_pipeline_comsol.pipeline import sweep_cases

        sweep_cases(tuple(args.input_files))
        return 0

    if args.command == "compare-metrics":
        from ews_fem_pipeline_comsol.pipeline import compare_metrics_cases

        compare_metrics_cases(tuple(args.input_files), baseline=args.baseline)
        return 0

    if args.command == "extract-source-case":
        from ews_fem_pipeline_comsol.pipeline import extract_source_case

        target = extract_source_case(args.input_file, output_file=args.output)
        print(target)
        return 0

    if args.command == "write-default-settings":
        from ews_fem_pipeline_comsol.config import default_settings, write_settings

        write_settings(args.filepath, default_settings())
        return 0

    if args.command == "license-check":
        from ews_fem_pipeline_comsol.pipeline import check_license

        ok = check_license(args.settings_file)
        return 0 if ok else 1

    parser.error(f"Unknown command: {args.command}")
    return 2
