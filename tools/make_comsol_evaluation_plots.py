from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "tools" / "_vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw


OUTPUT_ROOT = ROOT / "analysis_output" / "comsol_pipeline"
REVIEW_TIME_S = 1.125


@dataclass(frozen=True)
class Case:
    key: str
    label: str
    stage: str
    output_dir: Path

    @property
    def solve_dir(self) -> Path:
        return self.output_dir / "solve"

    @property
    def plot_screens_dir(self) -> Path:
        return self.output_dir / "plot_screens_auto"

    @property
    def result_mph_path(self) -> Path | None:
        matches = sorted(self.solve_dir.glob("*_result.mph"))
        return matches[0] if matches else None

    @property
    def metrics_path(self) -> Path:
        matches = self._preferred_files(
            "*_metrics.json",
            ("_internal_tumor_metrics.json", "_metrics.json", "_ews_surface_metrics.json", "_global_metrics.json"),
        )
        if not matches:
            raise FileNotFoundError(f"No metrics JSON in {self.solve_dir}")
        return matches[0]

    @property
    def time_series_path(self) -> Path:
        matches = self._preferred_files(
            "*_time_series.csv",
            ("_internal_tumor_time_series.csv", "_time_series.csv", "_ews_surface_time_series.csv", "_global_time_series.csv"),
        )
        if not matches:
            raise FileNotFoundError(f"No time-series CSV in {self.solve_dir}")
        return matches[0]

    @property
    def surface_displacement_path(self) -> Path | None:
        matches = self._preferred_files(
            "*_surface_displacement.csv",
            ("_ews_surface_surface_displacement.csv", "_surface_displacement.csv"),
        )
        return matches[0] if matches else None

    @property
    def landmark_displacement_path(self) -> Path | None:
        matches = self._preferred_files(
            "*_landmark_displacement.csv",
            ("_ews_surface_landmark_displacement.csv", "_landmark_displacement.csv"),
        )
        return matches[0] if matches else None

    @property
    def tissue_stress_stats_path(self) -> Path | None:
        matches = self._preferred_files(
            "*_tissue_stress_stats.csv",
            ("_internal_tumor_tissue_stress_stats.csv", "_tissue_stress_stats.csv", "_ews_surface_tissue_stress_stats.csv"),
        )
        return matches[0] if matches else None

    def _preferred_files(self, pattern: str, suffix_priority: tuple[str, ...]) -> list[Path]:
        matches = sorted(self.solve_dir.glob(pattern))
        if not matches:
            return []
        ordered: list[Path] = []
        for suffix in suffix_priority:
            ordered.extend(path for path in matches if path.name.endswith(suffix) and path not in ordered)
        ordered.extend(path for path in matches if path not in ordered)
        return ordered


