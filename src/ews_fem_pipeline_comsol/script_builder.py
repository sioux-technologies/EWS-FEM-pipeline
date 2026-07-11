"""Generate COMSOL Java API source files from prepared case artefacts.

This is the main translation layer from Python/TOML settings to COMSOL Java. It
emits the model builder, postprocess class, verification helpers, and selection
hints. The generated Java owns the COMSOL-side geometry, selections, material
variables, dynamic loading, Cooper/tumor scaffolds, plots, and metrics export.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
import numpy as np

from ews_fem_pipeline_comsol.java_utils import (
    chunk_list as _chunk_list,
    comsol_safe_name as _comsol_safe_name,
    safe_java_identifier as _safe_java_identifier,
)
from ews_fem_pipeline_comsol.material_mapping import linearize_mooney_rivlin as _linearize_mooney_rivlin
from ews_fem_pipeline_comsol.settings import ComsolSettings


def generate_comsol_java_builder(
    *,
    case_name: str,
    output_dir: Path,
    prepare_artefacts: dict[str, str],
    comsol_settings: ComsolSettings | None = None,
) -> dict[str, str]:
    """Generate builder/postprocess/verification Java and selection hints."""
    output_dir.mkdir(parents=True, exist_ok=True)
    class_name = _safe_java_identifier(f"{case_name}_comsol_builder")

    build_plan_path = prepare_artefacts.get("comsol_build_plan_json", "")
    build_plan_summary = {
        "lobule_count": 0,
        "geometry": {},
        "mesh": {},
        "simulation": {},
        "material": {},
        "lobules": [],
    }
    if build_plan_path and Path(build_plan_path).exists():
        plan = json.loads(Path(build_plan_path).read_text(encoding="utf-8"))
        build_plan_summary["lobule_count"] = len(plan.get("lobules", []))
        build_plan_summary["geometry"] = plan.get("geometry", {})
        build_plan_summary["mesh"] = plan.get("mesh", {})
        build_plan_summary["simulation"] = plan.get("simulation", {})
        build_plan_summary["material"] = plan.get("material", {})
        build_plan_summary["lobules"] = plan.get("lobules", [])

    skin_material = build_plan_summary["material"].get("skin", {})
    adipose_material = build_plan_summary["material"].get("adipose", {})
    glandular_material = build_plan_summary["material"].get("glandular", {})
    tumor_material = build_plan_summary["material"].get("tumor", {}) or {}
    shell_physics_enabled = bool(comsol_settings.enable_skin_shell_physics) if comsol_settings else False
    shell_coupling_enabled = bool(comsol_settings.enable_skin_solid_coupling_scaffold) if comsol_settings else False
    skin_shell_thickness_m = float(comsol_settings.skin_shell_thickness_m) if comsol_settings else 0.0001
    volumetric_skin_enabled = (
        bool(getattr(comsol_settings, "enable_volumetric_skin_layer", False))
        if comsol_settings
        else False
    )
    volumetric_skin_thickness_m = (
        float(getattr(comsol_settings, "volumetric_skin_thickness_m", 0.0015))
        if comsol_settings
        else 0.0015
    )
    postprocess_export_plot_images = (
        bool(getattr(comsol_settings, "postprocess_export_plot_images", True))
        if comsol_settings
        else True
    )
    postprocess_save_postprocessed_mph = (
        bool(getattr(comsol_settings, "postprocess_save_postprocessed_mph", False))
        if comsol_settings
        else False
    )
    postprocess_quick_mode = (
        bool(getattr(comsol_settings, "postprocess_quick_mode", False))
        if comsol_settings
        else False
    )
    postprocess_mode = (
        str(getattr(comsol_settings, "postprocess_mode", "full") or "full").strip().lower().replace("-", "_")
        if comsol_settings
        else "full"
    )
    if postprocess_quick_mode and postprocess_mode == "full":
        postprocess_mode = "global"
    if postprocess_mode not in {"full", "global", "ews_surface", "internal_tumor", "none", "skip"}:
        postprocess_mode = "full"
    postprocess_export_plot_images_java = "true" if postprocess_export_plot_images else "false"
    postprocess_save_postprocessed_mph_java = "true" if postprocess_save_postprocessed_mph else "false"
    postprocess_quick_mode_java = "true" if postprocess_quick_mode and postprocess_mode == "global" else "false"
    postprocess_mode_java = postprocess_mode
    dynamic_motion_profile = (
        str(getattr(comsol_settings, "dynamic_motion_profile", "cosine_down_pulse") or "cosine_down_pulse")
        .strip()
        .lower()
    )
    dynamic_motion_mode = (
        str(getattr(comsol_settings, "dynamic_motion_mode", "prescribed_support_displacement") or "prescribed_support_displacement")
        .strip()
        .lower()
    )
    if dynamic_motion_mode not in {
        "prescribed_support_displacement",
        "gravity_only",
        "fixed_support_acceleration_pulse",
        "smooth_support_displacement",
    }:
        dynamic_motion_mode = "prescribed_support_displacement"
    if dynamic_motion_profile not in {
        "cosine_down_pulse",
        "febio_parabolic_support",
        "parabolic_support",
        "smooth_cosine_bump",
        "smooth_c2_bump",
        "none",
    }:
        dynamic_motion_profile = "cosine_down_pulse"
    dynamic_motion_hold_s = (
        float(getattr(comsol_settings, "dynamic_motion_hold_s", 0.25))
        if comsol_settings
        else 0.25
    )
    dynamic_motion_hold_s = min(max(dynamic_motion_hold_s, 0.0), 5.0)
    dynamic_acceleration_amplitude_g = (
        float(getattr(comsol_settings, "dynamic_acceleration_amplitude_g", 0.75))
        if comsol_settings
        else 0.75
    )
    dynamic_acceleration_amplitude_g = min(max(dynamic_acceleration_amplitude_g, 0.0), 5.0)
    dynamic_acceleration_duration_s = (
        float(getattr(comsol_settings, "dynamic_acceleration_duration_s", 0.45))
        if comsol_settings
        else 0.45
    )
    dynamic_acceleration_duration_s = min(max(dynamic_acceleration_duration_s, 0.01), 5.0)
    support_geometry_mode = str(getattr(comsol_settings, "support_geometry_mode", "auto") or "auto").lower() if comsol_settings else "auto"
    if support_geometry_mode not in {
        "auto",
        "slab",
        "curved",
        "transverse",
        "transverse_circle",
        "transverse_vp",
        "transverse_volume_preserving",
        "transverse_near_volume_preserving",
    }:
        support_geometry_mode = "auto"
    curved_chestwall_enabled = (
        bool(comsol_settings.enable_curved_chestwall)
        if support_geometry_mode == "auto"
        else support_geometry_mode == "curved"
    ) if comsol_settings else False
    transverse_volume_preserving_enabled = support_geometry_mode in {
        "transverse_vp",
        "transverse_volume_preserving",
        "transverse_near_volume_preserving",
    }
    transverse_chestwall_enabled = support_geometry_mode in {
        "transverse",
        "transverse_circle",
        "transverse_vp",
        "transverse_volume_preserving",
        "transverse_near_volume_preserving",
    }
    chestwall_curve_depth_m = float(comsol_settings.chestwall_curve_depth_m) if comsol_settings else 0.0007
    chestwall_curve_max_depth_ratio = (
        float(getattr(comsol_settings, "chestwall_curve_max_depth_ratio", 0.2))
        if comsol_settings else 0.2
    )
    chestwall_curve_max_depth_ratio = min(max(chestwall_curve_max_depth_ratio, 0.05), 0.95)
    chestwall_curve_center_x_offset_m = (
        float(getattr(comsol_settings, "chestwall_curve_center_x_offset_m", 0.0))
        if comsol_settings else 0.0
    )
    chestwall_curve_max_offset_ratio = (
        float(getattr(comsol_settings, "chestwall_curve_max_offset_ratio", 0.75))
        if comsol_settings else 0.75
    )
    chestwall_curve_max_offset_ratio = min(max(chestwall_curve_max_offset_ratio, 0.10), 1.25)
    chestwall_curve_si_depth_m = (
        float(getattr(comsol_settings, "chestwall_curve_si_depth_m", 0.0))
        if comsol_settings else 0.0
    )
    chestwall_alignment_mode = (
        str(getattr(comsol_settings, "chestwall_alignment_mode", "manual") or "manual").lower()
        if comsol_settings else "manual"
    )
    if chestwall_alignment_mode not in {"manual", "projected_normal_axis"}:
        chestwall_alignment_mode = "manual"
    chestwall_si_alignment_mode = (
        str(getattr(comsol_settings, "chestwall_si_alignment_mode", "global_x") or "global_x").lower()
        if comsol_settings else "global_x"
    )
    if chestwall_si_alignment_mode not in {"global_x", "transverse_tangent"}:
        chestwall_si_alignment_mode = "global_x"
    chestwall_support_mode = (
        str(getattr(comsol_settings, "chestwall_support_mode", "cylinder_band") or "cylinder_band").lower()
        if comsol_settings else "cylinder_band"
    )
    if chestwall_support_mode not in {"cylinder_band", "conformal_keep_region"}:
        chestwall_support_mode = "cylinder_band"
    chestwall_curve_nipple_follow_factor = (
        float(getattr(comsol_settings, "chestwall_curve_nipple_follow_factor", 0.0))
        if comsol_settings else 0.0
    )
    chestwall_curve_nipple_follow_factor = min(max(chestwall_curve_nipple_follow_factor, -1.0), 1.0)
    chestwall_curve_gland_follow_factor = (
        float(getattr(comsol_settings, "chestwall_curve_gland_follow_factor", 0.0))
        if comsol_settings else 0.0
    )
    chestwall_curve_gland_follow_factor = min(max(chestwall_curve_gland_follow_factor, -1.0), 1.0)
    transverse_volume_preserve_y_scale = (
        float(getattr(comsol_settings, "transverse_volume_preserve_y_scale", 1.0))
        if comsol_settings else 1.0
    )
    transverse_volume_preserve_gland_y_scale = (
        float(getattr(comsol_settings, "transverse_volume_preserve_gland_y_scale", transverse_volume_preserve_y_scale))
        if comsol_settings else 1.0
    )
    outer_shape_scale_x = (
        float(getattr(comsol_settings, "outer_shape_scale_x", 1.0))
        if comsol_settings else 1.0
    )
    outer_shape_scale_y = (
        float(getattr(comsol_settings, "outer_shape_scale_y", 1.0))
        if comsol_settings else 1.0
    )
    outer_shape_scale_z = (
        float(getattr(comsol_settings, "outer_shape_scale_z", 1.0))
        if comsol_settings else 1.0
    )
    outer_inferior_fullness_enabled = (
        bool(getattr(comsol_settings, "outer_inferior_fullness_enabled", False))
        if comsol_settings else False
    )
    outer_inferior_fullness_ratio = (
        float(getattr(comsol_settings, "outer_inferior_fullness_ratio", 0.0))
        if comsol_settings else 0.0
    )
    outer_lateral_fullness_enabled = (
        bool(getattr(comsol_settings, "outer_lateral_fullness_enabled", False))
        if comsol_settings else False
    )
    outer_lateral_fullness_ratio = (
        float(getattr(comsol_settings, "outer_lateral_fullness_ratio", 0.0))
        if comsol_settings else 0.0
    )
    outer_lateral_fullness_side = (
        float(getattr(comsol_settings, "outer_lateral_fullness_side", 1.0))
        if comsol_settings else 1.0
    )
    nipple_surface_offset_factor = (
        float(getattr(comsol_settings, "nipple_surface_offset_factor", 0.18))
        if comsol_settings else 0.18
    )
    gland_nipple_surface_offset_factor = (
        float(getattr(comsol_settings, "gland_nipple_surface_offset_factor", 0.16))
        if comsol_settings else 0.16
    )
    nipple_surface_anchor_y_m = (
        float(getattr(comsol_settings, "nipple_surface_anchor_y_m", -1.0))
        if comsol_settings else -1.0
    )
    nipple_surface_protrusion_m = (
        float(getattr(comsol_settings, "nipple_surface_protrusion_m", -1.0))
        if comsol_settings else -1.0
    )
    nipple_surface_overlap_m = (
        float(getattr(comsol_settings, "nipple_surface_overlap_m", -1.0))
        if comsol_settings else -1.0
    )
    nipple_surface_center_overlap_m = (
        float(getattr(comsol_settings, "nipple_surface_center_overlap_m", -1.0))
        if comsol_settings else -1.0
    )
    nipple_surface_center_overlap_fraction = (
        float(getattr(comsol_settings, "nipple_surface_center_overlap_fraction", -1.0))
        if comsol_settings else -1.0
    )
    nipple_geometry_x_offset_m = (
        float(getattr(comsol_settings, "nipple_geometry_x_offset_m", 0.0))
        if comsol_settings else 0.0
    )
    nipple_geometry_z_offset_m = (
        float(getattr(comsol_settings, "nipple_geometry_z_offset_m", 0.0))
        if comsol_settings else 0.0
    )
    nipple_surface_normal_alignment_enabled = (
        bool(getattr(comsol_settings, "nipple_surface_normal_alignment_enabled", False))
        if comsol_settings else False
    )
    gland_nipple_surface_depth_factor = (
        float(getattr(comsol_settings, "gland_nipple_surface_depth_factor", -1.0))
        if comsol_settings else -1.0
    )
    gland_nipple_surface_clearance_fraction = (
        float(getattr(comsol_settings, "gland_nipple_surface_clearance_fraction", -99.0))
        if comsol_settings else -99.0
    )
    gland_subareolar_surface_clearance_m = (
        float(getattr(comsol_settings, "gland_subareolar_surface_clearance_m", -1.0))
        if comsol_settings else -1.0
    )
    glandular_seed_surface_clearance_fraction = (
        float(getattr(comsol_settings, "glandular_seed_surface_clearance_fraction", -99.0))
        if comsol_settings else -99.0
    )
    debug_show_subareolar_helpers = (
        bool(getattr(comsol_settings, "debug_show_subareolar_helpers", False))
        if comsol_settings else False
    )
    glandular_shape_scale_x = (
        float(getattr(comsol_settings, "glandular_shape_scale_x", 1.0))
        if comsol_settings else 1.0
    )
    glandular_shape_scale_y = (
        float(getattr(comsol_settings, "glandular_shape_scale_y", 1.0))
        if comsol_settings else 1.0
    )
    glandular_shape_scale_z = (
        float(getattr(comsol_settings, "glandular_shape_scale_z", 1.0))
        if comsol_settings else 1.0
    )
    glandular_seed_center_x_offset_m = (
        float(getattr(comsol_settings, "glandular_seed_center_x_offset_m", 0.0))
        if comsol_settings else 0.0
    )
    glandular_seed_center_y_offset_m = (
        float(getattr(comsol_settings, "glandular_seed_center_y_offset_m", 0.0))
        if comsol_settings else 0.0
    )
    glandular_seed_center_z_offset_m = (
        float(getattr(comsol_settings, "glandular_seed_center_z_offset_m", 0.0))
        if comsol_settings else 0.0
    )
    glandular_lobule_include_subareolar_core = (
        bool(getattr(comsol_settings, "glandular_lobule_include_subareolar_core", False))
        if comsol_settings else False
    )
    glandular_lobule_include_subareolar_bridge = (
        bool(getattr(comsol_settings, "glandular_lobule_include_subareolar_bridge", False))
        if comsol_settings else False
    )
    glandular_lobule_include_reference_ellipsoid = (
        bool(getattr(comsol_settings, "glandular_lobule_include_reference_ellipsoid", False))
        if comsol_settings else False
    )
    glandular_subareolar_core_scale = (
        float(getattr(comsol_settings, "glandular_subareolar_core_scale", 1.0))
        if comsol_settings else 1.0
    )
    glandular_subareolar_bridge_scale = (
        float(getattr(comsol_settings, "glandular_subareolar_bridge_scale", 1.0))
        if comsol_settings else 1.0
    )
    if not transverse_volume_preserving_enabled:
        transverse_volume_preserve_y_scale = 1.0
        transverse_volume_preserve_gland_y_scale = 1.0
    transverse_volume_preserve_y_scale = min(max(transverse_volume_preserve_y_scale, 1.0), 1.35)
    transverse_volume_preserve_gland_y_scale = min(max(transverse_volume_preserve_gland_y_scale, 1.0), 1.35)
    outer_shape_scale_x = min(max(outer_shape_scale_x, 0.75), 1.25)
    outer_shape_scale_y = min(max(outer_shape_scale_y, 0.75), 1.25)
    outer_shape_scale_z = min(max(outer_shape_scale_z, 0.75), 1.25)
    outer_inferior_fullness_ratio = min(max(outer_inferior_fullness_ratio, 0.0), 0.65)
    outer_lateral_fullness_ratio = min(max(outer_lateral_fullness_ratio, 0.0), 0.65)
    outer_lateral_fullness_side = 1.0 if outer_lateral_fullness_side >= 0.0 else -1.0
    nipple_surface_offset_factor = min(max(nipple_surface_offset_factor, -2.50), 0.35)
    gland_nipple_surface_offset_factor = min(max(gland_nipple_surface_offset_factor, -2.50), 0.35)
    nipple_surface_anchor_y_m = max(nipple_surface_anchor_y_m, -1.0)
    nipple_surface_protrusion_m = max(nipple_surface_protrusion_m, -1.0)
    nipple_surface_overlap_m = max(nipple_surface_overlap_m, -1.0)
    nipple_surface_center_overlap_m = max(nipple_surface_center_overlap_m, -1.0)
    nipple_surface_center_overlap_fraction = min(max(nipple_surface_center_overlap_fraction, -1.0), 0.95)
    nipple_geometry_x_offset_m = min(max(nipple_geometry_x_offset_m, -0.05), 0.05)
    nipple_geometry_z_offset_m = min(max(nipple_geometry_z_offset_m, -0.05), 0.05)
    gland_nipple_surface_depth_factor = min(max(gland_nipple_surface_depth_factor, -1.0), 1.75)
    gland_nipple_surface_clearance_fraction = min(max(gland_nipple_surface_clearance_fraction, -0.95), 2.0)
    gland_subareolar_surface_clearance_m = max(gland_subareolar_surface_clearance_m, -1.0)
    if glandular_seed_surface_clearance_fraction > -90.0:
        glandular_seed_surface_clearance_fraction = min(max(glandular_seed_surface_clearance_fraction, -0.95), 5.0)
    outer_inferior_fullness_enabled = (
        outer_inferior_fullness_enabled and outer_inferior_fullness_ratio > 0.0
    )
    outer_lateral_fullness_enabled = (
        outer_lateral_fullness_enabled and outer_lateral_fullness_ratio > 0.0
    )
    requested_outer_inferior_fullness_enabled = outer_inferior_fullness_enabled
    requested_outer_lateral_fullness_enabled = outer_lateral_fullness_enabled
    if outer_inferior_fullness_enabled or outer_lateral_fullness_enabled:
        # These additive primitives were visually useful during early Stage 4
        # exploration, but unioning them into the COMSOL breast envelope creates
        # detached ellipsoid lobes rather than a true surface deformation.
        outer_inferior_fullness_enabled = False
        outer_lateral_fullness_enabled = False
    glandular_shape_scale_x = min(max(glandular_shape_scale_x, 0.35), 1.80)
    glandular_shape_scale_y = min(max(glandular_shape_scale_y, 0.35), 1.80)
    glandular_shape_scale_z = min(max(glandular_shape_scale_z, 0.35), 1.80)
    glandular_subareolar_core_scale = min(max(glandular_subareolar_core_scale, 0.5), 2.0)
    glandular_subareolar_bridge_scale = min(max(glandular_subareolar_bridge_scale, 0.5), 2.2)
    subareolar_helper_selresultshow = "all" if debug_show_subareolar_helpers else "off"
    chest_density = float(comsol_settings.chest_density_kg_m3) if comsol_settings else 1050.0
    chest_E = float(comsol_settings.chest_youngs_modulus_pa) if comsol_settings else 10000.0
    chest_nu = float(comsol_settings.chest_poissons_ratio) if comsol_settings else 0.49
    split_support_regions = bool(comsol_settings.enable_split_support_regions) if comsol_settings else False
    upper_support_fraction = float(comsol_settings.upper_support_fraction) if comsol_settings else (2.0 / 3.0)
    upper_support_fraction = min(max(upper_support_fraction, 0.05), 0.95)
    pectoralis_density = float(comsol_settings.pectoralis_density_kg_m3) if comsol_settings else 1050.0
    pectoralis_bulk_modulus = float(comsol_settings.pectoralis_bulk_modulus_pa) if comsol_settings else 425000.0
    pectoralis_coef1 = float(comsol_settings.pectoralis_coef1_pa) if comsol_settings else 950.0
    pectoralis_coef2 = float(comsol_settings.pectoralis_coef2_pa) if comsol_settings else 717.0
    cooper_ligament_enabled = bool(getattr(comsol_settings, "enable_cooper_ligament_scaffold", False)) if comsol_settings else False
    cooper_ligament_variant = str(getattr(comsol_settings, "cooper_ligament_variant", "none") or "none").lower() if comsol_settings else "none"
    cooper_effective_modulus = float(getattr(comsol_settings, "cooper_ligament_effective_modulus_pa", 5.8e6)) if comsol_settings else 5.8e6
    cooper_reference_length = float(getattr(comsol_settings, "cooper_ligament_reference_length_m", 0.07)) if comsol_settings else 0.07
    cooper_area_fraction = float(getattr(comsol_settings, "cooper_ligament_area_fraction", 0.15)) if comsol_settings else 0.15
    cooper_tangential_scale = float(getattr(comsol_settings, "cooper_ligament_tangential_scale", 0.35)) if comsol_settings else 0.35
    cooper_damping = float(getattr(comsol_settings, "cooper_ligament_damping_pa_s_per_m", 0.0)) if comsol_settings else 0.0
    default_result_plots_enabled = bool(getattr(comsol_settings, "enable_default_result_plots", True)) if comsol_settings else True
    cooper_ligament_enabled = cooper_ligament_enabled and cooper_ligament_variant != "none"
    cooper_reference_length = max(cooper_reference_length, 1e-6)
    cooper_area_fraction = min(max(cooper_area_fraction, 0.0), 1.0)
    cooper_tangential_scale = max(cooper_tangential_scale, 0.0)
    cooper_damping = max(cooper_damping, 0.0)
    cooper_velocity_term = " - cooper_damping*vt" if cooper_damping > 0.0 else ""
    coop_nipple_fy_expr = f"-0.20*cooper_spring_ky*v{cooper_velocity_term}"
    coop_skin_fy_expr = f"-cooper_skin_web_ky*v{cooper_velocity_term}"
    coop_gland_fy_expr = f"-cooper_gland_web_ky*v{cooper_velocity_term}"
    skin_bulk_modulus = float(skin_material.get("bulk_modulus", 1.0))
    skin_coef1 = float(skin_material.get("coef1", 0.0))
    skin_coef2 = float(skin_material.get("coef2", 0.0))
    adipose_bulk_modulus = float(adipose_material.get("bulk_modulus", 1.0))
    adipose_coef1 = float(adipose_material.get("coef1", 0.0))
    adipose_coef2 = float(adipose_material.get("coef2", 0.0))
    glandular_bulk_modulus = float(glandular_material.get("bulk_modulus", 1.0))
    glandular_coef1 = float(glandular_material.get("coef1", 0.0))
    glandular_coef2 = float(glandular_material.get("coef2", 0.0))
    tumor_enabled = bool(tumor_material.get("tumorous", False))
    tumor_density = float(tumor_material.get("density", 1079.0))
    tumor_radius = float(tumor_material.get("radius", 0.005))
    tumor_position = tumor_material.get("position", [0.035, 0.040, 0.0])
    if not isinstance(tumor_position, list) or len(tumor_position) != 3:
        tumor_position = [0.035, 0.040, 0.0]
    tumor_x = float(tumor_position[0])
    tumor_y = float(tumor_position[1])
    tumor_z = float(tumor_position[2])
    tumor_coef1_adipose = float(tumor_material.get("coef1_adipose", tumor_material.get("coef1", 971.0)))
    tumor_coef2_adipose = float(tumor_material.get("coef2_adipose", tumor_material.get("coef2", 939.0)))
    tumor_coef1_glandular = float(tumor_material.get("coef1_glandular", tumor_material.get("coef1", 920.0)))
    tumor_coef2_glandular = float(tumor_material.get("coef2_glandular", tumor_material.get("coef2", 870.0)))
    tumor_E_default_adipose = 6.0 * (tumor_coef1_adipose + tumor_coef2_adipose)
    tumor_E_default_glandular = 6.0 * (tumor_coef1_glandular + tumor_coef2_glandular)
    tumor_E_common = tumor_material.get(
        "youngs_modulus_pa",
        tumor_material.get("youngs_modulus", tumor_material.get("E", None)),
    )
    tumor_E_adipose = float(
        tumor_material.get(
            "youngs_modulus_adipose_pa",
            tumor_material.get(
                "youngs_modulus_adipose",
                tumor_E_common if tumor_E_common is not None else tumor_E_default_adipose,
            ),
        )
    )
    tumor_E_glandular = float(
        tumor_material.get(
            "youngs_modulus_glandular_pa",
            tumor_material.get(
                "youngs_modulus_glandular",
                tumor_E_common if tumor_E_common is not None else tumor_E_default_glandular,
            ),
        )
    )
    skin_E, skin_nu = _linearize_mooney_rivlin(skin_material)
    adipose_E, adipose_nu = _linearize_mooney_rivlin(adipose_material)
    glandular_E, glandular_nu = _linearize_mooney_rivlin(glandular_material)
    pectoralis_E, pectoralis_nu = _linearize_mooney_rivlin({
        "bulk_modulus": pectoralis_bulk_modulus,
        "coef1": pectoralis_coef1,
        "coef2": pectoralis_coef2,
    })

    geometry = build_plan_summary["geometry"]
    radius = float(geometry.get("radius", 0.07))
    volumetric_skin_thickness_m = max(
        0.0,
        min(volumetric_skin_thickness_m, 0.25 * radius),
    )
    chest_thickness = float(geometry.get("thickness_chest_wall", 0.002))
    left_rel = float(geometry.get("left_relative_position_ellipse", 0.4))
    nipple_rel = float(geometry.get("right_relative_position_ellipse", 0.05))
    center_rel = float(geometry.get("center_relative_position_ellipse", 0.3))
    asymmetry = geometry.get("asymmetry", {}) or {}
    scale_y = float(asymmetry.get("scale_y", 1.0))
    scale_z = float(asymmetry.get("scale_z", 1.0))
    asym_enabled = bool(asymmetry.get("enabled", False))
    gland_hetero = build_plan_summary["material"].get("glandular", {}).get("hetero", {}) or {}
    droplet_components = max(1, int(gland_hetero.get("droplet_components", 1)))
    comsol_detail_mode = str(gland_hetero.get("comsol_geometry_detail_mode", "full")).lower()
    duct_only_detail_mode = comsol_detail_mode == "duct_only"
    comsol_petal_segments_override = max(0, int(gland_hetero.get("comsol_petal_segments", 0) or 0))
    comsol_duct_beads_override = max(0, int(gland_hetero.get("comsol_duct_beads", 0) or 0))
    comsol_duct_style = str(gland_hetero.get("comsol_duct_style", "beads") or "beads").lower()
    if comsol_duct_style not in {"beads", "ellipsoid_segments"}:
        comsol_duct_style = "beads"
    comsol_duct_segments_override = max(0, int(gland_hetero.get("comsol_duct_segments", 0) or 0))
    comsol_duct_radius_scale = float(gland_hetero.get("comsol_duct_radius_scale", 1.0) or 1.0)
    comsol_duct_radius_scale = min(max(comsol_duct_radius_scale, 0.55), 1.80)

    left_pos = left_rel * radius
    nipple_pos = nipple_rel * radius
    center_pos = center_rel * radius
    outer_semiaxis_x = radius * outer_shape_scale_x
    outer_semiaxis_z = radius * outer_shape_scale_z
    outer_semiaxis_y = radius * transverse_volume_preserve_y_scale * outer_shape_scale_y
    skin_core_semiaxis_x = max(outer_semiaxis_x - volumetric_skin_thickness_m, 1e-6)
    skin_core_semiaxis_z = max(outer_semiaxis_z - volumetric_skin_thickness_m, 1e-6)
    skin_core_semiaxis_y = max(outer_semiaxis_y - volumetric_skin_thickness_m, 1e-6)
    glandular_seed_center_x_offset_m = min(
        max(glandular_seed_center_x_offset_m, -0.60 * outer_semiaxis_x),
        0.60 * outer_semiaxis_x,
    )
    glandular_seed_center_y_offset_m = min(
        max(glandular_seed_center_y_offset_m, -0.70 * outer_semiaxis_y),
        0.70 * outer_semiaxis_y,
    )
    glandular_seed_center_z_offset_m = min(
        max(glandular_seed_center_z_offset_m, -0.60 * outer_semiaxis_z),
        0.60 * outer_semiaxis_z,
    )
    nipple = gland_hetero.get("nipple", [0.0, 0.068, 0.0])
    nipple_x = float(nipple[0]) if isinstance(nipple, list) and len(nipple) >= 1 else 0.0
    nipple_y = float(nipple[1]) if isinstance(nipple, list) and len(nipple) >= 2 else radius
    nipple_z = float(nipple[2]) if isinstance(nipple, list) and len(nipple) >= 3 else 0.0
    # The generated COMSOL ellipsoid uses semiaxes in the same order as the
    # historic model ("x z y") plus axistype="y".  In the currently accepted
    # COMSOL builds, the visible anterior/posterior surface follows the second
    # semiaxis.  Keep the Java order unchanged for backward geometry
    # compatibility, but use this COMSOL-axis mapping for surface-aware nipple
    # placement so x/z profile scaling moves the nipple with the visible breast.
    comsol_outer_axis_x = outer_semiaxis_x
    comsol_outer_axis_y = outer_semiaxis_z
    comsol_outer_axis_z = outer_semiaxis_y
    intended_outer_axis_y = outer_semiaxis_y
    outer_anterior_y = comsol_outer_axis_y
    outer_support_half_x = 1.2 * radius * max(outer_shape_scale_x, 1.0)
    outer_support_half_z = 1.2 * radius * max(outer_shape_scale_z, 1.0)
    chestwall_curve_max_offset_m = chestwall_curve_max_offset_ratio * outer_support_half_x
    chestwall_curve_center_x_offset_m = min(
        max(chestwall_curve_center_x_offset_m, -chestwall_curve_max_offset_m),
        chestwall_curve_max_offset_m,
    )
    chest_curve_max_depth = radius * chestwall_curve_max_depth_ratio
    chest_curve_depth = min(max(chestwall_curve_depth_m, chest_thickness * 0.05), chest_curve_max_depth)
    chest_curve_si_depth = min(max(chestwall_curve_si_depth_m, 0.0), chest_curve_max_depth)
    si_chestwall_enabled = transverse_chestwall_enabled and chest_curve_si_depth > max(chest_thickness * 0.05, 1.0e-6)
    transverse_curve_span_x = outer_semiaxis_x + abs(chestwall_curve_center_x_offset_m)
    chest_curve_radius = ((radius * radius) + (chest_curve_depth * chest_curve_depth)) / max(2.0 * chest_curve_depth, 1e-9)
    chest_curve_center_y = chest_curve_radius - chest_curve_depth
    transverse_curve_radius = ((transverse_curve_span_x * transverse_curve_span_x) + (chest_curve_depth * chest_curve_depth)) / max(2.0 * chest_curve_depth, 1e-9)
    transverse_curve_center_y = transverse_curve_radius - chest_curve_depth
    si_curve_radius = ((radius * radius) + (chest_curve_si_depth * chest_curve_si_depth)) / max(2.0 * chest_curve_si_depth, 1e-9)
    si_curve_center_y = si_curve_radius - chest_curve_si_depth
    alignment_enabled = transverse_chestwall_enabled and chestwall_alignment_mode == "projected_normal_axis"
    alignment_anchor_x = 0.0
    alignment_circle_center_x = chestwall_curve_center_x_offset_m
    alignment_circle_center_y = -transverse_curve_center_y
    alignment_anchor_dx = alignment_anchor_x - alignment_circle_center_x
    alignment_anchor_root = float(
        np.sqrt(max(transverse_curve_radius * transverse_curve_radius - alignment_anchor_dx * alignment_anchor_dx, 0.0))
    )
    alignment_anchor_y = alignment_circle_center_y + alignment_anchor_root
    alignment_axis_dx = alignment_anchor_x - alignment_circle_center_x
    alignment_axis_dy = alignment_anchor_y - alignment_circle_center_y
    alignment_axis_norm = float(np.sqrt(alignment_axis_dx * alignment_axis_dx + alignment_axis_dy * alignment_axis_dy))
    if alignment_axis_norm > 1.0e-12:
        alignment_axis_unit_x = alignment_axis_dx / alignment_axis_norm
        alignment_axis_unit_y = alignment_axis_dy / alignment_axis_norm
    else:
        alignment_axis_unit_x = 0.0
        alignment_axis_unit_y = 1.0
    si_alignment_enabled = (
        si_chestwall_enabled
        and transverse_chestwall_enabled
        and chestwall_si_alignment_mode == "transverse_tangent"
    )
    conformal_chestwall_support_enabled = (
        transverse_chestwall_enabled
        and chestwall_support_mode == "conformal_keep_region"
    )

    def _alignment_x_at_y(y_value: float) -> float:
        if not alignment_enabled or abs(alignment_axis_unit_y) < 1.0e-9:
            return nipple_x + chestwall_curve_nipple_follow_factor * chestwall_curve_center_x_offset_m
        return alignment_anchor_x + (alignment_axis_unit_x / alignment_axis_unit_y) * (y_value - alignment_anchor_y)

    if alignment_enabled:
        # Keep the nipple transversely coupled to the subareolar/gland axis.
        # Using the very anterior surface y would over-tilt the nipple for large
        # chestwall offsets, while the surface y is still used below for the AP
        # overlap placement.
        nipple_geometry_x = _alignment_x_at_y(outer_anterior_y * 0.45)
    else:
        nipple_geometry_x = (
            nipple_x + chestwall_curve_nipple_follow_factor * chestwall_curve_center_x_offset_m
            if transverse_chestwall_enabled
            else nipple_x
        )
    nipple_geometry_x = min(
        max(nipple_geometry_x + nipple_geometry_x_offset_m, -0.92 * outer_semiaxis_x),
        0.92 * outer_semiaxis_x,
    )
    nipple_geometry_z = min(
        max(nipple_z + nipple_geometry_z_offset_m, -0.92 * outer_semiaxis_z),
        0.92 * outer_semiaxis_z,
    )
    lobule_alignment_dx = nipple_geometry_x - nipple_x
    lobule_alignment_dz = nipple_geometry_z - nipple_z
    nipple_outer_radius_y = max(nipple_pos * 0.84, radius * 0.0185)
    nipple_outer_radius_x = max(center_pos * 0.31, radius * 0.0145)
    nipple_outer_radius_z = max(center_pos * 0.31, radius * 0.0145)
    intended_local_surface_arg = 1.0
    if outer_semiaxis_x > 0.0:
        intended_local_surface_arg -= (nipple_geometry_x / outer_semiaxis_x) ** 2
    if outer_semiaxis_z > 0.0:
        intended_local_surface_arg -= (nipple_geometry_z / outer_semiaxis_z) ** 2
    intended_local_surface_arg = min(max(intended_local_surface_arg, 0.0), 1.0)
    intended_local_outer_surface_y = intended_outer_axis_y * float(np.sqrt(intended_local_surface_arg))
    comsol_local_surface_arg = 1.0
    if comsol_outer_axis_x > 0.0:
        comsol_local_surface_arg -= (nipple_geometry_x / comsol_outer_axis_x) ** 2
    if comsol_outer_axis_z > 0.0:
        comsol_local_surface_arg -= (nipple_geometry_z / comsol_outer_axis_z) ** 2
    comsol_local_surface_arg = min(max(comsol_local_surface_arg, 0.0), 1.0)
    comsol_local_outer_surface_y = comsol_outer_axis_y * float(np.sqrt(comsol_local_surface_arg))
    nipple_surface_normal_x = 0.0
    nipple_surface_normal_y = 1.0
    nipple_surface_normal_z = 0.0
    if comsol_outer_axis_x > 0.0 and comsol_outer_axis_y > 0.0 and comsol_outer_axis_z > 0.0:
        nipple_surface_normal_x = nipple_geometry_x / (comsol_outer_axis_x * comsol_outer_axis_x)
        nipple_surface_normal_y = comsol_local_outer_surface_y / (comsol_outer_axis_y * comsol_outer_axis_y)
        nipple_surface_normal_z = nipple_geometry_z / (comsol_outer_axis_z * comsol_outer_axis_z)
        nipple_surface_normal_norm = float(
            np.sqrt(
                nipple_surface_normal_x * nipple_surface_normal_x
                + nipple_surface_normal_y * nipple_surface_normal_y
                + nipple_surface_normal_z * nipple_surface_normal_z
            )
        )
        if nipple_surface_normal_norm > 1.0e-12:
            nipple_surface_normal_x /= nipple_surface_normal_norm
            nipple_surface_normal_y /= nipple_surface_normal_norm
            nipple_surface_normal_z /= nipple_surface_normal_norm
        else:
            nipple_surface_normal_x = 0.0
            nipple_surface_normal_y = 1.0
            nipple_surface_normal_z = 0.0
    use_surface_aware_nipple = (
        nipple_surface_center_overlap_m >= 0.0
        or nipple_surface_overlap_m >= 0.0
        or nipple_surface_protrusion_m >= 0.0
        or gland_nipple_surface_depth_factor >= 0.0
        or gland_subareolar_surface_clearance_m >= 0.0
    )
    local_outer_surface_y = (
        comsol_local_outer_surface_y if use_surface_aware_nipple else intended_local_outer_surface_y
    )
    nipple_anchor_y = nipple_surface_anchor_y_m if nipple_surface_anchor_y_m >= 0.0 else local_outer_surface_y
    nipple_surface_mode = "legacy_offset"
    nipple_axis_y_radius = nipple_outer_radius_z if use_surface_aware_nipple else nipple_outer_radius_y
    nipple_center_overlap = 0.0
    if nipple_surface_anchor_y_m >= 0.0:
        nipple_outer_center_y = nipple_anchor_y
        nipple_surface_mode = "fixed_anchor"
    elif nipple_surface_center_overlap_m >= 0.0:
        nipple_center_overlap = min(nipple_surface_center_overlap_m, nipple_axis_y_radius * 0.9)
        nipple_outer_center_y = nipple_anchor_y - nipple_center_overlap
        nipple_surface_mode = "surface_center_overlap"
    elif nipple_surface_center_overlap_fraction >= 0.0:
        nipple_center_overlap = min(nipple_surface_center_overlap_fraction * nipple_axis_y_radius, nipple_axis_y_radius * 0.9)
        nipple_outer_center_y = nipple_anchor_y - nipple_center_overlap
        nipple_surface_mode = "surface_center_overlap_fraction"
    elif nipple_surface_overlap_m >= 0.0:
        nipple_overlap = min(nipple_surface_overlap_m, nipple_axis_y_radius * 0.95)
        nipple_outer_center_y = nipple_anchor_y + nipple_axis_y_radius - nipple_overlap
        nipple_surface_mode = "surface_edge_overlap"
    elif nipple_surface_protrusion_m >= 0.0:
        nipple_protrusion = min(nipple_surface_protrusion_m, nipple_axis_y_radius * 0.95)
        nipple_outer_center_y = nipple_anchor_y - nipple_axis_y_radius + nipple_protrusion
        nipple_surface_mode = "surface_tip_protrusion"
    else:
        nipple_outer_center_y = nipple_anchor_y + nipple_outer_radius_y * nipple_surface_offset_factor
        nipple_center_overlap = nipple_anchor_y - nipple_outer_center_y
    normal_alignment_active = nipple_surface_normal_alignment_enabled and use_surface_aware_nipple
    if normal_alignment_active:
        normal_ap_depth = nipple_anchor_y - nipple_outer_center_y
        nipple_outer_center_x = nipple_geometry_x - nipple_surface_normal_x * normal_ap_depth
        nipple_outer_center_y = nipple_anchor_y - nipple_surface_normal_y * normal_ap_depth
        nipple_outer_center_z = nipple_geometry_z - nipple_surface_normal_z * normal_ap_depth
    else:
        nipple_outer_center_x = nipple_geometry_x
        nipple_outer_center_z = nipple_geometry_z
    nipple_sel_half_x = nipple_outer_radius_x * 1.45
    nipple_sel_half_z = nipple_outer_radius_z * 1.45
    nipple_sel_xmin = nipple_geometry_x - nipple_sel_half_x
    nipple_sel_xmax = nipple_geometry_x + nipple_sel_half_x
    nipple_sel_ymin = nipple_outer_center_y - nipple_axis_y_radius * 1.05
    nipple_sel_ymax = nipple_outer_center_y + nipple_axis_y_radius * 1.10
    nipple_support_sel_half_x = max(nipple_sel_half_x * 2.25, radius * 0.18)
    nipple_support_sel_half_z = max(nipple_sel_half_z * 2.25, radius * 0.18)
    nipple_support_sel_xmin = nipple_geometry_x - nipple_support_sel_half_x
    nipple_support_sel_xmax = nipple_geometry_x + nipple_support_sel_half_x
    nipple_support_sel_ymin = nipple_outer_center_y - nipple_axis_y_radius * 2.35
    nipple_support_sel_ymax = nipple_outer_center_y + nipple_axis_y_radius * 1.25
    anterior_skin_sel_ymin = max(outer_anterior_y * 0.18, 0.008)
    anterior_skin_sel_ymax = outer_anterior_y + nipple_outer_radius_y * 1.35
    anterior_skin_sel_half_x = radius * 0.92 * max(outer_shape_scale_x, 1.0)
    anterior_skin_sel_half_z = radius * 0.92 * max(outer_shape_scale_z, 1.0)
    anterior_skin_sel_xmin = nipple_geometry_x - anterior_skin_sel_half_x
    anterior_skin_sel_xmax = nipple_geometry_x + anterior_skin_sel_half_x
    gland_nipple_radius_y = max(nipple_outer_radius_y * 0.96, radius * 0.0180)
    gland_nipple_radius_x = max(nipple_outer_radius_x * 0.90, radius * 0.0130)
    gland_nipple_radius_z = max(nipple_outer_radius_z * 0.90, radius * 0.0130)
    gland_nipple_radius_y *= glandular_subareolar_core_scale
    gland_nipple_radius_x *= glandular_subareolar_core_scale
    gland_nipple_radius_z *= glandular_subareolar_core_scale
    gland_nipple_axis_y_radius = gland_nipple_radius_z if use_surface_aware_nipple else gland_nipple_radius_y
    # The bridge should read as a ductal/subareolar AP connection, not as a
    # wide transverse disk. Keep x/z compact and let the y semiaxis provide
    # the anterior-posterior reach toward the nipple core.
    gland_subareolar_bridge_radius_y = max(radius * 0.155, gland_nipple_radius_y * 2.85) * glandular_subareolar_bridge_scale
    gland_subareolar_bridge_radius_x = max(gland_nipple_radius_x * 0.72, radius * 0.0085) * min(glandular_subareolar_bridge_scale, 1.10)
    gland_subareolar_bridge_radius_z = max(gland_nipple_radius_z * 0.72, radius * 0.0085) * min(glandular_subareolar_bridge_scale, 1.10)
    gland_subareolar_bridge_axis_y_radius = (
        gland_subareolar_bridge_radius_z if use_surface_aware_nipple else gland_subareolar_bridge_radius_y
    )
    chest_overlap = min(max(chest_thickness * 0.05, 5.0e-5), 2.5e-4)
    cooper_spring_ky = (cooper_effective_modulus * cooper_area_fraction) / cooper_reference_length
    cooper_spring_kxz = cooper_spring_ky * cooper_tangential_scale
    cooper_skin_web_ky = cooper_spring_ky * 0.65
    cooper_skin_web_kxz = cooper_skin_web_ky * cooper_tangential_scale
    cooper_gland_web_ky = cooper_spring_ky * 0.45
    cooper_gland_web_kxz = cooper_gland_web_ky * cooper_tangential_scale
    support_geometry_extra_x_margin = abs(chestwall_curve_center_x_offset_m) if transverse_chestwall_enabled else 0.0
    support_geometry_half_x = outer_support_half_x + support_geometry_extra_x_margin
    outer_keep_y_size = max(2.0 * radius, outer_anterior_y + 2.0 * nipple_outer_radius_y)
    chest_base_xmin = -support_geometry_half_x
    chest_base_xmax = support_geometry_half_x
    si_alignment_axis_x = 1.0
    si_alignment_axis_y = 0.0
    si_alignment_axis_z = 0.0
    si_alignment_normal_x = 0.0
    si_alignment_normal_y = 1.0
    si_alignment_center_x = 0.0
    si_alignment_center_y = -si_curve_center_y
    si_alignment_center_z = 0.0
    si_alignment_length_m = 2.0 * support_geometry_half_x
    si_alignment_base_x = -support_geometry_half_x
    si_alignment_base_y = -si_curve_center_y
    si_alignment_base_z = 0.0
    si_support_depth_for_selection = chest_curve_si_depth if si_chestwall_enabled else 0.0
    if si_alignment_enabled:
        si_alignment_normal_x = alignment_axis_unit_x
        si_alignment_normal_y = alignment_axis_unit_y
        si_alignment_axis_x = alignment_axis_unit_y
        si_alignment_axis_y = -alignment_axis_unit_x
        si_axis_norm = float(np.sqrt(si_alignment_axis_x * si_alignment_axis_x + si_alignment_axis_y * si_alignment_axis_y))
        if si_axis_norm > 1.0e-12:
            si_alignment_axis_x /= si_axis_norm
            si_alignment_axis_y /= si_axis_norm
        else:
            si_alignment_axis_x = 1.0
            si_alignment_axis_y = 0.0
        si_alignment_length_m = max(
            2.8 * support_geometry_half_x,
            2.0 * outer_support_half_z,
            2.0 * radius,
        )
        # Put the SI cylinder apex exactly on the same local chestwall anchor as
        # the transverse arc. Earlier previews placed the SI apex one SI-depth
        # anterior to this point, which made combined curves cut/support from
        # different local contact lines.
        si_alignment_center_x = alignment_anchor_x - si_alignment_normal_x * si_curve_radius
        si_alignment_center_y = alignment_anchor_y - si_alignment_normal_y * si_curve_radius
        si_alignment_center_z = 0.0
        si_alignment_base_x = si_alignment_center_x - 0.5 * si_alignment_length_m * si_alignment_axis_x
        si_alignment_base_y = si_alignment_center_y - 0.5 * si_alignment_length_m * si_alignment_axis_y
        si_alignment_base_z = 0.0
        si_support_depth_for_selection = max(0.0, alignment_anchor_y)
    support_depth_for_selection = max(
        chest_curve_depth if (curved_chestwall_enabled or transverse_chestwall_enabled) else 0.0,
        si_support_depth_for_selection,
    )
    chest_base_ymin = -chest_thickness - chest_overlap
    chest_base_ymax = support_depth_for_selection + chest_overlap
    breast_attach_ymin = -chest_overlap
    breast_attach_ymax = support_depth_for_selection + chest_overlap
    support_lower_fraction = max(1.0 - upper_support_fraction, 0.05)
    support_split_z = -radius * outer_shape_scale_z + 2.0 * radius * outer_shape_scale_z * support_lower_fraction
    support_lower_zmin = -outer_support_half_z
    support_lower_z_size = max(support_split_z - support_lower_zmin, radius * 0.05)
    support_upper_z_size = max(outer_support_half_z - support_split_z, radius * 0.05)
    simulation = build_plan_summary["simulation"]
    control_step1 = simulation.get("control_step1", {}) if isinstance(simulation, dict) else {}
    control_step2 = simulation.get("control_step2", {}) if isinstance(simulation, dict) else {}
    parabolic_jump = simulation.get("parabolic_jump", {}) if isinstance(simulation, dict) else {}
    animation = simulation.get("animation", {}) if isinstance(simulation, dict) else {}
    gravity_duration_s = float(control_step1.get("time_steps", 10)) * float(control_step1.get("step_size", 0.1))
    dynamic_duration_s = float(control_step2.get("time_steps", 120)) * float(control_step2.get("step_size", 0.01))
    gravity_ramp_duration_override_s = (
        float(getattr(comsol_settings, "gravity_ramp_duration_s", 0.0))
        if comsol_settings
        else 0.0
    )
    if gravity_ramp_duration_override_s > 0.0:
        gravity_duration_s = gravity_ramp_duration_override_s
    dynamic_settle_duration_override_s = (
        float(getattr(comsol_settings, "dynamic_settle_duration_s", 0.0))
        if comsol_settings
        else 0.0
    )
    if dynamic_settle_duration_override_s > 0.0:
        dynamic_duration_s = dynamic_settle_duration_override_s
    jump_max_height_m = float(parabolic_jump.get("max_height", 0.01))
    output_fps = max(float(animation.get("fps", 40)), 1.0)
    output_dt_override_s = (
        float(getattr(comsol_settings, "dynamic_output_step_s", 0.0))
        if comsol_settings
        else 0.0
    )
    output_dt_s = output_dt_override_s if output_dt_override_s > 0.0 else 1.0 / output_fps
    output_dt_s = min(max(output_dt_s, 0.001), 1.0)
    pulse_output_dt_s = (
        float(getattr(comsol_settings, "dynamic_pulse_output_step_s", 0.002))
        if comsol_settings
        else 0.002
    )
    pulse_output_dt_s = min(max(pulse_output_dt_s, 0.001), output_dt_s)
    jump_initial_velocity = float(np.sqrt(max(2.0 * 9.81 * jump_max_height_m, 0.0)))
    legacy_jump_duration_s = float(2.0 * jump_initial_velocity / 9.81) if jump_initial_velocity > 0.0 else 0.0
    support_displacement_amplitude_m = (
        float(getattr(comsol_settings, "dynamic_support_displacement_amplitude_m", 0.0))
        if comsol_settings
        else 0.0
    )
    support_displacement_duration_s = (
        float(getattr(comsol_settings, "dynamic_support_displacement_duration_s", 0.0))
        if comsol_settings
        else 0.0
    )
    support_displacement_amplitude_m = support_displacement_amplitude_m if support_displacement_amplitude_m > 0.0 else jump_max_height_m
    support_displacement_duration_s = support_displacement_duration_s if support_displacement_duration_s > 0.0 else legacy_jump_duration_s
    jump_duration_s = support_displacement_duration_s
    pulse_duration_s = dynamic_acceleration_duration_s
    dynamic_start_s = gravity_duration_s
    jump_start_s = dynamic_start_s + dynamic_motion_hold_s
    dynamic_excitation_duration_s = pulse_duration_s if dynamic_motion_mode == "fixed_support_acceleration_pulse" else jump_duration_s
    dynamic_end_s = max(dynamic_start_s + dynamic_duration_s, jump_start_s + dynamic_excitation_duration_s)
    if dynamic_motion_mode == "gravity_only":
        jump_z_expression_java = '"0"'
    elif dynamic_motion_mode == "smooth_support_displacement":
        dynamic_motion_profile = "smooth_cosine_bump"
        jump_z_expression_java = (
            '"if(t<t_jump_start,0,"'
            '\n      + "if(t<(t_jump_start+t_jump_duration),"'
            '\n      + "jump_amp*0.5*(1-cos(2*pi*(t-t_jump_start)/t_jump_duration)),"'
            '\n      + "0))"'
        )
    elif dynamic_motion_profile == "smooth_c2_bump":
        jump_z_expression_java = (
            '"if(t<t_jump_start,0,"'
            '\n      + "if(t<(t_jump_start+t_jump_duration),"'
            '\n      + "jump_amp*64*((t-t_jump_start)/t_jump_duration)^3*(1-((t-t_jump_start)/t_jump_duration))^3,"'
            '\n      + "0))"'
        )
    elif dynamic_motion_profile in {"febio_parabolic_support", "parabolic_support"}:
        dynamic_motion_profile = "parabolic_support"
        jump_z_expression_java = (
            '"if(t<t_jump_start,0,"'
            '\n      + "if(t<(t_jump_start+t_jump_duration),"'
            '\n      + "(-0.5*g_acc*(t-t_jump_start)^2+jump_v0*(t-t_jump_start)),"'
            '\n      + "0))"'
        )
    else:
        jump_z_expression_java = (
            '"if(t<t_jump_start,0,"'
            '\n      + "if(t<(t_jump_start+t_jump_duration),"'
            '\n      + "-jump_amp*0.5*(1-cos(2*pi*(t-t_jump_start)/t_jump_duration)),"'
            '\n      + "0))"'
        )
    inertial_acc_expression_java = (
        '"if(t<t_jump_start,0,"'
        '\n      + "if(t<(t_jump_start+t_pulse_duration),"'
        '\n      + "-pulse_acc_amp*g_acc*sin(2*pi*(t-t_jump_start)/t_pulse_duration),"'
        '\n      + "0))"'
        if dynamic_motion_mode == "fixed_support_acceleration_pulse"
        else '"0"'
    )
    gravity_z_expression = (
        "-g_acc*grav_scale_t+inertial_acc_z_t"
        if dynamic_motion_mode == "fixed_support_acceleration_pulse"
        else "-g_acc*grav_scale_t"
    )
    fixed_boundary_active_java = "true" if dynamic_motion_mode in {"gravity_only", "fixed_support_acceleration_pulse"} else "false"
    prescribed_support_motion_java = ""
    if dynamic_motion_mode in {"prescribed_support_displacement", "smooth_support_displacement"}:
        prescribed_support_motion_java = """
    tryCreateDirectionalPrescribedDisplacementFeature(
      model,
      "solid",
      "disp_jump",
      "breast_attach_bnd",
      true,
      "0",
      true,
      "0",
      true,
      "jump_z_t",
      dynamicMotionNotes
    );
"""
    report_review_time_s = (
        dynamic_end_s
        if dynamic_motion_mode == "gravity_only"
        else jump_start_s + 0.5 * dynamic_excitation_duration_s
    )
    # The source-case dynamic step applies body mass damping to skin/adipose/glandular.
    # The closest general COMSOL analogue is Rayleigh damping with a pure mass term.
    mass_damping_alpha = (
        float(getattr(comsol_settings, "dynamic_mass_damping_alpha_s_inv", 20.0))
        if comsol_settings
        else 20.0
    )
    mass_damping_alpha = min(max(mass_damping_alpha, 0.0), 1000.0)
    stiffness_damping_beta = 0.0

    # Model the glandular core as a half-ellipsoid clipped at the chest-wall plane.
    # The clipping plane y=0 should coincide with the ellipse midline so the gland
    # remains broad at the chest wall, while the anterior reach is preserved toward
    # the nipple side.
    gland_center_y = glandular_seed_center_y_offset_m
    gland_center_x_base = (
        min(max(_alignment_x_at_y(outer_anterior_y * 0.45), -0.70 * outer_semiaxis_x), 0.70 * outer_semiaxis_x)
        if alignment_enabled
        else (
            chestwall_curve_gland_follow_factor * chestwall_curve_center_x_offset_m
            if transverse_chestwall_enabled
            else 0.0
        )
    )
    gland_center_x = min(
        max(gland_center_x_base + glandular_seed_center_x_offset_m, -0.85 * outer_semiaxis_x),
        0.85 * outer_semiaxis_x,
    )
    gland_semiaxis_y = max(radius + nipple_pos, radius * 0.05) * transverse_volume_preserve_gland_y_scale * glandular_shape_scale_y
    gland_seed_surface_clearance_m = (
        glandular_seed_surface_clearance_fraction * nipple_axis_y_radius
        if glandular_seed_surface_clearance_fraction > -90.0
        else -1.0
    )
    if glandular_seed_surface_clearance_fraction > -90.0:
        gland_seed_anterior_limit_y = max(radius * 0.20, nipple_anchor_y - gland_seed_surface_clearance_m)
        gland_semiaxis_y = min(gland_semiaxis_y, max(radius * 0.05, gland_seed_anterior_limit_y - gland_center_y))
    else:
        gland_seed_anterior_limit_y = gland_center_y + gland_semiaxis_y
    if gland_nipple_surface_clearance_fraction > -90.0:
        gland_nipple_center_y = nipple_anchor_y - gland_nipple_axis_y_radius * (1.0 + gland_nipple_surface_clearance_fraction)
        effective_gland_nipple_surface_depth_factor = 1.0 + gland_nipple_surface_clearance_fraction
    elif gland_nipple_surface_depth_factor >= 0.0:
        gland_nipple_center_y = nipple_anchor_y - gland_nipple_axis_y_radius * gland_nipple_surface_depth_factor
        effective_gland_nipple_surface_depth_factor = gland_nipple_surface_depth_factor
    else:
        gland_nipple_center_y = min(gland_semiaxis_y, nipple_anchor_y) + gland_nipple_radius_y * gland_nipple_surface_offset_factor
        effective_gland_nipple_surface_depth_factor = -1.0
    if normal_alignment_active:
        gland_nipple_normal_depth = max(nipple_anchor_y - gland_nipple_center_y, -gland_nipple_axis_y_radius * 0.95)
        gland_nipple_center_x = nipple_geometry_x - nipple_surface_normal_x * gland_nipple_normal_depth
        gland_nipple_center_y = nipple_anchor_y - nipple_surface_normal_y * gland_nipple_normal_depth
        gland_nipple_center_z = nipple_geometry_z - nipple_surface_normal_z * gland_nipple_normal_depth
    else:
        gland_nipple_center_x = nipple_geometry_x
        gland_nipple_center_z = nipple_geometry_z
    gland_semiaxis_x = max(center_pos * 1.15, radius * 0.09) * glandular_shape_scale_x
    gland_semiaxis_z = max(center_pos * (scale_z if asym_enabled else 1.0) * 1.10, radius * 0.09) * glandular_shape_scale_z
    gland_center_z = (-0.15 * center_pos if asym_enabled else 0.0) + glandular_seed_center_z_offset_m
    if gland_subareolar_surface_clearance_m >= 0.0:
        gland_subareolar_bridge_center_y = min(
            gland_nipple_center_y - gland_nipple_axis_y_radius * 0.35,
            nipple_anchor_y - gland_subareolar_surface_clearance_m - gland_subareolar_bridge_axis_y_radius,
        )
    else:
        gland_subareolar_bridge_center_y = min(
            gland_nipple_center_y - gland_nipple_axis_y_radius * 0.78,
            nipple_anchor_y - gland_subareolar_bridge_axis_y_radius * 0.38,
        )
        gland_subareolar_bridge_center_y = max(gland_subareolar_bridge_center_y, gland_subareolar_bridge_axis_y_radius * 0.74)
    if normal_alignment_active:
        gland_subareolar_bridge_normal_depth = max(
            nipple_anchor_y - gland_subareolar_bridge_center_y,
            gland_subareolar_bridge_axis_y_radius * 0.10,
        )
        gland_subareolar_bridge_center_x = (
            nipple_geometry_x - nipple_surface_normal_x * gland_subareolar_bridge_normal_depth
        )
        gland_subareolar_bridge_center_y = (
            nipple_anchor_y - nipple_surface_normal_y * gland_subareolar_bridge_normal_depth
        )
        gland_subareolar_bridge_center_z = (
            nipple_geometry_z - nipple_surface_normal_z * gland_subareolar_bridge_normal_depth
        )
    else:
        gland_subareolar_bridge_center_x = nipple_geometry_x
        gland_subareolar_bridge_center_z = nipple_geometry_z
    anterior_gland_sel_ymin = max(gland_center_y + gland_semiaxis_y * 0.25, 0.006)
    anterior_gland_sel_ymax = gland_center_y + gland_semiaxis_y * 0.98
    anterior_gland_sel_center_x = 0.5 * (gland_center_x + nipple_geometry_x)
    anterior_gland_sel_center_z = 0.5 * (gland_center_z + nipple_geometry_z)
    anterior_gland_sel_half_x = max(
        gland_semiaxis_x * 1.05,
        abs(nipple_geometry_x - gland_center_x) + gland_nipple_radius_x * 2.0,
    )
    anterior_gland_sel_half_z = max(
        gland_semiaxis_z * 1.05,
        abs(nipple_geometry_z - gland_center_z) + gland_nipple_radius_z * 2.0,
    )
    anterior_gland_sel_xmin = anterior_gland_sel_center_x - anterior_gland_sel_half_x
    anterior_gland_sel_xmax = anterior_gland_sel_center_x + anterior_gland_sel_half_x
    anterior_gland_sel_zmin = anterior_gland_sel_center_z - anterior_gland_sel_half_z
    anterior_gland_sel_zmax = anterior_gland_sel_center_z + anterior_gland_sel_half_z
    landmark_reference_y = min(max(outer_anterior_y * 0.55, radius * 0.20), outer_anterior_y + nipple_outer_radius_y * 0.35)
    landmark_patch_half_y = max(radius * 0.16, nipple_outer_radius_y * 1.75)
    landmark_ymin = max(0.0, landmark_reference_y - landmark_patch_half_y)
    landmark_ymax = min(outer_anterior_y + nipple_outer_radius_y * 1.35, landmark_reference_y + landmark_patch_half_y)
    landmark_side_band_x = max(comsol_outer_axis_x * 0.18, radius * 0.09)
    landmark_pole_band_z = max(comsol_outer_axis_z * 0.18, radius * 0.09)
    landmark_side_zmin = -comsol_outer_axis_z * 0.72
    landmark_side_zmax = comsol_outer_axis_z * 0.72
    landmark_pole_xmin = -comsol_outer_axis_x * 0.72
    landmark_pole_xmax = comsol_outer_axis_x * 0.72
    lobules: list[dict[str, object]] = list(build_plan_summary["lobules"])

    inferior_fullness_java = ""
    lateral_fullness_java = ""
    breast_outer_extra_tags = ['"nipple_outer"']
    if outer_inferior_fullness_enabled:
        fullness_radius_x = radius * (0.28 + 0.12 * outer_inferior_fullness_ratio) * outer_shape_scale_x
        fullness_radius_y = (
            radius
            * transverse_volume_preserve_y_scale
            * outer_shape_scale_y
            * (0.13 + 0.10 * outer_inferior_fullness_ratio)
        )
        fullness_radius_z = radius * (0.16 + 0.13 * outer_inferior_fullness_ratio) * outer_shape_scale_z
        fullness_center_y = (
            radius
            * transverse_volume_preserve_y_scale
            * outer_shape_scale_y
            * (0.48 + 0.12 * outer_inferior_fullness_ratio)
        )
        fullness_center_z = -radius * outer_shape_scale_z * (0.38 + 0.15 * outer_inferior_fullness_ratio)
        inferior_fullness_java = f"""
    model.component("comp1").geom("geom1").create("breast_inferior_fullness", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("breast_inferior_fullness").set("semiaxes", "{fullness_radius_x:.8f} {fullness_radius_z:.8f} {fullness_radius_y:.8f}");
    model.component("comp1").geom("geom1").feature("breast_inferior_fullness").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("breast_inferior_fullness").set("pos", "0 {fullness_center_y:.8f} {fullness_center_z:.8f}");
    model.component("comp1").geom("geom1").feature("breast_inferior_fullness").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("breast_inferior_fullness").set("selresultshow", "off");
"""
        breast_outer_extra_tags.append('"breast_inferior_fullness"')
    if outer_lateral_fullness_enabled:
        lateral_radius_x = radius * (0.18 + 0.10 * outer_lateral_fullness_ratio) * outer_shape_scale_x
        lateral_radius_y = comsol_outer_axis_y * (0.22 + 0.10 * outer_lateral_fullness_ratio)
        lateral_radius_z = radius * (0.42 + 0.10 * outer_lateral_fullness_ratio) * outer_shape_scale_z
        lateral_center_x = (
            outer_lateral_fullness_side
            * radius
            * outer_shape_scale_x
            * (0.55 + 0.08 * outer_lateral_fullness_ratio)
        )
        lateral_center_y = comsol_outer_axis_y * (0.58 + 0.08 * outer_lateral_fullness_ratio)
        lateral_center_z = -radius * outer_shape_scale_z * (0.03 + 0.10 * outer_lateral_fullness_ratio)
        lateral_fullness_java = f"""
    model.component("comp1").geom("geom1").create("breast_lateral_fullness", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("breast_lateral_fullness").set("semiaxes", "{lateral_radius_x:.8f} {lateral_radius_z:.8f} {lateral_radius_y:.8f}");
    model.component("comp1").geom("geom1").feature("breast_lateral_fullness").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("breast_lateral_fullness").set("pos", "{lateral_center_x:.8f} {lateral_center_y:.8f} {lateral_center_z:.8f}");
    model.component("comp1").geom("geom1").feature("breast_lateral_fullness").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("breast_lateral_fullness").set("selresultshow", "off");
"""
        breast_outer_extra_tags.append('"breast_lateral_fullness"')
    breast_outer_extra_assignments = "\n".join(
        f"    breastOuterInput[breastBaseObjs.length + {idx}] = {tag};"
        for idx, tag in enumerate(breast_outer_extra_tags)
    )
    if si_alignment_enabled:
        thorax_keep_si_axis_java = f"""
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("axistype", "cartesian");
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("axis", new double[]{{{si_alignment_axis_x:.12f}, {si_alignment_axis_y:.12f}, {si_alignment_axis_z:.12f}}});
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("h", "{si_alignment_length_m:.8f}");
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("pos", "{si_alignment_base_x:.8f} {si_alignment_base_y:.8f} {si_alignment_base_z:.8f}");"""
        thorax_inner_si_axis_java = f"""
        model.component("comp1").geom("geom1").feature("thorax_inner_si").set("axistype", "cartesian");
        model.component("comp1").geom("geom1").feature("thorax_inner_si").set("axis", new double[]{{{si_alignment_axis_x:.12f}, {si_alignment_axis_y:.12f}, {si_alignment_axis_z:.12f}}});
        model.component("comp1").geom("geom1").feature("thorax_inner_si").set("h", "{si_alignment_length_m:.8f}");
        model.component("comp1").geom("geom1").feature("thorax_inner_si").set("pos", "{si_alignment_base_x:.8f} {si_alignment_base_y:.8f} {si_alignment_base_z:.8f}");"""
        thorax_outer_si_axis_java = f"""
        model.component("comp1").geom("geom1").feature("thorax_outer_si").set("axistype", "cartesian");
        model.component("comp1").geom("geom1").feature("thorax_outer_si").set("axis", new double[]{{{si_alignment_axis_x:.12f}, {si_alignment_axis_y:.12f}, {si_alignment_axis_z:.12f}}});
        model.component("comp1").geom("geom1").feature("thorax_outer_si").set("h", "{si_alignment_length_m:.8f}");
        model.component("comp1").geom("geom1").feature("thorax_outer_si").set("pos", "{si_alignment_base_x:.8f} {si_alignment_base_y:.8f} {si_alignment_base_z:.8f}");"""
    else:
        thorax_keep_si_axis_java = f"""
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("axistype", "x");
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("h", "{2.0 * support_geometry_half_x:.8f}");
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("pos", "{-support_geometry_half_x:.8f} si_curve_center_y 0");"""
        thorax_inner_si_axis_java = f"""
        model.component("comp1").geom("geom1").feature("thorax_inner_si").set("axistype", "x");
        model.component("comp1").geom("geom1").feature("thorax_inner_si").set("h", "{2.0 * support_geometry_half_x:.8f}");
        model.component("comp1").geom("geom1").feature("thorax_inner_si").set("pos", "{-support_geometry_half_x:.8f} si_curve_center_y 0");"""
        thorax_outer_si_axis_java = f"""
        model.component("comp1").geom("geom1").feature("thorax_outer_si").set("axistype", "x");
        model.component("comp1").geom("geom1").feature("thorax_outer_si").set("h", "{2.0 * support_geometry_half_x:.8f}");
        model.component("comp1").geom("geom1").feature("thorax_outer_si").set("pos", "{-support_geometry_half_x:.8f} si_curve_center_y 0");"""

    script_path = output_dir / f"{class_name}.java"
    result_mph = (output_dir / f"{case_name}_generated.mph").resolve()
    build_plan_java = _comsol_safe_name(build_plan_path)
    output_dir_java = _comsol_safe_name(str(output_dir.resolve()))
    result_mph_java = result_mph.as_posix()
    output_root = output_dir.parent
    solve_dir = output_root / "solve"
    postprocess_output_stem = case_name if postprocess_mode == "full" else f"{case_name}_{postprocess_mode}"
    metrics_json_path = solve_dir / f"{postprocess_output_stem}_metrics.json"
    selection_hints_path = output_dir / f"{case_name}_comsol_selection_hints.json"
    # Selection hints give humans a stable map from model concepts to generated
    # COMSOL tags, which is especially useful for build-only inspection.
    nipple_placement_debug = {
        "nipple_surface_mode": nipple_surface_mode,
        "nipple_surface_aware_enabled": use_surface_aware_nipple,
        "nipple_surface_normal_alignment_enabled": nipple_surface_normal_alignment_enabled,
        "nipple_surface_normal_alignment_active": normal_alignment_active,
        "nipple_surface_normal_x": nipple_surface_normal_x,
        "nipple_surface_normal_y": nipple_surface_normal_y,
        "nipple_surface_normal_z": nipple_surface_normal_z,
        "nipple_geometry_x_m": nipple_geometry_x,
        "nipple_geometry_z_m": nipple_geometry_z,
        "lobule_alignment_dx_m": lobule_alignment_dx,
        "lobule_alignment_dz_m": lobule_alignment_dz,
        "chestwall_alignment_mode": chestwall_alignment_mode,
        "alignment_anchor_x_m": alignment_anchor_x,
        "alignment_anchor_y_m": alignment_anchor_y,
        "alignment_circle_center_x_m": alignment_circle_center_x,
        "alignment_circle_center_y_m": alignment_circle_center_y,
        "alignment_axis_direction_x": alignment_axis_unit_x,
        "alignment_axis_direction_y": alignment_axis_unit_y,
        "chestwall_curve_nipple_follow_factor": chestwall_curve_nipple_follow_factor,
        "chestwall_curve_gland_follow_factor": chestwall_curve_gland_follow_factor,
        "nipple_geometry_x_offset_m": nipple_geometry_x_offset_m,
        "nipple_geometry_z_offset_m": nipple_geometry_z_offset_m,
        "nipple_surface_arg": comsol_local_surface_arg if use_surface_aware_nipple else intended_local_surface_arg,
        "nipple_local_surface_y_m": local_outer_surface_y,
        "nipple_comsol_local_surface_y_m": comsol_local_outer_surface_y,
        "nipple_intended_local_surface_y_m": intended_local_outer_surface_y,
        "nipple_surface_anchor_y_m": nipple_anchor_y,
        "nipple_surface_center_overlap_m": nipple_surface_center_overlap_m,
        "nipple_surface_center_overlap_fraction": nipple_surface_center_overlap_fraction,
        "nipple_surface_overlap_m": nipple_surface_overlap_m,
        "nipple_axis_y_radius_m": nipple_axis_y_radius,
        "nipple_outer_center_x_m": nipple_outer_center_x,
        "nipple_outer_center_y_m": nipple_outer_center_y,
        "nipple_outer_center_z_m": nipple_outer_center_z,
        "nipple_outer_posterior_y_m": nipple_outer_center_y - nipple_axis_y_radius,
        "nipple_outer_anterior_y_m": nipple_outer_center_y + nipple_axis_y_radius,
        "gland_nipple_axis_y_radius_m": gland_nipple_axis_y_radius,
        "gland_center_x_base_m": gland_center_x_base,
        "gland_center_x_m": gland_center_x,
        "gland_center_y_m": gland_center_y,
        "gland_center_z_m": gland_center_z,
        "glandular_seed_center_x_offset_m": glandular_seed_center_x_offset_m,
        "glandular_seed_center_y_offset_m": glandular_seed_center_y_offset_m,
        "glandular_seed_center_z_offset_m": glandular_seed_center_z_offset_m,
        "gland_seed_surface_clearance_m": gland_seed_surface_clearance_m,
        "gland_seed_anterior_limit_y_m": gland_seed_anterior_limit_y,
        "gland_nipple_core_center_x_m": gland_nipple_center_x,
        "gland_nipple_core_center_y_m": gland_nipple_center_y,
        "gland_nipple_core_center_z_m": gland_nipple_center_z,
        "gland_nipple_surface_depth_factor": gland_nipple_surface_depth_factor,
        "gland_nipple_surface_clearance_fraction": gland_nipple_surface_clearance_fraction,
        "effective_gland_nipple_surface_depth_factor": effective_gland_nipple_surface_depth_factor,
        "glandular_seed_surface_clearance_fraction": glandular_seed_surface_clearance_fraction,
        "gland_subareolar_bridge_axis_y_radius_m": gland_subareolar_bridge_axis_y_radius,
        "gland_subareolar_bridge_center_x_m": gland_subareolar_bridge_center_x,
        "gland_subareolar_bridge_center_y_m": gland_subareolar_bridge_center_y,
        "gland_subareolar_bridge_center_z_m": gland_subareolar_bridge_center_z,
        "requested_outer_inferior_fullness_enabled": requested_outer_inferior_fullness_enabled,
        "requested_outer_lateral_fullness_enabled": requested_outer_lateral_fullness_enabled,
        "additive_fullness_primitives_disabled": (
            requested_outer_inferior_fullness_enabled
            or requested_outer_lateral_fullness_enabled
        ),
    }
    selection_hints = {
        "component_domain_selections": {
            "geom1_breast_union_dom": "Final union of the deformable breast domains (adipose, glandular, and optional volumetric skin layer)",
            "geom1_skin_layer_dom": "Optional volumetric solid skin layer, generated only when enable_volumetric_skin_layer is true",
            "geom1_adipose_diff_dom": "Adipose region after subtracting glandular volume from outer breast",
            "geom1_gland_clip_dom": "Glandular ellipsoid clipped to the outer breast",
            "geom1_chest_cyl_dom": "Chest-wall support domain",
            "geom1_chest_lower_support_dom": "Lower posterior support subdomain when split support regions are enabled",
            "geom1_pect_support_dom": "Upper posterior pectoralis-like support subdomain when split support regions are enabled",
        },
        "component_boundary_selections": {
            "geom1_breast_union_bnd": "Exterior boundaries of the deformable breast volume",
            "geom1_breast_outer_bnd": "Outer breast envelope boundary; used as the current skin-shell carrier boundary",
            "geom1_adipose_diff_bnd": "Boundaries of the adipose domain",
            "geom1_gland_clip_bnd": "Boundaries of the glandular domain",
            "geom1_chest_cyl_bnd": "Boundaries of the chest-wall support domain",
        },
        "component_manual_boundary_selections": {
            "chest_base_bnd": "Posterior base boundary of the chest support; intended COMSOL analogue of the source-case chest support surface",
            "chest_interface_bnd": "Anterior chest-support interface boundary near the breast attachment plane",
            "breast_attach_box_bnd": "Search band for the breast attachment boundary; widened automatically for curved/transverse chestwall modes",
            "breast_attach_bnd": "Posterior attachment boundary on the breast itself; intersected with the outer breast boundary so curved/transverse supports do not keep using a flat y=0 patch",
            "nipple_bnd": "Anterior nipple-region boundary selection used for stage-5 ligament scaffolds and localized probing",
            "nipple_support_bnd": "Broader subareolar anterior support patch used for the stage-5 nipple-to-chestwall ligament surrogate",
            "anterior_skin_bnd": "Anterior outer breast boundary patch used as a skin-side endpoint for glandular-to-skin ligament scaffolds; defined as outer_skin_free_bnd intersected with an anterior search box so internal gland/lobule boundaries are excluded",
            "anterior_gland_bnd": "Glandular/lobule boundary selection used as a gland-side endpoint for glandular-to-skin ligament scaffolds; kept broad so all lobules participate instead of only the central anterior patch",
            "outer_skin_free_bnd": "Outer breast/skin surface used for report displacement metrics; intended as geom1_breast_outer_bnd minus the posterior breast attachment boundary",
            "landmark_nipple_bnd": "Nipple-region outer-skin landmark patch used for signed displacement export",
            "landmark_left_bnd": "Left/lateral outer-skin landmark patch used for signed displacement export",
            "landmark_right_bnd": "Right/lateral outer-skin landmark patch used for signed displacement export",
            "landmark_superior_bnd": "Superior outer-skin landmark patch used for signed displacement export",
            "landmark_inferior_bnd": "Inferior outer-skin landmark patch used for signed displacement export",
        },
        "geometry_feature_tags": {
            "breast_outer": "Outer breast envelope with source-case baseline and optional light thorax curvature",
            "skin_core": "Optional inner breast core used to subtract a volumetric skin layer from the outer breast",
            "skin_layer": "Optional volumetric skin domain made as breast_outer minus skin_core",
            "gland_clip": "Glandular source volume clipped directly to the breast outer volume; no separate anterior clipping block is used.",
            "gland_lobules": "Union of COMSOL-native lobule ellipsoids derived from the exported source-case lobule layout",
            "adipose_diff": "Adipose outer volume minus glandular volume",
            "chest_cyl": "Chest-wall support body; slab-like in baseline mode, profile-curved in curved mode, and width-curved in transverse mode",
            "breast_union": "Final deformable breast union used for meshing/physics",
            "tumor_preview_sphere": "Sphere in separate component comp_tumor_preview/geom_preview at the analytic tumor_mask center/radius; visualization helper only, not included in breast_union or solid physics",
            "chest_cyl": "Separate chest-wall reference body; not part of the deformable breast physics domain",
            "chest_lower_support": "Lower third posterior support region when split support regions are enabled",
            "pect_support": "Upper two-thirds pectoralis-like posterior support region when split support regions are enabled",
        },
        "recommended_physics_targets": {
            "full_breast_domain_selection": "geom1_breast_union_dom",
            "skin_solid_domain_selection": "geom1_skin_layer_dom",
            "skin_shell_boundary_selection": "geom1_breast_outer_bnd",
            "surface_displacement_selection": "outer_skin_free_bnd",
            "surface_displacement_coordinate": "COMSOL z displacement w is used as signed vertical displacement; COMSOL y displacement v is anterior-posterior",
            "adipose_domain_selection": "geom1_adipose_diff_dom",
            "glandular_domain_selection": "geom1_gland_clip_dom",
            "chest_domain_selection": "geom1_chest_cyl_dom",
            "fixed_boundary_selection": "breast_attach_bnd",
            "dynamic_motion_boundary_selection": "breast_attach_bnd",
            "cooper_ligament_nipple_probe_selection": "nipple_bnd",
            "cooper_ligament_nipple_anchor_selection": "nipple_support_bnd",
            "cooper_ligament_skin_patch_selection": "anterior_skin_bnd",
            "cooper_ligament_gland_patch_selection": "anterior_gland_bnd",
        },
        "tumor_material_overlay": {
            "enabled": tumor_enabled,
            "implementation": "Analytic spherical tumor_mask material overlay inside the existing adipose/glandular domains; no separate COMSOL tumor domain is generated yet. The linear-elastic material nodes use adipose_E_eff/glandular_E_eff so COMSOL's Solid Mechanics 'From material' path can see the tumor stiffness.",
            "preview_geometry": "tumor_preview_sphere is emitted in separate component comp_tumor_preview/geom_preview using the same center and radius so placement can be visually inspected without changing the FEM union.",
            "radius_m": tumor_radius,
            "diameter_mm": 2000.0 * tumor_radius,
            "position_m": [tumor_x, tumor_y, tumor_z],
            "density_kg_m3": tumor_density,
            "youngs_modulus_adipose_pa": tumor_E_adipose,
            "youngs_modulus_glandular_pa": tumor_E_glandular,
            "coef1_adipose_pa": tumor_coef1_adipose,
            "coef2_adipose_pa": tumor_coef2_adipose,
            "coef1_glandular_pa": tumor_coef1_glandular,
            "coef2_glandular_pa": tumor_coef2_glandular,
            "nominal_sphere_volume_ml": (4.0 / 3.0) * 3.141592653589793 * tumor_radius**3 * 1_000_000.0,
            "recommended_checks": [
                "Use build-only verification and the generated tumor_volume metric after solve/postprocess to confirm the analytic sphere intersects the breast domain.",
                "In the generated MPH, inspect Component comp_tumor_preview > geom_preview > tumor_preview_sphere and compare its coordinates/radius with comp1 breast_union/gland_clip/adipose_diff; it is a visual helper, not mat_tumor.",
                "Because this is not a separate geometry domain, COMSOL selection lists will not contain a tumor domain; local tumor metrics are computed with tumor_mask integrals over the breast domain.",
                "Stage 6 tumor-material validation cases should be rebuilt from Java rather than using MPH parameter reuse unless the reused MPH is known to contain adipose_E_eff/glandular_E_eff material expressions.",
                "If boolean clipping becomes necessary for inspection or meshing, add a later explicit inclusion/domain route rather than treating this overlay as an anatomical segmentation.",
            ],
        },
        "skin_shell_scaffold": {
            "enabled": shell_physics_enabled,
            "solid_coupling_scaffold_enabled": shell_coupling_enabled,
            "skin_shell_thickness_m": skin_shell_thickness_m,
            "shell_boundary_selection": "geom1_breast_outer_bnd",
            "notes": [
                "The shell scaffold is generated defensively because COMSOL API identifiers can vary by version/license.",
                "The Solid-Thin Structure Connection is emitted as a scaffold on the same outer boundary selection and may need manual refinement in COMSOL.",
            ],
        },
        "volumetric_skin_layer": {
            "enabled": volumetric_skin_enabled,
            "skin_thickness_m": volumetric_skin_thickness_m,
            "skin_domain_selection": "geom1_skin_layer_dom",
            "core_domain_selection": "geom1_skin_core_dom",
            "notes": [
                "Diagnostic solid-skin route: adipose and glandular tissue are built inside skin_core, while skin_layer is added back into breast_union.",
                "The route is intentionally opt-in so existing stage TOMLs keep the previous no-solid-skin geometry unless enabled explicitly.",
            ],
        },
        "chest_wall_scaffold": {
            "curved_enabled": curved_chestwall_enabled,
            "transverse_enabled": transverse_chestwall_enabled,
            "transverse_volume_preserving_enabled": transverse_volume_preserving_enabled,
            "transverse_volume_preserve_y_scale": transverse_volume_preserve_y_scale,
            "transverse_volume_preserve_gland_y_scale": transverse_volume_preserve_gland_y_scale,
            "chestwall_alignment_mode": chestwall_alignment_mode,
            "chestwall_support_mode": chestwall_support_mode,
            "conformal_chestwall_support_enabled": conformal_chestwall_support_enabled,
            "alignment_anchor_x_m": alignment_anchor_x,
            "alignment_anchor_y_m": alignment_anchor_y,
            "alignment_axis_direction_x": alignment_axis_unit_x,
            "alignment_axis_direction_y": alignment_axis_unit_y,
            "computed_nipple_geometry_x_m": nipple_geometry_x,
            "computed_nipple_geometry_z_m": nipple_geometry_z,
            "nipple_geometry_x_offset_m": nipple_geometry_x_offset_m,
            "nipple_geometry_z_offset_m": nipple_geometry_z_offset_m,
            "lobule_alignment_dx_m": lobule_alignment_dx,
            "lobule_alignment_dz_m": lobule_alignment_dz,
            "computed_gland_center_x_m": gland_center_x,
            "curve_center_x_offset_m": chestwall_curve_center_x_offset_m,
            "curve_max_offset_ratio": chestwall_curve_max_offset_ratio,
            "curve_max_offset_m": chestwall_curve_max_offset_m,
            "requested_curve_depth_m": chestwall_curve_depth_m,
            "curve_max_depth_ratio": chestwall_curve_max_depth_ratio,
            "curve_max_depth_m": chest_curve_max_depth,
            "transverse_curve_span_x_m": transverse_curve_span_x,
            "support_geometry_extra_x_margin_m": support_geometry_extra_x_margin,
            "support_geometry_half_x_m": support_geometry_half_x,
            "si_curve_enabled": si_chestwall_enabled,
            "si_alignment_mode": chestwall_si_alignment_mode,
            "si_alignment_enabled": si_alignment_enabled,
            "si_alignment_normal_x": si_alignment_normal_x,
            "si_alignment_normal_y": si_alignment_normal_y,
            "si_alignment_axis_x": si_alignment_axis_x,
            "si_alignment_axis_y": si_alignment_axis_y,
            "si_alignment_axis_z": si_alignment_axis_z,
            "si_alignment_center_x_m": si_alignment_center_x,
            "si_alignment_center_y_m": si_alignment_center_y,
            "si_alignment_center_z_m": si_alignment_center_z,
            "si_alignment_base_x_m": si_alignment_base_x,
            "si_alignment_base_y_m": si_alignment_base_y,
            "si_alignment_base_z_m": si_alignment_base_z,
            "si_alignment_length_m": si_alignment_length_m,
            "si_support_depth_for_selection_m": si_support_depth_for_selection,
            "si_curve_depth_m": chest_curve_si_depth,
            "si_curve_radius_m": si_curve_radius,
            "si_curve_center_y_m": -si_curve_center_y,
            "glandular_shape_scale_x": glandular_shape_scale_x,
            "glandular_shape_scale_y": glandular_shape_scale_y,
            "glandular_shape_scale_z": glandular_shape_scale_z,
            "glandular_seed_center_x_offset_m": glandular_seed_center_x_offset_m,
            "glandular_seed_center_y_offset_m": glandular_seed_center_y_offset_m,
            "glandular_seed_center_z_offset_m": glandular_seed_center_z_offset_m,
            "gland_center_x_base_m": gland_center_x_base,
            "gland_center_x_m": gland_center_x,
            "gland_center_y_m": gland_center_y,
            "gland_center_z_m": gland_center_z,
            "anterior_gland_selection_center_x_m": anterior_gland_sel_center_x,
            "anterior_gland_selection_center_z_m": anterior_gland_sel_center_z,
            "gland_seed_surface_clearance_m": gland_seed_surface_clearance_m,
            "gland_seed_anterior_limit_y_m": gland_seed_anterior_limit_y,
            "glandular_lobule_include_subareolar_core": glandular_lobule_include_subareolar_core,
            "glandular_lobule_include_subareolar_bridge": glandular_lobule_include_subareolar_bridge,
            "glandular_lobule_include_reference_ellipsoid": glandular_lobule_include_reference_ellipsoid,
            "glandular_subareolar_core_scale": glandular_subareolar_core_scale,
            "glandular_subareolar_bridge_scale": glandular_subareolar_bridge_scale,
            "nipple_placement": nipple_placement_debug,
            "comsol_duct_style": comsol_duct_style,
            "comsol_duct_segments": comsol_duct_segments_override,
            "comsol_duct_radius_scale": comsol_duct_radius_scale,
            "chestwall_aware_lobules": bool(gland_hetero.get("chestwall_aware_lobules", False)),
            "chestwall_clearance_m": float(gland_hetero.get("chestwall_clearance_m", 0.0) or 0.0),
            "curve_depth_m": chest_curve_depth,
            "curve_radius_m": chest_curve_radius,
            "curve_center_y_m": -chest_curve_center_y,
            "transverse_curve_center_y_m": -transverse_curve_center_y,
            "transverse_interface_centerline_y_m": chest_curve_depth,
            "transverse_interface_lateral_y_m": 0.0,
            "combined_support_depth_for_selection_m": support_depth_for_selection,
            "chest_overlap_m": chest_overlap,
            "split_support_regions": split_support_regions,
            "upper_support_fraction": upper_support_fraction,
            "support_split_z_m": support_split_z,
            "notes": [
                "Curved mode replaces the flat posterior clip plane with a shallow cylindrical arc in the yz side-view, so the chest wall reads as a ')' style curve.",
                "Transverse mode uses a circular arc in the xy width section. The arc passes through the lateral breast edge at y=0 and reaches chestwall_curve_depth_m on the transverse curve axis.",
                "chestwall_curve_depth_m is clamped to radius*chestwall_curve_max_depth_ratio; increase chestwall_curve_max_depth_ratio for deliberately stronger build-only preview cases.",
                "chestwall_curve_center_x_offset_m shifts the transverse cylinder axis in COMSOL x; positive values move the deepest transverse interface toward +x. It is clamped to chestwall_curve_max_offset_ratio*outer_support_half_x.",
                "With x-offset enabled, the transverse arc radius is based on the largest distance from the shifted axis to the breast edge, so the far lateral side does not fall below the support surface.",
                "With chestwall_alignment_mode=projected_normal_axis, nipple/subareolar helpers and the simple gland seed are placed from a normal-axis line through the transverse chestwall circle center and a central breast anchor point, instead of manual follow factors.",
                "Generated lobule structures are translated in COMSOL x/z by lobule_alignment_d*_m so the rich glandular structure follows the final nipple axis after Stage 2 auto-alignment.",
                "chestwall_curve_nipple_follow_factor can move the nipple/subareolar helper geometry with or against the shifted curvature axis. Negative values are useful when the visible breast mound shifts opposite to the curvature-axis offset.",
                "chestwall_curve_gland_follow_factor shifts the simple gland seed in x for large-offset preview cases. Lobule-based rich glandular layouts still need a dedicated transform before this can be considered report-ready.",
                "glandular_seed_center_*_offset_m shifts only the simple gland seed after chestwall auto-alignment. Use this for Stage 3 spatial distribution previews; subareolar/nipple helper geometry remains surface-anchored.",
                "For offset previews the chest-wall trim/support boxes are widened symmetrically by abs(chestwall_curve_center_x_offset_m), so the support plate still extends beyond both lateral breast edges.",
                "chestwall_curve_si_depth_m adds an optional superior-inferior cylindrical arc in the yz section; combined transverse+SI mode keeps the anterior side of both arcs, so the posterior interface follows the more restrictive local curve.",
                "With chestwall_si_alignment_mode=transverse_tangent, the SI cylinder is generated on the local tangent of the transverse chestwall arc instead of the global x-axis, so the SI curvature follows strong x-offset chestwalls instead of sitting behind them.",
                "With chestwall_support_mode=conformal_keep_region, the chest-wall support body is created from the same thorax_keep_reg object that clips the breast. This is intended for combined x-offset/SI previews where separate cylinder bands can leave local support gaps.",
                "Transverse volume-preserving mode additionally scales the anterior-posterior breast and glandular semiaxes to compensate for posterior volume removed by the curved interface; volumes still need build-only verification after offset/SI changes.",
                "The chest-wall support domain reuses that same interface family so the breast and chest wall remain approximately conformal.",
                "A small overlap is added between breast and chest support to avoid solver-side sliding at a zero-thickness contact plane.",
            ],
        },
        "cooper_ligament_scaffold": {
            "enabled": cooper_ligament_enabled,
            "variant": cooper_ligament_variant,
            "effective_modulus_pa": cooper_effective_modulus,
            "reference_length_m": cooper_reference_length,
            "area_fraction": cooper_area_fraction,
            "spring_constant_per_area_y_n_per_m3": cooper_spring_ky,
            "spring_constant_per_area_xz_n_per_m3": cooper_spring_kxz,
            "skin_patch_ky_n_per_m3": cooper_skin_web_ky,
            "skin_patch_kxz_n_per_m3": cooper_skin_web_kxz,
            "gland_patch_ky_n_per_m3": cooper_gland_web_ky,
            "gland_patch_kxz_n_per_m3": cooper_gland_web_kxz,
            "damping_per_area_n_s_per_m3": cooper_damping,
            "notes": [
                "Stage 5A currently uses an effective nipple tether approximation rather than explicit 3D ligament strands.",
                "The stage-5A load is applied to a broader subareolar support patch instead of the tiny nipple-tip probe patch to avoid artificial local stress spikes.",
                "The nipple-to-chestwall surrogate is now anterior-posterior only and deliberately softened so the nipple is not vertically pinned during dynamic motion.",
                "The stage-5 boundary-load surrogates intentionally avoid lateral global pinning; explicit 3D ligament strands remain a later refinement.",
                "Stage 5B uses a skin-side outer-surface anterior patch and a broad glandular/lobule boundary selection as a first surrogate for a fibrous web running through the adipose region.",
            ],
        },
        "default_result_plots": {
            "enabled": default_result_plots_enabled,
            "notes": [
                "Generated MPH files include ready-made 3D displacement, directional displacement, von Mises, glandular stress, and cut-plane plots. Legacy Cooper arrow screenshots are intentionally not exported by the current postprocess image list.",
                "Plot creation is defensive in the Java builder: unsupported plot properties are skipped rather than failing the COMSOL build.",
            ],
        },
        "dynamic_motion": {
            "mode": dynamic_motion_mode,
            "profile": dynamic_motion_profile,
            "boundary_selection": "breast_attach_bnd",
            "gravity_end_time_s": gravity_duration_s,
            "dynamic_start_time_s": dynamic_start_s,
            "dynamic_end_time_s": dynamic_end_s,
            "configured_review_time_s": report_review_time_s,
            "jump_hold_s": dynamic_motion_hold_s,
            "jump_start_time_s": jump_start_s,
            "jump_duration_s": jump_duration_s,
            "jump_max_height_m": jump_max_height_m,
            "support_displacement_amplitude_m": support_displacement_amplitude_m,
            "support_displacement_duration_s": support_displacement_duration_s,
            "pulse_duration_s": pulse_duration_s,
            "pulse_acceleration_amplitude_g": dynamic_acceleration_amplitude_g,
            "notes": [
                "Stage 1 supports three diagnostic motion routes: gravity-only sag, fixed-support inertial pulse, and prescribed support displacement fallback.",
                "Report displacement should be interpreted relative to the dynamic-start state; support-relative displacement is only meaningful when support motion is enabled and nonzero.",
            ],
        },
        "mooney_rivlin_material_mapping": {
            "note": (
                "The COMSOL builder now scaffolds Mooney-Rivlin two-parameter hyperelastic features from the "
                "source-case inputs bulk_modulus, coef1, and coef2. The chest wall remains a separate linear elastic "
                "placeholder material."
            ),
            "skin": {
                "density_kg_m3": float(skin_material.get("density", 1100.0)),
                "bulk_modulus_pa": skin_bulk_modulus,
                "c10_pa": skin_coef1,
                "c01_pa": skin_coef2,
            },
            "adipose": {
                "density_kg_m3": float(adipose_material.get("density", 911.0)),
                "bulk_modulus_pa": adipose_bulk_modulus,
                "c10_pa": adipose_coef1,
                "c01_pa": adipose_coef2,
            },
            "glandular": {
                "density_kg_m3": float(glandular_material.get("density", 911.0)),
                "bulk_modulus_pa": glandular_bulk_modulus,
                "c10_pa": glandular_coef1,
                "c01_pa": glandular_coef2,
            },
        },
        "chest_material_assignment": {
            "density_kg_m3": chest_density,
            "youngs_modulus_pa": chest_E,
            "poissons_ratio": chest_nu,
            "source": "Explicit COMSOL chest-wall placeholder values, independent from source-case breast-tissue materials.",
        },
        "planned_metrics_export": {
            "metrics_json": str(metrics_json_path.resolve()),
            "metrics": [
                "breast_volume",
                "glandular_volume",
                "adipose_volume",
                "max_displacement_breast",
                "avg_displacement_breast",
                "max_von_mises_breast",
                "max_von_mises_glandular",
                "tumor_volume",
                "avg_displacement_tumor",
                "max_displacement_tumor",
                "avg_von_mises_tumor",
                "max_von_mises_tumor",
            ],
        },
    }
    selection_hints_path.write_text(json.dumps(selection_hints, indent=2), encoding="utf-8")
    selection_hints_java = selection_hints_path.as_posix()

    use_template_lobes = any(str(lob.get("template_kind", "")) == "duct_lobe" for lob in lobules)

    visible_lobules = list(lobules)
    if duct_only_detail_mode:
        visible_lobules = [lob for lob in lobules if str(lob.get("component_role", "")) == "duct"]

    # Convert source-case lobule descriptors into COMSOL geometry primitives.
    # Template-lobe mode builds bulb/duct families; older modes remain simple
    # ellipsoid chains.
    lobule_feature_tags: list[str] = []
    lobule_specs: list[dict[str, float | str | int]] = []
    lobule_java_blocks: list[str] = []
    for idx, lobule in enumerate(visible_lobules, start=1):
        center = lobule.get("center", [0.0, 0.0, 0.0])
        if not isinstance(center, list) or len(center) != 3:
            continue
        cx, cy, cz = (float(center[0]), float(center[1]), float(center[2]))
        cx += lobule_alignment_dx
        cz += lobule_alignment_dz
        component_role = str(lobule.get("component_role", "bulb"))
        component_index = int(lobule.get("component_index", 0))
        component_count = int(lobule.get("component_count", 1))
        lobe_id = int(lobule.get("lobe_id", idx))

        base_sx = float(lobule.get("width_x", lobule.get("width", 0.002)))
        base_sy = float(lobule.get("width_y", lobule.get("width", 0.002)))
        base_sz = float(lobule.get("width_z", lobule.get("width", 0.002)))

        if component_role == "duct":
            sx = max(base_sx * 0.78, radius * 0.007)
            sy = max(base_sy * 1.45, radius * 0.014)
            sz = max(base_sz * 0.78, radius * 0.007)
        else:
            sx = max(base_sx * 1.12, radius * 0.010)
            sy = max(base_sy * 1.08, radius * 0.012)
            sz = max(base_sz * 1.12, radius * 0.010)

        tag = f"lobule_{idx:02d}"
        lobule_specs.append(
            {
                "tag": tag,
                "cx": cx,
                "cy": cy,
                "cz": cz,
                "sx": sx,
                "sy": sy,
                "sz": sz,
                "lobe_id": lobe_id,
                "component_index": component_index,
                "component_count": component_count,
                "component_role": component_role,
                "ring_name": str(lobule.get("ring_name", "inner")),
            }
        )
        if not use_template_lobes:
            lobule_feature_tags.append(tag)
            lobule_java_blocks.append(
                f"""
    model.component("comp1").geom("geom1").create("{tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{tag}").set("semiaxes", "{sx:.8f} {sz:.8f} {sy:.8f}");
    model.component("comp1").geom("geom1").feature("{tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{tag}").set("pos", "{cx:.8f} {cy:.8f} {cz:.8f}");
    model.component("comp1").geom("geom1").feature("{tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{tag}").set("selresultshow", "all");
"""
            )
    lobe_groups: dict[int, list[dict[str, float | str | int]]] = defaultdict(list)
    for spec in lobule_specs:
        lobe_groups[int(spec["lobe_id"])].append(spec)

    anatomical_lobe_tags: list[str] = []
    anatomical_lobe_java_blocks: list[str] = []
    lobe_refinement_java_blocks: list[str] = []
    shared_duct_tags: list[str] = []
    shared_duct_java_blocks: list[str] = []
    if lobe_groups and use_template_lobes:
        fast_detail_mode = comsol_detail_mode == "fast"
        hub_y = nipple_y - radius * 0.17
        hub_tag = "duct_hub_core"
        hub_cap_tag = "duct_hub_cap"
        trunk_tag = "duct_trunk_main"
        shared_duct_tags.extend([hub_tag, hub_cap_tag, trunk_tag])
        shared_duct_java_blocks.extend(
            [
                f"""
    model.component("comp1").geom("geom1").create("{hub_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{hub_tag}").set("semiaxes", "{radius * 0.0205:.8f} {radius * 0.0205:.8f} {radius * 0.0300:.8f}");
    model.component("comp1").geom("geom1").feature("{hub_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{hub_tag}").set("pos", "{nipple_geometry_x:.8f} {hub_y:.8f} {nipple_geometry_z:.8f}");
    model.component("comp1").geom("geom1").feature("{hub_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{hub_tag}").set("selresultshow", "all");
""",
                f"""
    model.component("comp1").geom("geom1").create("{hub_cap_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{hub_cap_tag}").set("semiaxes", "{radius * 0.0280:.8f} {radius * 0.0280:.8f} {radius * 0.0160:.8f}");
    model.component("comp1").geom("geom1").feature("{hub_cap_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{hub_cap_tag}").set("pos", "{nipple_geometry_x:.8f} {hub_y - radius * 0.0130:.8f} {nipple_geometry_z:.8f}");
    model.component("comp1").geom("geom1").feature("{hub_cap_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{hub_cap_tag}").set("selresultshow", "all");
""",
                f"""
    model.component("comp1").geom("geom1").create("{trunk_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{trunk_tag}").set("semiaxes", "{radius * 0.0120:.8f} {radius * 0.0120:.8f} {radius * 0.0440:.8f}");
    model.component("comp1").geom("geom1").feature("{trunk_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{trunk_tag}").set("pos", "{nipple_geometry_x:.8f} {hub_y - radius * 0.0300:.8f} {nipple_geometry_z:.8f}");
    model.component("comp1").geom("geom1").feature("{trunk_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{trunk_tag}").set("selresultshow", "all");
""",
            ]
        )
        for lobe_id in sorted(lobe_groups):
            bulb = lobe_groups[lobe_id][0]
            bx = float(bulb["cx"])
            by = float(bulb["cy"])
            bz = float(bulb["cz"])
            bsx = float(bulb["sx"])
            bsy = float(bulb["sy"])
            bsz = float(bulb["sz"])
            ring_name = str(bulb.get("ring_name", "inner"))

            original = next((lob for lob in lobules if int(lob.get("lobe_id", -1)) == lobe_id), None)
            if original is None:
                continue
            bulb_sidecar = original.get("bulb_sidecar", [bx, by, bz])
            duct_mid = original.get("duct_mid", [bx, by, bz])
            duct_tip = original.get("duct_tip", [bx, by, bz])
            if not isinstance(bulb_sidecar, list) or len(bulb_sidecar) != 3:
                bulb_sidecar = [bx, by, bz]
            if not isinstance(duct_mid, list) or len(duct_mid) != 3:
                duct_mid = [bx, by, bz]
            if not isinstance(duct_tip, list) or len(duct_tip) != 3:
                duct_tip = [bx, by, bz]
            bulb_sidecar = [
                float(bulb_sidecar[0]) + lobule_alignment_dx,
                float(bulb_sidecar[1]),
                float(bulb_sidecar[2]) + lobule_alignment_dz,
            ]
            duct_mid = [
                float(duct_mid[0]) + lobule_alignment_dx,
                float(duct_mid[1]),
                float(duct_mid[2]) + lobule_alignment_dz,
            ]
            duct_tip = [
                float(duct_tip[0]) + lobule_alignment_dx,
                float(duct_tip[1]),
                float(duct_tip[2]) + lobule_alignment_dz,
            ]

            radial_x = bx - nipple_geometry_x
            radial_z = bz - nipple_geometry_z
            radial_norm = max((radial_x ** 2 + radial_z ** 2) ** 0.5, 1e-9)
            radial_x /= radial_norm
            radial_z /= radial_norm
            tangent_x = -radial_z
            tangent_z = radial_x

            petal_segment_tags: list[str] = []
            petal_segment_java_blocks: list[str] = []
            segment_count = (
                comsol_petal_segments_override
                if comsol_petal_segments_override > 0
                else (4 if fast_detail_mode else 8)
            )
            petal_span = 2.45 if ring_name == "outer" else 2.05
            petal_curve = 0.42 if ring_name == "outer" else 0.32
            petal_twist = 0.14 if ring_name == "outer" else 0.10
            for seg_idx in range(segment_count):
                t = seg_idx / max(segment_count - 1, 1)
                seg_tag = f"lobe_{lobe_id:02d}_petal_seg_{seg_idx + 1:02d}"
                petal_segment_tags.append(seg_tag)
                radial_shift = (-0.30 + petal_span * t) * bsx
                tangent_shift = (petal_curve * np.sin(np.pi * t) - petal_twist * t) * bsx
                seg_cx = bx + radial_x * radial_shift + tangent_x * tangent_shift
                seg_cy = by - (0.08 + 0.70 * t) * bsy
                seg_cz = bz + radial_z * radial_shift + tangent_z * tangent_shift
                seg_sx = max(bsx * (0.88 + 0.34 * np.sin(np.pi * t)), radius * 0.0068)
                seg_sy = max(bsy * (0.68 - 0.16 * t), radius * 0.0050)
                seg_sz = max(bsz * (0.82 + 0.26 * np.sin(np.pi * t)), radius * 0.0062)
                petal_segment_java_blocks.append(
                    f"""
    model.component("comp1").geom("geom1").create("{seg_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("semiaxes", "{seg_sx:.8f} {seg_sz:.8f} {seg_sy:.8f}");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("pos", "{seg_cx:.8f} {seg_cy:.8f} {seg_cz:.8f}");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("selresultshow", "all");
"""
                )

            petal_wing_tag = f"lobe_{lobe_id:02d}_petal_wing"
            wing_cx = bulb_sidecar[0] + tangent_x * (0.12 * bsx)
            wing_cy = bulb_sidecar[1] - 0.24 * bsy
            wing_cz = bulb_sidecar[2] + tangent_z * (0.12 * bsz)
            wing_sx = max(bsx * (1.16 if ring_name == "outer" else 1.05), radius * 0.0060)
            wing_sy = max(bsy * 0.48, radius * 0.0044)
            wing_sz = max(bsz * (1.12 if ring_name == "outer" else 1.02), radius * 0.0062)

            posterior_cap_tag = f"lobe_{lobe_id:02d}_posterior_cap"
            cap_cx = bx - radial_x * (0.60 * bsx)
            cap_cy = by - 0.66 * bsy
            cap_cz = bz - radial_z * (0.60 * bsz)
            cap_sx = max(bsx * 1.04, radius * 0.0070)
            cap_sy = max(bsy * 0.62, radius * 0.0050)
            cap_sz = max(bsz * 0.96, radius * 0.0062)

            duct_component_tags: list[str] = []
            duct_component_java_blocks: list[str] = []
            duct_start_x = bx - radial_x * (0.30 * bsx)
            duct_start_y = by + 0.02 * bsy
            duct_start_z = bz - radial_z * (0.30 * bsz)
            control_x = duct_mid[0]
            control_y = duct_mid[1]
            control_z = duct_mid[2]
            end_x = duct_tip[0]
            end_y = duct_tip[1]
            end_z = duct_tip[2]
            if comsol_duct_style == "ellipsoid_segments":
                segment_count = (
                    comsol_duct_segments_override
                    if comsol_duct_segments_override > 0
                    else (4 if fast_detail_mode else 7)
                )

                def duct_point(t: float) -> tuple[float, float, float]:
                    omt = 1.0 - t
                    return (
                        omt * omt * duct_start_x + 2.0 * omt * t * control_x + t * t * end_x,
                        omt * omt * duct_start_y + 2.0 * omt * t * control_y + t * t * end_y,
                        omt * omt * duct_start_z + 2.0 * omt * t * control_z + t * t * end_z,
                    )

                for seg_idx in range(1, segment_count + 1):
                    t0 = (seg_idx - 1) / segment_count
                    t1 = seg_idx / segment_count
                    tm = 0.5 * (t0 + t1)
                    p0 = duct_point(t0)
                    p1 = duct_point(t1)
                    mid_x = 0.5 * (p0[0] + p1[0])
                    mid_y = 0.5 * (p0[1] + p1[1])
                    mid_z = 0.5 * (p0[2] + p1[2])
                    span_x = abs(p1[0] - p0[0])
                    span_y = abs(p1[1] - p0[1])
                    span_z = abs(p1[2] - p0[2])
                    anterior_taper = 1.0 - 0.34 * tm
                    duct_radius = radius * (0.0135 + 0.0050 * (1.0 - tm)) * comsol_duct_radius_scale
                    seg_tag = f"lobe_{lobe_id:02d}_duct_seg_{seg_idx:02d}"
                    duct_component_tags.append(seg_tag)
                    seg_sx = max(0.62 * span_x + duct_radius, radius * 0.0064)
                    seg_sy = max(0.62 * span_y + 1.20 * duct_radius * anterior_taper, radius * 0.0100)
                    seg_sz = max(0.62 * span_z + duct_radius, radius * 0.0064)
                    duct_component_java_blocks.append(
                        f"""
    model.component("comp1").geom("geom1").create("{seg_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("semiaxes", "{seg_sx:.8f} {seg_sz:.8f} {seg_sy:.8f}");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("pos", "{mid_x:.8f} {mid_y:.8f} {mid_z:.8f}");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{seg_tag}").set("selresultshow", "all");
"""
                    )
            else:
                bead_count = (
                    comsol_duct_beads_override
                    if comsol_duct_beads_override > 0
                    else (6 if fast_detail_mode else 18)
                )
                for bead_idx in range(1, bead_count + 1):
                    t = bead_idx / bead_count
                    omt = 1.0 - t
                    px = omt * omt * duct_start_x + 2.0 * omt * t * control_x + t * t * end_x
                    py = omt * omt * duct_start_y + 2.0 * omt * t * control_y + t * t * end_y
                    pz = omt * omt * duct_start_z + 2.0 * omt * t * control_z + t * t * end_z
                    bead_tag = f"lobe_{lobe_id:02d}_duct_bead_{bead_idx:02d}"
                    duct_component_tags.append(bead_tag)
                    bead_rxy = max(radius * (0.0105 + 0.0055 * omt), radius * 0.0068)
                    bead_ry = max(radius * (0.0135 + 0.0065 * omt), radius * 0.0084)
                    duct_component_java_blocks.append(
                        f"""
    model.component("comp1").geom("geom1").create("{bead_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{bead_tag}").set("semiaxes", "{bead_rxy:.8f} {bead_rxy:.8f} {bead_ry:.8f}");
    model.component("comp1").geom("geom1").feature("{bead_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{bead_tag}").set("pos", "{px:.8f} {py:.8f} {pz:.8f}");
    model.component("comp1").geom("geom1").feature("{bead_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{bead_tag}").set("selresultshow", "all");
"""
                    )

            lobe_refinement_java_blocks.append(
                f"""
{"".join(petal_segment_java_blocks)}
    model.component("comp1").geom("geom1").create("{petal_wing_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{petal_wing_tag}").set("semiaxes", "{wing_sx:.8f} {wing_sz:.8f} {wing_sy:.8f}");
    model.component("comp1").geom("geom1").feature("{petal_wing_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{petal_wing_tag}").set("pos", "{wing_cx:.8f} {wing_cy:.8f} {wing_cz:.8f}");
    model.component("comp1").geom("geom1").feature("{petal_wing_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{petal_wing_tag}").set("selresultshow", "all");
    model.component("comp1").geom("geom1").create("{posterior_cap_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{posterior_cap_tag}").set("semiaxes", "{cap_sx:.8f} {cap_sz:.8f} {cap_sy:.8f}");
    model.component("comp1").geom("geom1").feature("{posterior_cap_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{posterior_cap_tag}").set("pos", "{cap_cx:.8f} {cap_cy:.8f} {cap_cz:.8f}");
    model.component("comp1").geom("geom1").feature("{posterior_cap_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{posterior_cap_tag}").set("selresultshow", "all");
{"".join(duct_component_java_blocks)}
"""
            )

            lobe_tag = f"anatomical_lobe_{lobe_id:02d}"
            anatomical_lobe_tags.append(lobe_tag)
            lobe_input_tags = [*petal_segment_tags, petal_wing_tag, posterior_cap_tag, *duct_component_tags]
            lobe_input_args = ", ".join(f'"{tag}"' for tag in lobe_input_tags)
            anatomical_lobe_java_blocks.append(
                f"""
    model.component("comp1").geom("geom1").create("{lobe_tag}", "Union");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").selection("input").set({lobe_input_args});
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("intbnd", "off");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("selresultshow", "all");
"""
            )
    elif lobe_groups:
        for lobe_id in sorted(lobe_groups):
            ordered_group = sorted(lobe_groups[lobe_id], key=lambda item: int(item["component_index"]))
            comp_tags = [str(spec["tag"]) for spec in ordered_group]
            bulb = next((spec for spec in ordered_group if str(spec["component_role"]) == "bulb"), ordered_group[0])
            duct = next((spec for spec in ordered_group if str(spec["component_role"]) == "duct"), ordered_group[-1])
            ring_name = str(bulb.get("ring_name", "inner"))

            bx = float(bulb["cx"])
            by = float(bulb["cy"])
            bz = float(bulb["cz"])
            bsx = float(bulb["sx"])
            bsy = float(bulb["sy"])
            bsz = float(bulb["sz"])
            dx = float(duct["cx"])
            dy = float(duct["cy"])
            dz = float(duct["cz"])
            dsx = float(duct["sx"])
            dsy = float(duct["sy"])
            dsz = float(duct["sz"])

            toward_x = nipple_geometry_x - bx
            toward_y = nipple_y - by
            toward_z = nipple_geometry_z - bz
            toward_norm = max((toward_x ** 2 + toward_y ** 2 + toward_z ** 2) ** 0.5, 1e-9)
            toward_x /= toward_norm
            toward_y /= toward_norm
            toward_z /= toward_norm

            tangent_x = -(bz - nipple_geometry_z)
            tangent_z = bx - nipple_geometry_x
            tangent_norm = max((tangent_x ** 2 + tangent_z ** 2) ** 0.5, 1e-9)
            tangent_x /= tangent_norm
            tangent_z /= tangent_norm

            radial_x = bx - nipple_geometry_x
            radial_z = bz - nipple_geometry_z
            radial_norm = max((radial_x ** 2 + radial_z ** 2) ** 0.5, 1e-9)
            radial_x /= radial_norm
            radial_z /= radial_norm

            bulb_sidecar_tag = f"lobe_{lobe_id:02d}_bulb_sidecar"
            bulb_sidecar_cx = bx + radial_x * (0.36 * bsx) - tangent_x * (0.18 * bsx)
            bulb_sidecar_cy = by - 0.16 * bsy
            bulb_sidecar_cz = bz + radial_z * (0.36 * bsz) + tangent_z * (0.18 * bsz)
            bulb_sidecar_sx = max(bsx * 0.62, radius * 0.006)
            bulb_sidecar_sy = max(bsy * 0.72, radius * 0.008)
            bulb_sidecar_sz = max(bsz * 0.58, radius * 0.006)

            duct_tip_tag = f"lobe_{lobe_id:02d}_duct_tip"
            curvature_scale = 0.45 if ring_name == "outer" else 0.20
            duct_tip_cx = dx + toward_x * (0.42 * dsy) + tangent_x * (curvature_scale * dsx)
            duct_tip_cy = dy + toward_y * (0.48 * dsy)
            duct_tip_cz = dz + toward_z * (0.42 * dsy) + tangent_z * (curvature_scale * dsz)
            duct_tip_sx = max(dsx * 0.82, radius * 0.005)
            duct_tip_sy = max(dsy * 0.96, radius * 0.010)
            duct_tip_sz = max(dsz * 0.82, radius * 0.005)

            lobe_refinement_java_blocks.append(
                f"""
    model.component("comp1").geom("geom1").create("{bulb_sidecar_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{bulb_sidecar_tag}").set("semiaxes", "{bulb_sidecar_sx:.8f} {bulb_sidecar_sz:.8f} {bulb_sidecar_sy:.8f}");
    model.component("comp1").geom("geom1").feature("{bulb_sidecar_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{bulb_sidecar_tag}").set("pos", "{bulb_sidecar_cx:.8f} {bulb_sidecar_cy:.8f} {bulb_sidecar_cz:.8f}");
    model.component("comp1").geom("geom1").feature("{bulb_sidecar_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{bulb_sidecar_tag}").set("selresultshow", "all");

    model.component("comp1").geom("geom1").create("{duct_tip_tag}", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("{duct_tip_tag}").set("semiaxes", "{duct_tip_sx:.8f} {duct_tip_sz:.8f} {duct_tip_sy:.8f}");
    model.component("comp1").geom("geom1").feature("{duct_tip_tag}").set("axistype", "y");
    model.component("comp1").geom("geom1").feature("{duct_tip_tag}").set("pos", "{duct_tip_cx:.8f} {duct_tip_cy:.8f} {duct_tip_cz:.8f}");
    model.component("comp1").geom("geom1").feature("{duct_tip_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{duct_tip_tag}").set("selresultshow", "all");
"""
            )

            lobe_union_inputs = ", ".join(f'"{tag}"' for tag in [*comp_tags, bulb_sidecar_tag, duct_tip_tag])
            lobe_tag = f"anatomical_lobe_{lobe_id:02d}"
            anatomical_lobe_tags.append(lobe_tag)
            anatomical_lobe_java_blocks.append(
                f"""
    model.component("comp1").geom("geom1").create("{lobe_tag}", "Union");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").selection("input").set({lobe_union_inputs});
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("intbnd", "off");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("{lobe_tag}").set("selresultshow", "all");
"""
            )

    union_source_tags = [*(anatomical_lobe_tags or lobule_feature_tags), *shared_duct_tags]
    lobule_union_inputs = ", ".join(f'"{tag}"' for tag in union_source_tags)
    use_lobules = bool(union_source_tags)
    lobule_helper_methods: list[str] = []
    lobule_helper_invocations: list[str] = []

    if use_template_lobes and anatomical_lobe_java_blocks:
        if shared_duct_java_blocks:
            shared_method_name = "buildSharedDuctHub"
            lobule_helper_invocations.append(f"    {shared_method_name}(model);\n")
            lobule_helper_methods.append(
                f"""
  private static void {shared_method_name}(Model model) {{
{"".join(shared_duct_java_blocks)}
  }}
"""
            )
        for method_index, (refinement_block, lobe_union_block) in enumerate(
            zip(lobe_refinement_java_blocks, anatomical_lobe_java_blocks),
            start=1,
        ):
            method_name = f"buildAnatomicalLobe{method_index:02d}"
            lobule_helper_invocations.append(f"    {method_name}(model);\n")
            lobule_helper_methods.append(
                f"""
  private static void {method_name}(Model model) {{
{refinement_block}
{lobe_union_block}
  }}
"""
            )
    else:
        primitive_blocks = [*lobule_java_blocks, *shared_duct_java_blocks]
        for chunk_index, chunk in enumerate(_chunk_list(primitive_blocks, 40), start=1):
            method_name = f"buildLobulePrimitiveChunk{chunk_index:02d}"
            lobule_helper_invocations.append(f"    {method_name}(model);\n")
            lobule_helper_methods.append(
                f"""
  private static void {method_name}(Model model) {{
{"".join(chunk)}
  }}
"""
            )
        for chunk_index, chunk in enumerate(_chunk_list(anatomical_lobe_java_blocks, 20), start=1):
            method_name = f"buildLobuleUnionChunk{chunk_index:02d}"
            lobule_helper_invocations.append(f"    {method_name}(model);\n")
            lobule_helper_methods.append(
                f"""
  private static void {method_name}(Model model) {{
{"".join(chunk)}
  }}
"""
            )

    lobule_helper_methods_java = "".join(lobule_helper_methods)
    lobule_helper_invocations_java = "".join(lobule_helper_invocations)
    lobule_builder_method_java = (
        f"""
  private static String[] buildGlandLobules(Model model) {{
{lobule_helper_invocations_java}
    model.component("comp1").geom("geom1").create("gland_lobules", "Union");
    model.component("comp1").geom("geom1").feature("gland_lobules").selection("input").set({lobule_union_inputs});
    model.component("comp1").geom("geom1").feature("gland_lobules").set("intbnd", "off");
    model.component("comp1").geom("geom1").feature("gland_lobules").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("gland_lobules").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("gland_lobules").set("selresultshow", "all");
    model.component("comp1").geom("geom1").run("gland_lobules");
    return model.component("comp1").geom("geom1").feature("gland_lobules").objectNames();
  }}
"""
        if use_lobules
        else ""
    )
    use_lobule_source_union = use_lobules and (
        glandular_lobule_include_subareolar_core
        or glandular_lobule_include_subareolar_bridge
        or glandular_lobule_include_reference_ellipsoid
    )
    lobule_source_union_java = ""
    if use_lobule_source_union:
        lobule_source_inputs = ['"gland_lobules"']
        if glandular_lobule_include_subareolar_core:
            lobule_source_inputs.append('"gland_nipple_core"')
        if glandular_lobule_include_subareolar_bridge:
            lobule_source_inputs.append('"gland_subareolar_bridge"')
        if glandular_lobule_include_reference_ellipsoid:
            lobule_source_inputs.append('"gland_seed"')
        lobule_source_union_java = f"""
    model.component("comp1").geom("geom1").create("gland_lobule_source", "Union");
    model.component("comp1").geom("geom1").feature("gland_lobule_source").selection("input").set({", ".join(lobule_source_inputs)});
    model.component("comp1").geom("geom1").feature("gland_lobule_source").set("intbnd", "off");
    model.component("comp1").geom("geom1").feature("gland_lobule_source").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("gland_lobule_source").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("gland_lobule_source").set("selresultshow", "all");
    model.component("comp1").geom("geom1").run("gland_lobule_source");
    String[] glandLobuleSourceObjs = model.component("comp1").geom("geom1").feature("gland_lobule_source").objectNames();
"""
    gland_source_tag = (
        "gland_lobule_source"
        if use_lobule_source_union
        else ("gland_lobules" if use_lobules else "gland_seed_with_nipple")
    )
    gland_source_objects_var = (
        "glandLobuleSourceObjs"
        if use_lobule_source_union
        else ("glandLobuleObjs" if use_lobules else "glandSeedWithNippleObjs")
    )
    needs_gland_seed = (not use_lobules) or glandular_lobule_include_reference_ellipsoid
    needs_gland_nipple_core = (not use_lobules) or glandular_lobule_include_subareolar_core
    needs_gland_subareolar_bridge = use_lobules and glandular_lobule_include_subareolar_bridge
    needs_gland_seed_with_nipple = not use_lobules
    lobule_union_java = (
        f"""
    String[] glandLobuleObjs = buildGlandLobules(model);
{lobule_source_union_java}
"""
        if use_lobules
        else ""
    )
    skin_solid_hyperelastic_java = f"""
    if ({str(volumetric_skin_enabled).lower()}) {{
      boolean skinSolidHyperelasticReady = tryCreateMooneyRivlinFeature(
        model,
        "solid",
        "hmat_skin_solid",
        3,
        "geom1_skin_layer_dom",
        "skin_density",
        "skin_c10",
        "skin_c01",
        "skin_bulk_modulus",
        hyperelasticNotes
      );
      if (skinSolidHyperelasticReady) {{
        tryCreateRayleighDampingSubfeature(model, "solid", "hmat_skin_solid", "dmp_skin_solid", "mass_damping_alpha", "stiffness_damping_beta", hyperelasticNotes);
      }}
      solidHyperelasticReady = skinSolidHyperelasticReady && solidHyperelasticReady;
    }}
"""

    shell_physics_java = ""
    if shell_physics_enabled:
        shell_physics_java = f"""
    StringBuilder hyperelasticNotes = new StringBuilder();
    boolean solidHyperelasticReady = true;
    boolean adiposeHyperelasticReady = tryCreateMooneyRivlinFeature(
      model,
      "solid",
      "hmat_adipose",
      3,
      "geom1_adipose_diff_dom",
      "adipose_density_eff",
      "adipose_c10_eff",
      "adipose_c01_eff",
      "adipose_bulk_modulus",
      hyperelasticNotes
    );
    if (adiposeHyperelasticReady) {{
      tryCreateRayleighDampingSubfeature(model, "solid", "hmat_adipose", "dmp_adipose", "mass_damping_alpha", "stiffness_damping_beta", hyperelasticNotes);
    }}
    solidHyperelasticReady = adiposeHyperelasticReady && solidHyperelasticReady;
    boolean glandularHyperelasticReady = tryCreateMooneyRivlinFeature(
      model,
      "solid",
      "hmat_glandular",
      3,
      "geom1_gland_clip_dom",
      "glandular_density_eff",
      "glandular_c10_eff",
      "glandular_c01_eff",
      "glandular_bulk_modulus",
      hyperelasticNotes
    );
    if (glandularHyperelasticReady) {{
      tryCreateRayleighDampingSubfeature(model, "solid", "hmat_glandular", "dmp_glandular", "mass_damping_alpha", "stiffness_damping_beta", hyperelasticNotes);
    }}
    solidHyperelasticReady = glandularHyperelasticReady && solidHyperelasticReady;
{skin_solid_hyperelastic_java}
    if (solidHyperelasticReady) {{
      tryRestrictLinearElasticFeature(model, "solid", "geom1_chest_cyl_dom", hyperelasticNotes);
    }} else {{
      hyperelasticNotes.append("Solid Mooney-Rivlin scaffold incomplete; keeping default linear elastic fallback on solid.\\n");
    }}

    StringBuilder shellScaffoldNotes = new StringBuilder();
    String shellPhysicsTag = tryCreatePhysics(model, "shell1", new String[] {{ "Shell", "shell" }}, "geom1", shellScaffoldNotes);
    if (shellPhysicsTag != null) {{
      model.component("comp1").physics(shellPhysicsTag).selection().named("geom1_breast_outer_bnd");
      tryConfigureShellThickness(model, shellPhysicsTag, "skin_shell_thickness", shellScaffoldNotes);
      boolean shellHyperelasticReady = tryCreateMooneyRivlinFeature(
        model,
        shellPhysicsTag,
        "hmat_skin",
        2,
        "geom1_breast_outer_bnd",
        "skin_density",
        "skin_c10",
        "skin_c01",
        "skin_bulk_modulus",
        hyperelasticNotes
      );
      if (shellHyperelasticReady) {{
        tryCreateRayleighDampingSubfeature(model, shellPhysicsTag, "hmat_skin", "dmp_skin", "mass_damping_alpha", "stiffness_damping_beta", hyperelasticNotes);
        tryDeactivateLinearElasticFeatures(model, shellPhysicsTag, hyperelasticNotes);
      }} else {{
        hyperelasticNotes.append("Shell Mooney-Rivlin scaffold incomplete; leaving default shell constitutive fallback active.\\n");
      }}
    }}
    if ({str(shell_coupling_enabled).lower()} && shellPhysicsTag != null) {{
      tryCreateSolidThinStructureConnection(
        model,
        "sthin1",
        new String[] {{ "SolidThinStructureConnection", "SolidShellConnection", "solidthin", "sthin" }},
        "geom1",
        "geom1_breast_outer_bnd",
        "solid",
        shellPhysicsTag,
        shellScaffoldNotes
      );
    }}
    // Do not store free-form debug notes in COMSOL parameters; they are parsed as expressions.
"""
    else:
        shell_physics_java = """
    StringBuilder hyperelasticNotes = new StringBuilder();
    boolean solidHyperelasticReady = true;
    boolean adiposeHyperelasticReady = tryCreateMooneyRivlinFeature(
      model,
      "solid",
      "hmat_adipose",
      3,
      "geom1_adipose_diff_dom",
      "adipose_density_eff",
      "adipose_c10_eff",
      "adipose_c01_eff",
      "adipose_bulk_modulus",
      hyperelasticNotes
    );
    if (adiposeHyperelasticReady) {
      tryCreateRayleighDampingSubfeature(model, "solid", "hmat_adipose", "dmp_adipose", "mass_damping_alpha", "stiffness_damping_beta", hyperelasticNotes);
    }
    solidHyperelasticReady = adiposeHyperelasticReady && solidHyperelasticReady;
    boolean glandularHyperelasticReady = tryCreateMooneyRivlinFeature(
      model,
      "solid",
      "hmat_glandular",
      3,
      "geom1_gland_clip_dom",
      "glandular_density_eff",
      "glandular_c10_eff",
      "glandular_c01_eff",
      "glandular_bulk_modulus",
      hyperelasticNotes
    );
    if (glandularHyperelasticReady) {
      tryCreateRayleighDampingSubfeature(model, "solid", "hmat_glandular", "dmp_glandular", "mass_damping_alpha", "stiffness_damping_beta", hyperelasticNotes);
    }
    solidHyperelasticReady = glandularHyperelasticReady && solidHyperelasticReady;
{skin_solid_hyperelastic_java}
    if (solidHyperelasticReady) {
      tryRestrictLinearElasticFeature(model, "solid", "geom1_chest_cyl_dom", hyperelasticNotes);
    } else {
      hyperelasticNotes.append("Solid Mooney-Rivlin scaffold incomplete; keeping default linear elastic fallback on solid.\\n");
    }
    // Do not store free-form debug notes in COMSOL parameters; they are parsed as expressions.
"""
    shell_physics_java = shell_physics_java.replace(
        "{skin_solid_hyperelastic_java}",
        skin_solid_hyperelastic_java,
    )

    java_source = f"""import com.comsol.model.*;
import com.comsol.model.util.*;

public class {class_name} {{
  public static Model run() {{
    ModelUtil.initStandalone(true);
    Model model = ModelUtil.create("Model");
    model.label("{result_mph.name}");
    model.modelPath("{output_dir_java}");

    model.param().set("breast_radius", "{build_plan_summary["geometry"].get("radius", 0.07)}[m]");
    model.param().set("chest_thickness", "{build_plan_summary["geometry"].get("thickness_chest_wall", 0.002)}[m]");
    model.param().set("skin_shell_thickness", "{skin_shell_thickness_m:.10f}[m]");
    model.param().set("volumetric_skin_thickness", "{volumetric_skin_thickness_m:.10f}[m]");
    model.param().set("chest_curve_depth", "{chest_curve_depth:.10f}[m]");
    model.param().set("chestwall_curve_center_x_offset", "{chestwall_curve_center_x_offset_m:.10f}[m]");
    model.param().set("chest_curve_si_depth", "{chest_curve_si_depth:.10f}[m]");
    model.param().set("chest_curve_radius", "{chest_curve_radius:.10f}[m]");
    model.param().set("chest_curve_center_y", "{-chest_curve_center_y:.10f}[m]");
    model.param().set("transverse_curve_radius", "{transverse_curve_radius:.10f}[m]");
    model.param().set("transverse_curve_center_y", "{-transverse_curve_center_y:.10f}[m]");
    model.param().set("si_curve_radius", "{si_curve_radius:.10f}[m]");
    model.param().set("si_curve_center_y", "{-si_curve_center_y:.10f}[m]");
    model.param().set("transverse_volume_preserve_y_scale", "{transverse_volume_preserve_y_scale:.10f}");
    model.param().set("transverse_volume_preserve_gland_y_scale", "{transverse_volume_preserve_gland_y_scale:.10f}");
    model.param().set("cooper_effective_modulus", "{cooper_effective_modulus:.10f}[Pa]");
    model.param().set("cooper_reference_length", "{cooper_reference_length:.10f}[m]");
    model.param().set("cooper_area_fraction", "{cooper_area_fraction:.10f}");
    model.param().set("cooper_spring_ky", "{cooper_spring_ky:.10f}[N/m^3]");
    model.param().set("cooper_spring_kxz", "{cooper_spring_kxz:.10f}[N/m^3]");
    model.param().set("cooper_skin_web_ky", "{cooper_skin_web_ky:.10f}[N/m^3]");
    model.param().set("cooper_skin_web_kxz", "{cooper_skin_web_kxz:.10f}[N/m^3]");
    model.param().set("cooper_gland_web_ky", "{cooper_gland_web_ky:.10f}[N/m^3]");
    model.param().set("cooper_gland_web_kxz", "{cooper_gland_web_kxz:.10f}[N/m^3]");
    model.param().set("cooper_damping", "{cooper_damping:.10f}[N*s/m^3]");
    model.param().set("mesh_density_hint", "{build_plan_summary["mesh"].get("density", 140.0)}");
    model.param().set("skin_density", "{build_plan_summary["material"].get("skin", {}).get("density", 1100.0)}[kg/m^3]");
    model.param().set("adipose_density", "{build_plan_summary["material"].get("adipose", {}).get("density", 911.0)}[kg/m^3]");
    model.param().set("glandular_density", "{build_plan_summary["material"].get("glandular", {}).get("density", 911.0)}[kg/m^3]");
    model.param().set("chest_density", "{chest_density:.12f}[kg/m^3]");
    model.param().set("pectoralis_density", "{pectoralis_density:.12f}[kg/m^3]");
    model.param().set("g_acc", "9.81[m/s^2]");
    model.param().set("t_gravity_end", "{gravity_duration_s:.12f}[s]");
    model.param().set("t_dynamic_start", "{dynamic_start_s:.12f}[s]");
    model.param().set("t_dynamic_end", "{dynamic_end_s:.12f}[s]");
    model.param().set("t_jump_hold", "{dynamic_motion_hold_s:.12f}[s]");
    model.param().set("t_jump_start", "t_dynamic_start+t_jump_hold");
    model.param().set("t_jump_duration", "{jump_duration_s:.12f}[s]");
    model.param().set("t_pulse_duration", "{pulse_duration_s:.12f}[s]");
    model.param().set("t_excitation_duration", "{dynamic_excitation_duration_s:.12f}[s]");
    model.param().set("jump_v0", "{jump_initial_velocity:.12f}[m/s]");
    model.param().set("jump_amp", "{support_displacement_amplitude_m:.12f}[m]");
    model.param().set("pulse_acc_amp", "{dynamic_acceleration_amplitude_g:.12f}");
    model.param().set("tumor_enabled", "{1 if tumor_enabled else 0}");
    model.param().set("tumor_density", "{tumor_density:.12f}[kg/m^3]");
    model.param().set("tumor_radius", "{tumor_radius:.12f}[m]");
    model.param().set("tumor_x", "{tumor_x:.12f}[m]");
    model.param().set("tumor_y", "{tumor_y:.12f}[m]");
    model.param().set("tumor_z", "{tumor_z:.12f}[m]");
    model.param().set("tumor_coef1_adipose", "{tumor_coef1_adipose:.12f}[Pa]");
    model.param().set("tumor_coef2_adipose", "{tumor_coef2_adipose:.12f}[Pa]");
    model.param().set("tumor_coef1_glandular", "{tumor_coef1_glandular:.12f}[Pa]");
    model.param().set("tumor_coef2_glandular", "{tumor_coef2_glandular:.12f}[Pa]");
    model.param().set("tumor_E_adipose", "{tumor_E_adipose:.12f}[Pa]");
    model.param().set("tumor_E_glandular", "{tumor_E_glandular:.12f}[Pa]");
    model.param().set("t_output_step", "{output_dt_s:.12f}[s]");
    model.param().set("t_pulse_output_step", "{pulse_output_dt_s:.12f}[s]");
    model.param().set("mass_damping_alpha", "{mass_damping_alpha:.12f}[1/s]");
    model.param().set("stiffness_damping_beta", "{stiffness_damping_beta:.12f}[s]");
    model.param().set("skin_bulk_modulus", "{skin_bulk_modulus:.12f}[Pa]");
    model.param().set("skin_c10", "{skin_coef1:.12f}[Pa]");
    model.param().set("skin_c01", "{skin_coef2:.12f}[Pa]");
    model.param().set("adipose_bulk_modulus", "{adipose_bulk_modulus:.12f}[Pa]");
    model.param().set("adipose_c10", "{adipose_coef1:.12f}[Pa]");
    model.param().set("adipose_c01", "{adipose_coef2:.12f}[Pa]");
    model.param().set("glandular_bulk_modulus", "{glandular_bulk_modulus:.12f}[Pa]");
    model.param().set("glandular_c10", "{glandular_coef1:.12f}[Pa]");
    model.param().set("glandular_c01", "{glandular_coef2:.12f}[Pa]");
    model.param().set("skin_E", "{skin_E:.12f}[Pa]");
    model.param().set("skin_nu", "{skin_nu:.12f}");
    model.param().set("adipose_E", "{adipose_E:.12f}[Pa]");
    model.param().set("adipose_nu", "{adipose_nu:.12f}");
    model.param().set("glandular_E", "{glandular_E:.12f}[Pa]");
    model.param().set("glandular_nu", "{glandular_nu:.12f}");
    model.param().set("chest_E", "{chest_E:.12f}[Pa]");
    model.param().set("chest_nu", "{chest_nu:.12f}");
    model.param().set("pectoralis_E", "{pectoralis_E:.12f}[Pa]");
    model.param().set("pectoralis_nu", "{pectoralis_nu:.12f}");

    // Base component/geometry
    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").geom("geom1").lengthUnit("m");
    model.component("comp1").variable().create("var1");
    model.component("comp1").variable("var1").set("grav_scale_t", "if(t<t_gravity_end,t/t_gravity_end,1)");
    model.component("comp1").variable("var1").set("tumor_mask", "if(tumor_enabled>0.5,if((x-tumor_x)^2+(y-tumor_y)^2+(z-tumor_z)^2<=tumor_radius^2,1,0),0)");
    model.component("comp1").variable("var1").set("adipose_density_eff", "adipose_density+tumor_mask*(tumor_density-adipose_density)");
    model.component("comp1").variable("var1").set("adipose_E_eff", "adipose_E+tumor_mask*(tumor_E_adipose-adipose_E)");
    model.component("comp1").variable("var1").set("adipose_c10_eff", "adipose_c10+tumor_mask*(tumor_coef1_adipose)");
    model.component("comp1").variable("var1").set("adipose_c01_eff", "adipose_c01+tumor_mask*(tumor_coef2_adipose)");
    model.component("comp1").variable("var1").set("glandular_density_eff", "glandular_density+tumor_mask*(tumor_density-glandular_density)");
    model.component("comp1").variable("var1").set("glandular_E_eff", "glandular_E+tumor_mask*(tumor_E_glandular-glandular_E)");
    model.component("comp1").variable("var1").set("glandular_c10_eff", "glandular_c10+tumor_mask*(tumor_coef1_glandular)");
    model.component("comp1").variable("var1").set("glandular_c01_eff", "glandular_c01+tumor_mask*(tumor_coef2_glandular)");
    model.component("comp1").variable("var1").set(
      "jump_z_t",
      {jump_z_expression_java}
    );
    model.component("comp1").variable("var1").set(
      "inertial_acc_z_t",
      {inertial_acc_expression_java}
    );
    model.component("comp1").variable("var1").set("disp_mag", "sqrt(u^2+v^2+w^2)");
    model.component("comp1").variable("var1").set("disp_mag_mm", "disp_mag/1[mm]");
    model.component("comp1").variable("var1").set("u_mm", "u/1[mm]");
    model.component("comp1").variable("var1").set("v_mm", "v/1[mm]");
    model.component("comp1").variable("var1").set("w_mm", "w/1[mm]");
    model.component("comp1").variable("var1").set("vm_kpa", "solid.mises/1[kPa]");
    model.component("comp1").variable("var1").set("coop_nipple_fx", "0[N/m^2]");
    model.component("comp1").variable("var1").set("coop_nipple_fy", "{coop_nipple_fy_expr}");
    model.component("comp1").variable("var1").set("coop_nipple_fz", "0[N/m^2]");
    model.component("comp1").variable("var1").set("coop_skin_fx", "0[N/m^2]");
    model.component("comp1").variable("var1").set("coop_skin_fy", "{coop_skin_fy_expr}");
    model.component("comp1").variable("var1").set("coop_skin_fz", "0[N/m^2]");
    model.component("comp1").variable("var1").set("coop_gland_fx", "0[N/m^2]");
    model.component("comp1").variable("var1").set("coop_gland_fy", "{coop_gland_fy_expr}");
    model.component("comp1").variable("var1").set("coop_gland_fz", "0[N/m^2]");
    createTumorPreviewComponent(model);

    // Source-case dynamic study scaffold: gravity ramp first, then parabolic chest motion.
    model.study().create("std1");
    model.study("std1").create("time", "Transient");
    model.study("std1").feature("time").set(
      "tlist",
      "range(0,t_output_step,t_jump_start-2*t_output_step) "
      + "range(t_jump_start-2*t_output_step,t_pulse_output_step,t_jump_start+t_excitation_duration+2*t_output_step) "
      + "range(t_jump_start+t_excitation_duration+2*t_output_step,t_output_step,t_dynamic_end)"
    );

    // Geometry scaffold matching the current source-case baseline more closely.
    if ({str(transverse_volume_preserving_enabled or outer_shape_scale_x != 1.0 or outer_shape_scale_y != 1.0 or outer_shape_scale_z != 1.0).lower()}) {{
      model.component("comp1").geom("geom1").create("sph_outer", "Ellipsoid");
      model.component("comp1").geom("geom1").feature("sph_outer").set("semiaxes", "breast_radius*{outer_shape_scale_x:.8f} breast_radius*{outer_shape_scale_z:.8f} breast_radius*transverse_volume_preserve_y_scale*{outer_shape_scale_y:.8f}");
    }} else {{
      model.component("comp1").geom("geom1").create("sph_outer", "Sphere");
      model.component("comp1").geom("geom1").feature("sph_outer").set("r", "breast_radius");
    }}
    model.component("comp1").geom("geom1").feature("sph_outer").set("pos", "0 0 0");
    model.component("comp1").geom("geom1").feature("sph_outer").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("sph_outer").set("selresultshow", "all");

    model.component("comp1").geom("geom1").create("nipple_outer", "Ellipsoid");
    model.component("comp1").geom("geom1").feature("nipple_outer").set("semiaxes", "{nipple_outer_radius_x:.8f} {nipple_outer_radius_z:.8f} {nipple_outer_radius_y:.8f}");
    trySetLocalSurfaceAxis(model, "nipple_outer", {str(normal_alignment_active).lower()}, {nipple_surface_normal_x:.12f}, {nipple_surface_normal_y:.12f}, {nipple_surface_normal_z:.12f});
    model.component("comp1").geom("geom1").feature("nipple_outer").set("pos", "{nipple_outer_center_x:.8f} {nipple_outer_center_y:.8f} {nipple_outer_center_z:.8f}");
    model.component("comp1").geom("geom1").feature("nipple_outer").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("nipple_outer").set("selresultshow", "all");

{inferior_fullness_java}
{lateral_fullness_java}

    String[] breastBaseObjs;
    String[] chestObjs = new String[0];
    String[] thoraxKeepRegObjs = new String[0];
    if ({str(curved_chestwall_enabled).lower()}) {{
      model.component("comp1").geom("geom1").create("thorax_keep_blk", "Block");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("size", "{2.0 * support_geometry_half_x:.8f} {outer_keep_y_size:.8f} {2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("pos", "{-support_geometry_half_x:.8f} 0 {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("thorax_keep", "Cylinder");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("axistype", "x");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("r", "chest_curve_radius");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("h", "{2.0 * support_geometry_half_x:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("pos", "{-support_geometry_half_x:.8f} chest_curve_center_y 0");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("thorax_keep_reg", "Difference");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").selection("input").set("thorax_keep_blk");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").selection("input2").set("thorax_keep");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("thorax_keep_reg");
      thoraxKeepRegObjs = model.component("comp1").geom("geom1").feature("thorax_keep_reg").objectNames();

      if ({str(conformal_chestwall_support_enabled).lower()}) {{
        model.component("comp1").geom("geom1").create("chest_trim_blk", "Block");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("size", "{2.0 * support_geometry_half_x:.8f} chest_thickness+{support_depth_for_selection:.10f}+{2.0 * chest_overlap:.10f} {2.0 * outer_support_half_z:.8f}");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("pos", "{-support_geometry_half_x:.8f} -chest_thickness-{chest_overlap:.10f} {-outer_support_half_z:.8f}");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresultshow", "all");

        model.component("comp1").geom("geom1").create("chest_cyl", "Difference");
        model.component("comp1").geom("geom1").feature("chest_cyl").selection("input").set("chest_trim_blk");
        model.component("comp1").geom("geom1").feature("chest_cyl").selection("input2").set(thoraxKeepRegObjs);
        model.component("comp1").geom("geom1").feature("chest_cyl").set("keepsubtract", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("intbnd", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("propagatesel", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("selresultshow", "all");
        model.component("comp1").geom("geom1").run("chest_cyl");
        chestObjs = model.component("comp1").geom("geom1").feature("chest_cyl").objectNames();
      }}

      model.component("comp1").geom("geom1").create("breast_base", "Intersection");
      model.component("comp1").geom("geom1").feature("breast_base").selection("input").set("sph_outer", "thorax_keep_reg");
      model.component("comp1").geom("geom1").feature("breast_base").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("breast_base");
      breastBaseObjs = model.component("comp1").geom("geom1").feature("breast_base").objectNames();
    }} else if ({str(transverse_chestwall_enabled).lower()}) {{
      model.component("comp1").geom("geom1").create("thorax_keep_blk", "Block");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("size", "{2.0 * support_geometry_half_x:.8f} {outer_keep_y_size:.8f} {2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("pos", "{-support_geometry_half_x:.8f} 0 {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_blk").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("thorax_keep", "Cylinder");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("axistype", "z");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("r", "transverse_curve_radius");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("h", "{2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("pos", "chestwall_curve_center_x_offset transverse_curve_center_y {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep").set("selresultshow", "all");

      String thoraxKeepVoidTag = "thorax_keep";
      if ({str(si_chestwall_enabled).lower()}) {{
        model.component("comp1").geom("geom1").create("thorax_keep_si", "Cylinder");
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("r", "si_curve_radius");
{thorax_keep_si_axis_java}
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("thorax_keep_si").set("selresultshow", "all");

        model.component("comp1").geom("geom1").create("thorax_keep_voids", "Union");
        model.component("comp1").geom("geom1").feature("thorax_keep_voids").selection("input").set("thorax_keep", "thorax_keep_si");
        model.component("comp1").geom("geom1").feature("thorax_keep_voids").set("intbnd", "on");
        model.component("comp1").geom("geom1").feature("thorax_keep_voids").set("propagatesel", "on");
        model.component("comp1").geom("geom1").feature("thorax_keep_voids").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("thorax_keep_voids").set("selresultshow", "all");
        model.component("comp1").geom("geom1").run("thorax_keep_voids");
        thoraxKeepVoidTag = "thorax_keep_voids";
      }}

      model.component("comp1").geom("geom1").create("thorax_keep_reg", "Difference");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").selection("input").set("thorax_keep_blk");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").selection("input2").set(thoraxKeepVoidTag);
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_keep_reg").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("thorax_keep_reg");
      thoraxKeepRegObjs = model.component("comp1").geom("geom1").feature("thorax_keep_reg").objectNames();

      if ({str(conformal_chestwall_support_enabled).lower()}) {{
        model.component("comp1").geom("geom1").create("chest_trim_blk", "Block");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("size", "{2.0 * support_geometry_half_x:.8f} chest_thickness+{support_depth_for_selection:.10f}+{2.0 * chest_overlap:.10f} {2.0 * outer_support_half_z:.8f}");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("pos", "{-support_geometry_half_x:.8f} -chest_thickness-{chest_overlap:.10f} {-outer_support_half_z:.8f}");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresultshow", "all");

        model.component("comp1").geom("geom1").create("chest_cyl", "Difference");
        model.component("comp1").geom("geom1").feature("chest_cyl").selection("input").set("chest_trim_blk");
        model.component("comp1").geom("geom1").feature("chest_cyl").selection("input2").set(thoraxKeepRegObjs);
        model.component("comp1").geom("geom1").feature("chest_cyl").set("keepsubtract", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("intbnd", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("propagatesel", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("selresultshow", "all");
        model.component("comp1").geom("geom1").run("chest_cyl");
        chestObjs = model.component("comp1").geom("geom1").feature("chest_cyl").objectNames();
      }}

      model.component("comp1").geom("geom1").create("breast_base", "Intersection");
      model.component("comp1").geom("geom1").feature("breast_base").selection("input").set("sph_outer", "thorax_keep_reg");
      model.component("comp1").geom("geom1").feature("breast_base").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("breast_base");
      breastBaseObjs = model.component("comp1").geom("geom1").feature("breast_base").objectNames();
    }} else {{
      model.component("comp1").geom("geom1").create("blk_half", "Block");
      model.component("comp1").geom("geom1").feature("blk_half").set("size", "{2.0 * support_geometry_half_x:.8f} {outer_keep_y_size:.8f} {2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("blk_half").set("pos", "{-support_geometry_half_x:.8f} 0 {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("blk_half").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("blk_half").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("breast_base", "Intersection");
      model.component("comp1").geom("geom1").feature("breast_base").selection("input").set("sph_outer", "blk_half");
      model.component("comp1").geom("geom1").feature("breast_base").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("breast_base").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("breast_base");
      breastBaseObjs = model.component("comp1").geom("geom1").feature("breast_base").objectNames();
    }}

    model.component("comp1").geom("geom1").create("breast_outer", "Union");
    String[] breastOuterInput = new String[breastBaseObjs.length + {len(breast_outer_extra_tags)}];
    System.arraycopy(breastBaseObjs, 0, breastOuterInput, 0, breastBaseObjs.length);
{breast_outer_extra_assignments}
    model.component("comp1").geom("geom1").feature("breast_outer").selection("input").set(breastOuterInput);
    model.component("comp1").geom("geom1").feature("breast_outer").set("intbnd", "on");
    model.component("comp1").geom("geom1").feature("breast_outer").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("breast_outer").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("breast_outer").set("selresultshow", "all");
    model.component("comp1").geom("geom1").run("breast_outer");
    String[] breastOuterObjs = model.component("comp1").geom("geom1").feature("breast_outer").objectNames();
    String[] breastCoreObjs = breastOuterObjs;
    String[] skinLayerObjs = new String[0];
    if ({str(volumetric_skin_enabled).lower()}) {{
      if ({str(transverse_volume_preserving_enabled or outer_shape_scale_x != 1.0 or outer_shape_scale_y != 1.0 or outer_shape_scale_z != 1.0).lower()}) {{
        model.component("comp1").geom("geom1").create("skin_core_raw", "Ellipsoid");
        model.component("comp1").geom("geom1").feature("skin_core_raw").set(
          "semiaxes",
          "{skin_core_semiaxis_x:.10f}[m] {skin_core_semiaxis_z:.10f}[m] {skin_core_semiaxis_y:.10f}[m]"
        );
      }} else {{
        model.component("comp1").geom("geom1").create("skin_core_raw", "Sphere");
        model.component("comp1").geom("geom1").feature("skin_core_raw").set("r", "{skin_core_semiaxis_x:.10f}[m]");
      }}
      model.component("comp1").geom("geom1").feature("skin_core_raw").set("pos", "0 0 0");
      model.component("comp1").geom("geom1").feature("skin_core_raw").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("skin_core_raw").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("skin_core", "Intersection");
      model.component("comp1").geom("geom1").feature("skin_core").selection("input").set("skin_core_raw", breastOuterObjs[0]);
      model.component("comp1").geom("geom1").feature("skin_core").set("keep", "on");
      model.component("comp1").geom("geom1").feature("skin_core").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("skin_core").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("skin_core").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("skin_core").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("skin_core");
      breastCoreObjs = model.component("comp1").geom("geom1").feature("skin_core").objectNames();

      model.component("comp1").geom("geom1").create("skin_layer", "Difference");
      model.component("comp1").geom("geom1").feature("skin_layer").selection("input").set(breastOuterObjs);
      model.component("comp1").geom("geom1").feature("skin_layer").selection("input2").set(breastCoreObjs);
      model.component("comp1").geom("geom1").feature("skin_layer").set("keepsubtract", "on");
      model.component("comp1").geom("geom1").feature("skin_layer").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("skin_layer").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("skin_layer").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("skin_layer").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("skin_layer");
      skinLayerObjs = model.component("comp1").geom("geom1").feature("skin_layer").objectNames();
    }}

    if ({str(curved_chestwall_enabled).lower()}) {{
      model.component("comp1").geom("geom1").create("thorax_outer", "Cylinder");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("axistype", "x");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("r", "chest_curve_radius+chest_thickness");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("h", "{2.0 * support_geometry_half_x:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("pos", "{-support_geometry_half_x:.8f} chest_curve_center_y 0");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("chest_trim_blk", "Block");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("size", "{2.0 * support_geometry_half_x:.8f} chest_thickness+chest_curve_depth+{chest_overlap:.10f} {2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("pos", "{-support_geometry_half_x:.8f} -chest_thickness {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("chest_band", "Difference");
      model.component("comp1").geom("geom1").feature("chest_band").selection("input").set("thorax_outer");
      model.component("comp1").geom("geom1").feature("chest_band").selection("input2").set("thorax_keep");
      model.component("comp1").geom("geom1").feature("chest_band").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("chest_band").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("chest_band").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("chest_band").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("chest_band");

      model.component("comp1").geom("geom1").create("chest_cyl", "Intersection");
      model.component("comp1").geom("geom1").feature("chest_cyl").selection("input").set("chest_band", "chest_trim_blk");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("chest_cyl");
      chestObjs = model.component("comp1").geom("geom1").feature("chest_cyl").objectNames();
    }} else if ({str(transverse_chestwall_enabled and not conformal_chestwall_support_enabled).lower()}) {{
      model.component("comp1").geom("geom1").create("thorax_inner", "Cylinder");
      model.component("comp1").geom("geom1").feature("thorax_inner").set("axistype", "z");
      model.component("comp1").geom("geom1").feature("thorax_inner").set("r", "transverse_curve_radius-chest_thickness");
      model.component("comp1").geom("geom1").feature("thorax_inner").set("h", "{2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_inner").set("pos", "chestwall_curve_center_x_offset transverse_curve_center_y {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_inner").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_inner").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("thorax_outer", "Cylinder");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("axistype", "z");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("r", "transverse_curve_radius");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("h", "{2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("pos", "chestwall_curve_center_x_offset transverse_curve_center_y {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("thorax_outer").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("chest_trim_blk", "Block");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("size", "{2.0 * support_geometry_half_x:.8f} chest_thickness+{support_depth_for_selection:.10f}+{2.0 * chest_overlap:.10f} {2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("pos", "{-support_geometry_half_x:.8f} -chest_thickness-{chest_overlap:.10f} {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("chest_trim_blk").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("chest_band", "Difference");
        model.component("comp1").geom("geom1").feature("chest_band").selection("input").set("thorax_outer");
        model.component("comp1").geom("geom1").feature("chest_band").selection("input2").set("thorax_inner");
        model.component("comp1").geom("geom1").feature("chest_band").set("intbnd", "on");
        model.component("comp1").geom("geom1").feature("chest_band").set("propagatesel", "on");
        model.component("comp1").geom("geom1").feature("chest_band").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("chest_band").set("selresultshow", "all");
        model.component("comp1").geom("geom1").run("chest_band");

        String chestBandInputTag = "chest_band";
        if ({str(si_chestwall_enabled).lower()}) {{
          model.component("comp1").geom("geom1").create("thorax_inner_si", "Cylinder");
          model.component("comp1").geom("geom1").feature("thorax_inner_si").set("r", "si_curve_radius-chest_thickness");
{thorax_inner_si_axis_java}
          model.component("comp1").geom("geom1").feature("thorax_inner_si").set("selresult", "on");
          model.component("comp1").geom("geom1").feature("thorax_inner_si").set("selresultshow", "all");

          model.component("comp1").geom("geom1").create("thorax_outer_si", "Cylinder");
          model.component("comp1").geom("geom1").feature("thorax_outer_si").set("r", "si_curve_radius");
{thorax_outer_si_axis_java}
          model.component("comp1").geom("geom1").feature("thorax_outer_si").set("selresult", "on");
          model.component("comp1").geom("geom1").feature("thorax_outer_si").set("selresultshow", "all");

          model.component("comp1").geom("geom1").create("chest_band_si", "Difference");
          model.component("comp1").geom("geom1").feature("chest_band_si").selection("input").set("thorax_outer_si");
          model.component("comp1").geom("geom1").feature("chest_band_si").selection("input2").set("thorax_inner_si");
          model.component("comp1").geom("geom1").feature("chest_band_si").set("intbnd", "on");
          model.component("comp1").geom("geom1").feature("chest_band_si").set("propagatesel", "on");
          model.component("comp1").geom("geom1").feature("chest_band_si").set("selresult", "on");
          model.component("comp1").geom("geom1").feature("chest_band_si").set("selresultshow", "all");
          model.component("comp1").geom("geom1").run("chest_band_si");

          model.component("comp1").geom("geom1").create("chest_band_combined", "Union");
          model.component("comp1").geom("geom1").feature("chest_band_combined").selection("input").set("chest_band", "chest_band_si");
          model.component("comp1").geom("geom1").feature("chest_band_combined").set("intbnd", "on");
          model.component("comp1").geom("geom1").feature("chest_band_combined").set("propagatesel", "on");
          model.component("comp1").geom("geom1").feature("chest_band_combined").set("selresult", "on");
          model.component("comp1").geom("geom1").feature("chest_band_combined").set("selresultshow", "all");
          model.component("comp1").geom("geom1").run("chest_band_combined");
          chestBandInputTag = "chest_band_combined";
        }}

        model.component("comp1").geom("geom1").create("chest_cyl", "Intersection");
        model.component("comp1").geom("geom1").feature("chest_cyl").selection("input").set(chestBandInputTag, "chest_trim_blk");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("intbnd", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("propagatesel", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("selresult", "on");
        model.component("comp1").geom("geom1").feature("chest_cyl").set("selresultshow", "all");
        model.component("comp1").geom("geom1").run("chest_cyl");
      chestObjs = model.component("comp1").geom("geom1").feature("chest_cyl").objectNames();
    }} else if ({str(not transverse_chestwall_enabled).lower()}) {{
      model.component("comp1").geom("geom1").create("chest_cyl", "Block");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("size", "{2.0 * support_geometry_half_x:.8f} chest_thickness+{chest_overlap:.10f} {2.0 * outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("pos", "{-support_geometry_half_x:.8f} -chest_thickness {-outer_support_half_z:.8f}");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("chest_cyl").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("chest_cyl");
      chestObjs = model.component("comp1").geom("geom1").feature("chest_cyl").objectNames();
    }}

    if ({str(split_support_regions).lower()}) {{
      model.component("comp1").geom("geom1").create("support_lower_blk", "Block");
      model.component("comp1").geom("geom1").feature("support_lower_blk").set("size", "{2.0 * support_geometry_half_x:.8f} chest_thickness+{support_depth_for_selection:.10f}+{chest_overlap:.10f} {support_lower_z_size:.12f}");
      model.component("comp1").geom("geom1").feature("support_lower_blk").set("pos", "{-support_geometry_half_x:.8f} -chest_thickness {support_lower_zmin:.12f}");
      model.component("comp1").geom("geom1").feature("support_lower_blk").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("support_lower_blk").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("support_upper_blk", "Block");
      model.component("comp1").geom("geom1").feature("support_upper_blk").set("size", "{2.0 * support_geometry_half_x:.8f} chest_thickness+{support_depth_for_selection:.10f}+{chest_overlap:.10f} {support_upper_z_size:.12f}");
      model.component("comp1").geom("geom1").feature("support_upper_blk").set("pos", "{-support_geometry_half_x:.8f} -chest_thickness {support_split_z:.12f}");
      model.component("comp1").geom("geom1").feature("support_upper_blk").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("support_upper_blk").set("selresultshow", "all");

      model.component("comp1").geom("geom1").create("chest_lower_support", "Intersection");
      model.component("comp1").geom("geom1").feature("chest_lower_support").selection("input").set("chest_cyl", "support_lower_blk");
      model.component("comp1").geom("geom1").feature("chest_lower_support").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("chest_lower_support").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("chest_lower_support").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("chest_lower_support").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("chest_lower_support");

      model.component("comp1").geom("geom1").create("pect_support", "Intersection");
      model.component("comp1").geom("geom1").feature("pect_support").selection("input").set("chest_cyl", "support_upper_blk");
      model.component("comp1").geom("geom1").feature("pect_support").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("pect_support").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("pect_support").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("pect_support").set("selresultshow", "all");
      model.component("comp1").geom("geom1").run("pect_support");
    }}

    String[] glandSeedObjs = new String[0];
    if ({str(needs_gland_seed).lower()}) {{
      model.component("comp1").geom("geom1").create("gland_seed", "Ellipsoid");
      model.component("comp1").geom("geom1").feature("gland_seed").set("semiaxes", "{gland_semiaxis_x:.8f} {gland_semiaxis_z:.8f} {gland_semiaxis_y:.8f}");
      model.component("comp1").geom("geom1").feature("gland_seed").set("axistype", "y");
      model.component("comp1").geom("geom1").feature("gland_seed").set("pos", "{gland_center_x:.8f} {gland_center_y:.8f} {gland_center_z:.8f}");
      model.component("comp1").geom("geom1").feature("gland_seed").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("gland_seed").set("selresultshow", "off");
      model.component("comp1").geom("geom1").run("gland_seed");
      glandSeedObjs = model.component("comp1").geom("geom1").feature("gland_seed").objectNames();
    }}

    String[] glandNippleCoreObjs = new String[0];
    if ({str(needs_gland_nipple_core).lower()}) {{
      model.component("comp1").geom("geom1").create("gland_nipple_core", "Ellipsoid");
      model.component("comp1").geom("geom1").feature("gland_nipple_core").set("semiaxes", "{gland_nipple_radius_x:.8f} {gland_nipple_radius_z:.8f} {gland_nipple_radius_y:.8f}");
      trySetLocalSurfaceAxis(model, "gland_nipple_core", {str(normal_alignment_active).lower()}, {nipple_surface_normal_x:.12f}, {nipple_surface_normal_y:.12f}, {nipple_surface_normal_z:.12f});
      model.component("comp1").geom("geom1").feature("gland_nipple_core").set("pos", "{gland_nipple_center_x:.8f} {gland_nipple_center_y:.8f} {gland_nipple_center_z:.8f}");
      model.component("comp1").geom("geom1").feature("gland_nipple_core").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("gland_nipple_core").set("selresultshow", "{subareolar_helper_selresultshow}");
      model.component("comp1").geom("geom1").run("gland_nipple_core");
      glandNippleCoreObjs = model.component("comp1").geom("geom1").feature("gland_nipple_core").objectNames();
    }}

    if ({str(needs_gland_subareolar_bridge).lower()}) {{
      model.component("comp1").geom("geom1").create("gland_subareolar_bridge", "Ellipsoid");
      model.component("comp1").geom("geom1").feature("gland_subareolar_bridge").set("semiaxes", "{gland_subareolar_bridge_radius_x:.8f} {gland_subareolar_bridge_radius_z:.8f} {gland_subareolar_bridge_radius_y:.8f}");
      trySetLocalSurfaceAxis(model, "gland_subareolar_bridge", {str(normal_alignment_active).lower()}, {nipple_surface_normal_x:.12f}, {nipple_surface_normal_y:.12f}, {nipple_surface_normal_z:.12f});
      model.component("comp1").geom("geom1").feature("gland_subareolar_bridge").set("pos", "{gland_subareolar_bridge_center_x:.8f} {gland_subareolar_bridge_center_y:.8f} {gland_subareolar_bridge_center_z:.8f}");
      model.component("comp1").geom("geom1").feature("gland_subareolar_bridge").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("gland_subareolar_bridge").set("selresultshow", "{subareolar_helper_selresultshow}");
      model.component("comp1").geom("geom1").run("gland_subareolar_bridge");
    }}

    String[] glandSeedWithNippleObjs = new String[0];
    if ({str(needs_gland_seed_with_nipple).lower()}) {{
      model.component("comp1").geom("geom1").create("gland_seed_with_nipple", "Union");
      model.component("comp1").geom("geom1").feature("gland_seed_with_nipple").selection("input").set("gland_seed", "gland_nipple_core");
      model.component("comp1").geom("geom1").feature("gland_seed_with_nipple").set("intbnd", "on");
      model.component("comp1").geom("geom1").feature("gland_seed_with_nipple").set("propagatesel", "on");
      model.component("comp1").geom("geom1").feature("gland_seed_with_nipple").set("selresult", "on");
      model.component("comp1").geom("geom1").feature("gland_seed_with_nipple").set("selresultshow", "off");
      model.component("comp1").geom("geom1").run("gland_seed_with_nipple");
      glandSeedWithNippleObjs = model.component("comp1").geom("geom1").feature("gland_seed_with_nipple").objectNames();
    }}

{lobule_union_java}

    model.component("comp1").geom("geom1").create("gland_clip", "Intersection");
    model.component("comp1").geom("geom1").feature("gland_clip").selection("input").set({gland_source_objects_var}[0], breastCoreObjs[0]);
    model.component("comp1").geom("geom1").feature("gland_clip").set("keep", "on");
    model.component("comp1").geom("geom1").feature("gland_clip").set("intbnd", "on");
    model.component("comp1").geom("geom1").feature("gland_clip").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("gland_clip").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("gland_clip").set("selresultshow", "all");
    model.component("comp1").geom("geom1").run("gland_clip");
    String[] glandClipObjs = model.component("comp1").geom("geom1").feature("gland_clip").objectNames();

    model.component("comp1").geom("geom1").create("adipose_diff", "Difference");
    model.component("comp1").geom("geom1").feature("adipose_diff").selection("input").set(breastCoreObjs);
    model.component("comp1").geom("geom1").feature("adipose_diff").selection("input2").set(glandClipObjs);
    model.component("comp1").geom("geom1").feature("adipose_diff").set("keepsubtract", "on");
    model.component("comp1").geom("geom1").feature("adipose_diff").set("intbnd", "on");
    model.component("comp1").geom("geom1").feature("adipose_diff").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("adipose_diff").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("adipose_diff").set("selresultshow", "all");
    model.component("comp1").geom("geom1").run("adipose_diff");
    String[] adiposeObjs = model.component("comp1").geom("geom1").feature("adipose_diff").objectNames();

    model.component("comp1").geom("geom1").create("breast_union", "Union");
    String[] unionInput = new String[adiposeObjs.length + glandClipObjs.length + skinLayerObjs.length];
    System.arraycopy(adiposeObjs, 0, unionInput, 0, adiposeObjs.length);
    System.arraycopy(glandClipObjs, 0, unionInput, adiposeObjs.length, glandClipObjs.length);
    System.arraycopy(skinLayerObjs, 0, unionInput, adiposeObjs.length + glandClipObjs.length, skinLayerObjs.length);
    model.component("comp1").geom("geom1").feature("breast_union").selection("input").set(unionInput);
    model.component("comp1").geom("geom1").feature("breast_union").set("intbnd", "on");
    model.component("comp1").geom("geom1").feature("breast_union").set("propagatesel", "on");
    model.component("comp1").geom("geom1").feature("breast_union").set("selresult", "on");
    model.component("comp1").geom("geom1").feature("breast_union").set("selresultshow", "all");
    model.component("comp1").geom("geom1").run("breast_union");
    model.component("comp1").selection().create("chest_base_bnd", "Box");
    model.component("comp1").selection("chest_base_bnd").label("Chest Base Boundary");
    model.component("comp1").selection("chest_base_bnd").geom("geom1", 2);
    model.component("comp1").selection("chest_base_bnd").set("condition", "inside");
    model.component("comp1").selection("chest_base_bnd").set("xmin", "{chest_base_xmin:.12f}");
    model.component("comp1").selection("chest_base_bnd").set("xmax", "{chest_base_xmax:.12f}");
    model.component("comp1").selection("chest_base_bnd").set("ymin", "{chest_base_ymin:.12f}");
    model.component("comp1").selection("chest_base_bnd").set("ymax", "{chest_base_ymax:.12f}");
    model.component("comp1").selection("chest_base_bnd").set("zmin", "-1.2*breast_radius");
    model.component("comp1").selection("chest_base_bnd").set("zmax", "1.2*breast_radius");
    model.component("comp1").selection().create("chest_interface_bnd", "Box");
    model.component("comp1").selection("chest_interface_bnd").label("Chest Interface Boundary");
    model.component("comp1").selection("chest_interface_bnd").geom("geom1", 2);
    model.component("comp1").selection("chest_interface_bnd").set("condition", "inside");
    model.component("comp1").selection("chest_interface_bnd").set("xmin", "-1.2*breast_radius");
    model.component("comp1").selection("chest_interface_bnd").set("xmax", "1.2*breast_radius");
    model.component("comp1").selection("chest_interface_bnd").set("ymin", "{breast_attach_ymin:.12f}");
    model.component("comp1").selection("chest_interface_bnd").set("ymax", "{breast_attach_ymax:.12f}");
    model.component("comp1").selection("chest_interface_bnd").set("zmin", "-1.2*breast_radius");
    model.component("comp1").selection("chest_interface_bnd").set("zmax", "1.2*breast_radius");
    model.component("comp1").selection().create("breast_attach_box_bnd", "Box");
    model.component("comp1").selection("breast_attach_box_bnd").label("Breast Posterior Attachment Search Band");
    model.component("comp1").selection("breast_attach_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("breast_attach_box_bnd").set("condition", "inside");
    model.component("comp1").selection("breast_attach_box_bnd").set("xmin", "-1.2*breast_radius");
    model.component("comp1").selection("breast_attach_box_bnd").set("xmax", "1.2*breast_radius");
    model.component("comp1").selection("breast_attach_box_bnd").set("ymin", "{breast_attach_ymin:.12f}");
    model.component("comp1").selection("breast_attach_box_bnd").set("ymax", "{breast_attach_ymax:.12f}");
    model.component("comp1").selection("breast_attach_box_bnd").set("zmin", "-1.2*breast_radius");
    model.component("comp1").selection("breast_attach_box_bnd").set("zmax", "1.2*breast_radius");
    StringBuilder selectionNotes = new StringBuilder();
    tryCreateBoundaryIntersectionSelection(
      model,
      "breast_attach_bnd",
      "Breast Posterior Attachment",
      new String[] {{ "geom1_breast_outer_bnd", "breast_attach_box_bnd" }},
      "breast_attach_box_bnd",
      selectionNotes
    );
    tryCreateBoundaryDifferenceSelection(
      model,
      "outer_skin_free_bnd",
      "Free Outer Breast Skin Surface",
      "geom1_breast_outer_bnd",
      new String[] {{ "breast_attach_bnd" }},
      "geom1_breast_outer_bnd",
      selectionNotes
    );
    model.component("comp1").selection().create("nipple_bnd", "Box");
    model.component("comp1").selection("nipple_bnd").label("Cooper Ligament Nipple Region");
    model.component("comp1").selection("nipple_bnd").geom("geom1", 2);
    model.component("comp1").selection("nipple_bnd").set("condition", "inside");
    model.component("comp1").selection("nipple_bnd").set("xmin", "{nipple_sel_xmin:.12f}");
    model.component("comp1").selection("nipple_bnd").set("xmax", "{nipple_sel_xmax:.12f}");
    model.component("comp1").selection("nipple_bnd").set("ymin", "{nipple_sel_ymin:.12f}");
    model.component("comp1").selection("nipple_bnd").set("ymax", "{nipple_sel_ymax:.12f}");
    model.component("comp1").selection("nipple_bnd").set("zmin", "{-nipple_sel_half_z:.12f}");
    model.component("comp1").selection("nipple_bnd").set("zmax", "{nipple_sel_half_z:.12f}");
    model.component("comp1").selection().create("nipple_support_box_bnd", "Box");
    model.component("comp1").selection("nipple_support_box_bnd").label("Cooper Ligament Subareolar Support Box");
    model.component("comp1").selection("nipple_support_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("nipple_support_box_bnd").set("condition", "inside");
    model.component("comp1").selection("nipple_support_box_bnd").set("xmin", "{nipple_support_sel_xmin:.12f}");
    model.component("comp1").selection("nipple_support_box_bnd").set("xmax", "{nipple_support_sel_xmax:.12f}");
    model.component("comp1").selection("nipple_support_box_bnd").set("ymin", "{nipple_support_sel_ymin:.12f}");
    model.component("comp1").selection("nipple_support_box_bnd").set("ymax", "{nipple_support_sel_ymax:.12f}");
    model.component("comp1").selection("nipple_support_box_bnd").set("zmin", "{-nipple_support_sel_half_z:.12f}");
    model.component("comp1").selection("nipple_support_box_bnd").set("zmax", "{nipple_support_sel_half_z:.12f}");
    tryCreateBoundaryIntersectionSelection(
      model,
      "nipple_support_bnd",
      "Cooper Ligament Subareolar Support Patch",
      new String[] {{ "geom1_breast_outer_bnd", "nipple_support_box_bnd" }},
      "nipple_support_box_bnd",
      selectionNotes
    );
    tryCreateBoundaryIntersectionSelection(
      model,
      "landmark_nipple_bnd",
      "Nipple Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "nipple_support_box_bnd" }},
      "nipple_support_bnd",
      selectionNotes
    );
    model.component("comp1").selection().create("landmark_left_box_bnd", "Box");
    model.component("comp1").selection("landmark_left_box_bnd").label("Left Landmark Search Box");
    model.component("comp1").selection("landmark_left_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("landmark_left_box_bnd").set("condition", "inside");
    model.component("comp1").selection("landmark_left_box_bnd").set("xmin", "{-comsol_outer_axis_x:.12f}");
    model.component("comp1").selection("landmark_left_box_bnd").set("xmax", "{(-comsol_outer_axis_x + landmark_side_band_x):.12f}");
    model.component("comp1").selection("landmark_left_box_bnd").set("ymin", "{landmark_ymin:.12f}");
    model.component("comp1").selection("landmark_left_box_bnd").set("ymax", "{landmark_ymax:.12f}");
    model.component("comp1").selection("landmark_left_box_bnd").set("zmin", "{landmark_side_zmin:.12f}");
    model.component("comp1").selection("landmark_left_box_bnd").set("zmax", "{landmark_side_zmax:.12f}");
    tryCreateBoundaryIntersectionSelection(
      model,
      "landmark_left_bnd",
      "Left Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_left_box_bnd" }},
      "landmark_left_box_bnd",
      selectionNotes
    );
    model.component("comp1").selection().create("landmark_right_box_bnd", "Box");
    model.component("comp1").selection("landmark_right_box_bnd").label("Right Landmark Search Box");
    model.component("comp1").selection("landmark_right_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("landmark_right_box_bnd").set("condition", "inside");
    model.component("comp1").selection("landmark_right_box_bnd").set("xmin", "{(comsol_outer_axis_x - landmark_side_band_x):.12f}");
    model.component("comp1").selection("landmark_right_box_bnd").set("xmax", "{comsol_outer_axis_x:.12f}");
    model.component("comp1").selection("landmark_right_box_bnd").set("ymin", "{landmark_ymin:.12f}");
    model.component("comp1").selection("landmark_right_box_bnd").set("ymax", "{landmark_ymax:.12f}");
    model.component("comp1").selection("landmark_right_box_bnd").set("zmin", "{landmark_side_zmin:.12f}");
    model.component("comp1").selection("landmark_right_box_bnd").set("zmax", "{landmark_side_zmax:.12f}");
    tryCreateBoundaryIntersectionSelection(
      model,
      "landmark_right_bnd",
      "Right Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_right_box_bnd" }},
      "landmark_right_box_bnd",
      selectionNotes
    );
    model.component("comp1").selection().create("landmark_superior_box_bnd", "Box");
    model.component("comp1").selection("landmark_superior_box_bnd").label("Superior Landmark Search Box");
    model.component("comp1").selection("landmark_superior_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("landmark_superior_box_bnd").set("condition", "inside");
    model.component("comp1").selection("landmark_superior_box_bnd").set("xmin", "{landmark_pole_xmin:.12f}");
    model.component("comp1").selection("landmark_superior_box_bnd").set("xmax", "{landmark_pole_xmax:.12f}");
    model.component("comp1").selection("landmark_superior_box_bnd").set("ymin", "{landmark_ymin:.12f}");
    model.component("comp1").selection("landmark_superior_box_bnd").set("ymax", "{landmark_ymax:.12f}");
    model.component("comp1").selection("landmark_superior_box_bnd").set("zmin", "{(comsol_outer_axis_z - landmark_pole_band_z):.12f}");
    model.component("comp1").selection("landmark_superior_box_bnd").set("zmax", "{comsol_outer_axis_z:.12f}");
    tryCreateBoundaryIntersectionSelection(
      model,
      "landmark_superior_bnd",
      "Superior Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_superior_box_bnd" }},
      "landmark_superior_box_bnd",
      selectionNotes
    );
    model.component("comp1").selection().create("landmark_inferior_box_bnd", "Box");
    model.component("comp1").selection("landmark_inferior_box_bnd").label("Inferior Landmark Search Box");
    model.component("comp1").selection("landmark_inferior_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("landmark_inferior_box_bnd").set("condition", "inside");
    model.component("comp1").selection("landmark_inferior_box_bnd").set("xmin", "{landmark_pole_xmin:.12f}");
    model.component("comp1").selection("landmark_inferior_box_bnd").set("xmax", "{landmark_pole_xmax:.12f}");
    model.component("comp1").selection("landmark_inferior_box_bnd").set("ymin", "{landmark_ymin:.12f}");
    model.component("comp1").selection("landmark_inferior_box_bnd").set("ymax", "{landmark_ymax:.12f}");
    model.component("comp1").selection("landmark_inferior_box_bnd").set("zmin", "{-comsol_outer_axis_z:.12f}");
    model.component("comp1").selection("landmark_inferior_box_bnd").set("zmax", "{(-comsol_outer_axis_z + landmark_pole_band_z):.12f}");
    tryCreateBoundaryIntersectionSelection(
      model,
      "landmark_inferior_bnd",
      "Inferior Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_inferior_box_bnd" }},
      "landmark_inferior_box_bnd",
      selectionNotes
    );
    model.component("comp1").selection().create("anterior_skin_box_bnd", "Box");
    model.component("comp1").selection("anterior_skin_box_bnd").label("Cooper Ligament Skin Patch Search Box");
    model.component("comp1").selection("anterior_skin_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("anterior_skin_box_bnd").set("condition", "inside");
    model.component("comp1").selection("anterior_skin_box_bnd").set("xmin", "{anterior_skin_sel_xmin:.12f}");
    model.component("comp1").selection("anterior_skin_box_bnd").set("xmax", "{anterior_skin_sel_xmax:.12f}");
    model.component("comp1").selection("anterior_skin_box_bnd").set("ymin", "{anterior_skin_sel_ymin:.12f}");
    model.component("comp1").selection("anterior_skin_box_bnd").set("ymax", "{anterior_skin_sel_ymax:.12f}");
    model.component("comp1").selection("anterior_skin_box_bnd").set("zmin", "{-anterior_skin_sel_half_z:.12f}");
    model.component("comp1").selection("anterior_skin_box_bnd").set("zmax", "{anterior_skin_sel_half_z:.12f}");
    tryCreateBoundaryIntersectionSelection(
      model,
      "anterior_skin_bnd",
      "Cooper Ligament Skin Patch",
      new String[] {{ "outer_skin_free_bnd", "anterior_skin_box_bnd" }},
      "outer_skin_free_bnd",
      selectionNotes
    );
    model.component("comp1").selection().create("anterior_gland_box_bnd", "Box");
    model.component("comp1").selection("anterior_gland_box_bnd").label("Cooper Ligament Gland Full-Boundary Search Box");
    model.component("comp1").selection("anterior_gland_box_bnd").geom("geom1", 2);
    model.component("comp1").selection("anterior_gland_box_bnd").set("condition", "inside");
    model.component("comp1").selection("anterior_gland_box_bnd").set("xmin", "-1.2*breast_radius");
    model.component("comp1").selection("anterior_gland_box_bnd").set("xmax", "1.2*breast_radius");
    model.component("comp1").selection("anterior_gland_box_bnd").set("ymin", "-0.1*breast_radius");
    model.component("comp1").selection("anterior_gland_box_bnd").set("ymax", "1.2*breast_radius");
    model.component("comp1").selection("anterior_gland_box_bnd").set("zmin", "-1.2*breast_radius");
    model.component("comp1").selection("anterior_gland_box_bnd").set("zmax", "1.2*breast_radius");
    tryCreateBoundaryIntersectionSelection(
      model,
      "anterior_gland_bnd",
      "Cooper Ligament Gland Patch",
      new String[] {{ "geom1_gland_clip_bnd", "anterior_gland_box_bnd" }},
      "anterior_gland_box_bnd",
      selectionNotes
    );

    // Auto-generated pointers:
    // - Build plan JSON: {build_plan_java}
    // - Selection hints JSON: {selection_hints_java}
    // - Lobule primitives in plan: {build_plan_summary["lobule_count"]}
    // - Anatomical lobe groups interpreted in COMSOL: {len(anatomical_lobe_tags) if anatomical_lobe_tags else build_plan_summary["lobule_count"]}
    //
    // Source geometry summary:
    // - radius: {build_plan_summary["geometry"].get("radius", "n/a")}
    // - chest-wall thickness: {build_plan_summary["geometry"].get("thickness_chest_wall", "n/a")}
    // - asymmetry enabled: {build_plan_summary["geometry"].get("asymmetry", {}).get("enabled", False)}
    //
    // Source mesh summary:
    // - density: {build_plan_summary["mesh"].get("density", "n/a")}
    // - order: {build_plan_summary["mesh"].get("order", "n/a")}
    //
    // Source material summary:
    // - skin density: {build_plan_summary["material"].get("skin", {}).get("density", "n/a")}
    // - adipose density: {build_plan_summary["material"].get("adipose", {}).get("density", "n/a")}
    // - glandular density: {build_plan_summary["material"].get("glandular", {}).get("density", "n/a")}
    // - chest density (COMSOL explicit): {chest_density}
    // - chest E (COMSOL explicit): {chest_E}
    // - chest nu (COMSOL explicit): {chest_nu}
    //
    // Physics scaffold:
    model.component("comp1").material().create("mat_chest", "Common");
    model.component("comp1").material("mat_chest").label("ChestWall");
    model.component("comp1").material("mat_chest").selection().named("geom1_chest_cyl_dom");
    model.component("comp1").material("mat_chest").propertyGroup("def").set("density", new String[] {{ "chest_density" }});
    model.component("comp1").material("mat_chest").propertyGroup("def").set("youngsmodulus", new String[] {{ "chest_E" }});
    model.component("comp1").material("mat_chest").propertyGroup("def").set("poissonsratio", new String[] {{ "chest_nu" }});

    if ({str(split_support_regions).lower()}) {{
      model.component("comp1").material("mat_chest").selection().named("geom1_chest_lower_support_dom");
      model.component("comp1").material().create("mat_pectoralis_support", "Common");
      model.component("comp1").material("mat_pectoralis_support").label("PectoralisSupport");
      model.component("comp1").material("mat_pectoralis_support").selection().named("geom1_pect_support_dom");
      model.component("comp1").material("mat_pectoralis_support").propertyGroup("def").set("density", new String[] {{ "pectoralis_density" }});
      model.component("comp1").material("mat_pectoralis_support").propertyGroup("def").set("youngsmodulus", new String[] {{ "pectoralis_E" }});
      model.component("comp1").material("mat_pectoralis_support").propertyGroup("def").set("poissonsratio", new String[] {{ "pectoralis_nu" }});
    }}

    model.component("comp1").material().create("mat_skin_shell", "Common");
    model.component("comp1").material("mat_skin_shell").label("SkinShellScaffold");
    model.component("comp1").material("mat_skin_shell").selection().named("geom1_breast_outer_bnd");
    model.component("comp1").material("mat_skin_shell").propertyGroup("def").set("density", new String[] {{ "skin_density" }});
    model.component("comp1").material("mat_skin_shell").propertyGroup("def").set("youngsmodulus", new String[] {{ "skin_E" }});
    model.component("comp1").material("mat_skin_shell").propertyGroup("def").set("poissonsratio", new String[] {{ "skin_nu" }});

    if ({str(volumetric_skin_enabled).lower()}) {{
      model.component("comp1").material().create("mat_skin_solid", "Common");
      model.component("comp1").material("mat_skin_solid").label("SkinSolidLayer");
      model.component("comp1").material("mat_skin_solid").selection().named("geom1_skin_layer_dom");
      model.component("comp1").material("mat_skin_solid").propertyGroup("def").set("density", new String[] {{ "skin_density" }});
      model.component("comp1").material("mat_skin_solid").propertyGroup("def").set("youngsmodulus", new String[] {{ "skin_E" }});
      model.component("comp1").material("mat_skin_solid").propertyGroup("def").set("poissonsratio", new String[] {{ "skin_nu" }});
    }}

    model.component("comp1").material().create("mat_adipose", "Common");
    model.component("comp1").material("mat_adipose").label("Adipose");
    model.component("comp1").material("mat_adipose").selection().named("geom1_adipose_diff_dom");
    model.component("comp1").material("mat_adipose").propertyGroup("def").set("density", new String[] {{ "adipose_density_eff" }});
    model.component("comp1").material("mat_adipose").propertyGroup("def").set("youngsmodulus", new String[] {{ "adipose_E_eff" }});
    model.component("comp1").material("mat_adipose").propertyGroup("def").set("poissonsratio", new String[] {{ "adipose_nu" }});

    model.component("comp1").material().create("mat_glandular", "Common");
    model.component("comp1").material("mat_glandular").label("Glandular");
    model.component("comp1").material("mat_glandular").selection().named("geom1_gland_clip_dom");
    model.component("comp1").material("mat_glandular").propertyGroup("def").set("density", new String[] {{ "glandular_density_eff" }});
    model.component("comp1").material("mat_glandular").propertyGroup("def").set("youngsmodulus", new String[] {{ "glandular_E_eff" }});
    model.component("comp1").material("mat_glandular").propertyGroup("def").set("poissonsratio", new String[] {{ "glandular_nu" }});

    model.component("comp1").physics().create("solid", "SolidMechanics", "geom1");
    model.component("comp1").physics("solid").selection().named("geom1_breast_union_dom");
    model.component("comp1").physics("solid").create("fix1", "Fixed", 2);
    model.component("comp1").physics("solid").feature("fix1").selection().named("breast_attach_bnd");
    model.component("comp1").physics("solid").feature("fix1").active({fixed_boundary_active_java});
    model.component("comp1").physics("solid").create("gacc1", "GravityAcceleration", -1);
    model.component("comp1").physics("solid").feature("gacc1").set("g", new String[] {{ "0", "0", "GRAVITY_Z_EXPRESSION_PLACEHOLDER" }});
    StringBuilder dynamicMotionNotes = new StringBuilder();
    DYNAMIC_SUPPORT_MOTION_BLOCK_PLACEHOLDER
    if ({str(cooper_ligament_enabled and cooper_ligament_variant == "nipple_to_chestwall").lower()}) {{
      tryCreateLigamentNippleTetherBoundaryLoad(
        model,
        "solid",
        "coop_nipple_tether",
        "nipple_support_bnd",
        "coop_nipple_fx",
        "coop_nipple_fy",
        "coop_nipple_fz",
        "cooper_damping",
        dynamicMotionNotes
      );
    }}
    if ({str(cooper_ligament_enabled and cooper_ligament_variant in {"glandular_to_skin", "dense_network"}).lower()}) {{
      tryCreateLigamentNippleTetherBoundaryLoad(
        model,
        "solid",
        "coop_skin_patch",
        "anterior_skin_bnd",
        "coop_skin_fx",
        "coop_skin_fy",
        "coop_skin_fz",
        "cooper_damping",
        dynamicMotionNotes
      );
      tryCreateLigamentNippleTetherBoundaryLoad(
        model,
        "solid",
        "coop_gland_patch",
        "anterior_gland_bnd",
        "coop_gland_fx",
        "coop_gland_fy",
        "coop_gland_fz",
        "cooper_damping",
        dynamicMotionNotes
      );
    }}
    System.out.println(dynamicMotionNotes.toString());
{shell_physics_java}

    // Current builder scope:
    // 1) build a COMSOL-native outer breast, glandular core, and chest-wall support
    // 2) expose stable finalized geometry selections for the main regions
    // 3) attach a separate linear chest-wall material and source-case-derived Mooney-Rivlin
    //    hyperelastic scaffolds for adipose, glandular, and optional skin shell
    // 4) optionally scaffold a COMSOL Shell interface and a first Solid-Thin Structure Connection attempt
    // 5) run and save MPH
    //
    // Note:
    // This file now attempts a source-case dynamic sequence in one COMSOL time-dependent
    // study by ramping gravity first and then applying a prescribed z-displacement on
    // the chest boundary. The Mooney-Rivlin materials are mapped from source-case inputs, but
    // exact solver parity and mass-damping equivalence may still require refinement.

    model.component("comp1").mesh("mesh1").run();
    if ({str(default_result_plots_enabled).lower()}) {{
      tryCreateDefaultResultPlots(model, dynamicMotionNotes);
    }}
    return model;
  }}

  public static void main(String[] args) throws Exception {{
    Model model = run();
    model.save("{result_mph_java}");
    ModelUtil.disconnect();
  }}

  private static void trySetLocalSurfaceAxis(Model model, String tag, boolean enabled, double nx, double ny, double nz) {{
    if (!enabled) {{
      model.component("comp1").geom("geom1").feature(tag).set("axistype", "y");
      return;
    }}
    try {{
      model.component("comp1").geom("geom1").feature(tag).set("axistype", "cartesian");
      model.component("comp1").geom("geom1").feature(tag).set("axis", new double[] {{ nx, ny, nz }});
    }} catch (Exception ex) {{
      model.component("comp1").geom("geom1").feature(tag).set("axistype", "y");
      System.out.println("LOCAL_SURFACE_AXIS_FALLBACK " + tag + " " + ex.getMessage());
    }}
  }}

  private static void createTumorPreviewComponent(Model model) {{
    try {{
      model.component().create("comp_tumor_preview", true);
      model.component("comp_tumor_preview").geom().create("geom_preview", 3);
      model.component("comp_tumor_preview").geom("geom_preview").lengthUnit("m");
      model.component("comp_tumor_preview").geom("geom_preview").create("tumor_preview_sphere", "Sphere");
      model.component("comp_tumor_preview").geom("geom_preview").feature("tumor_preview_sphere").label("Tumor preview sphere");
      model.component("comp_tumor_preview").geom("geom_preview").feature("tumor_preview_sphere").set("r", "tumor_radius");
      model.component("comp_tumor_preview").geom("geom_preview").feature("tumor_preview_sphere").set("pos", "tumor_x tumor_y tumor_z");
      model.component("comp_tumor_preview").geom("geom_preview").feature("tumor_preview_sphere").set("selresult", "on");
      model.component("comp_tumor_preview").geom("geom_preview").feature("tumor_preview_sphere").set("selresultshow", "all");
      model.component("comp_tumor_preview").geom("geom_preview").run();
      System.out.println("TUMOR_PREVIEW_COMPONENT_READY comp_tumor_preview geom_preview tumor_preview_sphere");
    }} catch (Exception ex) {{
      System.out.println("TUMOR_PREVIEW_COMPONENT_SKIPPED " + ex.getMessage());
    }}
  }}

  private static void tryCreateBoundaryIntersectionSelection(
      Model model,
      String tag,
      String label,
      String[] inputTags,
      String fallbackSelection,
      StringBuilder notes
    ) {{
      try {{
        model.component("comp1").selection().create(tag, "Intersection");
        model.component("comp1").selection(tag).label(label);
        model.component("comp1").selection(tag).geom("geom1", 2);
        model.component("comp1").selection(tag).set("input", inputTags);
        notes.append("Created boundary intersection selection ").append(tag).append("\\n");
      }} catch (Exception ex) {{
        notes.append("Could not create boundary intersection selection ").append(tag)
             .append(": ").append(ex.getMessage()).append("\\n");
        try {{
          model.component("comp1").selection().duplicate(tag, fallbackSelection);
          model.component("comp1").selection(tag).label(label + " (fallback box)");
          notes.append("Created fallback duplicate selection ").append(tag)
               .append(" from ").append(fallbackSelection).append("\\n");
        }} catch (Exception dupEx) {{
          notes.append("Could not duplicate fallback selection ").append(fallbackSelection)
               .append(": ").append(dupEx.getMessage()).append("\\n");
        }}
      }}
    }}

  private static void tryCreateBoundaryDifferenceSelection(
      Model model,
      String tag,
      String label,
      String addTag,
      String[] subtractTags,
      String fallbackSelection,
      StringBuilder notes
    ) {{
      try {{
        model.component("comp1").selection().create(tag, "Difference");
        model.component("comp1").selection(tag).label(label);
        model.component("comp1").selection(tag).geom("geom1", 2);
        model.component("comp1").selection(tag).set("add", new String[] {{ addTag }});
        model.component("comp1").selection(tag).set("subtract", subtractTags);
        notes.append("Created boundary difference selection ").append(tag).append("\\n");
      }} catch (Exception ex) {{
        notes.append("Could not create boundary difference selection ").append(tag)
             .append(": ").append(ex.getMessage()).append("\\n");
        try {{
          model.component("comp1").selection().duplicate(tag, fallbackSelection);
          model.component("comp1").selection(tag).label(label + " (fallback full outer surface)");
          notes.append("Created fallback duplicate selection ").append(tag)
               .append(" from ").append(fallbackSelection).append("\\n");
        }} catch (Exception dupEx) {{
          notes.append("Could not duplicate fallback selection ").append(fallbackSelection)
               .append(": ").append(dupEx.getMessage()).append("\\n");
        }}
      }}
    }}

  private static String tryCreatePhysics(Model model, String tag, String[] candidateIds, String geomTag, StringBuilder notes) {{
    for (String candidateId : candidateIds) {{
      try {{
        model.component("comp1").physics().create(tag, candidateId, geomTag);
        notes.append("Created physics ").append(tag).append(" with id ").append(candidateId).append("\\n");
        return tag;
      }} catch (Exception ex) {{
        notes.append("Physics id ").append(candidateId).append(" failed: ").append(ex.getMessage()).append("\\n");
      }}
    }}
    return null;
  }}

  private static void tryConfigureShellThickness(Model model, String physicsTag, String thicknessExpr, StringBuilder notes) {{
    String[] candidateFeatureTags = new String[] {{ "thick1", "thk1", "to1", "t1" }};
    for (String featureTag : candidateFeatureTags) {{
      try {{
        model.component("comp1").physics(physicsTag).feature(featureTag).set("d0", thicknessExpr);
        notes.append("Assigned shell thickness on feature ").append(featureTag).append("\\n");
        return;
      }} catch (Exception ignored) {{
      }}
      try {{
        model.component("comp1").physics(physicsTag).feature(featureTag).set("thickness", thicknessExpr);
        notes.append("Assigned shell thickness on feature ").append(featureTag).append(" via thickness property\\n");
        return;
      }} catch (Exception ignored) {{
      }}
    }}
    try {{
      for (String featureTag : model.component("comp1").physics(physicsTag).feature().tags()) {{
        try {{
          model.component("comp1").physics(physicsTag).feature(featureTag).set("d0", thicknessExpr);
          notes.append("Assigned shell thickness on discovered feature ").append(featureTag).append("\\n");
          return;
        }} catch (Exception ignored) {{
        }}
        try {{
          model.component("comp1").physics(physicsTag).feature(featureTag).set("thickness", thicknessExpr);
          notes.append("Assigned shell thickness on discovered feature ").append(featureTag).append(" via thickness property\\n");
          return;
        }} catch (Exception ignored) {{
        }}
      }}
    }} catch (Exception ex) {{
      notes.append("Could not inspect shell features for thickness assignment: ").append(ex.getMessage()).append("\\n");
      return;
    }}
    notes.append("Shell physics was created, but no thickness feature accepted skin_shell_thickness automatically.\\n");
  }}

  private static String tryCreateSolidThinStructureConnection(
    Model model,
    String tag,
    String[] candidateIds,
    String geomTag,
    String selectionName,
    String solidPhysicsTag,
    String shellPhysicsTag,
    StringBuilder notes
  ) {{
    for (String candidateId : candidateIds) {{
      try {{
        model.multiphysics().create(tag, candidateId, geomTag);
        try {{
          model.multiphysics(tag).selection().named(selectionName);
        }} catch (Exception selectionEx) {{
          notes.append("Created ").append(tag).append(" but selection binding failed: ").append(selectionEx.getMessage()).append("\\n");
        }}
        trySetStringProperties(model, tag, new String[] {{ "solid", "solidphys", "solidtag", "solidphysics" }}, solidPhysicsTag, notes);
        trySetStringProperties(model, tag, new String[] {{ "shell", "thinstructure", "shellphys", "shelltag", "shellphysics" }}, shellPhysicsTag, notes);
        notes.append("Created multiphysics ").append(tag).append(" with id ").append(candidateId).append("\\n");
        return tag;
      }} catch (Exception ex) {{
        notes.append("Multiphysics id ").append(candidateId).append(" failed: ").append(ex.getMessage()).append("\\n");
      }}
    }}
    return null;
  }}

  private static void trySetStringProperties(Model model, String multiphysicsTag, String[] keys, String value, StringBuilder notes) {{
    for (String key : keys) {{
      try {{
        model.multiphysics(multiphysicsTag).set(key, value);
        notes.append("Set ").append(multiphysicsTag).append(".").append(key).append("=").append(value).append("\\n");
        return;
      }} catch (Exception ignored) {{
      }}
      try {{
        model.multiphysics(multiphysicsTag).set(key, new String[] {{ value }});
        notes.append("Set ").append(multiphysicsTag).append(".").append(key).append("=[").append(value).append("]\\n");
        return;
      }} catch (Exception ignored) {{
      }}
    }}
  }}

  private static boolean tryCreateMooneyRivlinFeature(
    Model model,
    String physicsTag,
    String featureTag,
    int entityDim,
    String selectionName,
    String densityExpr,
    String c10Expr,
    String c01Expr,
    String bulkExpr,
    StringBuilder notes
  ) {{
    String[] candidateIds = new String[] {{ "HyperelasticMaterial", "Hyperelastic", "hyperelastic" }};
    for (String candidateId : candidateIds) {{
      try {{
        model.component("comp1").physics(physicsTag).create(featureTag, candidateId, entityDim);
        bindFeatureSelection(model, physicsTag, featureTag, selectionName, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "materialmodel", "MaterialModel", "model" }}, new String[] {{ "MooneyRivlin2", "MooneyRivlin", "Mooney-Rivlin, Two Parameters" }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "compressibility", "Compressibility", "comp" }}, new String[] {{ "NearlyIncompressible", "nearlyincompressible", "Nearly incompressible" }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "c10", "C10" }}, new String[] {{ c10Expr }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "c01", "C01" }}, new String[] {{ c01Expr }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "kappa", "K", "bulkmodulus", "bulkModulus" }}, new String[] {{ bulkExpr }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "rho", "density" }}, new String[] {{ densityExpr }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "usemixedformulation", "mixedformulation", "mixed" }}, new String[] {{ "Pressure formulation", "PressureFormulation", "pressure" }}, notes);
        notes.append("Created Mooney-Rivlin hyperelastic feature ").append(featureTag).append(" on physics ").append(physicsTag).append(" with id ").append(candidateId).append("\\n");
        return true;
      }} catch (Exception ex) {{
        notes.append("Hyperelastic feature id ").append(candidateId).append(" failed on ").append(physicsTag).append(": ").append(ex.getMessage()).append("\\n");
      }}
    }}
    return false;
  }}

  private static void bindFeatureSelection(Model model, String physicsTag, String featureTag, String selectionName, StringBuilder notes) {{
    try {{
      model.component("comp1").physics(physicsTag).feature(featureTag).selection().named(selectionName);
      notes.append("Bound ").append(featureTag).append(" to selection ").append(selectionName).append("\\n");
    }} catch (Exception ex) {{
      notes.append("Selection binding failed for ").append(featureTag).append(": ").append(ex.getMessage()).append("\\n");
    }}
  }}

  private static void trySetFeatureProperty(
    Model model,
    String physicsTag,
    String featureTag,
    String[] keys,
    String[] values,
    StringBuilder notes
  ) {{
    for (String key : keys) {{
      for (String value : values) {{
        try {{
          model.component("comp1").physics(physicsTag).feature(featureTag).set(key, value);
          notes.append("Set ").append(featureTag).append(".").append(key).append("=").append(value).append("\\n");
          return;
        }} catch (Exception ignored) {{
        }}
        try {{
          model.component("comp1").physics(physicsTag).feature(featureTag).set(key, new String[] {{ value }});
          notes.append("Set ").append(featureTag).append(".").append(key).append("=[").append(value).append("]\\n");
          return;
        }} catch (Exception ignored) {{
        }}
      }}
    }}
  }}

  private static String tryCreateDirectionalPrescribedDisplacementFeature(
    Model model,
    String physicsTag,
    String featureTag,
    String selectionName,
    boolean useX,
    String xExpr,
    boolean useY,
    String yExpr,
    boolean useZ,
    String zExpr,
    StringBuilder notes
  ) {{
    try {{
      model.component("comp1").physics(physicsTag).create(featureTag, "Displacement2", 2);
      model.component("comp1").physics(physicsTag).feature(featureTag).label("Posterior Dynamic Support Motion");
      bindFeatureSelection(model, physicsTag, featureTag, selectionName, notes);
      model.component("comp1").physics(physicsTag).feature(featureTag).setIndex("Direction", useX ? "prescribed" : "free", 0);
      model.component("comp1").physics(physicsTag).feature(featureTag).setIndex("Direction", useY ? "prescribed" : "free", 1);
      model.component("comp1").physics(physicsTag).feature(featureTag).setIndex("Direction", useZ ? "prescribed" : "free", 2);
      if (useX) {{
        model.component("comp1").physics(physicsTag).feature(featureTag).setIndex("U0", xExpr, 0);
      }}
      if (useY) {{
        model.component("comp1").physics(physicsTag).feature(featureTag).setIndex("U0", yExpr, 1);
      }}
      if (useZ) {{
        model.component("comp1").physics(physicsTag).feature(featureTag).setIndex("U0", zExpr, 2);
      }}
      notes.append("Created prescribed displacement feature ").append(featureTag)
           .append(" with exact COMSOL Displacement2 mapping\\n");
      return featureTag;
    }} catch (Exception ex) {{
      notes.append("Exact COMSOL Displacement2 mapping failed for ").append(featureTag)
           .append(": ").append(ex.getMessage()).append("\\n");
    }}

    String[] candidateIds = new String[] {{ "PrescribedDisplacement", "disp", "Displacement1" }};
    for (String candidateId : candidateIds) {{
      try {{
        model.component("comp1").physics(physicsTag).create(featureTag, candidateId, 2);
        model.component("comp1").physics(physicsTag).feature(featureTag).label("Posterior Dynamic Support Motion");
        bindFeatureSelection(model, physicsTag, featureTag, selectionName, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "coord", "CoordinateSystem", "coordsys" }}, new String[] {{ "cartesian", "Cartesian", "sys1" }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "prescribedx", "PrescribedInX", "constrx", "consx", "uxactive", "Uxactive", "actx", "constraintx", "Constraintx", "dispx" }}, new String[] {{ useX ? "true" : "false", useX ? "on" : "off", useX ? "1" : "0", useX ? "Prescribed" : "Free", useX ? "prescribed" : "free" }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "prescribedy", "PrescribedInY", "constry", "consy", "uyactive", "Uyactive", "acty", "constrainty", "Constrainty", "dispy" }}, new String[] {{ useY ? "true" : "false", useY ? "on" : "off", useY ? "1" : "0", useY ? "Prescribed" : "Free", useY ? "prescribed" : "free" }}, notes);
        trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "prescribedz", "PrescribedInZ", "constrz", "consz", "uzactive", "Uzactive", "actz", "constraintz", "Constraintz", "dispz" }}, new String[] {{ useZ ? "true" : "false", useZ ? "on" : "off", useZ ? "1" : "0", useZ ? "Prescribed" : "Free", useZ ? "prescribed" : "free" }}, notes);
        if (useX) {{
          trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "u0", "U0", "U0x", "u0x", "x0", "rx" }}, new String[] {{ xExpr }}, notes);
          trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "u0x", "U0x", "x0", "rx" }}, new String[] {{ xExpr }}, notes);
        }}
        if (useY) {{
          trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "v0", "V0", "U0y", "u0y", "y0", "ry" }}, new String[] {{ yExpr }}, notes);
          trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "u0y", "U0y", "y0", "ry" }}, new String[] {{ yExpr }}, notes);
        }}
        if (useZ) {{
          trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "w0", "W0", "U0z", "u0z", "z0", "rz" }}, new String[] {{ zExpr }}, notes);
          trySetFeatureProperty(model, physicsTag, featureTag, new String[] {{ "u0z", "U0z", "z0", "rz" }}, new String[] {{ zExpr }}, notes);
        }}
        notes.append("Created prescribed displacement feature ").append(featureTag).append(" with id ").append(candidateId).append("\\n");
        return featureTag;
      }} catch (Exception ex) {{
        notes.append("Prescribed displacement feature id ").append(candidateId).append(" failed: ").append(ex.getMessage()).append("\\n");
      }}
    }}
    return null;
  }}

  private static void trySetVectorFeatureProperty(
      Model model,
      String physicsTag,
      String featureTag,
    String[] keys,
    String[] values,
    StringBuilder notes
  ) {{
    for (String key : keys) {{
      try {{
        model.component("comp1").physics(physicsTag).feature(featureTag).set(key, values);
        notes.append("Set ").append(featureTag).append(".").append(key).append("=[vector]\\n");
        return;
      }} catch (Exception ignored) {{
        }}
      }}
    }}

  private static String tryCreateLigamentNippleTetherBoundaryLoad(
      Model model,
      String physicsTag,
      String featureTag,
      String selectionName,
      String fxExpr,
      String fyExpr,
      String fzExpr,
      String dampingExpr,
      StringBuilder notes
    ) {{
      String[] candidateIds = new String[] {{ "BoundaryLoad", "bndl" }};
      for (String candidateId : candidateIds) {{
        try {{
          model.component("comp1").physics(physicsTag).create(featureTag, candidateId, 2);
          String label = "Cooper Ligament Scaffold";
          if ("coop_nipple_tether".equals(featureTag)) {{
            label = "Cooper Ligament Nipple Tether";
          }} else if ("coop_skin_patch".equals(featureTag)) {{
            label = "Cooper Ligament Skin Patch";
          }} else if ("coop_gland_patch".equals(featureTag)) {{
            label = "Cooper Ligament Gland Patch";
          }}
          model.component("comp1").physics(physicsTag).feature(featureTag).label(label);
          bindFeatureSelection(model, physicsTag, featureTag, selectionName, notes);
          trySetFeatureProperty(
            model,
            physicsTag,
            featureTag,
            new String[] {{ "LoadType", "loadtype", "type" }},
            new String[] {{ "ForcePerReferenceArea", "Force per reference area", "ForcePerArea", "Force" }},
            notes
          );
          trySetVectorFeatureProperty(
            model,
            physicsTag,
            featureTag,
            new String[] {{ "FperArea", "FA", "F" }},
            new String[] {{
              fxExpr,
              fyExpr,
              fzExpr
            }},
            notes
          );
          notes.append("Created Cooper ligament nipple tether scaffold on ").append(selectionName)
               .append(" using boundary-load approximation\\n");
          return featureTag;
        }} catch (Exception ex) {{
          notes.append("Ligament nipple tether candidate ").append(candidateId).append(" failed: ")
               .append(ex.getMessage()).append("\\n");
        }}
      }}
      notes.append("Could not create Cooper ligament nipple tether scaffold\\n");
      return null;
    }}

  private static void tryCreateDefaultResultPlots(Model model, StringBuilder notes) {{
    tryCreateCutPlaneDataset(model, "cpl_sagittal_yz", "Stage Review - Sagittal YZ Cut", "yz", "0", notes);
    tryCreateCutPlaneDataset(model, "cpl_frontal_xz", "Stage Review - Frontal XZ Cut", "xz", "0.045", notes);
    tryCreateCutPlaneDataset(model, "cpl_transverse_xy", "Stage Review - Transverse XY Cut", "xy", "0", notes);

    tryCreateScalarResultPlot(
      model,
      "pg_disp_total",
      "01 Total displacement (mm)",
      "surf_disp_total",
      "Surface",
      null,
      "disp_mag",
      "mm",
      true,
      "0",
      "40",
      notes
    );
    tryCreateScalarResultPlot(
      model,
      "pg_disp_z",
      "02 Vertical displacement w (mm)",
      "surf_disp_z",
      "Surface",
      null,
      "w",
      "mm",
      true,
      "-40",
      "10",
      notes
    );
    tryCreateScalarResultPlot(
      model,
      "pg_disp_y",
      "03 Anterior-posterior displacement v (mm)",
      "surf_disp_y",
      "Surface",
      null,
      "v",
      "mm",
      true,
      "-30",
      "30",
      notes
    );
    tryCreateScalarResultPlot(
      model,
      "pg_vm_breast",
      "04 Breast von Mises stress (kPa)",
      "surf_vm_breast",
      "Surface",
      null,
      "solid.mises",
      "kPa",
      true,
      "0",
      "3",
      notes
    );
    tryCreateScalarResultPlot(
      model,
      "pg_vm_gland",
      "05 Glandular von Mises stress (kPa)",
      "surf_vm_gland",
      "Surface",
      "geom1_gland_clip_bnd",
      "solid.mises",
      "kPa",
      true,
      "0",
      "3",
      notes
    );
    tryCreateScalarResultPlot(
      model,
      "pg_cut_sagittal_vm",
      "06 Sagittal cut von Mises (kPa)",
      "surf_cut_sagittal_vm",
      "Surface",
      null,
      "solid.mises",
      "kPa",
      false,
      "0",
      "3",
      notes
    );
    trySetResultPlotProperty(model, "pg_cut_sagittal_vm", new String[] {{ "data" }}, new String[] {{ "cpl_sagittal_yz" }}, notes);
    tryCreateScalarResultPlot(
      model,
      "pg_cut_sagittal_disp",
      "07 Sagittal cut total displacement (mm)",
      "surf_cut_sagittal_disp",
      "Surface",
      null,
      "disp_mag",
      "mm",
      false,
      "0",
      "40",
      notes
    );
    trySetResultPlotProperty(model, "pg_cut_sagittal_disp", new String[] {{ "data" }}, new String[] {{ "cpl_sagittal_yz" }}, notes);

    
  }}

  private static void tryCreateCutPlaneDataset(
      Model model,
      String tag,
      String label,
      String plane,
      String coordinate,
      StringBuilder notes
    ) {{
      try {{
        model.result().dataset().create(tag, "CutPlane");
        model.result().dataset(tag).label(label);
        try {{
          model.result().dataset(tag).set("data", "dset1");
        }} catch (Exception ex) {{
          notes.append("Could not bind cut-plane dataset ").append(tag)
               .append(" to solution dataset dset1 yet: ")
               .append(ex.getMessage()).append("\\n");
        }}
        model.result().dataset(tag).set("quickplane", plane);
        if ("yz".equals(plane)) {{
          model.result().dataset(tag).set("quickx", coordinate);
        }} else if ("xz".equals(plane)) {{
          model.result().dataset(tag).set("quicky", coordinate);
        }} else if ("xy".equals(plane)) {{
          model.result().dataset(tag).set("quickz", coordinate);
        }}
        notes.append("Created result cut-plane dataset ").append(tag).append("\\n");
      }} catch (Exception ex) {{
        notes.append("Could not create result cut-plane dataset ").append(tag)
             .append(": ").append(ex.getMessage()).append("\\n");
      }}
    }}

  private static void tryCreateScalarResultPlot(
      Model model,
      String plotTag,
      String label,
      String featureTag,
      String featureType,
      String selectionName,
      String expr,
      String unit,
      boolean addDeformation,
      String colorMin,
      String colorMax,
      StringBuilder notes
    ) {{
      try {{
        model.result().create(plotTag, "PlotGroup3D");
        model.result(plotTag).label(label);
        trySetResultPlotProperty(model, plotTag, new String[] {{ "frametype" }}, new String[] {{ "spatial" }}, notes);
        trySetResultPlotProperty(model, plotTag, new String[] {{ "data" }}, new String[] {{ "dset1" }}, notes);
        model.result(plotTag).feature().create(featureTag, featureType);
        model.result(plotTag).feature(featureTag).label(label);
        if (selectionName != null && selectionName.length() > 0) {{
          try {{
            model.result(plotTag).feature(featureTag).selection().named(selectionName);
          }} catch (Exception ex) {{
            notes.append("Could not bind result plot ").append(plotTag)
                 .append(" to selection ").append(selectionName).append(": ")
                 .append(ex.getMessage()).append("\\n");
          }}
        }}
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "expr" }}, new String[] {{ expr }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "unit" }}, new String[] {{ unit }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "rangecoloractive", "manualrangecolor" }}, new String[] {{ "on", "true" }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "rangecolormin", "colortablemin" }}, new String[] {{ colorMin }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "rangecolormax", "colortablemax" }}, new String[] {{ colorMax }}, notes);
        if (addDeformation) {{
          trySetResultFeatureTransparency(model, plotTag, featureTag, "0.45", notes);
        }}
        if (addDeformation) {{
          try {{
            model.result(plotTag).feature(featureTag).feature().create("def1", "Deform");
            trySetResultSubfeatureVectorProperty(
              model,
              plotTag,
              featureTag,
              "def1",
              new String[] {{ "expr" }},
              new String[] {{ "u", "v", "w" }},
              notes
            );
            trySetResultSubfeatureProperty(model, plotTag, featureTag, "def1", new String[] {{ "scale", "scaleFactor" }}, new String[] {{ "1" }}, notes);
          }} catch (Exception ex) {{
            notes.append("Could not add deformation to result plot ").append(plotTag)
                 .append(": ").append(ex.getMessage()).append("\\n");
          }}
        }}
        notes.append("Created default result plot ").append(plotTag).append("\\n");
      }} catch (Exception ex) {{
        notes.append("Could not create default result plot ").append(plotTag)
             .append(": ").append(ex.getMessage()).append("\\n");
      }}
    }}

  private static void tryCreateArrowSurfaceResultPlot(
      Model model,
      String plotTag,
      String label,
      String featureTag,
      String selectionName,
      String fxExpr,
      String fyExpr,
      String fzExpr,
      StringBuilder notes
    ) {{
      try {{
        model.result().create(plotTag, "PlotGroup3D");
        model.result(plotTag).label(label);
        trySetResultPlotProperty(model, plotTag, new String[] {{ "data" }}, new String[] {{ "dset1" }}, notes);
        model.result(plotTag).feature().create(featureTag, "ArrowSurface");
        model.result(plotTag).feature(featureTag).label(label);
        if (selectionName != null && selectionName.length() > 0) {{
          try {{
            model.result(plotTag).feature(featureTag).selection().named(selectionName);
          }} catch (Exception ex) {{
            notes.append("Could not bind arrow plot ").append(plotTag)
                 .append(" to selection ").append(selectionName).append(": ")
                 .append(ex.getMessage()).append("\\n");
          }}
        }}
        trySetResultFeatureVectorProperty(
          model,
          plotTag,
          featureTag,
          new String[] {{ "expr", "arrowexpr" }},
          new String[] {{ fxExpr, fyExpr, fzExpr }},
          notes
        );
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "arrowcount" }}, new String[] {{ "40" }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "arrowlength" }}, new String[] {{ "normalized" }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "arrowbase" }}, new String[] {{ "center" }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "inheritarrowscale" }}, new String[] {{ "off" }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "scale", "scaleFactor" }}, new String[] {{ "0.0008" }}, notes);
        trySetResultFeatureProperty(model, plotTag, featureTag, new String[] {{ "color" }}, new String[] {{ "black" }}, notes);
        trySetResultFeatureTransparency(model, plotTag, featureTag, "0.15", notes);
        notes.append("Created default Cooper arrow plot ").append(plotTag).append("\\n");
      }} catch (Exception ex) {{
        notes.append("Could not create default Cooper arrow plot ").append(plotTag)
             .append(": ").append(ex.getMessage()).append("\\n");
      }}
    }}

  private static void trySetResultPlotProperty(
      Model model,
      String plotTag,
      String[] keys,
      String[] values,
      StringBuilder notes
    ) {{
      for (String key : keys) {{
        for (String value : values) {{
          try {{
            model.result(plotTag).set(key, value);
            return;
          }} catch (Exception ignored) {{
          }}
        }}
      }}
      notes.append("Could not set result plot property on ").append(plotTag).append("\\n");
    }}

  private static void trySetResultFeatureProperty(
      Model model,
      String plotTag,
      String featureTag,
      String[] keys,
      String[] values,
      StringBuilder notes
    ) {{
      for (String key : keys) {{
        for (String value : values) {{
          try {{
            model.result(plotTag).feature(featureTag).set(key, value);
            return;
          }} catch (Exception ignored) {{
          }}
        }}
      }}
      notes.append("Could not set result feature property on ").append(plotTag)
           .append("/").append(featureTag).append("\\n");
    }}

  private static void trySetResultFeatureTransparency(
      Model model,
      String plotTag,
      String featureTag,
      String transparencyValue,
      StringBuilder notes
    ) {{
      boolean activeSet = false;
      String[] activeKeys = new String[] {{ "transparencyactive", "transparent", "alphaactive" }};
      String[] activeValues = new String[] {{ "on", "true" }};
      for (String key : activeKeys) {{
        for (String value : activeValues) {{
          try {{
            model.result(plotTag).feature(featureTag).set(key, value);
            activeSet = true;
            break;
          }} catch (Exception ignored) {{
          }}
        }}
        if (activeSet) {{
          break;
        }}
      }}

      boolean valueSet = false;
      String[] valueKeys = new String[] {{ "transparency", "alpha", "opacity", "transparencyvalue" }};
      for (String key : valueKeys) {{
        try {{
          model.result(plotTag).feature(featureTag).set(key, transparencyValue);
          valueSet = true;
          break;
        }} catch (Exception ignored) {{
        }}
      }}

      if (activeSet || valueSet) {{
        notes.append("Applied transparency to result feature ")
             .append(plotTag).append("/").append(featureTag).append("\\n");
      }} else {{
        notes.append("Transparency was not supported for result feature ")
             .append(plotTag).append("/").append(featureTag).append("\\n");
      }}
    }}

  private static void trySetResultFeatureVectorProperty(
      Model model,
      String plotTag,
      String featureTag,
      String[] keys,
      String[] values,
      StringBuilder notes
    ) {{
      for (String key : keys) {{
        try {{
          model.result(plotTag).feature(featureTag).set(key, values);
          return;
        }} catch (Exception ignored) {{
        }}
      }}
      notes.append("Could not set result feature vector property on ").append(plotTag)
           .append("/").append(featureTag).append("\\n");
    }}

  private static void trySetResultSubfeatureProperty(
      Model model,
      String plotTag,
      String featureTag,
      String subfeatureTag,
      String[] keys,
      String[] values,
      StringBuilder notes
    ) {{
      for (String key : keys) {{
        for (String value : values) {{
          try {{
            model.result(plotTag).feature(featureTag).feature(subfeatureTag).set(key, value);
            return;
          }} catch (Exception ignored) {{
          }}
        }}
      }}
      notes.append("Could not set result subfeature property on ").append(plotTag)
           .append("/").append(featureTag).append("/").append(subfeatureTag).append("\\n");
    }}

  private static void trySetResultSubfeatureVectorProperty(
      Model model,
      String plotTag,
      String featureTag,
      String subfeatureTag,
      String[] keys,
      String[] values,
      StringBuilder notes
    ) {{
      for (String key : keys) {{
        try {{
          model.result(plotTag).feature(featureTag).feature(subfeatureTag).set(key, values);
          return;
        }} catch (Exception ignored) {{
        }}
      }}
      notes.append("Could not set result subfeature vector property on ").append(plotTag)
           .append("/").append(featureTag).append("/").append(subfeatureTag).append("\\n");
    }}
  
  private static String tryCreateRayleighDampingSubfeature(
      Model model,
      String physicsTag,
    String parentFeatureTag,
    String dampingTag,
    String alphaExpr,
    String betaExpr,
    StringBuilder notes
  ) {{
    String[] candidateIds = new String[] {{ "Damping", "dmp" }};
    for (String candidateId : candidateIds) {{
      try {{
        model.component("comp1").physics(physicsTag).feature(parentFeatureTag).create(dampingTag, candidateId);
        trySetSubfeatureProperty(
          model,
          physicsTag,
          parentFeatureTag,
          dampingTag,
          new String[] {{ "DampingType", "dampingtype", "dampType", "type" }},
          new String[] {{ "RayleighDamping", "Rayleigh damping", "Rayleigh" }},
          notes
        );
        trySetSubfeatureProperty(
          model,
          physicsTag,
          parentFeatureTag,
          dampingTag,
          new String[] {{ "alpha_dM", "alphadM", "alpha", "alphaDM" }},
          new String[] {{ alphaExpr }},
          notes
        );
        trySetSubfeatureProperty(
          model,
          physicsTag,
          parentFeatureTag,
          dampingTag,
          new String[] {{ "beta_dK", "betadK", "beta", "betaDK" }},
          new String[] {{ betaExpr }},
          notes
        );
        notes.append("Created damping subfeature ").append(dampingTag).append(" under ").append(parentFeatureTag).append(" with id ").append(candidateId).append("\\n");
        return dampingTag;
      }} catch (Exception ex) {{
        notes.append("Damping subfeature id ").append(candidateId).append(" failed on ").append(parentFeatureTag).append(": ").append(ex.getMessage()).append("\\n");
      }}
    }}
    return null;
  }}

  private static void trySetSubfeatureProperty(
    Model model,
    String physicsTag,
    String parentFeatureTag,
    String featureTag,
    String[] keys,
    String[] values,
    StringBuilder notes
  ) {{
    for (String key : keys) {{
      for (String value : values) {{
        try {{
          model.component("comp1").physics(physicsTag).feature(parentFeatureTag).feature(featureTag).set(key, value);
          notes.append("Set ").append(parentFeatureTag).append("/").append(featureTag).append(".").append(key).append("=").append(value).append("\\n");
          return;
        }} catch (Exception ignored) {{
        }}
        try {{
          model.component("comp1").physics(physicsTag).feature(parentFeatureTag).feature(featureTag).set(key, new String[] {{ value }});
          notes.append("Set ").append(parentFeatureTag).append("/").append(featureTag).append(".").append(key).append("=[").append(value).append("]\\n");
          return;
        }} catch (Exception ignored) {{
        }}
      }}
    }}
  }}

  private static void tryRestrictLinearElasticFeature(Model model, String physicsTag, String selectionName, StringBuilder notes) {{
    String[] candidateTags = new String[] {{ "lemm1", "lemm", "linel1", "linel" }};
    for (String candidateTag : candidateTags) {{
      try {{
        model.component("comp1").physics(physicsTag).feature(candidateTag).selection().named(selectionName);
        notes.append("Restricted linear elastic feature ").append(candidateTag).append(" to ").append(selectionName).append("\\n");
        return;
      }} catch (Exception ignored) {{
      }}
    }}
    try {{
      for (String featureTag : model.component("comp1").physics(physicsTag).feature().tags()) {{
        String normalized = featureTag.toLowerCase();
        if (!(normalized.contains("lemm") || normalized.contains("linel"))) {{
          continue;
        }}
        try {{
          model.component("comp1").physics(physicsTag).feature(featureTag).selection().named(selectionName);
          notes.append("Restricted discovered linear elastic feature ").append(featureTag).append(" to ").append(selectionName).append("\\n");
          return;
        }} catch (Exception ignored) {{
        }}
      }}
    }} catch (Exception ex) {{
      notes.append("Could not inspect linear elastic features on ").append(physicsTag).append(": ").append(ex.getMessage()).append("\\n");
      return;
    }}
    notes.append("Could not automatically restrict default linear elastic feature on ").append(physicsTag).append(".\\n");
  }}

  private static void tryDeactivateLinearElasticFeatures(Model model, String physicsTag, StringBuilder notes) {{
    String[] candidateTags = new String[] {{ "lemm1", "lemm", "linel1", "linel" }};
    for (String candidateTag : candidateTags) {{
      if (tryDeactivateFeature(model, physicsTag, candidateTag, notes)) {{
        return;
      }}
    }}
    try {{
      for (String featureTag : model.component("comp1").physics(physicsTag).feature().tags()) {{
        String normalized = featureTag.toLowerCase();
        if (!(normalized.contains("lemm") || normalized.contains("linel"))) {{
          continue;
        }}
        if (tryDeactivateFeature(model, physicsTag, featureTag, notes)) {{
          return;
        }}
      }}
    }} catch (Exception ex) {{
      notes.append("Could not inspect shell linear elastic features on ").append(physicsTag).append(": ").append(ex.getMessage()).append("\\n");
      return;
    }}
    notes.append("Could not automatically deactivate default linear elastic feature on ").append(physicsTag).append(".\\n");
  }}

  private static boolean tryDeactivateFeature(Model model, String physicsTag, String featureTag, StringBuilder notes) {{
    try {{
      model.component("comp1").physics(physicsTag).feature(featureTag).active(false);
      notes.append("Deactivated feature ").append(featureTag).append(" on ").append(physicsTag).append("\\n");
      return true;
    }} catch (Exception ignored) {{
    }}
    return false;
  }}
{lobule_builder_method_java}
{lobule_helper_methods_java}
}}
"""
    java_source = java_source.replace("GRAVITY_Z_EXPRESSION_PLACEHOLDER", gravity_z_expression)
    java_source = java_source.replace(
        "DYNAMIC_SUPPORT_MOTION_BLOCK_PLACEHOLDER",
        prescribed_support_motion_java,
    )
    script_path.write_text(java_source, encoding="utf-8")

    readme_path = output_dir / f"{case_name}_comsol_builder_README.txt"
    postprocess_class_name = "ComsolPostprocess"
    postprocess_java_path = output_dir / f"{postprocess_class_name}.java"
    postprocess_result_mph_java = (solve_dir / f"{case_name}_result.mph").resolve().as_posix()
    postprocess_metrics_json_java = metrics_json_path.resolve().as_posix()
    postprocess_progress_log_java = (output_root / "postprocess_progress.log").resolve().as_posix()
    build_verification_class_name = _safe_java_identifier(f"{case_name}_comsol_verify_build")
    build_verification_java_path = output_dir / f"{build_verification_class_name}.java"
    solve_verification_class_name = _safe_java_identifier(f"{case_name}_comsol_verify_solve")
    solve_verification_java_path = solve_dir / f"{solve_verification_class_name}.java"
    generated_verify_json_path = output_dir / f"{case_name}_build_verification.json"
    solve_verify_json_path = solve_dir / f"{case_name}_solve_verification.json"
    generated_mph_java = result_mph.resolve().as_posix()
    generated_mph_fallback_java = result_mph.with_name(f"{result_mph.stem}_Model{result_mph.suffix}").resolve().as_posix()
    plot_screen_dir_java = (output_dir.parent / "plot_screens_auto").resolve().as_posix()
    postprocess_java = f"""import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.File;
import java.io.FileWriter;

public class {postprocess_class_name} {{
  private static final String PROGRESS_LOG_PATH = "{postprocess_progress_log_java}";

  private static double firstReal(double[][] values) {{
    if (values == null || values.length == 0 || values[0].length == 0) {{
      return Double.NaN;
    }}
    return values[0][0];
  }}

  private static double[] firstRow(double[][] values) {{
    if (values == null || values.length == 0) {{
      return new double[0];
    }}
    return values[0];
  }}

  private static void removeNumericalIfExists(Model model, String tag) {{
    try {{
      model.result().numerical().remove(tag);
    }} catch (Exception ignored) {{
    }}
  }}

  private static double evalIntVolume(Model model, String tag, String selectionTag, String expr) {{
    removeNumericalIfExists(model, tag);
    model.result().numerical().create(tag, "IntVolume");
    model.result().numerical(tag).selection().named(selectionTag);
    model.result().numerical(tag).set("expr", new String[] {{ expr }});
    return firstReal(model.result().numerical(tag).getReal());
  }}

  private static double[] evalIntVolumeSeries(Model model, String tag, String selectionTag, String expr) {{
    removeNumericalIfExists(model, tag);
    model.result().numerical().create(tag, "IntVolume");
    model.result().numerical(tag).selection().named(selectionTag);
    model.result().numerical(tag).set("expr", new String[] {{ expr }});
    return firstRow(model.result().numerical(tag).getReal());
  }}

  private static double evalMaxVolume(Model model, String tag, String selectionTag, String expr) {{
    removeNumericalIfExists(model, tag);
    model.result().numerical().create(tag, "MaxVolume");
    model.result().numerical(tag).selection().named(selectionTag);
    model.result().numerical(tag).set("expr", new String[] {{ expr }});
    return firstReal(model.result().numerical(tag).getReal());
  }}

  private static double[] evalMaxVolumeSeries(Model model, String tag, String selectionTag, String expr) {{
    removeNumericalIfExists(model, tag);
    model.result().numerical().create(tag, "MaxVolume");
    model.result().numerical(tag).selection().named(selectionTag);
    model.result().numerical(tag).set("expr", new String[] {{ expr }});
    return firstRow(model.result().numerical(tag).getReal());
  }}

  private static double evalIntSurface(Model model, String tag, String selectionTag, String expr) {{
    try {{
      removeNumericalIfExists(model, tag);
      model.result().numerical().create(tag, "IntSurface");
      model.result().numerical(tag).selection().named(selectionTag);
      model.result().numerical(tag).set("expr", new String[] {{ expr }});
      return firstReal(model.result().numerical(tag).getReal());
    }} catch (Exception ex) {{
      return Double.NaN;
    }}
  }}

  private static double[] evalIntSurfaceSeries(Model model, String tag, String selectionTag, String expr) {{
    try {{
      removeNumericalIfExists(model, tag);
      model.result().numerical().create(tag, "IntSurface");
      model.result().numerical(tag).selection().named(selectionTag);
      model.result().numerical(tag).set("expr", new String[] {{ expr }});
      return firstRow(model.result().numerical(tag).getReal());
    }} catch (Exception ex) {{
      return new double[0];
    }}
  }}

  private static double[] evalMaxSurfaceSeries(Model model, String tag, String selectionTag, String expr) {{
    try {{
      removeNumericalIfExists(model, tag);
      model.result().numerical().create(tag, "MaxSurface");
      model.result().numerical(tag).selection().named(selectionTag);
      model.result().numerical(tag).set("expr", new String[] {{ expr }});
      return firstRow(model.result().numerical(tag).getReal());
    }} catch (Exception ex) {{
      return new double[0];
    }}
  }}

  private static double[] evalMinSurfaceSeries(Model model, String tag, String selectionTag, String expr) {{
    try {{
      removeNumericalIfExists(model, tag);
      model.result().numerical().create(tag, "MinSurface");
      model.result().numerical(tag).selection().named(selectionTag);
      model.result().numerical(tag).set("expr", new String[] {{ expr }});
      return firstRow(model.result().numerical(tag).getReal());
    }} catch (Exception ex) {{
      return new double[0];
    }}
  }}

  private static String detectSolutionTag(Model model) {{
    try {{
      String[] tags = model.sol().tags();
      if (tags != null && tags.length > 0) {{
        return tags[0];
      }}
    }} catch (Exception ignored) {{
    }}
    return "sol1";
  }}

  private static double[] getTimeValues(Model model) {{
    try {{
      String solTag = detectSolutionTag(model);
      double[][] values = model.sol(solTag).getSolutioninfo().getVals(0, new int[] {{ 0 }});
      if (values != null && values.length > 0) {{
        return values[0];
      }}
    }} catch (Exception ignored) {{
    }}
    return new double[0];
  }}

  private static int closestTimeIndexOneBased(double[] values, double target) {{
    if (values == null || values.length == 0) {{
      return 1;
    }}
    int bestIdx = 0;
    double bestDistance = Math.abs(values[0] - target);
    for (int i = 1; i < values.length; i++) {{
      double distance = Math.abs(values[i] - target);
      if (distance < bestDistance) {{
        bestDistance = distance;
        bestIdx = i;
      }}
    }}
    return bestIdx + 1;
  }}

  private static void trySetPlotData(Model model, String plotTag, String datasetTag) {{
    try {{
      model.result(plotTag).set("data", datasetTag);
    }} catch (Exception ignored) {{
    }}
  }}

  private static void trySetDatasetData(Model model, String datasetTag, String sourceDatasetTag) {{
    try {{
      model.result().dataset(datasetTag).set("data", sourceDatasetTag);
    }} catch (Exception ignored) {{
    }}
  }}

  private static void ensureDefaultResultPlotData(Model model) {{
    String solutionDatasetTag = "dset1";
    trySetDatasetData(model, "cpl_sagittal_yz", solutionDatasetTag);
    trySetDatasetData(model, "cpl_frontal_xz", solutionDatasetTag);
    trySetDatasetData(model, "cpl_transverse_xy", solutionDatasetTag);

    trySetPlotData(model, "pg_disp_total", solutionDatasetTag);
    trySetPlotData(model, "pg_disp_z", solutionDatasetTag);
    trySetPlotData(model, "pg_disp_y", solutionDatasetTag);
    trySetPlotData(model, "pg_vm_breast", solutionDatasetTag);
    trySetPlotData(model, "pg_vm_gland", solutionDatasetTag);
    trySetPlotData(model, "pg_cut_sagittal_vm", "cpl_sagittal_yz");
    trySetPlotData(model, "pg_cut_sagittal_disp", "cpl_sagittal_yz");
  }}

  private static boolean selectionExists(Model model, String tag) {{
    try {{
      model.component("comp1").selection(tag);
      return true;
    }} catch (Exception ex) {{
      return false;
    }}
  }}

  private static void ensureBoundaryBoxSelection(
      Model model,
      String tag,
      String label,
      String xmin,
      String xmax,
      String ymin,
      String ymax,
      String zmin,
      String zmax
    ) {{
    if (selectionExists(model, tag)) {{
      return;
    }}
    try {{
      model.component("comp1").selection().create(tag, "Box");
      model.component("comp1").selection(tag).label(label);
      model.component("comp1").selection(tag).geom("geom1", 2);
      model.component("comp1").selection(tag).set("condition", "inside");
      model.component("comp1").selection(tag).set("xmin", xmin);
      model.component("comp1").selection(tag).set("xmax", xmax);
      model.component("comp1").selection(tag).set("ymin", ymin);
      model.component("comp1").selection(tag).set("ymax", ymax);
      model.component("comp1").selection(tag).set("zmin", zmin);
      model.component("comp1").selection(tag).set("zmax", zmax);
    }} catch (Exception ignored) {{
    }}
  }}

  private static void ensureBoundaryIntersectionSelection(
      Model model,
      String tag,
      String label,
      String[] inputTags
    ) {{
    if (selectionExists(model, tag)) {{
      return;
    }}
    try {{
      model.component("comp1").selection().create(tag, "Intersection");
      model.component("comp1").selection(tag).label(label);
      model.component("comp1").selection(tag).geom("geom1", 2);
      model.component("comp1").selection(tag).set("input", inputTags);
    }} catch (Exception ignored) {{
    }}
  }}

  private static void ensureBoundaryDifferenceSelection(
      Model model,
      String tag,
      String label,
      String addTag,
      String[] subtractTags,
      String fallbackSelection
    ) {{
    if (selectionExists(model, tag)) {{
      return;
    }}
    try {{
      model.component("comp1").selection().create(tag, "Difference");
      model.component("comp1").selection(tag).label(label);
      model.component("comp1").selection(tag).geom("geom1", 2);
      model.component("comp1").selection(tag).set("add", new String[] {{ addTag }});
      model.component("comp1").selection(tag).set("subtract", subtractTags);
    }} catch (Exception ex) {{
      try {{
        model.component("comp1").selection().duplicate(tag, fallbackSelection);
        model.component("comp1").selection(tag).label(label + " (fallback full outer surface)");
      }} catch (Exception ignored) {{
      }}
    }}
  }}

  private static void ensureExtendedEvaluationSelections(Model model) {{
    ensureBoundaryDifferenceSelection(
      model,
      "outer_skin_free_bnd",
      "Free Outer Breast Skin Surface",
      "geom1_breast_outer_bnd",
      new String[] {{ "breast_attach_bnd" }},
      "geom1_breast_outer_bnd"
    );
    ensureBoundaryBoxSelection(
      model,
      "nipple_support_box_bnd",
      "Cooper Ligament Subareolar Support Box",
      "{nipple_support_sel_xmin:.12f}",
      "{nipple_support_sel_xmax:.12f}",
      "{nipple_support_sel_ymin:.12f}",
      "{nipple_support_sel_ymax:.12f}",
      "{-nipple_support_sel_half_z:.12f}",
      "{nipple_support_sel_half_z:.12f}"
    );
    ensureBoundaryIntersectionSelection(
      model,
      "landmark_nipple_bnd",
      "Nipple Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "nipple_support_box_bnd" }}
    );
    ensureBoundaryBoxSelection(
      model,
      "landmark_left_box_bnd",
      "Left Landmark Search Box",
      "{-comsol_outer_axis_x:.12f}",
      "{(-comsol_outer_axis_x + landmark_side_band_x):.12f}",
      "{landmark_ymin:.12f}",
      "{landmark_ymax:.12f}",
      "{landmark_side_zmin:.12f}",
      "{landmark_side_zmax:.12f}"
    );
    ensureBoundaryIntersectionSelection(
      model,
      "landmark_left_bnd",
      "Left Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_left_box_bnd" }}
    );
    ensureBoundaryBoxSelection(
      model,
      "landmark_right_box_bnd",
      "Right Landmark Search Box",
      "{(comsol_outer_axis_x - landmark_side_band_x):.12f}",
      "{comsol_outer_axis_x:.12f}",
      "{landmark_ymin:.12f}",
      "{landmark_ymax:.12f}",
      "{landmark_side_zmin:.12f}",
      "{landmark_side_zmax:.12f}"
    );
    ensureBoundaryIntersectionSelection(
      model,
      "landmark_right_bnd",
      "Right Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_right_box_bnd" }}
    );
    ensureBoundaryBoxSelection(
      model,
      "landmark_superior_box_bnd",
      "Superior Landmark Search Box",
      "{landmark_pole_xmin:.12f}",
      "{landmark_pole_xmax:.12f}",
      "{landmark_ymin:.12f}",
      "{landmark_ymax:.12f}",
      "{(comsol_outer_axis_z - landmark_pole_band_z):.12f}",
      "{comsol_outer_axis_z:.12f}"
    );
    ensureBoundaryIntersectionSelection(
      model,
      "landmark_superior_bnd",
      "Superior Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_superior_box_bnd" }}
    );
    ensureBoundaryBoxSelection(
      model,
      "landmark_inferior_box_bnd",
      "Inferior Landmark Search Box",
      "{landmark_pole_xmin:.12f}",
      "{landmark_pole_xmax:.12f}",
      "{landmark_ymin:.12f}",
      "{landmark_ymax:.12f}",
      "{-comsol_outer_axis_z:.12f}",
      "{(-comsol_outer_axis_z + landmark_pole_band_z):.12f}"
    );
    ensureBoundaryIntersectionSelection(
      model,
      "landmark_inferior_bnd",
      "Inferior Outer-Skin Landmark Patch",
      new String[] {{ "outer_skin_free_bnd", "landmark_inferior_box_bnd" }}
    );
  }}

  private static void trySetPlotReviewTime(Model model, String plotTag, int timeIndexOneBased) {{
    String timeIndex = Integer.toString(Math.max(1, timeIndexOneBased));
    try {{
      model.result(plotTag).set("looplevelinput", new String[] {{ "manual" }});
    }} catch (Exception ignored) {{
    }}
    try {{
      model.result(plotTag).set("looplevel", new String[] {{ timeIndex }});
    }} catch (Exception ignored) {{
    }}
    try {{
      model.result(plotTag).setIndex("looplevel", timeIndex, 0);
    }} catch (Exception ignored) {{
    }}
  }}

  private static void trySetExportProperty(Model model, String exportTag, String[] propertyNames, String value) {{
    for (String propertyName : propertyNames) {{
      try {{
        model.result().export(exportTag).set(propertyName, value);
        return;
      }} catch (Exception ignored) {{
      }}
    }}
  }}

  private static void trySetFrontCamera(Model model, String plotTag) {{
    try {{
      model.result(plotTag).set("view", "view1");
    }} catch (Exception ignored) {{
    }}
    try {{
      model.component("comp1").view("view1").camera().set("position", new double[] {{ -0.18, 0.24, 0.12 }});
      model.component("comp1").view("view1").camera().set("target", new double[] {{ 0.0, 0.035, 0.0 }});
      model.component("comp1").view("view1").camera().set("up", new double[] {{ 0.0, 0.0, 1.0 }});
      model.component("comp1").view("view1").camera().set("zoomangle", 26.0);
    }} catch (Exception ignored) {{
    }}
  }}

  private static void trySetCutPlaneCamera(Model model, String plotTag) {{
    try {{
      model.result(plotTag).set("view", "view1");
    }} catch (Exception ignored) {{
    }}
    try {{
      model.component("comp1").view("view1").camera().set("position", new double[] {{ 0.18, -0.24, 0.12 }});
      model.component("comp1").view("view1").camera().set("target", new double[] {{ 0.0, 0.02, 0.0 }});
      model.component("comp1").view("view1").camera().set("up", new double[] {{ 0.0, 0.0, 1.0 }});
      model.component("comp1").view("view1").camera().set("zoomangle", 28.0);
    }} catch (Exception ignored) {{
    }}
  }}

  private static void tryExportPlotImage(Model model, String exportTag, String plotTag, String outputFile, int timeIndexOneBased) {{
    try {{
      trySetPlotReviewTime(model, plotTag, timeIndexOneBased);
      if (plotTag.equals("pg_cut_sagittal_vm") || plotTag.equals("pg_cut_sagittal_disp")) {{
        trySetCutPlaneCamera(model, plotTag);
      }} else {{
        trySetFrontCamera(model, plotTag);
      }}
      try {{
        model.result(plotTag).run();
      }} catch (Exception ignored) {{
      }}
      try {{
        model.result().export().create(exportTag, "Image3D");
      }} catch (Exception ignored) {{
      }}
      trySetExportProperty(model, exportTag, new String[] {{ "plotgroup" }}, plotTag);
      trySetExportProperty(model, exportTag, new String[] {{ "imagetype" }}, "png");
      trySetExportProperty(model, exportTag, new String[] {{ "pngfilename", "filename" }}, outputFile);
      trySetExportProperty(model, exportTag, new String[] {{ "width" }}, "1600");
      trySetExportProperty(model, exportTag, new String[] {{ "height" }}, "1000");
      trySetExportProperty(model, exportTag, new String[] {{ "unit" }}, "px");
      trySetExportProperty(model, exportTag, new String[] {{ "resolution" }}, "150");
      model.result().export(exportTag).run();
      System.out.println("COMSOL_IMAGE_EXPORT " + outputFile);
    }} catch (Exception ex) {{
      System.out.println("COMSOL_IMAGE_EXPORT_FAILED " + plotTag + " " + ex.getMessage());
    }}
  }}

  private static void exportDefaultPlotImages(Model model, String outputDir, int timeIndexOneBased) {{
    try {{
      new File(outputDir).mkdirs();
    }} catch (Exception ignored) {{
    }}
    String[] plotTags = new String[] {{
      "pg_disp_total",
      "pg_disp_z",
      "pg_disp_y",
      "pg_vm_breast",
      "pg_vm_gland",
      "pg_cut_sagittal_vm",
      "pg_cut_sagittal_disp"
    }};
    String[] filenames = new String[] {{
      "01_total_displacement_mm.png",
      "02_vertical_displacement_w_mm.png",
      "03_anterior_posterior_displacement_v_mm.png",
      "04_breast_von_mises_kpa.png",
      "05_glandular_von_mises_kpa.png",
      "06_sagittal_cut_von_mises_kpa.png",
      "07_sagittal_cut_total_displacement_mm.png"
    }};
    for (int i = 0; i < plotTags.length; i++) {{
      tryExportPlotImage(model, "img_auto_" + (i + 1), plotTags[i], outputDir + "/" + filenames[i], timeIndexOneBased);
    }}
  }}

  private static int minLength(double[]... arrays) {{
    int result = Integer.MAX_VALUE;
    for (double[] array : arrays) {{
      if (array == null) {{
        continue;
      }}
      result = Math.min(result, array.length);
    }}
    return result == Integer.MAX_VALUE ? 0 : result;
  }}

  private static int peakIndex(double[] values) {{
    if (values == null || values.length == 0) {{
      return -1;
    }}
    int bestIdx = 0;
    double bestVal = values[0];
    for (int i = 1; i < values.length; i++) {{
      if (values[i] > bestVal) {{
        bestVal = values[i];
        bestIdx = i;
      }}
    }}
    return bestIdx;
  }}

  private static double safeAt(double[] values, int idx) {{
    if (values == null || idx < 0 || idx >= values.length) {{
      return Double.NaN;
    }}
    return values[idx];
  }}

  private static double safeDivide(double numerator, double denominator) {{
    if (Double.isNaN(numerator) || Double.isInfinite(numerator) || denominator == 0.0 || Double.isNaN(denominator)) {{
      return Double.NaN;
    }}
    return numerator / denominator;
  }}

  private static double safeStd(double mean, double meanSquares) {{
    if (Double.isNaN(mean) || Double.isNaN(meanSquares)) {{
      return Double.NaN;
    }}
    double variance = meanSquares - mean * mean;
    if (variance < 0.0 && variance > -1.0e-18) {{
      variance = 0.0;
    }}
    return variance >= 0.0 ? Math.sqrt(variance) : Double.NaN;
  }}

  private static double[] meanFromIntegralSeries(double[] integrals, double measure, int n) {{
    double[] out = new double[n];
    for (int i = 0; i < n; i++) {{
      out[i] = safeDivide(safeAt(integrals, i), measure);
    }}
    return out;
  }}

  private static double[] stdFromIntegralSeries(double[] integrals, double[] squareIntegrals, double measure, int n) {{
    double[] out = new double[n];
    for (int i = 0; i < n; i++) {{
      double mean = safeDivide(safeAt(integrals, i), measure);
      double meanSquares = safeDivide(safeAt(squareIntegrals, i), measure);
      out[i] = safeStd(mean, meanSquares);
    }}
    return out;
  }}

  private static double[] hotspotSeries(double[] maxValues, double[] meanValues, int n) {{
    double[] out = new double[n];
    for (int i = 0; i < n; i++) {{
      out[i] = safeDivide(safeAt(maxValues, i), safeAt(meanValues, i));
    }}
    return out;
  }}

  private static double[] evalSurfaceMeanSeries(
      Model model,
      String tag,
      String selectionTag,
      String expr,
      double measure,
      int n
    ) {{
    return meanFromIntegralSeries(evalIntSurfaceSeries(model, tag, selectionTag, expr), measure, n);
  }}

  private static double maxFinite(double[] values) {{
    if (values == null || values.length == 0) {{
      return Double.NaN;
    }}
    double best = Double.NaN;
    for (int i = 0; i < values.length; i++) {{
      double value = values[i];
      if (Double.isNaN(value) || Double.isInfinite(value)) {{
        continue;
      }}
      if (Double.isNaN(best) || value > best) {{
        best = value;
      }}
    }}
    return best;
  }}

  private static String formatArray(double[] values, int n) {{
    StringBuilder sb = new StringBuilder();
    sb.append("[");
    for (int i = 0; i < n; i++) {{
      if (i > 0) {{
        sb.append(", ");
      }}
      sb.append(safeAt(values, i));
    }}
    sb.append("]");
    return sb.toString();
  }}

  private static double[] nanArray(int n) {{
    double[] out = new double[n];
    for (int i = 0; i < n; i++) {{
      out[i] = Double.NaN;
    }}
    return out;
  }}

  private static void postprocessStatus(String status) {{
    System.out.println("COMSOL_POSTPROCESS_STATUS " + status);
    System.out.flush();
    try {{
      FileWriter writer = new FileWriter(PROGRESS_LOG_PATH, true);
      writer.write(new java.util.Date().toString() + " COMSOL_POSTPROCESS_STATUS " + status + "\\n");
      writer.close();
    }} catch (Exception ignored) {{
    }}
  }}

  public static Model run() throws Exception {{
    postprocessStatus("init_start");
    ModelUtil.initStandalone(true);
    postprocessStatus("init_complete");
    postprocessStatus("load_start");
    Model model = ModelUtil.load("PostModel", "{postprocess_result_mph_java}");
    postprocessStatus("load_complete");
    String postprocessMode = "{postprocess_mode_java}";
    boolean tumorMetricsEnabled = {str(tumor_enabled).lower()};
    boolean exportTumorMetrics = tumorMetricsEnabled && (postprocessMode.equals("full") || postprocessMode.equals("internal_tumor") || postprocessMode.equals("global"));
    boolean exportSurfaceMetrics = postprocessMode.equals("full") || postprocessMode.equals("ews_surface");
    boolean exportLandmarkMetrics = postprocessMode.equals("full") || postprocessMode.equals("ews_surface");
    boolean exportStressStdMetrics = postprocessMode.equals("full");
    boolean exportImages = postprocessMode.equals("full") && {postprocess_export_plot_images_java};
    if (exportSurfaceMetrics || exportLandmarkMetrics) {{
      ensureExtendedEvaluationSelections(model);
      postprocessStatus("extended_selections_ready");
    }} else {{
      postprocessStatus("extended_selections_skipped_by_mode");
    }}
    if (exportImages) {{
      ensureDefaultResultPlotData(model);
      postprocessStatus("plot_setup_ready");
    }} else {{
      postprocessStatus("plot_setup_skipped_by_mode");
    }}

    postprocessStatus("volume_scalars_start");
    double breastVolume = evalIntVolume(model, "ivBreastVol", "geom1_breast_union_dom", "1");
    double glandVolume = evalIntVolume(model, "ivGlandVol", "geom1_gland_clip_dom", "1");
    double adiposeVolume = evalIntVolume(model, "ivAdiposeVol", "geom1_adipose_diff_dom", "1");
    double tumorVolume = exportTumorMetrics
      ? evalIntVolume(model, "ivTumorMaskVol", "geom1_breast_union_dom", "tumor_mask")
      : 0.0;
    postprocessStatus("volume_scalars_ready");

    if ({postprocess_quick_mode_java}) {{
      postprocessStatus("quick_global_displacement_start");
      double[] timeValues = getTimeValues(model);
      double[] maxDispBreastSeries = evalMaxVolumeSeries(model, "mvDispBreastSeries", "geom1_breast_union_dom", "solid.disp");
      double[] intDispBreastSeries = evalIntVolumeSeries(model, "ivDispBreastSeries", "geom1_breast_union_dom", "solid.disp");
      double[] maxDispTumorSeries = exportTumorMetrics ? evalMaxVolumeSeries(model, "mvDispTumorSeries", "geom1_breast_union_dom", "if(tumor_mask>0.5,solid.disp,0)") : new double[0];
      double[] intDispTumorSeries = exportTumorMetrics ? evalIntVolumeSeries(model, "ivDispTumorSeries", "geom1_breast_union_dom", "tumor_mask*solid.disp") : new double[0];
      int seriesLength = minLength(timeValues, maxDispBreastSeries, intDispBreastSeries);
      double[] avgDispBreastSeries = new double[seriesLength];
      double[] avgDispTumorSeries = new double[seriesLength];
      for (int i = 0; i < seriesLength; i++) {{
        avgDispBreastSeries[i] = breastVolume != 0.0 ? intDispBreastSeries[i] / breastVolume : Double.NaN;
        avgDispTumorSeries[i] = tumorVolume != 0.0 ? safeAt(intDispTumorSeries, i) / tumorVolume : Double.NaN;
      }}
      double[] nanSeries = nanArray(seriesLength);
      int peakDispIdxQuick = peakIndex(maxDispBreastSeries);
      int peakTumorDispIdxQuick = peakIndex(maxDispTumorSeries);
      int reviewIdxQuick = closestTimeIndexOneBased(timeValues, {report_review_time_s:.12f}) - 1;
      double maxDispBreast = peakDispIdxQuick >= 0 ? safeAt(maxDispBreastSeries, peakDispIdxQuick) : Double.NaN;
      double avgDispBreast = maxFinite(avgDispBreastSeries);
      double maxDispTumor = peakTumorDispIdxQuick >= 0 ? safeAt(maxDispTumorSeries, peakTumorDispIdxQuick) : Double.NaN;
      double avgDispTumor = maxFinite(avgDispTumorSeries);
      double peakDispTimeQuick = (peakDispIdxQuick >= 0 && peakDispIdxQuick < timeValues.length) ? timeValues[peakDispIdxQuick] : Double.NaN;
      double peakTumorDispTimeQuick = (peakTumorDispIdxQuick >= 0 && peakTumorDispIdxQuick < timeValues.length) ? timeValues[peakTumorDispIdxQuick] : Double.NaN;
      String q = Character.toString((char)34);
      String nl = System.lineSeparator();
      String json = ""
        + "{{" + nl
        + "  " + q + "case_name" + q + ": " + q + "{case_name}" + q + "," + nl
        + "  " + q + "source" + q + ": " + q + "COMSOL" + q + "," + nl
        + "  " + q + "coordinate_convention" + q + ": " + q + "x/u = left-right lateral; y/v = anterior-posterior; z/w = vertical. Signed report displacement uses w, with negative values indicating downward motion." + q + "," + nl
        + "  " + q + "configured_dynamic_motion_mode" + q + ": " + q + "{dynamic_motion_mode}" + q + "," + nl
        + "  " + q + "configured_dynamic_motion_profile" + q + ": " + q + "{dynamic_motion_profile}" + q + "," + nl
        + "  " + q + "postprocess_mode" + q + ": " + q + postprocessMode + q + "," + nl
        + "  " + q + "postprocess_quick_mode" + q + ": true," + nl
        + "  " + q + "postprocess_export_plot_images" + q + ": false," + nl
        + "  " + q + "postprocess_save_postprocessed_mph" + q + ": {postprocess_save_postprocessed_mph_java}," + nl
        + "  " + q + "dynamic_start_time_s" + q + ": {dynamic_start_s:.12f}," + nl
        + "  " + q + "dynamic_end_time_s" + q + ": {dynamic_end_s:.12f}," + nl
        + "  " + q + "configured_review_time_s" + q + ": {report_review_time_s:.12f}," + nl
        + "  " + q + "jump_start_time_s" + q + ": {jump_start_s:.12f}," + nl
        + "  " + q + "jump_duration_s" + q + ": {jump_duration_s:.12f}," + nl
        + "  " + q + "jump_max_height_m" + q + ": {jump_max_height_m:.12f}," + nl
        + "  " + q + "support_displacement_amplitude_m" + q + ": {support_displacement_amplitude_m:.12f}," + nl
        + "  " + q + "support_displacement_duration_s" + q + ": {support_displacement_duration_s:.12f}," + nl
        + "  " + q + "pulse_duration_s" + q + ": {pulse_duration_s:.12f}," + nl
        + "  " + q + "pulse_acceleration_amplitude_g" + q + ": {dynamic_acceleration_amplitude_g:.12f}," + nl
        + "  " + q + "dynamic_motion_boundary_selection" + q + ": " + q + "breast_attach_bnd" + q + "," + nl
        + "  " + q + "surface_displacement_selection" + q + ": " + q + "not_exported_global_quick_mode" + q + "," + nl
        + "  " + q + "support_displacement_selection" + q + ": " + q + "not_exported_global_quick_mode" + q + "," + nl
        + "  " + q + "tumor_enabled" + q + ": {str(tumor_enabled).lower()}," + nl
        + "  " + q + "tumor_radius_m" + q + ": {tumor_radius:.12f}," + nl
        + "  " + q + "tumor_diameter_mm" + q + ": {2000.0 * tumor_radius:.12f}," + nl
        + "  " + q + "tumor_position_m" + q + ": [{tumor_x:.12f}, {tumor_y:.12f}, {tumor_z:.12f}]," + nl
        + "  " + q + "tumor_nominal_sphere_volume" + q + ": {((4.0 / 3.0) * 3.141592653589793 * tumor_radius**3):.12e}," + nl
        + "  " + q + "breast_volume" + q + ": " + breastVolume + "," + nl
        + "  " + q + "glandular_volume" + q + ": " + glandVolume + "," + nl
        + "  " + q + "adipose_volume" + q + ": " + adiposeVolume + "," + nl
        + "  " + q + "tumor_volume" + q + ": " + tumorVolume + "," + nl
        + "  " + q + "max_displacement_breast" + q + ": " + maxDispBreast + "," + nl
        + "  " + q + "avg_displacement_breast" + q + ": " + avgDispBreast + "," + nl
        + "  " + q + "max_displacement_tumor" + q + ": " + maxDispTumor + "," + nl
        + "  " + q + "avg_displacement_tumor" + q + ": " + avgDispTumor + "," + nl
        + "  " + q + "max_von_mises_breast" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "max_von_mises_glandular" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "max_von_mises_adipose" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "max_von_mises_tumor" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "avg_von_mises_breast" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "avg_von_mises_glandular" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "avg_von_mises_adipose" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "avg_von_mises_tumor" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "hotspot_factor_breast_at_peak_vm" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "hotspot_factor_glandular_at_peak_gland_vm" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "series_length" + q + ": " + seriesLength + "," + nl
        + "  " + q + "surface_series_length" + q + ": 0," + nl
        + "  " + q + "support_series_length" + q + ": 0," + nl
        + "  " + q + "surface_area_outer_skin" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "time_of_peak_displacement_breast" + q + ": " + peakDispTimeQuick + "," + nl
        + "  " + q + "time_of_peak_von_mises_breast" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "time_of_peak_von_mises_glandular" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "time_of_peak_von_mises_adipose" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "time_of_peak_displacement_tumor" + q + ": " + peakTumorDispTimeQuick + "," + nl
        + "  " + q + "time_of_peak_von_mises_tumor" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_time_s" + q + ": " + safeAt(timeValues, reviewIdxQuick) + "," + nl
        + "  " + q + "review_max_displacement_breast" + q + ": " + safeAt(maxDispBreastSeries, reviewIdxQuick) + "," + nl
        + "  " + q + "review_avg_displacement_breast" + q + ": " + safeAt(avgDispBreastSeries, reviewIdxQuick) + "," + nl
        + "  " + q + "review_max_displacement_tumor" + q + ": " + safeAt(maxDispTumorSeries, reviewIdxQuick) + "," + nl
        + "  " + q + "review_avg_displacement_tumor" + q + ": " + safeAt(avgDispTumorSeries, reviewIdxQuick) + "," + nl
        + "  " + q + "review_max_von_mises_breast" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_max_von_mises_glandular" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_max_von_mises_adipose" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_max_von_mises_tumor" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_avg_von_mises_breast" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_avg_von_mises_glandular" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_avg_von_mises_adipose" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_avg_von_mises_tumor" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_surface_disp_mag_mean" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_surface_disp_mag_max" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_surface_signed_w_mean" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_surface_signed_w_min" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "review_surface_signed_w_max" + q + ": " + Double.NaN + "," + nl
        + "  " + q + "time_s" + q + ": " + formatArray(timeValues, seriesLength) + "," + nl
        + "  " + q + "max_displacement_breast_series" + q + ": " + formatArray(maxDispBreastSeries, seriesLength) + "," + nl
        + "  " + q + "avg_displacement_breast_series" + q + ": " + formatArray(avgDispBreastSeries, seriesLength) + "," + nl
        + "  " + q + "max_displacement_tumor_series" + q + ": " + formatArray(maxDispTumorSeries, seriesLength) + "," + nl
        + "  " + q + "avg_displacement_tumor_series" + q + ": " + formatArray(avgDispTumorSeries, seriesLength) + "," + nl
        + "  " + q + "max_von_mises_breast_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "max_von_mises_glandular_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "max_von_mises_adipose_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "max_von_mises_tumor_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "avg_von_mises_breast_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "avg_von_mises_glandular_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "avg_von_mises_adipose_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "avg_von_mises_tumor_series" + q + ": " + formatArray(nanSeries, seriesLength) + "," + nl
        + "  " + q + "stress_percentiles_status" + q + ": " + q + "global quick mode: displacement and tumor displacement exported; von Mises, surface and landmark metrics not exported." + q + nl
        + "}}" + nl;
      System.out.println("COMSOL_METRICS_JSON_BEGIN");
      System.out.print(json);
      System.out.println("COMSOL_METRICS_JSON_END");
      postprocessStatus("quick_global_metrics_ready");
      return model;
    }}

    postprocessStatus("scalar_review_metrics_start");
    postprocessStatus("scalar_review_max_disp_breast_start");
    double maxDispBreast = evalMaxVolume(model, "mvDispBreast", "geom1_breast_union_dom", "solid.disp");
    postprocessStatus("scalar_review_max_disp_breast_ready");
    postprocessStatus("scalar_review_int_disp_breast_start");
    double intDispBreast = evalIntVolume(model, "ivDispBreast", "geom1_breast_union_dom", "solid.disp");
    postprocessStatus("scalar_review_int_disp_breast_ready");
    double avgDispBreast = breastVolume != 0.0 ? intDispBreast / breastVolume : Double.NaN;
    postprocessStatus("scalar_review_tumor_disp_start");
    double maxDispTumor = exportTumorMetrics ? evalMaxVolume(model, "mvDispTumor", "geom1_breast_union_dom", "if(tumor_mask>0.5,solid.disp,0)") : Double.NaN;
    double intDispTumor = exportTumorMetrics ? evalIntVolume(model, "ivDispTumor", "geom1_breast_union_dom", "tumor_mask*solid.disp") : Double.NaN;
    postprocessStatus("scalar_review_tumor_disp_ready");
    double avgDispTumor = tumorVolume != 0.0 ? intDispTumor / tumorVolume : Double.NaN;

    postprocessStatus("scalar_review_mises_max_start");
    double maxMisesBreast = evalMaxVolume(model, "mvMisesBreast", "geom1_breast_union_dom", "solid.mises");
    double maxMisesGland = evalMaxVolume(model, "mvMisesGland", "geom1_gland_clip_dom", "solid.mises");
    double maxMisesAdipose = evalMaxVolume(model, "mvMisesAdipose", "geom1_adipose_diff_dom", "solid.mises");
    double maxMisesTumor = exportTumorMetrics ? evalMaxVolume(model, "mvMisesTumor", "geom1_breast_union_dom", "if(tumor_mask>0.5,solid.mises,0)") : Double.NaN;
    postprocessStatus("scalar_review_mises_max_ready");
    postprocessStatus("scalar_review_mises_int_start");
    double intMisesBreast = evalIntVolume(model, "ivMisesBreast", "geom1_breast_union_dom", "solid.mises");
    double intMisesGland = evalIntVolume(model, "ivMisesGland", "geom1_gland_clip_dom", "solid.mises");
    double intMisesAdipose = evalIntVolume(model, "ivMisesAdipose", "geom1_adipose_diff_dom", "solid.mises");
    double intMisesTumor = exportTumorMetrics ? evalIntVolume(model, "ivMisesTumor", "geom1_breast_union_dom", "tumor_mask*solid.mises") : Double.NaN;
    postprocessStatus("scalar_review_mises_int_ready");
    double avgMisesBreast = breastVolume != 0.0 ? intMisesBreast / breastVolume : Double.NaN;
    double avgMisesGland = glandVolume != 0.0 ? intMisesGland / glandVolume : Double.NaN;
    double avgMisesAdipose = adiposeVolume != 0.0 ? intMisesAdipose / adiposeVolume : Double.NaN;
    double avgMisesTumor = tumorVolume != 0.0 ? intMisesTumor / tumorVolume : Double.NaN;
    postprocessStatus("scalar_review_metrics_ready");

    double[] timeValues = getTimeValues(model);
    postprocessStatus("time_values_ready");
    postprocessStatus("volume_series_start");
    double[] maxDispBreastSeries = evalMaxVolumeSeries(model, "mvDispBreastSeries", "geom1_breast_union_dom", "solid.disp");
    double[] intDispBreastSeries = evalIntVolumeSeries(model, "ivDispBreastSeries", "geom1_breast_union_dom", "solid.disp");
    double[] maxDispTumorSeries = exportTumorMetrics ? evalMaxVolumeSeries(model, "mvDispTumorSeries", "geom1_breast_union_dom", "if(tumor_mask>0.5,solid.disp,0)") : new double[0];
    double[] intDispTumorSeries = exportTumorMetrics ? evalIntVolumeSeries(model, "ivDispTumorSeries", "geom1_breast_union_dom", "tumor_mask*solid.disp") : new double[0];
    double[] maxMisesBreastSeries = evalMaxVolumeSeries(model, "mvMisesBreastSeries", "geom1_breast_union_dom", "solid.mises");
    double[] maxMisesGlandSeries = evalMaxVolumeSeries(model, "mvMisesGlandSeries", "geom1_gland_clip_dom", "solid.mises");
    double[] maxMisesAdiposeSeries = evalMaxVolumeSeries(model, "mvMisesAdiposeSeries", "geom1_adipose_diff_dom", "solid.mises");
    double[] maxMisesTumorSeries = exportTumorMetrics ? evalMaxVolumeSeries(model, "mvMisesTumorSeries", "geom1_breast_union_dom", "if(tumor_mask>0.5,solid.mises,0)") : new double[0];
    double[] intMisesBreastSeries = evalIntVolumeSeries(model, "ivMisesBreastSeries", "geom1_breast_union_dom", "solid.mises");
    double[] intMisesGlandSeries = evalIntVolumeSeries(model, "ivMisesGlandSeries", "geom1_gland_clip_dom", "solid.mises");
    double[] intMisesAdiposeSeries = evalIntVolumeSeries(model, "ivMisesAdiposeSeries", "geom1_adipose_diff_dom", "solid.mises");
    double[] intMisesTumorSeries = exportTumorMetrics ? evalIntVolumeSeries(model, "ivMisesTumorSeries", "geom1_breast_union_dom", "tumor_mask*solid.mises") : new double[0];
    double[] intMisesBreastSqSeries = exportStressStdMetrics ? evalIntVolumeSeries(model, "ivMisesBreastSqSeries", "geom1_breast_union_dom", "(solid.mises)^2") : new double[0];
    double[] intMisesGlandSqSeries = exportStressStdMetrics ? evalIntVolumeSeries(model, "ivMisesGlandSqSeries", "geom1_gland_clip_dom", "(solid.mises)^2") : new double[0];
    double[] intMisesAdiposeSqSeries = exportStressStdMetrics ? evalIntVolumeSeries(model, "ivMisesAdiposeSqSeries", "geom1_adipose_diff_dom", "(solid.mises)^2") : new double[0];
    double[] intMisesTumorSqSeries = exportStressStdMetrics && exportTumorMetrics ? evalIntVolumeSeries(model, "ivMisesTumorSqSeries", "geom1_breast_union_dom", "tumor_mask*(solid.mises)^2") : new double[0];
    postprocessStatus("volume_series_ready");
    int seriesLength = minLength(
      timeValues,
      maxDispBreastSeries,
      intDispBreastSeries,
      maxMisesBreastSeries,
      maxMisesGlandSeries,
      maxMisesAdiposeSeries,
      intMisesBreastSeries,
      intMisesGlandSeries,
      intMisesAdiposeSeries
    );
    double[] avgDispBreastSeries = new double[seriesLength];
    double[] avgDispTumorSeries = new double[seriesLength];
    double[] avgMisesBreastSeries = new double[seriesLength];
    double[] avgMisesGlandSeries = new double[seriesLength];
    double[] avgMisesAdiposeSeries = new double[seriesLength];
    double[] avgMisesTumorSeries = new double[seriesLength];
    double[] stdMisesBreastSeries = new double[seriesLength];
    double[] stdMisesGlandSeries = new double[seriesLength];
    double[] stdMisesAdiposeSeries = new double[seriesLength];
    double[] stdMisesTumorSeries = new double[seriesLength];
    for (int i = 0; i < seriesLength; i++) {{
      avgDispBreastSeries[i] = breastVolume != 0.0 ? intDispBreastSeries[i] / breastVolume : Double.NaN;
      avgDispTumorSeries[i] = tumorVolume != 0.0 ? safeAt(intDispTumorSeries, i) / tumorVolume : Double.NaN;
      avgMisesBreastSeries[i] = breastVolume != 0.0 ? intMisesBreastSeries[i] / breastVolume : Double.NaN;
      avgMisesGlandSeries[i] = glandVolume != 0.0 ? intMisesGlandSeries[i] / glandVolume : Double.NaN;
      avgMisesAdiposeSeries[i] = adiposeVolume != 0.0 ? intMisesAdiposeSeries[i] / adiposeVolume : Double.NaN;
      avgMisesTumorSeries[i] = tumorVolume != 0.0 ? safeAt(intMisesTumorSeries, i) / tumorVolume : Double.NaN;
      stdMisesBreastSeries[i] = exportStressStdMetrics ? safeStd(avgMisesBreastSeries[i], safeDivide(safeAt(intMisesBreastSqSeries, i), breastVolume)) : Double.NaN;
      stdMisesGlandSeries[i] = exportStressStdMetrics ? safeStd(avgMisesGlandSeries[i], safeDivide(safeAt(intMisesGlandSqSeries, i), glandVolume)) : Double.NaN;
      stdMisesAdiposeSeries[i] = exportStressStdMetrics ? safeStd(avgMisesAdiposeSeries[i], safeDivide(safeAt(intMisesAdiposeSqSeries, i), adiposeVolume)) : Double.NaN;
      stdMisesTumorSeries[i] = exportStressStdMetrics ? safeStd(avgMisesTumorSeries[i], safeDivide(safeAt(intMisesTumorSqSeries, i), tumorVolume)) : Double.NaN;
    }}
    double[] hotspotMisesBreastSeries = hotspotSeries(maxMisesBreastSeries, avgMisesBreastSeries, seriesLength);
    double[] hotspotMisesGlandSeries = hotspotSeries(maxMisesGlandSeries, avgMisesGlandSeries, seriesLength);
    double[] hotspotMisesAdiposeSeries = hotspotSeries(maxMisesAdiposeSeries, avgMisesAdiposeSeries, seriesLength);

    if ({postprocess_quick_mode_java}) {{
      int peakDispIdxQuick = peakIndex(maxDispBreastSeries);
      int peakVmIdxQuick = peakIndex(maxMisesBreastSeries);
      int peakGlandVmIdxQuick = peakIndex(maxMisesGlandSeries);
      int peakAdiposeVmIdxQuick = peakIndex(maxMisesAdiposeSeries);
      int reviewIdxQuick = closestTimeIndexOneBased(timeValues, {report_review_time_s:.12f}) - 1;
      double peakDispTimeQuick = (peakDispIdxQuick >= 0 && peakDispIdxQuick < timeValues.length) ? timeValues[peakDispIdxQuick] : Double.NaN;
      double peakVmTimeQuick = (peakVmIdxQuick >= 0 && peakVmIdxQuick < timeValues.length) ? timeValues[peakVmIdxQuick] : Double.NaN;
      double peakGlandVmTimeQuick = (peakGlandVmIdxQuick >= 0 && peakGlandVmIdxQuick < timeValues.length) ? timeValues[peakGlandVmIdxQuick] : Double.NaN;
      double peakAdiposeVmTimeQuick = (peakAdiposeVmIdxQuick >= 0 && peakAdiposeVmIdxQuick < timeValues.length) ? timeValues[peakAdiposeVmIdxQuick] : Double.NaN;
      if (peakDispIdxQuick >= 0) {{
        maxDispBreast = maxDispBreastSeries[peakDispIdxQuick];
      }}
      if (seriesLength > 0) {{
        avgDispBreast = maxFinite(avgDispBreastSeries);
      }}
      if (peakVmIdxQuick >= 0) {{
        maxMisesBreast = maxMisesBreastSeries[peakVmIdxQuick];
      }}
      if (peakGlandVmIdxQuick >= 0) {{
        maxMisesGland = maxMisesGlandSeries[peakGlandVmIdxQuick];
      }}
      if (peakAdiposeVmIdxQuick >= 0) {{
        maxMisesAdipose = maxMisesAdiposeSeries[peakAdiposeVmIdxQuick];
      }}
      avgMisesBreast = maxFinite(avgMisesBreastSeries);
      avgMisesGland = maxFinite(avgMisesGlandSeries);
      avgMisesAdipose = maxFinite(avgMisesAdiposeSeries);
      String json = ""
        + "{{\\n"
        + "  \\"case_name\\": \\"{case_name}\\",\\n"
        + "  \\"source\\": \\"COMSOL\\",\\n"
        + "  \\"coordinate_convention\\": \\"x/u = left-right lateral; y/v = anterior-posterior; z/w = vertical. Signed report displacement uses w, with negative values indicating downward motion.\\",\\n"
        + "  \\"configured_dynamic_motion_mode\\": \\"{dynamic_motion_mode}\\",\\n"
        + "  \\"configured_dynamic_motion_profile\\": \\"{dynamic_motion_profile}\\",\\n"
        + "  \\"postprocess_quick_mode\\": true,\\n"
        + "  \\"postprocess_export_plot_images\\": false,\\n"
        + "  \\"postprocess_save_postprocessed_mph\\": {postprocess_save_postprocessed_mph_java},\\n"
        + "  \\"dynamic_start_time_s\\": {dynamic_start_s:.12f},\\n"
        + "  \\"dynamic_end_time_s\\": {dynamic_end_s:.12f},\\n"
        + "  \\"configured_review_time_s\\": {report_review_time_s:.12f},\\n"
        + "  \\"jump_start_time_s\\": {jump_start_s:.12f},\\n"
        + "  \\"jump_duration_s\\": {jump_duration_s:.12f},\\n"
        + "  \\"jump_max_height_m\\": {jump_max_height_m:.12f},\\n"
        + "  \\"support_displacement_amplitude_m\\": {support_displacement_amplitude_m:.12f},\\n"
        + "  \\"support_displacement_duration_s\\": {support_displacement_duration_s:.12f},\\n"
        + "  \\"pulse_duration_s\\": {pulse_duration_s:.12f},\\n"
        + "  \\"pulse_acceleration_amplitude_g\\": {dynamic_acceleration_amplitude_g:.12f},\\n"
        + "  \\"dynamic_motion_boundary_selection\\": \\"breast_attach_bnd\\",\\n"
        + "  \\"surface_displacement_selection\\": \\"not_exported_quick_mode\\",\\n"
        + "  \\"support_displacement_selection\\": \\"not_exported_quick_mode\\",\\n"
        + "  \\"tumor_enabled\\": {str(tumor_enabled).lower()},\\n"
        + "  \\"tumor_radius_m\\": {tumor_radius:.12f},\\n"
        + "  \\"tumor_diameter_mm\\": {2000.0 * tumor_radius:.12f},\\n"
        + "  \\"tumor_position_m\\": [{tumor_x:.12f}, {tumor_y:.12f}, {tumor_z:.12f}],\\n"
        + "  \\"tumor_nominal_sphere_volume\\": {((4.0 / 3.0) * 3.141592653589793 * tumor_radius**3):.12e},\\n"
        + "  \\"breast_volume\\": " + breastVolume + ",\\n"
        + "  \\"glandular_volume\\": " + glandVolume + ",\\n"
        + "  \\"adipose_volume\\": " + adiposeVolume + ",\\n"
        + "  \\"tumor_volume\\": " + tumorVolume + ",\\n"
        + "  \\"max_displacement_breast\\": " + maxDispBreast + ",\\n"
        + "  \\"avg_displacement_breast\\": " + avgDispBreast + ",\\n"
        + "  \\"max_displacement_tumor\\": " + maxDispTumor + ",\\n"
        + "  \\"avg_displacement_tumor\\": " + avgDispTumor + ",\\n"
        + "  \\"max_von_mises_breast\\": " + maxMisesBreast + ",\\n"
        + "  \\"max_von_mises_glandular\\": " + maxMisesGland + ",\\n"
        + "  \\"max_von_mises_adipose\\": " + maxMisesAdipose + ",\\n"
        + "  \\"max_von_mises_tumor\\": " + maxMisesTumor + ",\\n"
        + "  \\"avg_von_mises_breast\\": " + avgMisesBreast + ",\\n"
        + "  \\"avg_von_mises_glandular\\": " + avgMisesGland + ",\\n"
        + "  \\"avg_von_mises_adipose\\": " + avgMisesAdipose + ",\\n"
        + "  \\"avg_von_mises_tumor\\": " + avgMisesTumor + ",\\n"
        + "  \\"hotspot_factor_breast_at_peak_vm\\": " + (safeAt(avgMisesBreastSeries, peakVmIdxQuick) != 0.0 ? maxMisesBreast / safeAt(avgMisesBreastSeries, peakVmIdxQuick) : Double.NaN) + ",\\n"
        + "  \\"hotspot_factor_glandular_at_peak_gland_vm\\": " + (safeAt(avgMisesGlandSeries, peakGlandVmIdxQuick) != 0.0 ? maxMisesGland / safeAt(avgMisesGlandSeries, peakGlandVmIdxQuick) : Double.NaN) + ",\\n"
        + "  \\"series_length\\": " + seriesLength + ",\\n"
        + "  \\"surface_series_length\\": 0,\\n"
        + "  \\"support_series_length\\": 0,\\n"
        + "  \\"surface_area_outer_skin\\": " + Double.NaN + ",\\n"
        + "  \\"time_of_peak_displacement_breast\\": " + peakDispTimeQuick + ",\\n"
        + "  \\"time_of_peak_von_mises_breast\\": " + peakVmTimeQuick + ",\\n"
        + "  \\"time_of_peak_von_mises_glandular\\": " + peakGlandVmTimeQuick + ",\\n"
        + "  \\"time_of_peak_von_mises_adipose\\": " + peakAdiposeVmTimeQuick + ",\\n"
        + "  \\"time_of_peak_displacement_tumor\\": " + Double.NaN + ",\\n"
        + "  \\"time_of_peak_von_mises_tumor\\": " + Double.NaN + ",\\n"
        + "  \\"review_time_s\\": " + safeAt(timeValues, reviewIdxQuick) + ",\\n"
        + "  \\"review_max_displacement_breast\\": " + safeAt(maxDispBreastSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_avg_displacement_breast\\": " + safeAt(avgDispBreastSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_max_displacement_tumor\\": " + Double.NaN + ",\\n"
        + "  \\"review_avg_displacement_tumor\\": " + Double.NaN + ",\\n"
        + "  \\"review_max_von_mises_breast\\": " + safeAt(maxMisesBreastSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_max_von_mises_glandular\\": " + safeAt(maxMisesGlandSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_max_von_mises_adipose\\": " + safeAt(maxMisesAdiposeSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_max_von_mises_tumor\\": " + Double.NaN + ",\\n"
        + "  \\"review_avg_von_mises_breast\\": " + safeAt(avgMisesBreastSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_avg_von_mises_glandular\\": " + safeAt(avgMisesGlandSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_avg_von_mises_adipose\\": " + safeAt(avgMisesAdiposeSeries, reviewIdxQuick) + ",\\n"
        + "  \\"review_avg_von_mises_tumor\\": " + Double.NaN + ",\\n"
        + "  \\"time_s\\": " + formatArray(timeValues, seriesLength) + ",\\n"
        + "  \\"max_displacement_breast_series\\": " + formatArray(maxDispBreastSeries, seriesLength) + ",\\n"
        + "  \\"avg_displacement_breast_series\\": " + formatArray(avgDispBreastSeries, seriesLength) + ",\\n"
        + "  \\"max_von_mises_breast_series\\": " + formatArray(maxMisesBreastSeries, seriesLength) + ",\\n"
        + "  \\"max_von_mises_glandular_series\\": " + formatArray(maxMisesGlandSeries, seriesLength) + ",\\n"
        + "  \\"max_von_mises_adipose_series\\": " + formatArray(maxMisesAdiposeSeries, seriesLength) + ",\\n"
        + "  \\"avg_von_mises_breast_series\\": " + formatArray(avgMisesBreastSeries, seriesLength) + ",\\n"
        + "  \\"avg_von_mises_glandular_series\\": " + formatArray(avgMisesGlandSeries, seriesLength) + ",\\n"
        + "  \\"avg_von_mises_adipose_series\\": " + formatArray(avgMisesAdiposeSeries, seriesLength) + ",\\n"
        + "  \\"stress_percentiles_status\\": \\"quick mode: surface, landmark, tumor and stress-std series are not exported.\\"\\n"
        + "}}\\n";
      System.out.println("COMSOL_METRICS_JSON_BEGIN");
      System.out.print(json);
      System.out.println("COMSOL_METRICS_JSON_END");
      postprocessStatus("quick_metrics_ready");
      return model;
    }}

    String surfaceSelectionTag = exportSurfaceMetrics ? "outer_skin_free_bnd" : "not_exported_" + postprocessMode;
    double surfaceArea = Double.NaN;
    double[] intSurfaceDispSeries = new double[0];
    double[] intSurfaceDispSqSeries = new double[0];
    double[] maxSurfaceDispSeries = new double[0];
    double[] intSurfaceWSeries = new double[0];
    double[] intSurfaceWSqSeries = new double[0];
    double[] minSurfaceWSeries = new double[0];
    double[] maxSurfaceWSeries = new double[0];
    double[] intSurfaceVSeries = new double[0];
    double[] intSurfaceVSqSeries = new double[0];
    double[] minSurfaceVSeries = new double[0];
    double[] maxSurfaceVSeries = new double[0];
    if (exportSurfaceMetrics) {{
      postprocessStatus("surface_series_start");
      surfaceArea = evalIntSurface(model, "isOuterSkinArea", surfaceSelectionTag, "1");
      intSurfaceDispSeries = evalIntSurfaceSeries(model, "isOuterSkinDisp", surfaceSelectionTag, "solid.disp");
      intSurfaceDispSqSeries = exportStressStdMetrics ? evalIntSurfaceSeries(model, "isOuterSkinDispSq", surfaceSelectionTag, "(solid.disp)^2") : new double[0];
      maxSurfaceDispSeries = evalMaxSurfaceSeries(model, "msOuterSkinDisp", surfaceSelectionTag, "solid.disp");
      intSurfaceWSeries = evalIntSurfaceSeries(model, "isOuterSkinW", surfaceSelectionTag, "w");
      intSurfaceWSqSeries = exportStressStdMetrics ? evalIntSurfaceSeries(model, "isOuterSkinWSq", surfaceSelectionTag, "(w)^2") : new double[0];
      minSurfaceWSeries = evalMinSurfaceSeries(model, "minsOuterSkinW", surfaceSelectionTag, "w");
      maxSurfaceWSeries = evalMaxSurfaceSeries(model, "maxsOuterSkinW", surfaceSelectionTag, "w");
      intSurfaceVSeries = evalIntSurfaceSeries(model, "isOuterSkinV", surfaceSelectionTag, "v");
      intSurfaceVSqSeries = exportStressStdMetrics ? evalIntSurfaceSeries(model, "isOuterSkinVSq", surfaceSelectionTag, "(v)^2") : new double[0];
      minSurfaceVSeries = evalMinSurfaceSeries(model, "minsOuterSkinV", surfaceSelectionTag, "v");
      maxSurfaceVSeries = evalMaxSurfaceSeries(model, "maxsOuterSkinV", surfaceSelectionTag, "v");
    }}
    postprocessStatus(exportSurfaceMetrics ? "surface_series_ready" : "surface_series_skipped");
    int surfaceSeriesLength = minLength(
      timeValues,
      intSurfaceDispSeries,
      intSurfaceDispSqSeries,
      intSurfaceWSeries,
      intSurfaceWSqSeries,
      intSurfaceVSeries,
      intSurfaceVSqSeries
    );
    double[] surfaceDispMeanSeries = meanFromIntegralSeries(intSurfaceDispSeries, surfaceArea, surfaceSeriesLength);
    double[] surfaceDispStdSeries = exportStressStdMetrics ? stdFromIntegralSeries(intSurfaceDispSeries, intSurfaceDispSqSeries, surfaceArea, surfaceSeriesLength) : nanArray(surfaceSeriesLength);
    double[] surfaceWMeanSeries = meanFromIntegralSeries(intSurfaceWSeries, surfaceArea, surfaceSeriesLength);
    double[] surfaceWStdSeries = exportStressStdMetrics ? stdFromIntegralSeries(intSurfaceWSeries, intSurfaceWSqSeries, surfaceArea, surfaceSeriesLength) : nanArray(surfaceSeriesLength);
    double[] surfaceVMeanSeries = meanFromIntegralSeries(intSurfaceVSeries, surfaceArea, surfaceSeriesLength);
    double[] surfaceVStdSeries = exportStressStdMetrics ? stdFromIntegralSeries(intSurfaceVSeries, intSurfaceVSqSeries, surfaceArea, surfaceSeriesLength) : nanArray(surfaceSeriesLength);

    String supportSelectionTag = (exportSurfaceMetrics || exportLandmarkMetrics) ? "breast_attach_bnd" : "not_exported_" + postprocessMode;
    double supportArea = Double.NaN;
    double[] supportWMeanSeries = new double[0];
    double[] supportDispMeanSeries = new double[0];
    if (exportSurfaceMetrics || exportLandmarkMetrics) {{
      postprocessStatus("support_series_start");
      supportArea = evalIntSurface(model, "isBreastAttachArea", supportSelectionTag, "1");
      supportWMeanSeries = evalSurfaceMeanSeries(model, "isBreastAttachW", supportSelectionTag, "w", supportArea, seriesLength);
      supportDispMeanSeries = evalSurfaceMeanSeries(model, "isBreastAttachDisp", supportSelectionTag, "solid.disp", supportArea, seriesLength);
    }}
    int supportSeriesLength = minLength(timeValues, supportWMeanSeries, supportDispMeanSeries);

    String[] landmarkNames = new String[] {{ "nipple", "left", "right", "superior", "inferior" }};
    String[] landmarkSelections = new String[] {{
      "landmark_nipple_bnd",
      "landmark_left_bnd",
      "landmark_right_bnd",
      "landmark_superior_bnd",
      "landmark_inferior_bnd"
    }};
    double[] landmarkAreas = new double[landmarkSelections.length];
    double[][] landmarkUMeanSeries = new double[landmarkSelections.length][];
    double[][] landmarkVMeanSeries = new double[landmarkSelections.length][];
    double[][] landmarkWMeanSeries = new double[landmarkSelections.length][];
    double[][] landmarkDispMeanSeries = new double[landmarkSelections.length][];
    postprocessStatus("landmark_series_start");
    for (int i = 0; i < landmarkSelections.length; i++) {{
      String selection = landmarkSelections[i];
      String prefix = "lm" + i;
      if (exportLandmarkMetrics) {{
        landmarkAreas[i] = evalIntSurface(model, prefix + "Area", selection, "1");
        landmarkUMeanSeries[i] = evalSurfaceMeanSeries(model, prefix + "U", selection, "u", landmarkAreas[i], seriesLength);
        landmarkVMeanSeries[i] = evalSurfaceMeanSeries(model, prefix + "V", selection, "v", landmarkAreas[i], seriesLength);
        landmarkWMeanSeries[i] = evalSurfaceMeanSeries(model, prefix + "W", selection, "w", landmarkAreas[i], seriesLength);
        landmarkDispMeanSeries[i] = evalSurfaceMeanSeries(model, prefix + "Disp", selection, "solid.disp", landmarkAreas[i], seriesLength);
      }} else {{
        landmarkAreas[i] = Double.NaN;
        landmarkUMeanSeries[i] = new double[0];
        landmarkVMeanSeries[i] = new double[0];
        landmarkWMeanSeries[i] = new double[0];
        landmarkDispMeanSeries[i] = new double[0];
      }}
    }}
    postprocessStatus(exportLandmarkMetrics ? "landmark_series_ready" : "landmark_series_skipped");
    int peakDispIdx = peakIndex(maxDispBreastSeries);
    int peakVmIdx = peakIndex(maxMisesBreastSeries);
    int peakGlandVmIdx = peakIndex(maxMisesGlandSeries);
    int peakTumorDispIdx = peakIndex(maxDispTumorSeries);
    int peakTumorVmIdx = peakIndex(maxMisesTumorSeries);
    if (peakDispIdx >= 0) {{
      maxDispBreast = maxDispBreastSeries[peakDispIdx];
    }}
    if (peakTumorDispIdx >= 0) {{
      maxDispTumor = maxDispTumorSeries[peakTumorDispIdx];
    }}
    if (seriesLength > 0) {{
      double bestAvgDisp = avgDispBreastSeries[0];
      for (int i = 1; i < seriesLength; i++) {{
        if (avgDispBreastSeries[i] > bestAvgDisp) {{
          bestAvgDisp = avgDispBreastSeries[i];
        }}
      }}
      avgDispBreast = bestAvgDisp;
    }}
    if (peakVmIdx >= 0) {{
      maxMisesBreast = maxMisesBreastSeries[peakVmIdx];
    }}
    if (peakGlandVmIdx >= 0) {{
      maxMisesGland = maxMisesGlandSeries[peakGlandVmIdx];
    }}
    if (peakTumorVmIdx >= 0) {{
      maxMisesTumor = maxMisesTumorSeries[peakTumorVmIdx];
    }}
    int peakAdiposeVmIdx = peakIndex(maxMisesAdiposeSeries);
    if (peakAdiposeVmIdx >= 0) {{
      maxMisesAdipose = maxMisesAdiposeSeries[peakAdiposeVmIdx];
    }}
    avgMisesBreast = maxFinite(avgMisesBreastSeries);
    avgMisesGland = maxFinite(avgMisesGlandSeries);
    avgMisesAdipose = maxFinite(avgMisesAdiposeSeries);
    avgDispTumor = maxFinite(avgDispTumorSeries);
    avgMisesTumor = maxFinite(avgMisesTumorSeries);
    double peakDispTime = (peakDispIdx >= 0 && peakDispIdx < timeValues.length) ? timeValues[peakDispIdx] : Double.NaN;
    double peakVmTime = (peakVmIdx >= 0 && peakVmIdx < timeValues.length) ? timeValues[peakVmIdx] : Double.NaN;
    double peakGlandVmTime = (peakGlandVmIdx >= 0 && peakGlandVmIdx < timeValues.length) ? timeValues[peakGlandVmIdx] : Double.NaN;
    double peakAdiposeVmTime = (peakAdiposeVmIdx >= 0 && peakAdiposeVmIdx < timeValues.length) ? timeValues[peakAdiposeVmIdx] : Double.NaN;
    double peakTumorDispTime = (peakTumorDispIdx >= 0 && peakTumorDispIdx < timeValues.length) ? timeValues[peakTumorDispIdx] : Double.NaN;
    double peakTumorVmTime = (peakTumorVmIdx >= 0 && peakTumorVmIdx < timeValues.length) ? timeValues[peakTumorVmIdx] : Double.NaN;
    int reviewIdx = closestTimeIndexOneBased(timeValues, {report_review_time_s:.12f}) - 1;
    StringBuilder landmarkJson = new StringBuilder();
    for (int i = 0; i < landmarkNames.length; i++) {{
      String prefix = "landmark_" + landmarkNames[i];
      landmarkJson.append("  \\"").append(prefix).append("_selection\\": \\"")
        .append(landmarkSelections[i]).append("\\",\\n");
      landmarkJson.append("  \\"").append(prefix).append("_area\\": ")
        .append(landmarkAreas[i]).append(",\\n");
      landmarkJson.append("  \\"").append(prefix).append("_u_mean_series\\": ")
        .append(formatArray(landmarkUMeanSeries[i], seriesLength)).append(",\\n");
      landmarkJson.append("  \\"").append(prefix).append("_v_mean_series\\": ")
        .append(formatArray(landmarkVMeanSeries[i], seriesLength)).append(",\\n");
      landmarkJson.append("  \\"").append(prefix).append("_w_mean_series\\": ")
        .append(formatArray(landmarkWMeanSeries[i], seriesLength)).append(",\\n");
      landmarkJson.append("  \\"").append(prefix).append("_disp_mean_series\\": ")
        .append(formatArray(landmarkDispMeanSeries[i], seriesLength)).append(",\\n");
      landmarkJson.append("  \\"").append(prefix).append("_review_w_mean\\": ")
        .append(safeAt(landmarkWMeanSeries[i], reviewIdx)).append(",\\n");
      landmarkJson.append("  \\"").append(prefix).append("_review_disp_mean\\": ")
        .append(safeAt(landmarkDispMeanSeries[i], reviewIdx)).append(",\\n");
    }}

    String json = ""
      + "{{\\n"
      + "  \\"case_name\\": \\"{case_name}\\",\\n"
      + "  \\"source\\": \\"COMSOL\\",\\n"
      + "  \\"coordinate_convention\\": \\"x/u = left-right lateral; y/v = anterior-posterior; z/w = vertical. Signed report displacement uses w, with negative values indicating downward motion.\\",\\n"
      + "  \\"configured_dynamic_motion_mode\\": \\"{dynamic_motion_mode}\\",\\n"
      + "  \\"configured_dynamic_motion_profile\\": \\"{dynamic_motion_profile}\\",\\n"
      + "  \\"postprocess_mode\\": \\"" + postprocessMode + "\\",\\n"
      + "  \\"postprocess_export_plot_images\\": {postprocess_export_plot_images_java},\\n"
      + "  \\"postprocess_save_postprocessed_mph\\": {postprocess_save_postprocessed_mph_java},\\n"
      + "  \\"dynamic_start_time_s\\": {dynamic_start_s:.12f},\\n"
      + "  \\"dynamic_end_time_s\\": {dynamic_end_s:.12f},\\n"
      + "  \\"configured_review_time_s\\": {report_review_time_s:.12f},\\n"
      + "  \\"jump_start_time_s\\": {jump_start_s:.12f},\\n"
      + "  \\"jump_duration_s\\": {jump_duration_s:.12f},\\n"
      + "  \\"jump_max_height_m\\": {jump_max_height_m:.12f},\\n"
      + "  \\"support_displacement_amplitude_m\\": {support_displacement_amplitude_m:.12f},\\n"
      + "  \\"support_displacement_duration_s\\": {support_displacement_duration_s:.12f},\\n"
      + "  \\"pulse_duration_s\\": {pulse_duration_s:.12f},\\n"
      + "  \\"pulse_acceleration_amplitude_g\\": {dynamic_acceleration_amplitude_g:.12f},\\n"
      + "  \\"dynamic_motion_boundary_selection\\": \\"breast_attach_bnd\\",\\n"
      + "  \\"surface_displacement_selection\\": \\"" + surfaceSelectionTag + "\\",\\n"
      + "  \\"support_displacement_selection\\": \\"" + supportSelectionTag + "\\",\\n"
      + "  \\"tumor_enabled\\": {str(tumor_enabled).lower()},\\n"
      + "  \\"tumor_radius_m\\": {tumor_radius:.12f},\\n"
      + "  \\"tumor_diameter_mm\\": {2000.0 * tumor_radius:.12f},\\n"
      + "  \\"tumor_position_m\\": [{tumor_x:.12f}, {tumor_y:.12f}, {tumor_z:.12f}],\\n"
      + "  \\"tumor_nominal_sphere_volume\\": {((4.0 / 3.0) * 3.141592653589793 * tumor_radius**3):.12e},\\n"
      + "  \\"breast_volume\\": " + breastVolume + ",\\n"
      + "  \\"glandular_volume\\": " + glandVolume + ",\\n"
      + "  \\"adipose_volume\\": " + adiposeVolume + ",\\n"
      + "  \\"tumor_volume\\": " + tumorVolume + ",\\n"
      + "  \\"max_displacement_breast\\": " + maxDispBreast + ",\\n"
      + "  \\"avg_displacement_breast\\": " + avgDispBreast + ",\\n"
      + "  \\"max_displacement_tumor\\": " + maxDispTumor + ",\\n"
      + "  \\"avg_displacement_tumor\\": " + avgDispTumor + ",\\n"
      + "  \\"max_von_mises_breast\\": " + maxMisesBreast + ",\\n"
      + "  \\"max_von_mises_glandular\\": " + maxMisesGland + ",\\n"
      + "  \\"max_von_mises_adipose\\": " + maxMisesAdipose + ",\\n"
      + "  \\"max_von_mises_tumor\\": " + maxMisesTumor + ",\\n"
      + "  \\"avg_von_mises_breast\\": " + avgMisesBreast + ",\\n"
      + "  \\"avg_von_mises_glandular\\": " + avgMisesGland + ",\\n"
      + "  \\"avg_von_mises_adipose\\": " + avgMisesAdipose + ",\\n"
      + "  \\"avg_von_mises_tumor\\": " + avgMisesTumor + ",\\n"
      + "  \\"hotspot_factor_breast_at_peak_vm\\": " + (safeAt(avgMisesBreastSeries, peakVmIdx) != 0.0 ? maxMisesBreast / safeAt(avgMisesBreastSeries, peakVmIdx) : Double.NaN) + ",\\n"
      + "  \\"hotspot_factor_glandular_at_peak_gland_vm\\": " + (safeAt(avgMisesGlandSeries, peakGlandVmIdx) != 0.0 ? maxMisesGland / safeAt(avgMisesGlandSeries, peakGlandVmIdx) : Double.NaN) + ",\\n"
      + "  \\"series_length\\": " + seriesLength + ",\\n"
      + "  \\"surface_series_length\\": " + surfaceSeriesLength + ",\\n"
      + "  \\"support_series_length\\": " + supportSeriesLength + ",\\n"
      + "  \\"surface_area_outer_skin\\": " + surfaceArea + ",\\n"
      + "  \\"time_of_peak_displacement_breast\\": " + peakDispTime + ",\\n"
      + "  \\"time_of_peak_von_mises_breast\\": " + peakVmTime + ",\\n"
      + "  \\"time_of_peak_von_mises_glandular\\": " + peakGlandVmTime + ",\\n"
      + "  \\"time_of_peak_von_mises_adipose\\": " + peakAdiposeVmTime + ",\\n"
      + "  \\"time_of_peak_displacement_tumor\\": " + peakTumorDispTime + ",\\n"
      + "  \\"time_of_peak_von_mises_tumor\\": " + peakTumorVmTime + ",\\n"
      + "  \\"review_time_s\\": " + safeAt(timeValues, reviewIdx) + ",\\n"
      + "  \\"review_max_displacement_breast\\": " + safeAt(maxDispBreastSeries, reviewIdx) + ",\\n"
      + "  \\"review_avg_displacement_breast\\": " + safeAt(avgDispBreastSeries, reviewIdx) + ",\\n"
      + "  \\"review_max_displacement_tumor\\": " + safeAt(maxDispTumorSeries, reviewIdx) + ",\\n"
      + "  \\"review_avg_displacement_tumor\\": " + safeAt(avgDispTumorSeries, reviewIdx) + ",\\n"
      + "  \\"review_max_von_mises_breast\\": " + safeAt(maxMisesBreastSeries, reviewIdx) + ",\\n"
      + "  \\"review_max_von_mises_glandular\\": " + safeAt(maxMisesGlandSeries, reviewIdx) + ",\\n"
      + "  \\"review_max_von_mises_adipose\\": " + safeAt(maxMisesAdiposeSeries, reviewIdx) + ",\\n"
      + "  \\"review_max_von_mises_tumor\\": " + safeAt(maxMisesTumorSeries, reviewIdx) + ",\\n"
      + "  \\"review_avg_von_mises_breast\\": " + safeAt(avgMisesBreastSeries, reviewIdx) + ",\\n"
      + "  \\"review_avg_von_mises_glandular\\": " + safeAt(avgMisesGlandSeries, reviewIdx) + ",\\n"
      + "  \\"review_avg_von_mises_adipose\\": " + safeAt(avgMisesAdiposeSeries, reviewIdx) + ",\\n"
      + "  \\"review_avg_von_mises_tumor\\": " + safeAt(avgMisesTumorSeries, reviewIdx) + ",\\n"
      + "  \\"review_surface_disp_mag_mean\\": " + safeAt(surfaceDispMeanSeries, reviewIdx) + ",\\n"
      + "  \\"review_surface_disp_mag_max\\": " + safeAt(maxSurfaceDispSeries, reviewIdx) + ",\\n"
      + "  \\"review_surface_signed_w_mean\\": " + safeAt(surfaceWMeanSeries, reviewIdx) + ",\\n"
      + "  \\"review_surface_signed_w_min\\": " + safeAt(minSurfaceWSeries, reviewIdx) + ",\\n"
      + "  \\"review_surface_signed_w_max\\": " + safeAt(maxSurfaceWSeries, reviewIdx) + ",\\n"
      + "  \\"time_s\\": " + formatArray(timeValues, seriesLength) + ",\\n"
      + "  \\"max_displacement_breast_series\\": " + formatArray(maxDispBreastSeries, seriesLength) + ",\\n"
      + "  \\"avg_displacement_breast_series\\": " + formatArray(avgDispBreastSeries, seriesLength) + ",\\n"
      + "  \\"max_displacement_tumor_series\\": " + formatArray(maxDispTumorSeries, seriesLength) + ",\\n"
      + "  \\"avg_displacement_tumor_series\\": " + formatArray(avgDispTumorSeries, seriesLength) + ",\\n"
      + "  \\"max_von_mises_breast_series\\": " + formatArray(maxMisesBreastSeries, seriesLength) + ",\\n"
      + "  \\"max_von_mises_glandular_series\\": " + formatArray(maxMisesGlandSeries, seriesLength) + ",\\n"
      + "  \\"max_von_mises_adipose_series\\": " + formatArray(maxMisesAdiposeSeries, seriesLength) + ",\\n"
      + "  \\"max_von_mises_tumor_series\\": " + formatArray(maxMisesTumorSeries, seriesLength) + ",\\n"
      + "  \\"avg_von_mises_breast_series\\": " + formatArray(avgMisesBreastSeries, seriesLength) + ",\\n"
      + "  \\"avg_von_mises_glandular_series\\": " + formatArray(avgMisesGlandSeries, seriesLength) + ",\\n"
      + "  \\"avg_von_mises_adipose_series\\": " + formatArray(avgMisesAdiposeSeries, seriesLength) + ",\\n"
      + "  \\"avg_von_mises_tumor_series\\": " + formatArray(avgMisesTumorSeries, seriesLength) + ",\\n"
      + "  \\"std_von_mises_breast_series\\": " + formatArray(stdMisesBreastSeries, seriesLength) + ",\\n"
      + "  \\"std_von_mises_glandular_series\\": " + formatArray(stdMisesGlandSeries, seriesLength) + ",\\n"
      + "  \\"std_von_mises_adipose_series\\": " + formatArray(stdMisesAdiposeSeries, seriesLength) + ",\\n"
      + "  \\"std_von_mises_tumor_series\\": " + formatArray(stdMisesTumorSeries, seriesLength) + ",\\n"
      + "  \\"hotspot_factor_breast_series\\": " + formatArray(hotspotMisesBreastSeries, seriesLength) + ",\\n"
      + "  \\"hotspot_factor_glandular_series\\": " + formatArray(hotspotMisesGlandSeries, seriesLength) + ",\\n"
      + "  \\"hotspot_factor_adipose_series\\": " + formatArray(hotspotMisesAdiposeSeries, seriesLength) + ",\\n"
      + "  \\"surface_disp_mag_mean_series\\": " + formatArray(surfaceDispMeanSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_disp_mag_max_series\\": " + formatArray(maxSurfaceDispSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_disp_mag_std_series\\": " + formatArray(surfaceDispStdSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_w_mean_series\\": " + formatArray(surfaceWMeanSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_w_min_series\\": " + formatArray(minSurfaceWSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_w_max_series\\": " + formatArray(maxSurfaceWSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_w_std_series\\": " + formatArray(surfaceWStdSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_v_mean_series\\": " + formatArray(surfaceVMeanSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_v_min_series\\": " + formatArray(minSurfaceVSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_v_max_series\\": " + formatArray(maxSurfaceVSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"surface_signed_v_std_series\\": " + formatArray(surfaceVStdSeries, surfaceSeriesLength) + ",\\n"
      + "  \\"support_signed_w_mean_series\\": " + formatArray(supportWMeanSeries, supportSeriesLength) + ",\\n"
      + "  \\"support_disp_mag_mean_series\\": " + formatArray(supportDispMeanSeries, supportSeriesLength) + ",\\n"
      + landmarkJson.toString()
      + "  \\"stress_percentiles_status\\": \\"median/p95/p99 are not computed from volume integrals; use sampled/raw field export for percentile statistics.\\"\\n"
      + "}}\\n";

    System.out.println("COMSOL_METRICS_JSON_BEGIN");
    System.out.print(json);
    System.out.println("COMSOL_METRICS_JSON_END");
    if (exportImages) {{
      exportDefaultPlotImages(model, "{plot_screen_dir_java}", reviewIdx + 1);
    }} else {{
      System.out.println("COMSOL_IMAGE_EXPORT_SKIPPED disabled_by_postprocess_mode_or_setting");
    }}
    if ({postprocess_save_postprocessed_mph_java}) {{
      try {{
        model.save("{postprocess_result_mph_java}");
      }} catch (Exception ignored) {{
      }}
    }} else {{
      System.out.println("COMSOL_POSTPROCESS_SAVE_SKIPPED disabled_by_postprocess_save_postprocessed_mph");
    }}
    return model;
  }}

  public static void main(String[] args) throws Exception {{
    run();
    postprocessStatus("main_run_complete");
    ModelUtil.disconnect();
  }}
}}
"""
    def _verification_java_source(*, class_name: str, model_path_candidates: list[str], loaded_role_expr: str) -> str:
        path_lines = "\n".join(
            [
                f'    String candidate{idx} = "{candidate}";\n'
                f'    if (new File(candidate{idx}).exists()) {{\n'
                f'      return candidate{idx};\n'
                f'    }}'
                for idx, candidate in enumerate(model_path_candidates, start=1)
            ]
        )
        return f"""import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.File;

public class {class_name} {{
  private static boolean hasPhysics(Model model, String tag) {{
    try {{
      model.component("comp1").physics(tag);
      return true;
    }} catch (Exception ex) {{
      return false;
    }}
  }}

  private static boolean hasPhysicsFeature(Model model, String physicsTag, String featureTag) {{
    try {{
      model.component("comp1").physics(physicsTag).feature(featureTag);
      return true;
    }} catch (Exception ex) {{
      return false;
    }}
  }}

  private static boolean hasMaterial(Model model, String tag) {{
    try {{
      model.component("comp1").material(tag);
      return true;
    }} catch (Exception ex) {{
      return false;
    }}
  }}

  private static boolean hasMultiphysics(Model model, String tag) {{
    try {{
      model.multiphysics(tag);
      return true;
    }} catch (Exception ex) {{
      return false;
    }}
  }}

  private static String paramOrEmpty(Model model, String name) {{
    try {{
      String value = model.param().get(name);
      return value == null ? "" : value.replace("\\\\", "/");
    }} catch (Exception ex) {{
      return "";
    }}
  }}

  private static double firstReal(double[][] values) {{
    if (values == null || values.length == 0 || values[0].length == 0) {{
      return Double.NaN;
    }}
    return values[0][0];
  }}

  private static void removeNumericalIfExists(Model model, String tag) {{
    try {{
      model.result().numerical().remove(tag);
    }} catch (Exception ignored) {{
    }}
  }}

  private static double evalGeometryVolume(Model model, String tag, String selectionTag) {{
    try {{
      removeNumericalIfExists(model, tag);
      model.result().numerical().create(tag, "IntVolume");
      model.result().numerical(tag).selection().named(selectionTag);
      model.result().numerical(tag).set("expr", new String[] {{ "1" }});
      return firstReal(model.result().numerical(tag).getReal());
    }} catch (Exception ex) {{
      return Double.NaN;
    }}
  }}

  private static String jsonNumber(double value) {{
    if (Double.isNaN(value) || Double.isInfinite(value)) {{
      return "null";
    }}
    return Double.toString(value);
  }}

  private static String chooseModelPath() {{
{path_lines}
    return "{model_path_candidates[0]}";
  }}

  public static Model run() throws Exception {{
    ModelUtil.initStandalone(true);
    String modelPath = chooseModelPath();
    Model model = ModelUtil.load("VerifyModel", modelPath);

    boolean hasSolid = hasPhysics(model, "solid");
    boolean hasShell = hasPhysics(model, "shell1");
    boolean hasHmatAdipose = hasPhysicsFeature(model, "solid", "hmat_adipose");
    boolean hasHmatGlandular = hasPhysicsFeature(model, "solid", "hmat_glandular");
    boolean hasHmatSkinSolid = hasPhysicsFeature(model, "solid", "hmat_skin_solid");
    boolean hasHmatSkin = hasShell && hasPhysicsFeature(model, "shell1", "hmat_skin");
    boolean hasSthin = hasMultiphysics(model, "sthin1");
    double breastVolume = evalGeometryVolume(model, "ivBuildBreastVol", "geom1_breast_union_dom");
    double skinVolume = evalGeometryVolume(model, "ivBuildSkinVol", "geom1_skin_layer_dom");
    double glandVolume = evalGeometryVolume(model, "ivBuildGlandVol", "geom1_gland_clip_dom");
    double adiposeVolume = evalGeometryVolume(model, "ivBuildAdiposeVol", "geom1_adipose_diff_dom");
    double glandFraction = (!Double.isNaN(breastVolume) && Math.abs(breastVolume) > 0.0)
      ? glandVolume / breastVolume
      : Double.NaN;
    double adiposeFraction = (!Double.isNaN(breastVolume) && Math.abs(breastVolume) > 0.0)
      ? adiposeVolume / breastVolume
      : Double.NaN;

    StringBuilder json = new StringBuilder();
    json.append("{{\\n");
    json.append("  \\"case_name\\": \\"{case_name}\\",\\n");
    json.append("  \\"loaded_model_path\\": \\"").append(modelPath.replace("\\\\", "/")).append("\\",\\n");
    json.append("  \\"loaded_model_role\\": \\"").append({loaded_role_expr}).append("\\",\\n");
    json.append("  \\"physics\\": {{\\n");
    json.append("    \\"solid\\": ").append(hasSolid).append(",\\n");
    json.append("    \\"shell1\\": ").append(hasShell).append(",\\n");
    json.append("    \\"sthin1\\": ").append(hasSthin).append("\\n");
    json.append("  }},\\n");
    json.append("  \\"hyperelastic_features\\": {{\\n");
    json.append("    \\"hmat_adipose\\": ").append(hasHmatAdipose).append(",\\n");
    json.append("    \\"hmat_glandular\\": ").append(hasHmatGlandular).append(",\\n");
    json.append("    \\"hmat_skin_solid\\": ").append(hasHmatSkinSolid).append(",\\n");
    json.append("    \\"hmat_skin\\": ").append(hasHmatSkin).append("\\n");
    json.append("  }},\\n");
    json.append("  \\"materials\\": {{\\n");
    json.append("    \\"mat_chest\\": ").append(hasMaterial(model, "mat_chest")).append(",\\n");
    json.append("    \\"mat_adipose\\": ").append(hasMaterial(model, "mat_adipose")).append(",\\n");
    json.append("    \\"mat_glandular\\": ").append(hasMaterial(model, "mat_glandular")).append(",\\n");
    json.append("    \\"mat_skin_shell\\": ").append(hasMaterial(model, "mat_skin_shell")).append(",\\n");
    json.append("    \\"mat_skin_solid\\": ").append(hasMaterial(model, "mat_skin_solid")).append("\\n");
    json.append("  }},\\n");
    json.append("  \\"geometry_volumes\\": {{\\n");
    json.append("    \\"breast_volume_m3\\": ").append(jsonNumber(breastVolume)).append(",\\n");
    json.append("    \\"skin_volume_m3\\": ").append(jsonNumber(skinVolume)).append(",\\n");
    json.append("    \\"glandular_volume_m3\\": ").append(jsonNumber(glandVolume)).append(",\\n");
    json.append("    \\"adipose_volume_m3\\": ").append(jsonNumber(adiposeVolume)).append(",\\n");
    json.append("    \\"breast_volume_ml\\": ").append(jsonNumber(1000000.0 * breastVolume)).append(",\\n");
    json.append("    \\"skin_volume_ml\\": ").append(jsonNumber(1000000.0 * skinVolume)).append(",\\n");
    json.append("    \\"glandular_volume_ml\\": ").append(jsonNumber(1000000.0 * glandVolume)).append(",\\n");
    json.append("    \\"adipose_volume_ml\\": ").append(jsonNumber(1000000.0 * adiposeVolume)).append(",\\n");
    json.append("    \\"glandular_fraction\\": ").append(jsonNumber(glandFraction)).append(",\\n");
    json.append("    \\"adipose_fraction\\": ").append(jsonNumber(adiposeFraction)).append("\\n");
    json.append("  }},\\n");
    json.append("  \\"source_parameters\\": {{\\n");
    json.append("    \\"skin_c10\\": \\"").append(paramOrEmpty(model, "skin_c10")).append("\\",\\n");
    json.append("    \\"skin_c01\\": \\"").append(paramOrEmpty(model, "skin_c01")).append("\\",\\n");
    json.append("    \\"skin_bulk_modulus\\": \\"").append(paramOrEmpty(model, "skin_bulk_modulus")).append("\\",\\n");
    json.append("    \\"adipose_c10\\": \\"").append(paramOrEmpty(model, "adipose_c10")).append("\\",\\n");
    json.append("    \\"adipose_c01\\": \\"").append(paramOrEmpty(model, "adipose_c01")).append("\\",\\n");
    json.append("    \\"adipose_bulk_modulus\\": \\"").append(paramOrEmpty(model, "adipose_bulk_modulus")).append("\\",\\n");
    json.append("    \\"adipose_E\\": \\"").append(paramOrEmpty(model, "adipose_E")).append("\\",\\n");
    json.append("    \\"glandular_c10\\": \\"").append(paramOrEmpty(model, "glandular_c10")).append("\\",\\n");
    json.append("    \\"glandular_c01\\": \\"").append(paramOrEmpty(model, "glandular_c01")).append("\\",\\n");
    json.append("    \\"glandular_bulk_modulus\\": \\"").append(paramOrEmpty(model, "glandular_bulk_modulus")).append("\\",\\n");
    json.append("    \\"glandular_E\\": \\"").append(paramOrEmpty(model, "glandular_E")).append("\\",\\n");
    json.append("    \\"tumor_enabled\\": \\"").append(paramOrEmpty(model, "tumor_enabled")).append("\\",\\n");
    json.append("    \\"tumor_E_adipose\\": \\"").append(paramOrEmpty(model, "tumor_E_adipose")).append("\\",\\n");
    json.append("    \\"tumor_E_glandular\\": \\"").append(paramOrEmpty(model, "tumor_E_glandular")).append("\\",\\n");
    json.append("    \\"chest_E\\": \\"").append(paramOrEmpty(model, "chest_E")).append("\\",\\n");
    json.append("    \\"chest_nu\\": \\"").append(paramOrEmpty(model, "chest_nu")).append("\\"\\n");
    json.append("  }}\\n");
    json.append("}}");

    System.out.println("COMSOL_VERIFICATION_JSON_BEGIN");
    System.out.println(json.toString());
    System.out.println("COMSOL_VERIFICATION_JSON_END");
    return model;
  }}

  public static void main(String[] args) throws Exception {{
    run();
    ModelUtil.disconnect();
  }}
}}
"""
    build_verification_java = _verification_java_source(
        class_name=build_verification_class_name,
        model_path_candidates=[generated_mph_java, generated_mph_fallback_java],
        loaded_role_expr='"generated_build"',
    )
    solve_verification_java = _verification_java_source(
        class_name=solve_verification_class_name,
        model_path_candidates=[postprocess_result_mph_java, generated_mph_java, generated_mph_fallback_java],
        loaded_role_expr='modelPath.endsWith("_result.mph") ? "solve_result" : "generated_build_fallback"',
    )
    build_verification_java_path.write_text(build_verification_java, encoding="utf-8")
    solve_verification_java_path.write_text(solve_verification_java, encoding="utf-8")
    postprocess_java_path.write_text(postprocess_java, encoding="utf-8")
    readme_path.write_text(
        "\n".join(
            [
                "Generated COMSOL builder scaffold",
                f"Java source: {script_path}",
                f"Build plan: {build_plan_path}",
                f"Selection hints: {selection_hints_path}",
                f"Metrics postprocess Java: {postprocess_java_path}",
                f"Metrics JSON target: {metrics_json_path}",
                f"Build verification Java: {build_verification_java_path}",
                f"Solve verification Java: {solve_verification_java_path}",
                f"Build verification JSON target: {generated_verify_json_path}",
                f"Solve verification JSON target: {solve_verify_json_path}",
                f"Target MPH: {result_mph}",
                "",
                "Typical next step:",
                "1) Open/compile this Java file via COMSOL Java API tooling",
                "2) Inspect the generated finalized geometry selections such as geom1_breast_union_dom",
                "3) Validate displacement/stress output for the static gravity case",
                "4) Replace the linearized material approximation if a higher-fidelity COMSOL constitutive law is needed",
                "5) Add the dynamic motion case after the static setup is stable",
                "",
                "Important:",
            "This Java file now builds real geometry and region selections, but material laws and loading are still the next step.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "comsol_builder_java": str(script_path.resolve()),
        "comsol_builder_readme": str(readme_path.resolve()),
        "comsol_generated_mph_target": str(result_mph.resolve()),
        "comsol_selection_hints_json": str(selection_hints_path.resolve()),
        "comsol_postprocess_java": str(postprocess_java_path.resolve()),
        "comsol_metrics_json_target": str(metrics_json_path.resolve()),
        "comsol_build_verification_java": str(build_verification_java_path.resolve()),
        "comsol_solve_verification_java": str(solve_verification_java_path.resolve()),
        "comsol_build_verification_json_target": str(generated_verify_json_path.resolve()),
        "comsol_solve_verification_json_target": str(solve_verify_json_path.resolve()),
        "comsol_nipple_placement_debug": nipple_placement_debug,
    }
