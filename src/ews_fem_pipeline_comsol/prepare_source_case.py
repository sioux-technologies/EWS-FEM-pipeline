"""Prepare COMSOL build inputs from source-case anatomy/material settings.

This module resolves the source case behind a COMSOL TOML, exports lightweight
mesh/lobule/build-plan artefacts, and writes the JSON/TOML files consumed by
``script_builder``. It does not run COMSOL.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import numpy as np

from ews_fem_pipeline_comsol.source_case import (
    generate_mesh,
    load_settings_from_toml as load_source_case_from_toml,
    write_settings_to_toml as write_source_case_to_toml,
)
from ews_fem_pipeline_comsol.settings import Settings, write_dict_to_toml


def _resolve_base_case_toml(comsol_case_toml: Path, settings: Settings) -> Path:
    if not settings.source.base_case_toml:
        raise ValueError(
            "Missing [source].base_case_toml in COMSOL case settings. "
            "Point it to a source-case TOML or embed [source_case] in the COMSOL case TOML."
        )
    base_case = Path(settings.source.base_case_toml)
    if not base_case.is_absolute():
        candidate_from_case = (comsol_case_toml.parent / base_case).resolve()
        if candidate_from_case.exists():
            base_case = candidate_from_case
        else:
            base_case = base_case.resolve()
    return base_case


def _extract_inline_source_case(comsol_case_toml: Path) -> dict | None:
    with open(comsol_case_toml, "rb") as handle:
        raw = tomllib.load(handle)
    source_case = raw.get("source_case")
    return source_case if isinstance(source_case, dict) and source_case else None


def resolve_source_case_toml(
    *,
    case_name: str,
    comsol_case_toml: Path,
    output_dir: Path,
    settings: Settings,
) -> tuple[Path, str]:
    """Return the source-case TOML path, creating an inline snapshot if needed."""
    inline_source_case = _extract_inline_source_case(comsol_case_toml)
    if inline_source_case:
        inline_path = output_dir / f"{case_name}_inline_source_case.toml"
        write_dict_to_toml(inline_path, inline_source_case)
        return inline_path, "inline_source_case"
    return _resolve_base_case_toml(comsol_case_toml, settings), "base_case_toml"


def _to_np_array(value):
    if value is None:
        return np.array([])
    return np.asarray(value)


def _export_mesh_csv(case_name: str, output_dir: Path, mesh) -> Path:
    csv_path = output_dir / f"{case_name}_mesh_nodes.csv"
    coords = np.asarray(mesh.nodes.coords)
    tags = np.asarray(mesh.nodes.tags).reshape(-1)

    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        handle.write("node_id,x,y,z\n")
        for node_id, coord in zip(tags, coords):
            handle.write(f"{int(node_id)},{coord[0]},{coord[1]},{coord[2]}\n")
    return csv_path


def _export_mesh_npz(case_name: str, output_dir: Path, mesh) -> tuple[Path, Path]:
    npz_path = output_dir / f"{case_name}_mesh_data.npz"
    summary_path = output_dir / f"{case_name}_mesh_summary.json"

    payload = {
        "node_tags": _to_np_array(mesh.nodes.tags),
        "node_coords": _to_np_array(mesh.nodes.coords),
    }
    summary = {
        "node_count": int(len(payload["node_tags"])),
        "parts": {},
    }

    tissues = mesh.tissue_parts
    for part_name in tissues.model_fields:
        part = getattr(tissues, part_name)
        part_elements = _to_np_array(part.elements)
        part_nodes = _to_np_array(part.nodes)
        payload[f"{part_name}_elements"] = part_elements
        payload[f"{part_name}_nodes"] = part_nodes
        payload[f"{part_name}_tags"] = _to_np_array(part.tags)
        summary["parts"][part_name] = {
            "dimension": int(part.dim) if part.dim is not None else None,
            "element_count": int(len(part_elements.reshape(-1))) if part_elements.size else 0,
            "node_ref_count": int(len(part_nodes.reshape(-1))) if part_nodes.size else 0,
        }

    np.savez_compressed(npz_path, **payload)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return npz_path, summary_path


def _export_lobules(case_name: str, output_dir: Path, source_case_settings) -> Path:
    lobule_path = output_dir / f"{case_name}_lobules.json"
    hetero = source_case_settings.material.glandular.hetero
    lobules = hetero.build_lobules()
    payload = {
        "nipple": list(hetero.nipple),
        "generator_mode": getattr(hetero, "generator_mode", "fan"),
        "lobule_count": len(lobules),
        "lobules": [lob.model_dump() for lob in lobules],
    }
    lobule_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return lobule_path


def prepare_source_case(
    *,
    case_name: str,
    comsol_case_toml: Path,
    output_dir: Path,
    settings: Settings,
) -> dict[str, str]:
    """Generate COMSOL-ready input artefacts from the source-case settings."""
    if not settings.source.reuse_source_prepare:
        return {}

    base_case_toml, source_case_mode = resolve_source_case_toml(
        case_name=case_name,
        comsol_case_toml=comsol_case_toml,
        output_dir=output_dir,
        settings=settings,
    )
    source_case_settings = load_source_case_from_toml(base_case_toml)

    artefacts: dict[str, str] = {}

    expanded_settings = output_dir / f"{case_name}_source_settings_expanded.toml"
    write_source_case_to_toml(expanded_settings, source_case_settings)
    artefacts["source_settings_expanded_toml"] = str(expanded_settings.resolve())

    prepare_status = {
        "mesh_export": "not_requested",
        "message": "",
        "builder_scope": (
            "Current COMSOL builder creates analytical breast geometry, selections, "
            "material scaffolds, dynamics, and postprocess Java from source-case settings. "
            "Some advanced anatomical features remain sensitivity/scaffold routes."
        ),
        "recommended_next_steps": [
            "Run build-only first and inspect geometry, selections, and tumor preview placement.",
            "Use solved result MPH files only after geometry has been visually checked.",
            "Start postprocess with global mode before heavier surface or tumor exports.",
            "Treat Cooper ligaments, asymmetry, and tumor routes as sensitivity models unless fully validated.",
        ],
        "source_case_mode": source_case_mode,
        "source_case_toml": str(base_case_toml.resolve()),
    }
    if settings.source.export_mesh_csv or settings.source.export_mesh_npz:
        try:
            mesh = generate_mesh(settings=source_case_settings)
            prepare_status["mesh_export"] = "ok"
            if settings.source.export_mesh_csv:
                mesh_csv = _export_mesh_csv(case_name, output_dir, mesh)
                artefacts["mesh_nodes_csv"] = str(mesh_csv.resolve())

            if settings.source.export_mesh_npz:
                mesh_npz, mesh_summary = _export_mesh_npz(case_name, output_dir, mesh)
                artefacts["mesh_data_npz"] = str(mesh_npz.resolve())
                artefacts["mesh_summary_json"] = str(mesh_summary.resolve())
        except ModuleNotFoundError as exc:
            prepare_status["mesh_export"] = "skipped"
            prepare_status["message"] = (
                "Mesh export skipped because required module is missing: "
                f"{exc.name}. Install gmsh in the active environment."
            )

    if settings.source.export_lobules_json:
        lobules_json = _export_lobules(case_name, output_dir, source_case_settings)
        artefacts["lobules_json"] = str(lobules_json.resolve())

    build_plan = {
        "case_name": case_name,
        "geometry": source_case_settings.model.geometry.model_dump(),
        "mesh": source_case_settings.model.mesh.model_dump(),
        "simulation": source_case_settings.simulation.model_dump(),
        "material": {
            "skin": source_case_settings.material.skin.model_dump(),
            "adipose": source_case_settings.material.adipose.model_dump(),
            "glandular": source_case_settings.material.glandular.model_dump(),
            "tumor": source_case_settings.material.tumor.model_dump(),
        },
        "lobules": [lob.model_dump() for lob in source_case_settings.material.glandular.hetero.build_lobules()],
    }
    build_plan_file = output_dir / f"{case_name}_comsol_build_plan.json"
    build_plan_file.write_text(json.dumps(build_plan, indent=2), encoding="utf-8")
    artefacts["comsol_build_plan_json"] = str(build_plan_file.resolve())

    artefacts["source_case_toml"] = str(base_case_toml.resolve())
    status_file = output_dir / f"{case_name}_prepare_status.json"
    status_file.write_text(json.dumps(prepare_status, indent=2), encoding="utf-8")
    artefacts["prepare_status_json"] = str(status_file.resolve())
    return artefacts
