"""Centralized output-folder resolution for COMSOL cases."""

from __future__ import annotations

from pathlib import Path

from ews_fem_pipeline_comsol.settings import Settings


def get_output_root(case_dir: Path, settings: Settings) -> Path:
    return (case_dir / settings.pipeline.output_subdir).resolve()


def get_prepare_dir(case_dir: Path, settings: Settings) -> Path:
    return get_output_root(case_dir, settings) / "prepare"


def get_build_dir(case_dir: Path, settings: Settings) -> Path:
    return get_output_root(case_dir, settings) / "build"


def get_solve_dir(case_dir: Path, settings: Settings) -> Path:
    return get_output_root(case_dir, settings) / "solve"


def get_logs_dir(case_dir: Path, settings: Settings) -> Path:
    return get_output_root(case_dir, settings) / "logs"


def ensure_output_tree(case_dir: Path, settings: Settings) -> dict[str, Path]:
    paths = {
        "root": get_output_root(case_dir, settings),
        "prepare": get_prepare_dir(case_dir, settings),
        "build": get_build_dir(case_dir, settings),
        "solve": get_solve_dir(case_dir, settings),
        "logs": get_logs_dir(case_dir, settings),
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