def p(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def has_core_outputs(case: Case) -> bool:
    return bool(list(case.solve_dir.glob("*_metrics.json"))) and bool(
        list(case.solve_dir.glob("*_time_series.csv"))
    )


STAGES: dict[str, list[Case]] = {
    "tier1_comparison": [
        Case(
            "tier1_stage1_025g",
            "Stage 1 0.25g baseline",
            "tier1_comparison",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_stage1_fixed_support_acceleration_pulse_mild_025g"),
        ),
        Case(
            "tier1_stage2_xoffset055",
            "Stage 2 xoffset055 chestwall",
            "tier1_comparison",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage2_chestwall",
                "outputs",
                "output_stage2_chestwall_xoffset_055_autoalign_vp_fixed_order2",
            ),
        ),
        Case(
            "tier1_stage3_realistic_ref",
            "Stage 3 realistic glandular",
            "tier1_comparison",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage3",
                "outputs",
                "output_stage3_glandular_realistic_spread_reference_xoffset055_preview",
            ),
        ),
        Case(
            "tier1_stage4_realistic_ref",
            "Stage 4 realistic reference",
            "tier1_comparison",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage4",
                "outputs",
                "output_stage4_realistic_reference_xoffset055_preview",
            ),
        ),
        Case(
            "tier1_stage5_no_cooper",
            "Stage 5 no-Cooper control",
            "tier1_comparison",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5_reference_no_cooper_xoffset055_025g_preview",
            ),
        ),
    ],
    "tier1_comparison_without_stage1": [
        Case(
            "tier1_stage2_xoffset055",
            "Stage 2 xoffset055 chestwall",
            "tier1_comparison_without_stage1",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage2_chestwall",
                "outputs",
                "output_stage2_chestwall_xoffset_055_autoalign_vp_fixed_order2",
            ),
        ),
        Case(
            "tier1_stage3_realistic_ref",
            "Stage 3 realistic glandular",
            "tier1_comparison_without_stage1",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage3",
                "outputs",
                "output_stage3_glandular_realistic_spread_reference_xoffset055_preview",
            ),
        ),
        Case(
            "tier1_stage4_realistic_ref",
            "Stage 4 realistic reference",
            "tier1_comparison_without_stage1",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage4",
                "outputs",
                "output_stage4_realistic_reference_xoffset055_preview",
            ),
        ),
        Case(
            "tier1_stage5_no_cooper",
            "Stage 5 no-Cooper control",
            "tier1_comparison_without_stage1",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5_reference_no_cooper_xoffset055_025g_preview",
            ),
        ),
    ],
    "stage1_baseline": [
        Case(
            "stage1_dynamic_simple_gland",
            "Dynamic simple gland",
            "stage1_baseline",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_baseline_simple_gland_dynamic_solid_only"),
        ),
        Case(
            "stage1_static_simple_gland",
            "Static simple gland",
            "stage1_baseline",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage1",
                "outputs",
                "output_full_baseline_reference_simple_gland_static_baseline",
            ),
        ),
        Case(
            "stage1_gravity_only_reference",
            "Gravity-only reference",
            "stage1_baseline",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_stage1_gravity_only_reference"),
        ),
        Case(
            "stage1_quasistatic_gravity_sag_reference",
            "Quasi-static gravity sag reference",
            "stage1_baseline",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_stage1_quasistatic_gravity_sag_reference"),
        ),
        Case(
            "stage1_fixed_support_acceleration_pulse",
            "Fixed-support acceleration pulse",
            "stage1_baseline",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_stage1_fixed_support_acceleration_pulse"),
        ),
        Case(
            "stage1_fixed_support_acceleration_pulse_mild_025g",
            "Fixed-support pulse mild 0.25g",
            "stage1_baseline",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_stage1_fixed_support_acceleration_pulse_mild_025g"),
        ),
        Case(
            "stage1_fixed_support_acceleration_pulse_moderate_050g",
            "Fixed-support pulse moderate 0.50g",
            "stage1_baseline",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_stage1_fixed_support_acceleration_pulse_moderate_050g"),
        ),
        Case(
            "stage1_smooth_support_motion",
            "Smooth support-motion fallback",
            "stage1_baseline",
            p("runs", "comsol_runs", "geometry_stage1", "outputs", "output_stage1_smooth_support_motion"),
        ),
    ],
    "stage2_chestwall": [
        Case(
            "stage2_xoffset055_autoalign_025g",
            "X-offset 0.055 m auto-align 0.25g",
            "stage2_chestwall",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage2_chestwall",
                "outputs",
                "output_stage2_chestwall_xoffset_055_autoalign_vp_fixed_order2",
            ),
        ),
        Case(
            "stage2_slab",
            "Slab reference",
            "stage2_chestwall",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage2_chestwall",
                "outputs",
                "output_stage2_vp_refined_slab_reference_fixed_order2",
            ),
        ),
        Case(
            "stage2_g1025",
            "VP mild g1025",
            "stage2_chestwall",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage2_chestwall",
                "outputs",
                "output_stage2_vp_refined_mild_g1025_fixed_order2",
            ),
        ),
        Case(
            "stage2_g1050",
            "VP mild g1050",
            "stage2_chestwall",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage2_chestwall",
                "outputs",
                "output_stage2_vp_refined_mild_g1050_fixed_order2",
            ),
        ),
    ],
    "stage3_glandular_fraction": [
        Case(
            "stage3_realistic_compact_xoffset055_025g",
            "Realistic compact lobule spread xoffset055 0.25g",
            "stage3_glandular_fraction",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage3",
                "outputs",
                "output_stage3_glandular_realistic_spread_compact_xoffset055_preview",
            ),
        ),
        Case(
            "stage3_realistic_reference_xoffset055_025g",
            "Realistic lobule reference xoffset055 0.25g",
            "stage3_glandular_fraction",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage3",
                "outputs",
                "output_stage3_glandular_realistic_spread_reference_xoffset055_preview",
            ),
        ),
        Case(
            "stage3_realistic_wide_xoffset055_025g",
            "Realistic wide lobule spread xoffset055 0.25g",
            "stage3_glandular_fraction",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage3",
                "outputs",
                "output_stage3_glandular_realistic_spread_wide_xoffset055_preview",
            ),
        ),
    ],
    "stage4_asymmetry": [
        Case(
            "stage4_realistic_reference_xoffset055_025g",
            "Realistic reference xoffset055 0.25g",
            "stage4_asymmetry",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage4",
                "outputs",
                "output_stage4_realistic_reference_xoffset055_preview",
            ),
        ),
        Case(
            "stage4_realistic_profile_asym_xoffset055_partial",
            "Realistic profile asym. xoffset055 partial",
            "stage4_asymmetry",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage4",
                "outputs",
                "output_stage4_realistic_profile_asym_xoffset055_preview",
            ),
        ),
        Case(
            "stage4_realistic_nipple_lateral_xoffset055_025g",
            "Realistic nipple lateral xoffset055 0.25g",
            "stage4_asymmetry",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage4",
                "outputs",
                "output_stage4_realistic_nipple_lateral_xoffset055_preview",
            ),
        ),
        Case(
            "stage4_realistic_nipple_superior_xoffset055_025g",
            "Realistic nipple superior xoffset055 0.25g",
            "stage4_asymmetry",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage4",
                "outputs",
                "output_stage4_realistic_nipple_superior_xoffset055_preview",
            ),
        ),
    ],
    "report_fixed_material_suite": [
        Case(
            "report_fixed_baseline_o1",
            "Report baseline O1",
            "report_fixed_material_suite",
            p(
                "runs",
                "comsol_runs",
                "report_fixed_material_suite",
                "outputs",
                "output_report_baseline_fixed_materials_order1",
            ),
        ),
        Case(
            "report_fixed_stage5b_o1",
            "Report Stage 5B O1",
            "report_fixed_material_suite",
            p(
                "runs",
                "comsol_runs",
                "report_fixed_material_suite",
                "outputs",
                "output_report_stage5b_fixed_materials_order1",
            ),
        ),
    ],
    "stage5_cooper": [
        Case(
            "stage5_no_cooper_xoffset055_025g",
            "No Cooper xoffset055 0.25g",
            "stage5_cooper",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5_reference_no_cooper_xoffset055_025g_preview",
            ),
        ),
        Case(
            "stage5b_default_xoffset055_025g_failed",
            "5B default xoffset055 failed early",
            "stage5_cooper",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5b_cooper_default_xoffset055_025g_preview",
            ),
        ),
        Case(
            "stage5b_mild_xoffset055_025g",
            "5B mild Cooper xoffset055 0.25g",
            "stage5_cooper",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5b_cooper_mild_xoffset055_025g_preview",
            ),
        ),
        Case(
            "stage5b_stiff_xoffset055_025g",
            "5B stiff Cooper xoffset055 0.25g",
            "stage5_cooper",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5b_cooper_stiff_xoffset055_025g_preview",
            ),
        ),
        Case(
            "stage5b_damped_xoffset055_025g",
            "5B damped Cooper xoffset055 0.25g",
            "stage5_cooper",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5b_cooper_damped_xoffset055_025g_preview",
            ),
        ),
        Case(
            "stage5c_dense_network_diagnostic_xoffset055_025g",
            "5C dense network diagnostic xoffset055 0.25g",
            "stage5_cooper",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5c_dense_network_diagnostic_xoffset055_025g_preview",
            ),
        ),
    ],
    "stage5_dynamic_amplitude_scout": [
        Case(
            "stage5_no_cooper_xoffset055_025g",
            "No Cooper xoffset055 0.25g",
            "stage5_dynamic_amplitude_scout",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5_reference_no_cooper_xoffset055_025g_preview",
            ),
        ),
        Case(
            "stage5_no_cooper_xoffset055_050g",
            "No Cooper xoffset055 0.50g",
            "stage5_dynamic_amplitude_scout",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5_reference_no_cooper_xoffset055_050g_preview",
            ),
        ),
        Case(
            "stage5_no_cooper_xoffset055_075g",
            "No Cooper xoffset055 0.75g",
            "stage5_dynamic_amplitude_scout",
            p(
                "runs",
                "comsol_runs",
                "geometry_stage5",
                "outputs",
                "output_stage5_reference_no_cooper_xoffset055_075g_preview",
            ),
        ),
    ],
    "stage6_fast_tumor_screening": [
        Case(
            "stage6_fast_control_xoffset055_025g",
            "Fast control no tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_control_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_small_central_xoffset055_025g",
            "Fast small central tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_small_central_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_medium_central_xoffset055_025g",
            "Fast medium central tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_medium_central_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_large_central_xoffset055_025g",
            "Fast large central tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_large_central_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_small_upper_outer_xoffset055_025g",
            "Fast small upper-outer tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_small_upper_outer_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_small_subareolar_xoffset055_025g",
            "Fast small subareolar tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_small_subareolar_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_small_posterior_xoffset055_025g",
            "Fast small posterior tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_small_posterior_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_small_upper_outer_surface_proximal_xoffset055_025g",
            "Fast small upper-outer surface-proximal tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_small_upper_outer_surface_proximal_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_small_upper_outer_superior_xoffset055_025g",
            "Fast small upper-outer superior tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_small_upper_outer_superior_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_medium_upper_outer_surface_proximal_xoffset055_025g",
            "Fast medium upper-outer surface-proximal tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_medium_upper_outer_surface_proximal_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_fast_medium_upper_outer_superior_xoffset055_025g",
            "Fast medium upper-outer superior tumor xoffset055 0.25g",
            "stage6_fast_tumor_screening",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_fast_tumor_medium_upper_outer_superior_xoffset055_025g_preview"),
        ),
    ],
    "stage6_tumor_preview": [
        Case(
            "stage6_control_xoffset055_025g",
            "Control no tumor xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_control_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_small_central_xoffset055_025g",
            "Small central tumor xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_small_central_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_medium_central_xoffset055_025g",
            "Medium central tumor xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_medium_central_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_large_central_xoffset055_025g",
            "Large central tumor xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_large_central_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_small_upper_outer_xoffset055_025g",
            "Small upper-outer tumor xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_small_upper_outer_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_small_subareolar_xoffset055_025g",
            "Small subareolar tumor xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_small_subareolar_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_small_posterior_xoffset055_025g",
            "Small posterior tumor xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_small_posterior_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_stiffness_mild_xoffset055_025g",
            "Mild tumor stiffness xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_stiffness_mild_xoffset055_025g_preview"),
        ),
        Case(
            "stage6_stiffness_stiff_xoffset055_025g",
            "Stiff tumor stiffness xoffset055 0.25g",
            "stage6_tumor_preview",
            p("runs", "comsol_runs", "geometry_stage6", "outputs", "output_stage6_tumor_stiffness_stiff_xoffset055_025g_preview"),
        ),
    ],
}


