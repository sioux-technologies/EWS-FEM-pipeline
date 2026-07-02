"""High-level orchestration for the COMSOL case pipeline.

This module connects the CLI verbs to the three main phases:
1. generate Python/JSON/Java artefacts from TOML case files;
2. build and optionally solve the COMSOL model through COMSOL batch;
3. rerun post-processing or metric comparison on existing solved cases.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from ews_fem_pipeline_comsol.paths import ensure_output_tree
from ews_fem_pipeline_comsol.prepare_source_case import prepare_source_case, resolve_source_case_toml
from ews_fem_pipeline_comsol.script_builder import generate_comsol_java_builder
from ews_fem_pipeline_comsol.source_case import load_settings_from_toml as load_source_case_from_toml
from ews_fem_pipeline_comsol.settings import (
    Settings,
    load_settings_from_toml,
    write_dict_to_toml,
    write_settings_to_toml,
)


def _load_raw_toml(filepath: Path) -> dict:
    with open(filepath, "rb") as handle:
        return tomllib.load(handle)


def _export_resolved_case_snapshot(
    *,
    case_file: Path,
    output_root: Path,
    settings: Settings,
) -> tuple[Path, Path]:
    """Write provenance TOMLs that capture the fully resolved COMSOL/source case."""
    source_case_path, source_case_mode = resolve_source_case_toml(
        case_name=case_file.stem,
        comsol_case_toml=case_file,
        output_dir=output_root / "prepare",
        settings=settings,
    )
    expanded_source_case = load_source_case_from_toml(source_case_path).model_dump()
    payload = {
        "case_overview": {
            "case_name": case_file.stem,
            "comsol_case_file": str(case_file.resolve()),
            "source_case_mode": source_case_mode,
            "source_case_file": str(source_case_path.resolve()),
            "output_root": str(output_root.resolve()),
        },
        "pipeline": settings.pipeline.__dict__,
        "comsol": settings.comsol.__dict__,
        "source": settings.source.__dict__,
        "source_case": expanded_source_case,
    }
    snapshot_path = output_root / f"{case_file.stem}_resolved_case.toml"
    write_dict_to_toml(snapshot_path, payload)
    single_file_payload = {
        "pipeline": settings.pipeline.__dict__,
        "comsol": settings.comsol.__dict__,
        "source": {
            **settings.source.__dict__,
            "base_case_toml": "",
            "notes": (
                f"{settings.source.notes} "
                "This generated single-file case embeds the resolved source_case below and does not require a separate base_case_toml."
            ).strip(),
        },
        "source_case": expanded_source_case,
    }
    single_file_path = output_root / f"{case_file.stem}_single_file_case.toml"
    write_dict_to_toml(single_file_path, single_file_payload)
    return snapshot_path, single_file_path


def generate_cases(input_files: tuple[Path, ...], *, postprocess_mode_override: str | None = None) -> tuple[Path, ...]:
    """Generate COMSOL input JSON and Java/build artefacts for TOML cases."""
    generated: list[Path] = []
    total = len(input_files)
    for index, filepath in enumerate(input_files, start=1):
        print(f"[COMSOL pipeline] ({index}/{total}) generate: {filepath.name}", flush=True)
        settings = load_settings_from_toml(filepath)
        if postprocess_mode_override is not None:
            settings.comsol.postprocess_mode = postprocess_mode_override
        output_paths = ensure_output_tree(filepath.parent, settings)
        output_root = output_paths["root"]
        prepare_dir = output_paths["prepare"]
        build_dir = output_paths["build"]

        write_settings_to_toml(output_root / f"{filepath.stem}_all_settings.toml", settings)
        resolved_case_toml, single_file_case_toml = _export_resolved_case_snapshot(
            case_file=filepath,
            output_root=output_root,
            settings=settings,
        )
        prepare_artefacts = prepare_source_case(
            case_name=filepath.stem,
            comsol_case_toml=filepath,
            output_dir=prepare_dir,
            settings=settings,
        )
        script_artefacts = generate_comsol_java_builder(
            case_name=filepath.stem,
            output_dir=build_dir,
            prepare_artefacts=prepare_artefacts,
            comsol_settings=settings.comsol,
        )
        prepare_artefacts.update(script_artefacts)

        payload = {
            "case_name": filepath.stem,
            "case_dir": str(filepath.parent.resolve()),
            "settings_file": str(filepath.resolve()),
            "model_name": settings.pipeline.model_name,
            "prepare_artefacts": prepare_artefacts,
            "resolved_case_toml": str(resolved_case_toml.resolve()),
            "single_file_case_toml": str(single_file_case_toml.resolve()),
            "output_layout": {name: str(path.resolve()) for name, path in output_paths.items()},
        }
        json_file = build_dir / f"{filepath.stem}_comsol_input.json"
        json_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        manifest_file = output_root / f"{filepath.stem}_output_manifest.json"
        manifest_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[COMSOL pipeline] ({index}/{total}) generated input: {json_file.name}", flush=True)
        generated.append(json_file)

    return tuple(generated)


def solve_cases(input_files: tuple[Path, ...], settings_map: dict[Path, Settings] | None = None) -> tuple[Path, ...]:
    """Run COMSOL build/solve for already generated JSON case inputs."""
    from ews_fem_pipeline_comsol.run_simulation import COMSOLRunner

    for filepath in input_files:
        assert filepath.suffix == ".json", "Input file must be a generated COMSOL JSON input."

    if settings_map is None:
        settings_map = {}
        for filepath in input_files:
            payload = json.loads(filepath.read_text(encoding="utf-8"))
            source_toml = Path(payload["settings_file"])
            settings_map[filepath] = load_settings_from_toml(source_toml)

    return COMSOLRunner().run(input_files, settings_map=settings_map)


def build_cases(input_files: tuple[Path, ...], settings_map: dict[Path, Settings] | None = None) -> tuple[Path, ...]:
    """Build generated COMSOL models without starting the transient solve."""
    from ews_fem_pipeline_comsol.run_simulation import COMSOLRunner

    for filepath in input_files:
        assert filepath.suffix == ".json", "Input file must be a generated COMSOL JSON input."

    if settings_map is None:
        settings_map = {}
        for filepath in input_files:
            payload = json.loads(filepath.read_text(encoding="utf-8"))
            source_toml = Path(payload["settings_file"])
            settings_map[filepath] = load_settings_from_toml(source_toml)

    return COMSOLRunner().run(input_files, settings_map=settings_map, build_only=True)


def postprocess_cases(input_files: tuple[Path, ...], settings_map: dict[Path, Settings] | None = None) -> tuple[Path, ...]:
    """Rerun generated COMSOL post-processing Java on existing result MPH files."""
    from ews_fem_pipeline_comsol.run_simulation import COMSOLRunner

    for filepath in input_files:
        assert filepath.suffix == ".json", "Input file must be a generated COMSOL JSON input."

    if settings_map is None:
        settings_map = {}
        for filepath in input_files:
            payload = json.loads(filepath.read_text(encoding="utf-8"))
            source_toml = Path(payload["settings_file"])
            settings_map[filepath] = load_settings_from_toml(source_toml)

    return COMSOLRunner().postprocess(input_files, settings_map=settings_map)


def run_full_pipeline(input_files: tuple[Path, ...]) -> tuple[Path, ...]:
    generated = generate_cases(input_files)
    settings_map: dict[Path, Settings] = {}
    for source_toml, generated_json in zip(input_files, generated):
        settings_map[generated_json] = load_settings_from_toml(source_toml)
    return solve_cases(generated, settings_map=settings_map)


def build_only_pipeline(input_files: tuple[Path, ...]) -> tuple[Path, ...]:
    generated = generate_cases(input_files)
    settings_map: dict[Path, Settings] = {}
    for source_toml, generated_json in zip(input_files, generated):
        settings_map[generated_json] = load_settings_from_toml(source_toml)
    return build_cases(generated, settings_map=settings_map)


def postprocess_only_pipeline(input_files: tuple[Path, ...], *, postprocess_mode: str | None = None) -> tuple[Path, ...]:
    generated = generate_cases(input_files, postprocess_mode_override=postprocess_mode)
    settings_map: dict[Path, Settings] = {}
    for source_toml, generated_json in zip(input_files, generated):
        settings = load_settings_from_toml(source_toml)
        if postprocess_mode is not None:
            settings.comsol.postprocess_mode = postprocess_mode
        settings_map[generated_json] = settings
    return postprocess_cases(generated, settings_map=settings_map)


def sweep_cases(input_files: tuple[Path, ...]) -> tuple[Path, ...]:
    return run_full_pipeline(input_files)


def compare_metrics_cases(input_files: tuple[Path, ...], baseline: str | None = None) -> Path:
    from ews_fem_pipeline_comsol.metrics_compare import compare_metrics

    return compare_metrics(input_files, baseline=baseline)


def extract_source_case(input_file: Path, output_file: Path | None = None) -> Path:
    settings = load_settings_from_toml(input_file)
    output_root = ensure_output_tree(input_file.parent, settings)["root"]
    source_case_path, _source_case_mode = resolve_source_case_toml(
        case_name=input_file.stem,
        comsol_case_toml=input_file,
        output_dir=output_root / "prepare",
        settings=settings,
    )
    expanded_source_case = load_source_case_from_toml(source_case_path).model_dump()
    target = output_file or (input_file.parent / f"{input_file.stem}_source_case.toml")
    write_dict_to_toml(target, expanded_source_case)
    return target


def check_license(settings_file: Path) -> bool:
    from ews_fem_pipeline_comsol.run_simulation import COMSOLRunner

    settings = load_settings_from_toml(settings_file)
    ok, message = COMSOLRunner().check_license(settings=settings, workdir=settings_file.parent.resolve())
    print(message)
    return ok
