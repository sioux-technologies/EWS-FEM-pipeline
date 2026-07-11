"""Dataclass settings for COMSOL pipeline TOML files.

The top-level TOML is split into ``[pipeline]``, ``[source]``, and ``[comsol]``.
User TOMLs are deep-merged with defaults so stage cases only need to specify the
settings that differ from the baseline.
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ComsolSettings:
    """COMSOL build, geometry, dynamics, support, and postprocess options."""

    enabled: bool = True
    batch_executable: str | None = None
    comsol_executable: str | None = None
    configuration_dir: str | None = None
    mph_file: str | None = None
    study: str = "std1"
    execute: bool = True
    auto_build_from_java: bool = True
    reuse_mph_apply_toml_parameters: bool = False
    java_compile_first: bool = False
    jdk_root: str | None = None
    extra_args: list[str] = field(default_factory=list)
    java_compile_timeout_s: int | None = 300
    java_build_timeout_s: int | None = 1800
    solve_timeout_s: int | None = 7200
    postprocess_timeout_s: int | None = 600
    enable_auxiliary_verification: bool = False
    enable_skin_shell_physics: bool = False
    enable_skin_solid_coupling_scaffold: bool = False
    skin_shell_thickness_m: float = 0.0001
    enable_volumetric_skin_layer: bool = False
    volumetric_skin_thickness_m: float = 0.0015
    enable_curved_chestwall: bool = False
    support_geometry_mode: str = "auto"
    chestwall_curve_depth_m: float = 0.0007
    chestwall_curve_max_depth_ratio: float = 0.2
    chestwall_curve_center_x_offset_m: float = 0.0
    chestwall_curve_max_offset_ratio: float = 0.75
    chestwall_curve_si_depth_m: float = 0.0
    chestwall_alignment_mode: str = "manual"
    chestwall_si_alignment_mode: str = "global_x"
    chestwall_support_mode: str = "cylinder_band"
    chestwall_curve_nipple_follow_factor: float = 0.0
    chestwall_curve_gland_follow_factor: float = 0.0
    transverse_volume_preserve_y_scale: float = 1.0
    transverse_volume_preserve_gland_y_scale: float = 1.0
    outer_shape_scale_x: float = 1.0
    outer_shape_scale_y: float = 1.0
    outer_shape_scale_z: float = 1.0
    outer_inferior_fullness_enabled: bool = False
    outer_inferior_fullness_ratio: float = 0.0
    outer_lateral_fullness_enabled: bool = False
    outer_lateral_fullness_ratio: float = 0.0
    outer_lateral_fullness_side: float = 1.0
    nipple_surface_offset_factor: float = 0.18
    gland_nipple_surface_offset_factor: float = 0.16
    nipple_surface_anchor_y_m: float = -1.0
    nipple_surface_protrusion_m: float = -1.0
    nipple_surface_overlap_m: float = -1.0
    nipple_surface_center_overlap_m: float = -1.0
    nipple_surface_center_overlap_fraction: float = -1.0
    nipple_geometry_x_offset_m: float = 0.0
    nipple_geometry_z_offset_m: float = 0.0
    nipple_surface_normal_alignment_enabled: bool = False
    gland_nipple_surface_depth_factor: float = -1.0
    gland_nipple_surface_clearance_fraction: float = -99.0
    gland_subareolar_surface_clearance_m: float = -1.0
    glandular_seed_surface_clearance_fraction: float = -99.0
    debug_show_subareolar_helpers: bool = False
    glandular_shape_scale_x: float = 1.0
    glandular_shape_scale_y: float = 1.0
    glandular_shape_scale_z: float = 1.0
    glandular_seed_center_x_offset_m: float = 0.0
    glandular_seed_center_y_offset_m: float = 0.0
    glandular_seed_center_z_offset_m: float = 0.0
    glandular_lobule_include_subareolar_core: bool = False
    glandular_lobule_include_subareolar_bridge: bool = False
    glandular_lobule_include_reference_ellipsoid: bool = False
    glandular_subareolar_core_scale: float = 1.0
    glandular_subareolar_bridge_scale: float = 1.0
    compact_output: bool = False
    chest_density_kg_m3: float = 1050.0
    chest_youngs_modulus_pa: float = 10000.0
    chest_poissons_ratio: float = 0.49
    enable_split_support_regions: bool = False
    upper_support_fraction: float = 2.0 / 3.0
    pectoralis_density_kg_m3: float = 1050.0
    pectoralis_bulk_modulus_pa: float = 425000.0
    pectoralis_coef1_pa: float = 950.0
    pectoralis_coef2_pa: float = 717.0
    enable_cooper_ligament_scaffold: bool = False
    cooper_ligament_variant: str = "none"
    cooper_ligament_effective_modulus_pa: float = 5.8e6
    cooper_ligament_reference_length_m: float = 0.07
    cooper_ligament_area_fraction: float = 0.15
    cooper_ligament_tangential_scale: float = 0.35
    cooper_ligament_damping_pa_s_per_m: float = 0.0
    enable_default_result_plots: bool = True
    postprocess_export_plot_images: bool = True
    postprocess_save_postprocessed_mph: bool = False
    postprocess_mode: str = "full"
    postprocess_quick_mode: bool = False
    postprocess_write_auxiliary_mph: bool = False
    dynamic_motion_mode: str = "prescribed_support_displacement"
    dynamic_motion_profile: str = "cosine_down_pulse"
    dynamic_motion_hold_s: float = 0.25
    dynamic_acceleration_amplitude_g: float = 0.75
    dynamic_acceleration_duration_s: float = 0.45
    dynamic_support_displacement_amplitude_m: float = 0.0
    dynamic_support_displacement_duration_s: float = 0.0
    dynamic_mass_damping_alpha_s_inv: float = 20.0
    dynamic_output_step_s: float = 0.0
    dynamic_pulse_output_step_s: float = 0.002
    gravity_ramp_duration_s: float = 0.0
    dynamic_settle_duration_s: float = 0.0


@dataclass
class PipelineSettings:
    """Small pipeline-level settings independent of COMSOL physics."""

    model_name: str = "breast_model_comsol"
    output_subdir: str = "output"


@dataclass
class SourceSettings:
    """Controls how a COMSOL TOML obtains source-case anatomy/material data."""

    base_case_toml: str = ""
    reuse_source_prepare: bool = True
    export_mesh_npz: bool = True
    export_mesh_csv: bool = True
    export_lobules_json: bool = True
    notes: str = ""


@dataclass
class Settings:
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)
    comsol: ComsolSettings = field(default_factory=ComsolSettings)
    source: SourceSettings = field(default_factory=SourceSettings)


def default_settings() -> Settings:
    return Settings()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _to_dict(settings: Settings) -> dict[str, Any]:
    return asdict(settings)


def _from_dict(data: dict[str, Any]) -> Settings:
    pipeline = PipelineSettings(**data.get("pipeline", {}))
    comsol = ComsolSettings(**data.get("comsol", {}))
    source = SourceSettings(**data.get("source", {}))
    return Settings(pipeline=pipeline, comsol=comsol, source=source)


def load_settings_from_toml(filepath: Path) -> Settings:
    """Load a COMSOL case TOML and merge it with default settings."""
    assert filepath.suffix == ".toml", "Input file must have .toml extension."
    with open(filepath, "rb") as handle:
        user_data = tomllib.load(handle)

    source_data = user_data.get("source")
    if isinstance(source_data, dict):
        legacy_prepare = source_data.pop("reuse_febio_prepare", None)
        if legacy_prepare is not None and "reuse_source_prepare" not in source_data:
            source_data["reuse_source_prepare"] = legacy_prepare

    merged = _deep_merge(_to_dict(default_settings()), user_data)
    return _from_dict(merged)


def _format_toml_value(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        return "[ " + ", ".join(_format_toml_value(item) for item in value) + " ]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _is_list_of_tables(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def _write_dict(lines: list[str], prefix: str, data: dict[str, Any]) -> None:
    scalars: list[tuple[str, Any]] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    array_tables: list[tuple[str, list[dict[str, Any]]]] = []
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            tables.append((key, value))
        elif _is_list_of_tables(value):
            array_tables.append((key, value))
        else:
            scalars.append((key, value))

    if prefix:
        lines.append(f"[{prefix}]")
    for key, value in scalars:
        lines.append(f"{key} = {_format_toml_value(value)}")
    if scalars and (tables or array_tables):
        lines.append("")

    for index, (key, table_data) in enumerate(tables):
        nested_prefix = f"{prefix}.{key}" if prefix else key
        _write_dict(lines, nested_prefix, table_data)
        if index != len(tables) - 1 or array_tables:
            lines.append("")

    for table_index, (key, items) in enumerate(array_tables):
        nested_prefix = f"{prefix}.{key}" if prefix else key
        for item_index, item in enumerate(items):
            lines.append(f"[[{nested_prefix}]]")
            item_lines: list[str] = []
            _write_dict(item_lines, "", item)
            lines.extend(item_lines)
            if item_index != len(items) - 1:
                lines.append("")
        if table_index != len(array_tables) - 1:
            lines.append("")


def write_settings_to_toml(filepath: Path, settings: Settings) -> None:
    assert filepath.suffix == ".toml", "Output file must have .toml extension."
    filepath.parent.mkdir(parents=True, exist_ok=True)
    payload = _to_dict(settings)
    lines: list[str] = []
    _write_dict(lines, "", payload)
    filepath.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_dict_to_toml(filepath: Path, payload: dict[str, Any]) -> None:
    assert filepath.suffix == ".toml", "Output file must have .toml extension."
    filepath.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    _write_dict(lines, "", payload)
    filepath.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