OBSOLETE_GENERATED_FIGURES = {
    "displacement_evolution.png",
    "stress_evolution.png",
    "tissue_stress_at_review.png",
    "volume_and_gland_fraction.png",
}


def read_csv_rows(path: Path) -> list[dict[str, float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = []
        for row in csv.DictReader(handle):
            clean_row = {}
            for key, value in row.items():
                if value in {"", None}:
                    continue
                try:
                    clean_row[key] = float(value)
                except ValueError:
                    continue
            rows.append(clean_row)
    return rows


def read_csv_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def float_or_none(value: object) -> float | None:
    if value in {"", None}:
        return None
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def finite_number(value: object) -> float | None:
    return float_or_none(value)


def time_series_columns(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def nearest_row(rows: list[dict[str, float]], time_s: float = REVIEW_TIME_S) -> dict[str, float]:
    return min(rows, key=lambda row: abs(float(row.get("time_s", 0.0)) - time_s))


def metrics_for(case: Case) -> dict:
    return json.loads(case.metrics_path.read_text(encoding="utf-8"))


def review_time_for(case: Case) -> float:
    payload = metrics_for(case)
    configured = finite_number(payload.get("configured_review_time_s"))
    if configured is not None:
        return configured

    mode = str(payload.get("configured_dynamic_motion_mode", "") or "").lower()
    times = [
        finite_number(value)
        for value in payload.get("time_s", [])
        if finite_number(value) is not None
    ]
    if mode == "gravity_only" and times:
        return max(times)

    jump_start = finite_number(payload.get("jump_start_time_s"))
    if jump_start is not None:
        duration_key = "pulse_duration_s" if mode == "fixed_support_acceleration_pulse" else "jump_duration_s"
        duration = finite_number(payload.get(duration_key))
        if duration is not None and duration > 0:
            return jump_start + 0.5 * duration

    metric_review = finite_number(payload.get("review_time_s"))
    return metric_review if metric_review is not None else REVIEW_TIME_S


def plot_review_markers(ax, cases: Iterable[Case]) -> None:
    times = sorted({round(review_time_for(case), 6) for case in cases})
    for index, time_s in enumerate(times):
        ax.axvline(
            time_s,
            color="black",
            linestyle="--",
            linewidth=1,
            alpha=0.45,
            label="review time" if index == 0 else None,
        )


def ml(value_m3: float | None) -> float | None:
    return None if value_m3 is None else value_m3 * 1_000_000.0


def pct(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline in {None, 0.0}:
        return None
    return 100.0 * (value - baseline) / baseline


def finite(value: float | None) -> float | None:
    if value is None:
        return None
    return value if math.isfinite(value) else None


def row_value(row: dict[str, float], key: str, scale: float = 1.0) -> float | None:
    value = finite(row.get(key))
    return None if value is None else value * scale


def series(rows: list[dict[str, float]], key: str, scale: float = 1.0) -> list[float] | None:
    if not rows or any(key not in row for row in rows):
        return None
    values = [row[key] * scale for row in rows]
    return values if any(math.isfinite(value) for value in values) else None


def preferred_series(rows: list[dict[str, float]], candidates: list[str]) -> tuple[list[float] | None, str | None]:
    for key in candidates:
        values = series(rows, key)
        if values is not None:
            return values, key
    return None, None


def support_motion_nonzero(rows: list[dict[str, float]], support_key: str) -> bool:
    values = [float_or_none(row.get(support_key)) for row in rows]
    finite_values = [value for value in values if value is not None]
    if not finite_values:
        return False
    return max(abs(value) for value in finite_values) > 1e-6


def dynamic_vertical_series(
    rows: list[dict[str, float]],
    *,
    support_key: str,
    relative_key: str,
    dynamic_start_key: str,
) -> tuple[list[float] | None, str | None]:
    if support_motion_nonzero(rows, support_key):
        values = series(rows, relative_key)
        if values is not None:
            return values, relative_key
    values = series(rows, dynamic_start_key)
    if values is not None:
        return values, dynamic_start_key
    return preferred_series(rows, [relative_key, dynamic_start_key])


def setup_axes(title: str, ylabel: str) -> tuple:
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.28)
    return fig, ax


def save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    tmp_path = path.with_name(f"{path.stem}.tmp{path.suffix}")
    fig.savefig(tmp_path, dpi=220)
    tmp_path.replace(path)
    plt.close(fig)


def cleanup_obsolete_figures(figure_dir: Path) -> None:
    for filename in OBSOLETE_GENERATED_FIGURES:
        path = figure_dir / filename
        if path.exists():
            path.unlink()


def plot_displacement_response(cases: Iterable[Case], figure_dir: Path) -> Path:
    fig, ax = setup_axes("Breast displacement magnitude response", "Displacement magnitude (mm)")
    for case in cases:
        rows = read_csv_rows(case.time_series_path)
        time = [r["time_s"] for r in rows]
        avg = series(rows, "disp_avg_mm")
        max_values = series(rows, "disp_max_mm")
        line = None
        if avg is not None:
            (line,) = ax.plot(time, avg, label=f"{case.label} avg", linewidth=2.2)
        if max_values is not None:
            color = line.get_color() if line else None
            ax.plot(time, max_values, label=f"{case.label} max", linewidth=1.2, linestyle="--", alpha=0.55, color=color)
    plot_review_markers(ax, cases)
    ax.legend(fontsize=7, ncol=2)
    ax.text(
        0.01,
        0.01,
        "Magnitude only: current COMSOL exports do not include vertical or landmark displacement.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    path = figure_dir / "displacement_magnitude_response.png"
    save(fig, path)
    return path


def plot_surface_signed_response(cases: Iterable[Case], figure_dir: Path) -> Path | None:
    available = [(case, case.surface_displacement_path) for case in cases if case.surface_displacement_path]
    if not available:
        return None
    fig, ax = setup_axes("Signed outer-surface vertical displacement", "Signed vertical displacement w (mm)")
    plotted = False
    for case, path in available:
        rows = read_csv_rows(path)
        if not rows:
            continue
        time = [r["time_s"] for r in rows if "time_s" in r]
        mean_w = series(rows, "signed_vertical_w_mean_mm")
        min_w = series(rows, "signed_vertical_w_min_mm")
        max_w = series(rows, "signed_vertical_w_max_mm")
        if mean_w is None or len(time) != len(mean_w):
            continue
        plotted = True
        (line,) = ax.plot(time, mean_w, label=f"{case.label} surface mean w", linewidth=2.2)
        if min_w is not None and max_w is not None and len(min_w) == len(time) and len(max_w) == len(time):
            ax.fill_between(time, min_w, max_w, color=line.get_color(), alpha=0.12)
    if not plotted:
        plt.close(fig)
        return None
    ax.axhline(0, color="black", linewidth=0.8, alpha=0.45)
    plot_review_markers(ax, cases)
    ax.legend(fontsize=7, ncol=2)
    ax.text(
        0.01,
        0.01,
        "Negative w = downward motion. Source: COMSOL outer-skin boundary integration, not volume magnitude.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    path = figure_dir / "surface_signed_vertical_response.png"
    save(fig, path)
    return path


def plot_surface_displacement_statistics(cases: Iterable[Case], figure_dir: Path) -> Path | None:
    available = [(case, case.surface_displacement_path) for case in cases if case.surface_displacement_path]
    if not available:
        return None
    fig, ax = setup_axes("Outer-surface displacement magnitude statistics", "Displacement magnitude (mm)")
    plotted = False
    for case, path in available:
        rows = read_csv_rows(path)
        if not rows:
            continue
        time = [r["time_s"] for r in rows if "time_s" in r]
        mean_disp = series(rows, "disp_mag_mean_mm")
        max_disp = series(rows, "disp_mag_max_mm")
        std_disp = series(rows, "disp_mag_std_mm")
        line = None
        if mean_disp is not None and len(mean_disp) == len(time):
            plotted = True
            (line,) = ax.plot(time, mean_disp, label=f"{case.label} surface mean", linewidth=2.2)
            if std_disp is not None and len(std_disp) == len(time):
                lower = [m - s for m, s in zip(mean_disp, std_disp)]
                upper = [m + s for m, s in zip(mean_disp, std_disp)]
                ax.fill_between(time, lower, upper, color=line.get_color(), alpha=0.12)
        if max_disp is not None and len(max_disp) == len(time):
            color = line.get_color() if line else None
            ax.plot(time, max_disp, label=f"{case.label} surface max", linewidth=1.1, linestyle="--", alpha=0.55, color=color)
    if not plotted:
        plt.close(fig)
        return None
    plot_review_markers(ax, cases)
    ax.legend(fontsize=7, ncol=2)
    ax.text(
        0.01,
        0.01,
        "Mean/std are area-based boundary statistics. Median/p95 need sampled-field export.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    path = figure_dir / "surface_displacement_statistics.png"
    save(fig, path)
    return path


def plot_surface_dynamic_vertical_response(cases: Iterable[Case], figure_dir: Path) -> Path | None:
    available = [(case, case.surface_displacement_path) for case in cases if case.surface_displacement_path]
    if not available:
        return None
    fig, ax = setup_axes("Outer-surface vertical dynamic response", "Vertical displacement w (mm)")
    plotted = False
    used_keys: set[str] = set()
    for case, path in available:
        rows = read_csv_rows(path)
        if not rows:
            continue
        time = [r["time_s"] for r in rows if "time_s" in r]
        values, key = dynamic_vertical_series(
            rows,
            support_key="support_signed_vertical_w_mean_mm",
            relative_key="signed_vertical_w_mean_relative_to_support_mm",
            dynamic_start_key="signed_vertical_w_mean_from_dynamic_start_mm",
        )
        if values is None or key is None or len(values) != len(time):
            continue
        dynamic_start_s = finite_number(metrics_for(case).get("dynamic_start_time_s")) or 0.0
        pairs = [(t, value) for t, value in zip(time, values) if t >= dynamic_start_s - 1e-9]
        if not pairs:
            continue
        plotted = True
        used_keys.add(key)
        label_suffix = "support-relative" if "relative_to_support" in key else "from dynamic start"
        ax.plot([t for t, _ in pairs], [value for _, value in pairs], label=f"{case.label} {label_suffix}", linewidth=2.2)
    if not plotted:
        plt.close(fig)
        return None
    ax.axhline(0, color="black", linewidth=0.8, alpha=0.45)
    plot_review_markers(ax, cases)
    ax.legend(fontsize=7, ncol=2)
    if "signed_vertical_w_mean_relative_to_support_mm" in used_keys:
        note = "Primary metric: outer-surface mean w minus posterior support/chestwall mean w."
    else:
        note = "Diagnostic fallback: outer-surface mean w minus value at dynamic start."
    ax.text(0.01, 0.01, note, transform=ax.transAxes, fontsize=8, color="#555555")
    path = figure_dir / "surface_vertical_dynamic_response.png"
    save(fig, path)
    return path


def plot_landmark_signed_response(cases: Iterable[Case], figure_dir: Path) -> Path | None:
    available = [(case, case.landmark_displacement_path) for case in cases if case.landmark_displacement_path]
    if not available:
        return None
    fig, ax = setup_axes("Nipple landmark signed vertical displacement", "Signed vertical displacement w (mm)")
    plotted = False
    for case, path in available:
        rows = [
            row for row in read_csv_table(path)
            if row.get("landmark") == "nipple"
        ]
        if not rows:
            continue
        time = [float_or_none(row.get("time_s")) for row in rows]
        values = [float_or_none(row.get("uz_vertical_mean_mm")) for row in rows]
        dynamic_start_s = finite_number(metrics_for(case).get("dynamic_start_time_s")) or 0.0
        pairs = [
            (t, v)
            for t, v in zip(time, values)
            if t is not None and v is not None and t >= dynamic_start_s - 1e-9
        ]
        if not pairs:
            continue
        plotted = True
        ax.plot([t for t, _ in pairs], [v for _, v in pairs], label=f"{case.label} nipple patch", linewidth=2.2)
    if not plotted:
        plt.close(fig)
        return None
    ax.axhline(0, color="black", linewidth=0.8, alpha=0.45)
    plot_review_markers(ax, cases)
    ax.legend(fontsize=7, ncol=2)
    ax.text(
        0.01,
        0.01,
        "Patch-average landmark displacement; more stable than a single mesh point.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    path = figure_dir / "landmark_nipple_signed_vertical_response.png"
    save(fig, path)
    return path


def plot_landmark_nipple_dynamic_response(cases: Iterable[Case], figure_dir: Path) -> Path | None:
    available = [(case, case.landmark_displacement_path) for case in cases if case.landmark_displacement_path]
    if not available:
        return None
    fig, ax = setup_axes("Nipple landmark vertical dynamic response", "Vertical displacement w (mm)")
    plotted = False
    used_keys: set[str] = set()
    for case, path in available:
        rows = [row for row in read_csv_table(path) if row.get("landmark") == "nipple"]
        if not rows:
            continue
        time = [float_or_none(row.get("time_s")) for row in rows]
        selected_key = (
            "uz_vertical_mean_relative_to_support_mm"
            if support_motion_nonzero(rows, "support_uz_vertical_mean_mm")
            else "uz_vertical_mean_from_dynamic_start_mm"
        )
        values = [float_or_none(row.get(selected_key)) for row in rows]
        if selected_key is None:
            continue
        dynamic_start_s = finite_number(metrics_for(case).get("dynamic_start_time_s")) or 0.0
        pairs = [
            (t, v)
            for t, v in zip(time, values)
            if t is not None and v is not None and t >= dynamic_start_s - 1e-9
        ]
        if not pairs:
            continue
        plotted = True
        used_keys.add(selected_key)
        label_suffix = "support-relative" if "relative_to_support" in selected_key else "from dynamic start"
        ax.plot([t for t, _ in pairs], [v for _, v in pairs], label=f"{case.label} nipple {label_suffix}", linewidth=2.2)
    if not plotted:
        plt.close(fig)
        return None
    ax.axhline(0, color="black", linewidth=0.8, alpha=0.45)
    plot_review_markers(ax, cases)
    ax.legend(fontsize=7, ncol=2)
    if "uz_vertical_mean_relative_to_support_mm" in used_keys:
        note = "Primary metric: nipple patch w minus posterior support/chestwall mean w."
    else:
        note = "Diagnostic fallback: nipple patch w minus value at dynamic start."
    ax.text(0.01, 0.01, note, transform=ax.transAxes, fontsize=8, color="#555555")
    path = figure_dir / "landmark_nipple_vertical_dynamic_response.png"
    save(fig, path)
    return path


def plot_stress_response(cases: Iterable[Case], figure_dir: Path) -> Path:
    fig, ax = setup_axes("Breast von Mises stress response", "Von Mises stress (kPa)")
    plotted_avg = False
    for case in cases:
        rows = read_csv_rows(case.time_series_path)
        time = [r["time_s"] for r in rows]
        avg = series(rows, "vm_avg_pa", 1.0 / 1000.0)
        max_values = series(rows, "vm_max_pa", 1.0 / 1000.0)
        line = None
        if avg is not None:
            plotted_avg = True
            (line,) = ax.plot(time, avg, label=f"{case.label} mean", linewidth=2.2)
        if max_values is not None:
            color = line.get_color() if line else None
            label = f"{case.label} max" if avg is None else f"{case.label} max hotspot"
            ax.plot(time, max_values, label=label, linewidth=1.1, linestyle="--", alpha=0.55, color=color)
    plot_review_markers(ax, cases)
    ax.legend(fontsize=7, ncol=2)
    note = "Mean uses COMSOL average stress export; dashed max is a hotspot indicator."
    if not plotted_avg:
        note = "Mean stress is not available for these outputs; only max hotspot series is exported."
    ax.text(0.01, 0.01, note, transform=ax.transAxes, fontsize=8, color="#555555")
    path = figure_dir / "stress_mean_max_response.png"
    save(fig, path)
    return path


def plot_tissue_review(cases: list[Case], figure_dir: Path) -> Path:
    rows_by_case = [
        (case, nearest_row(read_csv_rows(case.time_series_path), review_time_for(case)))
        for case in cases
    ]
    tissue_specs = [
        ("breast mean", "vm_avg_pa", "#5b7fb9"),
        ("gland mean", "gland_vm_avg_pa", "#b65f5f"),
        ("adipose mean", "adipose_vm_avg_pa", "#7e9f62"),
        ("breast max", "vm_max_pa", "#2f4d7a"),
        ("gland max", "gland_vm_max_pa", "#7a3434"),
        ("adipose max", "adipose_vm_max_pa", "#4c663b"),
    ]
    available_specs = []
    for label, key, color in tissue_specs:
        if any(row_value(row, key, 1.0 / 1000.0) is not None for _, row in rows_by_case):
            available_specs.append((label, key, color))

    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    x = list(range(len(cases)))
    if available_specs:
        width = min(0.8 / len(available_specs), 0.16)
        start = -0.5 * width * (len(available_specs) - 1)
        for idx, (label, key, color) in enumerate(available_specs):
            values = [row_value(row, key, 1.0 / 1000.0) for _, row in rows_by_case]
            positions = [pos + start + idx * width for pos in x]
            ax.bar(positions, [value if value is not None else math.nan for value in values], width=width, label=label, color=color)
    ax.set_title("Tissue stress at case-specific review time")
    ax.set_ylabel("Von Mises stress (kPa)")
    ax.set_xticks(x)
    ax.set_xticklabels([case.label for case in cases], rotation=20, ha="right")
    ax.grid(True, axis="y", alpha=0.28)
    ax.legend(fontsize=8, ncol=3)
    ax.text(
        0.01,
        0.01,
        "Missing tissue exports are omitted, not plotted as zero.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    path = figure_dir / "tissue_stress_review_available.png"
    save(fig, path)
    return path


def review_summary_row(stage: str, case: Case) -> dict[str, object]:
    review_time = review_time_for(case)
    ts_rows = read_csv_rows(case.time_series_path)
    ts_row = nearest_row(ts_rows, review_time)
    payload = metrics_for(case)
    surface_row = None
    if case.surface_displacement_path:
        surface_rows = read_csv_rows(case.surface_displacement_path)
        surface_row = nearest_row(surface_rows, review_time) if surface_rows else None
    landmark_row = None
    if case.landmark_displacement_path:
        landmark_rows = [
            row for row in read_csv_rows(case.landmark_displacement_path)
            if str(row.get("landmark", "")).lower() == "nipple"
        ]
        landmark_row = nearest_row(landmark_rows, review_time) if landmark_rows else None
    last_output_time_s = max((row.get("time_s", 0.0) for row in ts_rows), default=0.0)
    expected_end_time_s = finite_number(payload.get("dynamic_end_time_s"))
    result_mph = case.result_mph_path
    image_export_completed = False
    if case.plot_screens_dir.exists():
        image_export_completed = all(
            (case.plot_screens_dir / name).exists()
            for name in (
                "01_total_displacement_mm.png",
                "02_vertical_displacement_w_mm.png",
                "03_anterior_posterior_displacement_v_mm.png",
                "04_breast_von_mises_kpa.png",
                "05_glandular_von_mises_kpa.png",
                "06_sagittal_cut_von_mises_kpa.png",
                "07_sagittal_cut_total_displacement_mm.png",
            )
        )
    breast = ml(float(payload.get("breast_volume", 0.0)))
    gland = ml(float(payload.get("glandular_volume", 0.0)))
    adipose = ml(float(payload.get("adipose_volume", 0.0)))
    columns = time_series_columns(case.time_series_path)
    return {
        "stage": stage,
        "case_key": case.key,
        "case_label": case.label,
        "configured_dynamic_motion_mode": payload.get("configured_dynamic_motion_mode", ""),
        "configured_review_time_s": review_time,
        "result_mph_exists": result_mph is not None,
        "metrics_json_exists": case.metrics_path.exists(),
        "postprocess_completed": True,
        "image_export_completed": image_export_completed,
        "review_time_s": ts_row.get("time_s", review_time),
        "last_output_time_s": last_output_time_s,
        "expected_dynamic_end_time_s": expected_end_time_s,
        "solve_reached_review_time": last_output_time_s >= review_time - 1e-6,
        "solve_reached_expected_end": (
            None if expected_end_time_s is None else last_output_time_s >= expected_end_time_s - 1e-6
        ),
        "breast_volume_ml": breast,
        "glandular_volume_ml": gland,
        "adipose_volume_ml": adipose,
        "glandular_fraction_pct": 100.0 * (gland or 0.0) / breast if breast else None,
        "review_max_displacement_mm": row_value(ts_row, "disp_max_mm"),
        "review_avg_displacement_mm": row_value(ts_row, "disp_avg_mm"),
        "review_breast_vm_max_kpa": row_value(ts_row, "vm_max_pa", 1.0 / 1000.0),
        "review_breast_vm_avg_kpa": row_value(ts_row, "vm_avg_pa", 1.0 / 1000.0),
        "review_gland_vm_max_kpa": row_value(ts_row, "gland_vm_max_pa", 1.0 / 1000.0),
        "review_gland_vm_avg_kpa": row_value(ts_row, "gland_vm_avg_pa", 1.0 / 1000.0),
        "review_adipose_vm_max_kpa": row_value(ts_row, "adipose_vm_max_pa", 1.0 / 1000.0),
        "review_adipose_vm_avg_kpa": row_value(ts_row, "adipose_vm_avg_pa", 1.0 / 1000.0),
        "review_surface_signed_w_mean_mm": row_value(surface_row or {}, "signed_vertical_w_mean_mm"),
        "review_surface_signed_w_from_dynamic_start_mm": row_value(
            surface_row or {}, "signed_vertical_w_mean_from_dynamic_start_mm"
        ),
        "review_surface_signed_w_relative_to_support_mm": row_value(
            surface_row or {}, "signed_vertical_w_mean_relative_to_support_mm"
        ),
        "review_surface_disp_mag_mean_mm": row_value(surface_row or {}, "disp_mag_mean_mm"),
        "review_nipple_signed_w_mean_mm": row_value(landmark_row or {}, "uz_vertical_mean_mm"),
        "review_nipple_w_from_dynamic_start_mm": row_value(
            landmark_row or {}, "uz_vertical_mean_from_dynamic_start_mm"
        ),
        "review_nipple_w_relative_to_support_mm": row_value(
            landmark_row or {}, "uz_vertical_mean_relative_to_support_mm"
        ),
        "available_time_series_columns": ";".join(columns),
        "output_dir": case.output_dir.relative_to(ROOT).as_posix(),
        "metrics_json": case.metrics_path.relative_to(ROOT).as_posix(),
        "time_series_csv": case.time_series_path.relative_to(ROOT).as_posix(),
        "surface_displacement_csv": case.surface_displacement_path.relative_to(ROOT).as_posix() if case.surface_displacement_path else "",
        "landmark_displacement_csv": case.landmark_displacement_path.relative_to(ROOT).as_posix() if case.landmark_displacement_path else "",
        "tissue_stress_stats_csv": case.tissue_stress_stats_path.relative_to(ROOT).as_posix() if case.tissue_stress_stats_path else "",
    }


def plot_response_change(stage: str, rows: list[dict[str, object]], figure_dir: Path) -> Path | None:
    if len(rows) < 2:
        return None
    baseline = rows[0]
    metric_specs = [
        ("avg disp", "review_avg_displacement_mm"),
        ("max disp", "review_max_displacement_mm"),
        ("breast mean VM", "review_breast_vm_avg_kpa"),
        ("breast max VM", "review_breast_vm_max_kpa"),
    ]
    available = []
    for label, key in metric_specs:
        if baseline.get(key) is not None and any(row.get(key) is not None for row in rows[1:]):
            available.append((label, key))
    if not available:
        return None

    fig, ax = plt.subplots(figsize=(11.0, 5.8))
    labels = [str(row["case_label"]) for row in rows]
    x = list(range(len(rows)))
    width = min(0.8 / len(available), 0.18)
    start = -0.5 * width * (len(available) - 1)
    for idx, (label, key) in enumerate(available):
        base_value = baseline.get(key)
        values = [pct(row.get(key), base_value) for row in rows]  # type: ignore[arg-type]
        positions = [pos + start + idx * width for pos in x]
        ax.bar(positions, [value if value is not None else math.nan for value in values], width=width, label=label)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(f"Review-time response change vs {labels[0]}")
    ax.set_ylabel("Change (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(True, axis="y", alpha=0.28)
    ax.legend(fontsize=8, ncol=2)
    path = figure_dir / "response_change_vs_reference.png"
    save(fig, path)
    return path


def plot_gland_fraction_response(rows: list[dict[str, object]], figure_dir: Path) -> Path | None:
    fractions = [finite(row.get("glandular_fraction_pct")) for row in rows]  # type: ignore[arg-type]
    if any(value is None for value in fractions):
        return None
    if max(fractions) - min(fractions) < 2.0:  # type: ignore[arg-type]
        return None

    disp = [finite(row.get("review_avg_displacement_mm")) for row in rows]  # type: ignore[arg-type]
    stress = [
        finite(row.get("review_breast_vm_avg_kpa") if row.get("review_breast_vm_avg_kpa") is not None else row.get("review_breast_vm_max_kpa"))
        for row in rows
    ]
    labels = [str(row["case_label"]) for row in rows]
    fig, ax1 = plt.subplots(figsize=(9.5, 5.5))
    ax1.plot(fractions, disp, marker="o", linewidth=2.2, label="avg displacement", color="#5b7fb9")
    ax1.set_xlabel("Glandular fraction (%)")
    ax1.set_ylabel("Avg displacement magnitude at review (mm)")
    ax1.grid(True, alpha=0.28)
    ax2 = ax1.twinx()
    ax2.plot(fractions, stress, marker="s", linewidth=2.2, label="breast VM", color="#b65f5f")
    ax2.set_ylabel("Breast VM at review (kPa)")
    for x, y, label in zip(fractions, disp, labels):
        ax1.annotate(label, (x, y), textcoords="offset points", xytext=(4, 5), fontsize=8)
    ax1.set_title("Response versus glandular fraction")
    lines, line_labels = ax1.get_legend_handles_labels()
    lines2, line_labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, line_labels + line_labels2, loc="best")
    path = figure_dir / "gland_fraction_response.png"
    save(fig, path)
    return path


def write_contact_sheet(stage: str, figure_paths: list[Path], figure_dir: Path) -> Path:
    thumbs: list[tuple[str, Image.Image]] = []
    thumb_width = 760
    label_height = 34
    gap = 24
    margin = 32
    for path in figure_paths:
        image = Image.open(path).convert("RGB")
        width, height = image.size
        thumb_height = int(height * thumb_width / width)
        label = path.stem.replace("_", " ")
        thumbs.append((label, image.resize((thumb_width, thumb_height), Image.LANCZOS)))

    cols = 2
    rows = math.ceil(len(thumbs) / cols)
    cell_width = thumb_width
    cell_height = label_height + max(image.height for _, image in thumbs)
    canvas = Image.new(
        "RGB",
        (margin * 2 + cell_width * cols + gap * (cols - 1), margin * 2 + cell_height * rows + gap * (rows - 1)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 10), f"COMSOL evaluation contact sheet: {stage}", fill=(20, 20, 20))
    for index, (label, image) in enumerate(thumbs):
        col = index % cols
        row = index // cols
        x = margin + col * (cell_width + gap)
        y = margin + row * (cell_height + gap)
        draw.text((x, y), label, fill=(20, 20, 20))
        canvas.paste(image, (x, y + label_height))
    path = figure_dir / "contact_sheet.png"
    canvas.save(path)
    return path


def case_status_row(stage: str, case: Case) -> dict[str, object]:
    result_mph = case.result_mph_path
    metrics_files = sorted(case.solve_dir.glob("*_metrics.json"))
    time_series_files = sorted(case.solve_dir.glob("*_time_series.csv"))
    image_files = sorted(case.plot_screens_dir.glob("*.png")) if case.plot_screens_dir.exists() else []
    expected_image_names = {
        "01_total_displacement_mm.png",
        "02_vertical_displacement_w_mm.png",
        "03_anterior_posterior_displacement_v_mm.png",
        "04_breast_von_mises_kpa.png",
        "05_glandular_von_mises_kpa.png",
        "06_sagittal_cut_von_mises_kpa.png",
        "07_sagittal_cut_total_displacement_mm.png",
    }
    image_names = {path.name for path in image_files}
    legacy_cooper_names = {
        "08_cooper_nipple_load_arrows.png",
        "09_cooper_skin_load_arrows.png",
        "09_cooper_skin_patch_load_arrows.png",
        "10_cooper_glandular_load_arrows.png",
        "10_cooper_gland_patch_load_arrows.png",
    }
    return {
        "stage": stage,
        "case_key": case.key,
        "case_label": case.label,
        "result_mph_exists": result_mph is not None,
        "result_mph": result_mph.relative_to(ROOT).as_posix() if result_mph else "",
        "metrics_json_exists": bool(metrics_files),
        "time_series_csv_exists": bool(time_series_files),
        "postprocess_completed": bool(metrics_files and time_series_files),
        "image_export_completed": expected_image_names.issubset(image_names),
        "image_png_count": len(image_files),
        "expected_image_png_count": len(expected_image_names.intersection(image_names)),
        "legacy_cooper_image_png_count": len(legacy_cooper_names.intersection(image_names)),
        "output_dir": case.output_dir.relative_to(ROOT).as_posix(),
    }


def write_status_table(stage: str, cases: list[Case], table_dir: Path) -> None:
    table_dir.mkdir(parents=True, exist_ok=True)
    rows = [case_status_row(stage, case) for case in cases]
    csv_path = table_dir / "case_status.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    md_path = table_dir / "case_status.md"
    headers = [
        "case_label",
        "result_mph_exists",
        "metrics_json_exists",
        "time_series_csv_exists",
        "postprocess_completed",
        "image_export_completed",
        "image_png_count",
        "expected_image_png_count",
        "legacy_cooper_image_png_count",
    ]
    lines = [
        f"# {stage} Case Status",
        "",
        "This table includes requested cases even when metrics/time-series are still missing.",
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tables(stage: str, rows: list[dict[str, object]], table_dir: Path) -> None:
    table_dir.mkdir(parents=True, exist_ok=True)
    csv_path = table_dir / "review_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    headers = [
        "case_label",
        "configured_dynamic_motion_mode",
        "configured_review_time_s",
        "result_mph_exists",
        "metrics_json_exists",
        "postprocess_completed",
        "image_export_completed",
        "last_output_time_s",
        "expected_dynamic_end_time_s",
        "solve_reached_review_time",
        "solve_reached_expected_end",
        "glandular_fraction_pct",
        "review_avg_displacement_mm",
        "review_max_displacement_mm",
        "review_surface_signed_w_mean_mm",
        "review_surface_signed_w_from_dynamic_start_mm",
        "review_surface_signed_w_relative_to_support_mm",
        "review_surface_disp_mag_mean_mm",
        "review_breast_vm_avg_kpa",
        "review_breast_vm_max_kpa",
        "review_gland_vm_avg_kpa",
        "review_gland_vm_max_kpa",
        "review_adipose_vm_avg_kpa",
        "review_adipose_vm_max_kpa",
    ]
    md_path = table_dir / "review_metrics.md"
    lines = [
        f"# {stage} Review Metrics",
        "",
        "All values are extracted from existing COMSOL outputs at the case-specific review time.",
        "Blank cells mean that the metric was not exported for that run.",
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        cells = []
        for header in headers:
            value = row.get(header)
            if isinstance(value, float):
                cells.append(f"{value:.3f}")
            elif value is None:
                cells.append("")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary_headers = [
        "case_label",
        "last_output_time_s",
        "solve_reached_expected_end",
        "breast_volume_ml",
        "glandular_fraction_pct",
        "review_avg_displacement_mm",
        "review_surface_signed_w_from_dynamic_start_mm",
        "review_nipple_w_from_dynamic_start_mm",
        "review_breast_vm_avg_kpa",
        "review_breast_vm_max_kpa",
        "review_gland_vm_avg_kpa",
        "review_adipose_vm_avg_kpa",
    ]
    summary_csv_path = table_dir / "summary_results.csv"
    with summary_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in summary_headers})

    summary_md_path = table_dir / "summary_results.md"
    summary_lines = [
        f"# {stage} Summary Results",
        "",
        "Compact report table for quick cross-case comparison. Values are taken at the case-specific review time unless noted.",
        "",
        "| " + " | ".join(summary_headers) + " |",
        "|" + "|".join(["---"] * len(summary_headers)) + "|",
    ]
    for row in rows:
        cells = []
        for header in summary_headers:
            value = row.get(header)
            if isinstance(value, float):
                cells.append(f"{value:.3f}")
            elif value is None:
                cells.append("")
            else:
                cells.append(str(value))
        summary_lines.append("| " + " | ".join(cells) + " |")
    summary_md_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def write_sources(cases: list[Case], stage_dir: Path) -> None:
    sources_path = stage_dir / "sources.csv"
    with sources_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_key",
                "label",
                "output_dir",
                "metrics_json",
                "time_series_csv",
                "surface_displacement_csv",
                "landmark_displacement_csv",
                "tissue_stress_stats_csv",
                "available_time_series_columns",
                "available_metric_keys",
            ],
        )
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_key": case.key,
                    "label": case.label,
                    "output_dir": case.output_dir.relative_to(ROOT).as_posix(),
                    "metrics_json": case.metrics_path.relative_to(ROOT).as_posix(),
                    "time_series_csv": case.time_series_path.relative_to(ROOT).as_posix(),
                    "surface_displacement_csv": case.surface_displacement_path.relative_to(ROOT).as_posix() if case.surface_displacement_path else "",
                    "landmark_displacement_csv": case.landmark_displacement_path.relative_to(ROOT).as_posix() if case.landmark_displacement_path else "",
                    "tissue_stress_stats_csv": case.tissue_stress_stats_path.relative_to(ROOT).as_posix() if case.tissue_stress_stats_path else "",
                    "available_time_series_columns": ";".join(time_series_columns(case.time_series_path)),
                    "available_metric_keys": ";".join(sorted(metrics_for(case).keys())),
                }
            )


def write_readme(stage: str, cases: list[Case], stage_dir: Path, figure_paths: list[Path]) -> None:
    has_avg = any("vm_avg_pa" in time_series_columns(case.time_series_path) for case in cases)
    has_adipose = any("adipose_vm_max_pa" in time_series_columns(case.time_series_path) for case in cases)
    has_surface = any(case.surface_displacement_path for case in cases)
    has_landmarks = any(case.landmark_displacement_path for case in cases)
    has_stress_stats = any(case.tissue_stress_stats_path for case in cases)
    lines = [
        f"# COMSOL Evaluation: {stage}",
        "",
        "Generated from existing COMSOL solve outputs only. This script does not run COMSOL.",
        "",
        "## Contents",
        "",
    ]
    for path in figure_paths:
        lines.append(f"- `figures/{path.name}`")
    lines.extend(
        [
            "- `tables/review_metrics.csv`",
            "- `tables/review_metrics.md`",
            "- `tables/summary_results.csv`",
            "- `tables/summary_results.md`",
            "- `sources.csv`",
            "",
            "## Interpretation Notes",
            "",
            "- Volume displacement magnitude (`disp_avg_mm`, `disp_max_mm`) is kept as a diagnostic continuity metric.",
            "- Mean stress is plotted only when `vm_avg_pa` is present. COMSOL median stress is not exported in the current result files.",
            "- Adipose stress is plotted only when adipose stress columns are present. Missing adipose data is omitted, not set to zero.",
        ]
    )
    if has_surface:
        lines.append("- Signed surface displacement uses the COMSOL `w` component on the exported outer-skin surface CSV.")
        lines.append("- Dynamic-response plots prefer support-relative displacement when `support_*` columns exist; otherwise they fall back to dynamic-start correction as diagnostic output.")
    else:
        lines.append("- This stage has no surface displacement CSV yet; signed surface plots will appear after rerunning COMSOL postprocessing with the updated exporter.")
    if has_landmarks:
        lines.append("- Landmark plots use patch-average displacement, not a single mesh node.")
    else:
        lines.append("- This stage has no landmark displacement CSV yet.")
    if has_stress_stats:
        lines.append("- Tissue stress stats CSV is present; median/p95/p99 remain blank unless sampled-field exports are added.")
    if not has_avg:
        lines.append("- This stage has no mean stress time-series export, so stress plots are max-only hotspot indicators.")
    if not has_adipose:
        lines.append("- This stage has no adipose stress time-series export.")
    lines.extend(["", "## Source Cases", ""])
    for case in cases:
        lines.append(f"- {case.label}: `{case.output_dir.relative_to(ROOT).as_posix()}`")
    (stage_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_stage(stage: str, cases: list[Case]) -> list[dict[str, str]]:
    requested_cases = cases
    cases = [case for case in requested_cases if has_core_outputs(case)]
    skipped = [case for case in requested_cases if not has_core_outputs(case)]
    stage_dir = OUTPUT_ROOT / stage
    figure_dir = stage_dir / "figures"
    table_dir = stage_dir / "tables"
    figure_dir.mkdir(parents=True, exist_ok=True)
    write_status_table(stage, requested_cases, table_dir)
    cleanup_obsolete_figures(figure_dir)
    if skipped:
        print("Skipping cases without metrics/time-series: " + ", ".join(case.key for case in skipped))
    if not cases:
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / "README.md").write_text(
            "# COMSOL Evaluation: " + stage + "\n\nNo completed metrics/time-series outputs are available yet.\n",
            encoding="utf-8",
        )
        return []

    rows = [review_summary_row(stage, case) for case in cases]
    figure_paths = [
        plot_displacement_response(cases, figure_dir),
        plot_stress_response(cases, figure_dir),
        plot_tissue_review(cases, figure_dir),
    ]
    for optional_path in [
        plot_surface_signed_response(cases, figure_dir),
        plot_surface_displacement_statistics(cases, figure_dir),
        plot_surface_dynamic_vertical_response(cases, figure_dir),
        plot_landmark_signed_response(cases, figure_dir),
        plot_landmark_nipple_dynamic_response(cases, figure_dir),
    ]:
        if optional_path:
            figure_paths.append(optional_path)
    change_path = plot_response_change(stage, rows, figure_dir)
    if change_path:
        figure_paths.append(change_path)
    gland_path = plot_gland_fraction_response(rows, figure_dir)
    if gland_path:
        figure_paths.append(gland_path)
    contact_path = write_contact_sheet(stage, figure_paths, figure_dir)
    figure_paths.insert(0, contact_path)

    write_tables(stage, rows, table_dir)
    write_sources(cases, stage_dir)
    write_readme(stage, cases, stage_dir, figure_paths)
    print(f"Wrote {stage_dir}")
    return [
        {
            "stage": stage,
            "description": path.stem.replace("_", " "),
            "figure": path.relative_to(ROOT).as_posix(),
            "sources": (stage_dir / "sources.csv").relative_to(ROOT).as_posix(),
            "review_metrics": (table_dir / "review_metrics.csv").relative_to(ROOT).as_posix(),
        }
        for path in figure_paths
    ]


def write_root_readme() -> None:
    lines = [
        "# Clean COMSOL Evaluation Output",
        "",
        "This folder is the proposed clean replacement for the old mixed `analysis_output/figures` tree.",
        "It contains figures and tables generated from current COMSOL `*_metrics.json` and `*_time_series.csv` outputs.",
        "When available, it also consumes `*_surface_displacement.csv`, `*_landmark_displacement.csv`, and `*_tissue_stress_stats.csv`.",
        "",
        "The plot set emphasizes signed surface/landmark displacement when exported, average response metrics, and max values as hotspot indicators.",
        "Use `figure_index.md` or `figure_index.csv` to trace every generated figure to its stage source table.",
        "",
        "Stages generated:",
        "",
    ]
    for stage in STAGES:
        lines.append(f"- `{stage}`")
    (OUTPUT_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_figure_index(figure_rows: list[dict[str, str]]) -> None:
    index_csv = OUTPUT_ROOT / "figure_index.csv"
    with index_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(figure_rows[0].keys()))
        writer.writeheader()
        writer.writerows(figure_rows)

    index_md = OUTPUT_ROOT / "figure_index.md"
    md_lines = [
        "# COMSOL Figure Index",
        "",
        "All figures in this index are generated from existing COMSOL metrics/time-series outputs and optional extended COMSOL postprocess CSVs when present.",
        "",
        "| Stage | Description | Figure | Sources |",
        "| --- | --- | --- | --- |",
    ]
    for row in figure_rows:
        md_lines.append(f"| {row['stage']} | {row['description']} | `{row['figure']}` | `{row['sources']}` |")
    index_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Wrote {index_csv}")
    print(f"Wrote {index_md}")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    figure_rows: list[dict[str, str]] = []
    for stage, cases in STAGES.items():
        figure_rows.extend(run_stage(stage, cases))
    write_root_readme()
    print(f"Wrote {OUTPUT_ROOT / 'README.md'}")
    write_figure_index(figure_rows)


if __name__ == "__main__":
    main()
