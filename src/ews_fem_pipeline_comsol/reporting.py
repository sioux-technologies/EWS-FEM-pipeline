"""Create lightweight report artefacts from COMSOL metrics JSON.

The COMSOL postprocess Java emits metrics JSON. This module turns it into
Git-friendly summary JSON/CSV/Markdown and optional time-series CSVs for
surface displacement, landmark displacement, and tissue stress.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

from ews_fem_pipeline_comsol.settings import Settings


def _safe_read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _runtime_seconds(log_path: Path) -> float | None:
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"Total elapsed time [.]* : [\d:]* \(([\d.]+) sec\)", text)
    return float(match.group(1)) if match else None


def _numeric_series(metrics: dict, key: str, scale: float = 1.0) -> list[float]:
    values = metrics.get(key, [])
    if not isinstance(values, list):
        return []
    out: list[float] = []
    for value in values:
        try:
            out.append(scale * float(value))
        except Exception:
            out.append(float("nan"))
    return out


def _finite(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _csv_value(value: float | int | None) -> float | str:
    out = _finite(value)
    return "" if out is None else out


def _has_finite(values: list[float]) -> bool:
    return any(math.isfinite(value) for value in values)


def _nearest_index(time_s: list[float], target_s: float, n: int) -> int | None:
    if not time_s or n <= 0:
        return None
    limit = min(len(time_s), n)
    return min(range(limit), key=lambda idx: abs(time_s[idx] - target_s))


def _subtract_values(left: float | None, right: float | None) -> float | None:
    left_f = _finite(left)
    right_f = _finite(right)
    if left_f is None or right_f is None:
        return None
    return left_f - right_f


def _write_surface_displacement_csv(metrics: dict, time_s: list[float], path: Path) -> bool:
    series_map = {
        "disp_mag_mean_mm": _numeric_series(metrics, "surface_disp_mag_mean_series", 1000.0),
        "disp_mag_max_mm": _numeric_series(metrics, "surface_disp_mag_max_series", 1000.0),
        "disp_mag_std_mm": _numeric_series(metrics, "surface_disp_mag_std_series", 1000.0),
        "signed_vertical_w_mean_mm": _numeric_series(metrics, "surface_signed_w_mean_series", 1000.0),
        "signed_vertical_w_min_mm": _numeric_series(metrics, "surface_signed_w_min_series", 1000.0),
        "signed_vertical_w_max_mm": _numeric_series(metrics, "surface_signed_w_max_series", 1000.0),
        "signed_vertical_w_std_mm": _numeric_series(metrics, "surface_signed_w_std_series", 1000.0),
        "signed_ap_v_mean_mm": _numeric_series(metrics, "surface_signed_v_mean_series", 1000.0),
        "signed_ap_v_min_mm": _numeric_series(metrics, "surface_signed_v_min_series", 1000.0),
        "signed_ap_v_max_mm": _numeric_series(metrics, "surface_signed_v_max_series", 1000.0),
        "signed_ap_v_std_mm": _numeric_series(metrics, "surface_signed_v_std_series", 1000.0),
        "support_signed_vertical_w_mean_mm": _numeric_series(metrics, "support_signed_w_mean_series", 1000.0),
        "support_disp_mag_mean_mm": _numeric_series(metrics, "support_disp_mag_mean_series", 1000.0),
    }
    required = [series_map["disp_mag_mean_mm"], series_map["signed_vertical_w_mean_mm"]]
    if not time_s or not all(required) or not any(_has_finite(values) for values in required):
        return False
    n = min([len(time_s)] + [len(values) for values in series_map.values() if values])
    if n <= 0:
        return False
    area_mm2 = None
    try:
        area_mm2 = 1_000_000.0 * float(metrics.get("surface_area_outer_skin"))
    except Exception:
        area_mm2 = None
    fieldnames = [
        "step",
        "time_s",
        "selection",
        "surface_area_mm2",
        *series_map.keys(),
        "signed_vertical_w_mean_from_dynamic_start_mm",
        "signed_vertical_w_mean_relative_to_support_mm",
    ]
    dynamic_start_s = _finite(metrics.get("dynamic_start_time_s")) or 1.0
    baseline_idx = _nearest_index(time_s, dynamic_start_s, n)
    baseline_w = (
        series_map["signed_vertical_w_mean_mm"][baseline_idx]
        if baseline_idx is not None and baseline_idx < len(series_map["signed_vertical_w_mean_mm"])
        else None
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(n):
            row = {
                "step": idx,
                "time_s": time_s[idx],
                "selection": metrics.get("surface_displacement_selection", "outer_skin_free_bnd"),
                "surface_area_mm2": _csv_value(area_mm2),
            }
            for key, values in series_map.items():
                row[key] = _csv_value(values[idx] if idx < len(values) else None)
            row["signed_vertical_w_mean_from_dynamic_start_mm"] = _csv_value(
                _subtract_values(
                    series_map["signed_vertical_w_mean_mm"][idx]
                    if idx < len(series_map["signed_vertical_w_mean_mm"])
                    else None,
                    baseline_w,
                )
            )
            row["signed_vertical_w_mean_relative_to_support_mm"] = _csv_value(
                _subtract_values(
                    series_map["signed_vertical_w_mean_mm"][idx]
                    if idx < len(series_map["signed_vertical_w_mean_mm"])
                    else None,
                    series_map["support_signed_vertical_w_mean_mm"][idx]
                    if idx < len(series_map["support_signed_vertical_w_mean_mm"])
                    else None,
                )
            )
            writer.writerow(row)
    return True


def _write_landmark_displacement_csv(metrics: dict, time_s: list[float], path: Path) -> bool:
    names = ["nipple", "left", "right", "superior", "inferior"]
    fieldnames = [
        "step",
        "time_s",
        "landmark",
        "selection",
        "patch_area_mm2",
        "ux_mean_mm",
        "uy_ap_mean_mm",
        "uz_vertical_mean_mm",
        "disp_mag_mean_mm",
        "support_uz_vertical_mean_mm",
        "uz_vertical_mean_from_dynamic_start_mm",
        "uz_vertical_mean_relative_to_support_mm",
    ]
    rows: list[dict[str, object]] = []
    support_w = _numeric_series(metrics, "support_signed_w_mean_series", 1000.0)
    dynamic_start_s = _finite(metrics.get("dynamic_start_time_s")) or 1.0
    for name in names:
        prefix = f"landmark_{name}"
        u = _numeric_series(metrics, f"{prefix}_u_mean_series", 1000.0)
        v = _numeric_series(metrics, f"{prefix}_v_mean_series", 1000.0)
        w = _numeric_series(metrics, f"{prefix}_w_mean_series", 1000.0)
        disp = _numeric_series(metrics, f"{prefix}_disp_mean_series", 1000.0)
        if not time_s or not any(_has_finite(values) for values in [u, v, w, disp]):
            continue
        n = min([len(time_s)] + [len(values) for values in [u, v, w, disp] if values])
        if n <= 0:
            continue
        baseline_idx = _nearest_index(time_s, dynamic_start_s, n)
        baseline_w = w[baseline_idx] if baseline_idx is not None and baseline_idx < len(w) else None
        try:
            area_mm2 = 1_000_000.0 * float(metrics.get(f"{prefix}_area"))
        except Exception:
            area_mm2 = None
        for idx in range(n):
            rows.append(
                {
                    "step": idx,
                    "time_s": time_s[idx],
                    "landmark": name,
                    "selection": metrics.get(f"{prefix}_selection", f"landmark_{name}_bnd"),
                    "patch_area_mm2": _csv_value(area_mm2),
                    "ux_mean_mm": _csv_value(u[idx] if idx < len(u) else None),
                    "uy_ap_mean_mm": _csv_value(v[idx] if idx < len(v) else None),
                    "uz_vertical_mean_mm": _csv_value(w[idx] if idx < len(w) else None),
                    "disp_mag_mean_mm": _csv_value(disp[idx] if idx < len(disp) else None),
                    "support_uz_vertical_mean_mm": _csv_value(support_w[idx] if idx < len(support_w) else None),
                    "uz_vertical_mean_from_dynamic_start_mm": _csv_value(
                        _subtract_values(w[idx] if idx < len(w) else None, baseline_w)
                    ),
                    "uz_vertical_mean_relative_to_support_mm": _csv_value(
                        _subtract_values(
                            w[idx] if idx < len(w) else None,
                            support_w[idx] if idx < len(support_w) else None,
                        )
                    ),
                }
            )
    if not rows:
        return False
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def _write_tissue_stress_stats_csv(metrics: dict, time_s: list[float], path: Path) -> bool:
    tissues = [
        ("breast", "breast"),
        ("glandular", "glandular"),
        ("adipose", "adipose"),
        ("tumor", "tumor"),
    ]
    fieldnames = [
        "step",
        "time_s",
        "tissue",
        "mean_pa",
        "median_pa",
        "std_pa",
        "p95_pa",
        "p99_pa",
        "max_pa",
        "hotspot_factor_max_over_mean",
        "percentile_status",
    ]
    rows: list[dict[str, object]] = []
    for tissue, key in tissues:
        mean_values = _numeric_series(metrics, f"avg_von_mises_{key}_series")
        max_values = _numeric_series(metrics, f"max_von_mises_{key}_series")
        std_values = _numeric_series(metrics, f"std_von_mises_{key}_series")
        hotspot_values = _numeric_series(metrics, f"hotspot_factor_{key}_series")
        if not mean_values and tissue == "breast":
            mean_values = _numeric_series(metrics, "avg_von_mises_breast_series")
        if not max_values and tissue == "breast":
            max_values = _numeric_series(metrics, "max_von_mises_breast_series")
        if not any(_has_finite(values) for values in [mean_values, max_values, std_values]):
            continue
        n = min([len(time_s)] + [len(values) for values in [mean_values, max_values] if values])
        if n <= 0:
            continue
        for idx in range(n):
            rows.append(
                {
                    "step": idx,
                    "time_s": time_s[idx],
                    "tissue": tissue,
                    "mean_pa": _csv_value(mean_values[idx] if idx < len(mean_values) else None),
                    "median_pa": "",
                    "std_pa": _csv_value(std_values[idx] if idx < len(std_values) else None),
                    "p95_pa": "",
                    "p99_pa": "",
                    "max_pa": _csv_value(max_values[idx] if idx < len(max_values) else None),
                    "hotspot_factor_max_over_mean": _csv_value(
                        hotspot_values[idx] if idx < len(hotspot_values) else None
                    ),
                    "percentile_status": "requires sampled/raw field export",
                }
            )
    if not rows:
        return False
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def generate_case_report(
    *,
    case_name: str,
    metrics_path: Path,
    verification_path: Path | None,
    log_path: Path | None,
    output_dir: Path,
    settings: Settings,
) -> dict[str, Path]:
    """Write summary and time-series files for one postprocessed COMSOL case."""
    metrics = _safe_read_json(metrics_path)
    verification = _safe_read_json(verification_path) if verification_path else {}

    runtime_sec = _runtime_seconds(log_path) if log_path else None
    breast_volume_ml = 1_000_000.0 * float(metrics.get("breast_volume", 0.0))
    gland_volume_ml = 1_000_000.0 * float(metrics.get("glandular_volume", 0.0))
    adipose_volume_ml = 1_000_000.0 * float(metrics.get("adipose_volume", 0.0))
    tumor_volume_ml = 1_000_000.0 * float(metrics.get("tumor_volume", 0.0))
    max_disp_mm = 1000.0 * float(metrics.get("max_displacement_breast", 0.0))
    avg_disp_mm = 1000.0 * float(metrics.get("avg_displacement_breast", 0.0))
    max_disp_tumor_mm = 1000.0 * float(metrics.get("max_displacement_tumor", 0.0))
    avg_disp_tumor_mm = 1000.0 * float(metrics.get("avg_displacement_tumor", 0.0))
    max_vm_pa = float(metrics.get("max_von_mises_breast", 0.0))
    max_vm_gland_pa = float(metrics.get("max_von_mises_glandular", 0.0))
    max_vm_adipose_pa = float(metrics.get("max_von_mises_adipose", 0.0))
    max_vm_tumor_pa = float(metrics.get("max_von_mises_tumor", 0.0))
    avg_vm_pa = float(metrics.get("avg_von_mises_breast", 0.0))
    avg_vm_gland_pa = float(metrics.get("avg_von_mises_glandular", 0.0))
    avg_vm_adipose_pa = float(metrics.get("avg_von_mises_adipose", 0.0))
    avg_vm_tumor_pa = float(metrics.get("avg_von_mises_tumor", 0.0))
    time_s = _numeric_series(metrics, "time_s")
    disp_series_mm = _numeric_series(metrics, "max_displacement_breast_series", 1000.0)
    avg_disp_series_mm = _numeric_series(metrics, "avg_displacement_breast_series", 1000.0)
    tumor_disp_series_mm = _numeric_series(metrics, "max_displacement_tumor_series", 1000.0)
    avg_tumor_disp_series_mm = _numeric_series(metrics, "avg_displacement_tumor_series", 1000.0)
    vm_series_pa = _numeric_series(metrics, "max_von_mises_breast_series")
    gland_vm_series_pa = _numeric_series(metrics, "max_von_mises_glandular_series")
    adipose_vm_series_pa = _numeric_series(metrics, "max_von_mises_adipose_series")
    tumor_vm_series_pa = _numeric_series(metrics, "max_von_mises_tumor_series")
    avg_vm_series_pa = _numeric_series(metrics, "avg_von_mises_breast_series")
    avg_gland_vm_series_pa = _numeric_series(metrics, "avg_von_mises_glandular_series")
    avg_adipose_vm_series_pa = _numeric_series(metrics, "avg_von_mises_adipose_series")
    avg_tumor_vm_series_pa = _numeric_series(metrics, "avg_von_mises_tumor_series")
    std_vm_series_pa = _numeric_series(metrics, "std_von_mises_breast_series")
    std_gland_vm_series_pa = _numeric_series(metrics, "std_von_mises_glandular_series")
    std_adipose_vm_series_pa = _numeric_series(metrics, "std_von_mises_adipose_series")
    std_tumor_vm_series_pa = _numeric_series(metrics, "std_von_mises_tumor_series")
    hotspot_vm_series = _numeric_series(metrics, "hotspot_factor_breast_series")
    hotspot_gland_vm_series = _numeric_series(metrics, "hotspot_factor_glandular_series")
    hotspot_adipose_vm_series = _numeric_series(metrics, "hotspot_factor_adipose_series")
    if disp_series_mm:
        max_disp_mm = max(disp_series_mm)
    if avg_disp_series_mm:
        avg_disp_mm = max(avg_disp_series_mm)
    if tumor_disp_series_mm:
        max_disp_tumor_mm = max(tumor_disp_series_mm)
    if avg_tumor_disp_series_mm:
        avg_disp_tumor_mm = max(avg_tumor_disp_series_mm)
    if vm_series_pa:
        max_vm_pa = max(vm_series_pa)
    if gland_vm_series_pa:
        max_vm_gland_pa = max(gland_vm_series_pa)
    if adipose_vm_series_pa:
        max_vm_adipose_pa = max(adipose_vm_series_pa)
    if tumor_vm_series_pa:
        max_vm_tumor_pa = max(tumor_vm_series_pa)
    if avg_vm_series_pa:
        avg_vm_pa = max(avg_vm_series_pa)
    if avg_gland_vm_series_pa:
        avg_vm_gland_pa = max(avg_gland_vm_series_pa)
    if avg_adipose_vm_series_pa:
        avg_vm_adipose_pa = max(avg_adipose_vm_series_pa)
    if avg_tumor_vm_series_pa:
        avg_vm_tumor_pa = max(avg_tumor_vm_series_pa)

    payload = {
        "case_name": case_name,
        "source": "COMSOL",
        "study_type": "Transient",
        "postprocess_mode": metrics.get("postprocess_mode", getattr(settings.comsol, "postprocess_mode", "full")),
        "coordinate_convention": metrics.get("coordinate_convention"),
        "surface_displacement_selection": metrics.get("surface_displacement_selection"),
        "runtime_sec": runtime_sec,
        "breast_volume_ml": breast_volume_ml,
        "glandular_volume_ml": gland_volume_ml,
        "adipose_volume_ml": adipose_volume_ml,
        "tumor_enabled": metrics.get("tumor_enabled"),
        "tumor_radius_m": metrics.get("tumor_radius_m"),
        "tumor_diameter_mm": metrics.get("tumor_diameter_mm"),
        "tumor_position_m": metrics.get("tumor_position_m"),
        "tumor_nominal_sphere_volume_ml": 1_000_000.0 * float(metrics.get("tumor_nominal_sphere_volume", 0.0)),
        "tumor_volume_ml": tumor_volume_ml,
        "max_displacement_breast_mm": max_disp_mm,
        "avg_displacement_breast_mm": avg_disp_mm,
        "max_displacement_tumor_mm": max_disp_tumor_mm,
        "avg_displacement_tumor_mm": avg_disp_tumor_mm,
        "max_von_mises_breast_pa": max_vm_pa,
        "max_von_mises_glandular_pa": max_vm_gland_pa,
        "max_von_mises_adipose_pa": max_vm_adipose_pa,
        "max_von_mises_tumor_pa": max_vm_tumor_pa,
        "avg_von_mises_breast_pa": avg_vm_pa,
        "avg_von_mises_glandular_pa": avg_vm_gland_pa,
        "avg_von_mises_adipose_pa": avg_vm_adipose_pa,
        "avg_von_mises_tumor_pa": avg_vm_tumor_pa,
        "hotspot_factor_breast_at_peak_vm": metrics.get("hotspot_factor_breast_at_peak_vm"),
        "hotspot_factor_glandular_at_peak_gland_vm": metrics.get("hotspot_factor_glandular_at_peak_gland_vm"),
        "review_time_s": metrics.get("review_time_s"),
        "review_max_displacement_breast_mm": 1000.0 * float(metrics.get("review_max_displacement_breast", 0.0)),
        "review_avg_displacement_breast_mm": 1000.0 * float(metrics.get("review_avg_displacement_breast", 0.0)),
        "review_max_displacement_tumor_mm": 1000.0 * float(metrics.get("review_max_displacement_tumor", 0.0)),
        "review_avg_displacement_tumor_mm": 1000.0 * float(metrics.get("review_avg_displacement_tumor", 0.0)),
        "review_max_von_mises_breast_pa": metrics.get("review_max_von_mises_breast"),
        "review_max_von_mises_glandular_pa": metrics.get("review_max_von_mises_glandular"),
        "review_max_von_mises_adipose_pa": metrics.get("review_max_von_mises_adipose"),
        "review_max_von_mises_tumor_pa": metrics.get("review_max_von_mises_tumor"),
        "review_avg_von_mises_breast_pa": metrics.get("review_avg_von_mises_breast"),
        "review_avg_von_mises_glandular_pa": metrics.get("review_avg_von_mises_glandular"),
        "review_avg_von_mises_adipose_pa": metrics.get("review_avg_von_mises_adipose"),
        "review_avg_von_mises_tumor_pa": metrics.get("review_avg_von_mises_tumor"),
        "review_surface_disp_mag_mean_mm": 1000.0 * float(metrics.get("review_surface_disp_mag_mean", 0.0)),
        "review_surface_disp_mag_max_mm": 1000.0 * float(metrics.get("review_surface_disp_mag_max", 0.0)),
        "review_surface_signed_w_mean_mm": 1000.0 * float(metrics.get("review_surface_signed_w_mean", 0.0)),
        "review_surface_signed_w_min_mm": 1000.0 * float(metrics.get("review_surface_signed_w_min", 0.0)),
        "review_surface_signed_w_max_mm": 1000.0 * float(metrics.get("review_surface_signed_w_max", 0.0)),
        "stress_percentiles_status": metrics.get("stress_percentiles_status"),
        "series_length": int(metrics.get("series_length", len(time_s) or 0)),
        "time_of_peak_displacement_breast_s": metrics.get("time_of_peak_displacement_breast"),
        "time_of_peak_von_mises_breast_s": metrics.get("time_of_peak_von_mises_breast"),
        "time_of_peak_von_mises_glandular_s": metrics.get("time_of_peak_von_mises_glandular"),
        "time_of_peak_displacement_tumor_s": metrics.get("time_of_peak_displacement_tumor"),
        "time_of_peak_von_mises_tumor_s": metrics.get("time_of_peak_von_mises_tumor"),
        "shell_physics_enabled": settings.comsol.enable_skin_shell_physics,
        "shell_coupling_enabled": settings.comsol.enable_skin_solid_coupling_scaffold,
        "curved_chestwall_enabled": settings.comsol.enable_curved_chestwall,
        "chest_density_kg_m3": settings.comsol.chest_density_kg_m3,
        "chest_youngs_modulus_pa": settings.comsol.chest_youngs_modulus_pa,
        "chest_poissons_ratio": settings.comsol.chest_poissons_ratio,
        "verification": {
            "solid": verification.get("physics", {}).get("solid"),
            "shell1": verification.get("physics", {}).get("shell1"),
            "sthin1": verification.get("physics", {}).get("sthin1"),
            "hmat_adipose": verification.get("hyperelastic_features", {}).get("hmat_adipose"),
            "hmat_glandular": verification.get("hyperelastic_features", {}).get("hmat_glandular"),
            "hmat_skin": verification.get("hyperelastic_features", {}).get("hmat_skin"),
            "mat_chest": verification.get("materials", {}).get("mat_chest"),
            "mat_adipose": verification.get("materials", {}).get("mat_adipose"),
            "mat_glandular": verification.get("materials", {}).get("mat_glandular"),
            "mat_skin_shell": verification.get("materials", {}).get("mat_skin_shell"),
        },
        "compare_ready_inputs": {
            "comsol_metrics_json": str(metrics_path.resolve()),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    postprocess_mode = str(payload.get("postprocess_mode") or "full").strip().lower().replace("-", "_")
    output_stem = case_name if postprocess_mode == "full" else f"{case_name}_{postprocess_mode}"
    summary_json_path = output_dir / f"{output_stem}_summary.json"
    summary_csv_path = output_dir / f"{output_stem}_summary.csv"
    summary_md_path = output_dir / f"{output_stem}_summary.md"
    time_series_csv_path = output_dir / f"{output_stem}_time_series.csv"
    surface_displacement_csv_path = output_dir / f"{output_stem}_surface_displacement.csv"
    landmark_displacement_csv_path = output_dir / f"{output_stem}_landmark_displacement.csv"
    tissue_stress_stats_csv_path = output_dir / f"{output_stem}_tissue_stress_stats.csv"

    summary_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    csv_fields = [
        "case_name",
        "source",
        "study_type",
        "postprocess_mode",
        "runtime_sec",
        "breast_volume_ml",
        "glandular_volume_ml",
        "adipose_volume_ml",
        "tumor_volume_ml",
        "max_displacement_breast_mm",
        "avg_displacement_breast_mm",
        "max_displacement_tumor_mm",
        "avg_displacement_tumor_mm",
        "max_von_mises_breast_pa",
        "max_von_mises_glandular_pa",
        "max_von_mises_adipose_pa",
        "max_von_mises_tumor_pa",
        "avg_von_mises_breast_pa",
        "avg_von_mises_glandular_pa",
        "avg_von_mises_adipose_pa",
        "avg_von_mises_tumor_pa",
        "hotspot_factor_breast_at_peak_vm",
        "hotspot_factor_glandular_at_peak_gland_vm",
        "shell_physics_enabled",
        "shell_coupling_enabled",
        "curved_chestwall_enabled",
        "chest_density_kg_m3",
        "chest_youngs_modulus_pa",
        "chest_poissons_ratio",
    ]
    with open(summary_csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerow({key: payload.get(key) for key in csv_fields})

    series_len = min(len(time_s), len(disp_series_mm), len(avg_disp_series_mm), len(vm_series_pa), len(gland_vm_series_pa))
    if series_len > 0:
        optional_series = {
            "adipose_vm_max_pa": adipose_vm_series_pa,
            "tumor_disp_max_mm": tumor_disp_series_mm,
            "tumor_disp_avg_mm": avg_tumor_disp_series_mm,
            "tumor_vm_max_pa": tumor_vm_series_pa,
            "vm_avg_pa": avg_vm_series_pa,
            "gland_vm_avg_pa": avg_gland_vm_series_pa,
            "adipose_vm_avg_pa": avg_adipose_vm_series_pa,
            "tumor_vm_avg_pa": avg_tumor_vm_series_pa,
            "vm_std_pa": std_vm_series_pa,
            "gland_vm_std_pa": std_gland_vm_series_pa,
            "adipose_vm_std_pa": std_adipose_vm_series_pa,
            "tumor_vm_std_pa": std_tumor_vm_series_pa,
            "breast_hotspot_factor": hotspot_vm_series,
            "gland_hotspot_factor": hotspot_gland_vm_series,
            "adipose_hotspot_factor": hotspot_adipose_vm_series,
        }
        optional_fields = [
            name for name, values in optional_series.items()
            if len(values) >= series_len
        ]
        with open(time_series_csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "step",
                    "time_s",
                    "disp_max_mm",
                    "disp_avg_mm",
                    "vm_max_pa",
                    "gland_vm_max_pa",
                ] + optional_fields,
            )
            writer.writeheader()
            for idx in range(series_len):
                row = {
                    "step": idx,
                    "time_s": time_s[idx],
                    "disp_max_mm": disp_series_mm[idx],
                    "disp_avg_mm": avg_disp_series_mm[idx],
                    "vm_max_pa": vm_series_pa[idx],
                    "gland_vm_max_pa": gland_vm_series_pa[idx],
                }
                for name in optional_fields:
                    row[name] = optional_series[name][idx]
                writer.writerow(row)

    surface_written = _write_surface_displacement_csv(metrics, time_s, surface_displacement_csv_path)
    landmark_written = _write_landmark_displacement_csv(metrics, time_s, landmark_displacement_csv_path)
    tissue_stress_written = _write_tissue_stress_stats_csv(metrics, time_s, tissue_stress_stats_csv_path)
    if surface_written:
        payload["compare_ready_inputs"]["surface_displacement_csv"] = str(surface_displacement_csv_path.resolve())
    if landmark_written:
        payload["compare_ready_inputs"]["landmark_displacement_csv"] = str(landmark_displacement_csv_path.resolve())
    if tissue_stress_written:
        payload["compare_ready_inputs"]["tissue_stress_stats_csv"] = str(tissue_stress_stats_csv_path.resolve())
    if surface_written or landmark_written or tissue_stress_written:
        summary_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# COMSOL Summary: {case_name}",
        "",
        "## Main Results",
        f"- Runtime (s): {runtime_sec}",
        f"- Breast volume (ml): {breast_volume_ml:.3f}",
        f"- Glandular volume (ml): {gland_volume_ml:.3f}",
        f"- Adipose volume (ml): {adipose_volume_ml:.3f}",
        f"- Tumor enabled: {payload['tumor_enabled']}",
        f"- Tumor volume from mask (ml): {tumor_volume_ml:.3f}",
        f"- Max breast displacement (mm): {max_disp_mm:.3f}",
        f"- Time of peak breast displacement (s): {payload['time_of_peak_displacement_breast_s']}",
        f"- Avg breast displacement (mm): {avg_disp_mm:.3f}",
        f"- Max tumor-region displacement (mm): {max_disp_tumor_mm:.3f}",
        f"- Avg tumor-region displacement (mm): {avg_disp_tumor_mm:.3f}",
        f"- Max breast von Mises (Pa): {max_vm_pa:.3f}",
        f"- Avg breast von Mises (Pa): {avg_vm_pa:.3f}",
        f"- Time of peak breast von Mises (s): {payload['time_of_peak_von_mises_breast_s']}",
        f"- Max glandular von Mises (Pa): {max_vm_gland_pa:.3f}",
        f"- Avg glandular von Mises (Pa): {avg_vm_gland_pa:.3f}",
        f"- Time of peak glandular von Mises (s): {payload['time_of_peak_von_mises_glandular_s']}",
        f"- Max adipose von Mises (Pa): {max_vm_adipose_pa:.3f}",
        f"- Avg adipose von Mises (Pa): {avg_vm_adipose_pa:.3f}",
        f"- Max tumor-region von Mises (Pa): {max_vm_tumor_pa:.3f}",
        f"- Avg tumor-region von Mises (Pa): {avg_vm_tumor_pa:.3f}",
        f"- Breast hotspot factor at peak VM: {payload['hotspot_factor_breast_at_peak_vm']}",
        f"- Glandular hotspot factor at peak gland VM: {payload['hotspot_factor_glandular_at_peak_gland_vm']}",
        f"- Postprocess mode: {payload['postprocess_mode']}",
        f"- Coordinate convention: {payload['coordinate_convention']}",
        f"- Surface displacement selection: {payload['surface_displacement_selection']}",
        "",
        "## Model Checks",
        f"- Solid physics present: {payload['verification']['solid']}",
        f"- Shell physics present: {payload['verification']['shell1']}",
        f"- Solid-thin coupling present: {payload['verification']['sthin1']}",
        f"- Hyperelastic adipose present: {payload['verification']['hmat_adipose']}",
        f"- Hyperelastic glandular present: {payload['verification']['hmat_glandular']}",
        f"- Hyperelastic skin present: {payload['verification']['hmat_skin']}",
        f"- Chest material assigned: {payload['verification']['mat_chest']}",
        "",
        "## Compare Input",
        f"- COMSOL metrics JSON: {metrics_path.resolve()}",
    ]
    if series_len > 0:
        lines.append(f"- COMSOL time-series CSV: {time_series_csv_path.resolve()}")
    if surface_written:
        lines.append(f"- COMSOL surface displacement CSV: {surface_displacement_csv_path.resolve()}")
    if landmark_written:
        lines.append(f"- COMSOL landmark displacement CSV: {landmark_displacement_csv_path.resolve()}")
    if tissue_stress_written:
        lines.append(f"- COMSOL tissue stress stats CSV: {tissue_stress_stats_csv_path.resolve()}")
    summary_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    outputs = {
        "summary_json": summary_json_path,
        "summary_csv": summary_csv_path,
        "summary_md": summary_md_path,
        "time_series_csv": time_series_csv_path,
    }
    if surface_written:
        outputs["surface_displacement_csv"] = surface_displacement_csv_path
    if landmark_written:
        outputs["landmark_displacement_csv"] = landmark_displacement_csv_path
    if tissue_stress_written:
        outputs["tissue_stress_stats_csv"] = tissue_stress_stats_csv_path
    return outputs
