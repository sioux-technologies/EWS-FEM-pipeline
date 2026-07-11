from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "tools" / "_vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

import matplotlib.pyplot as plt


OUTPUT_ROOT = ROOT / "analysis_output" / "comsol_pipeline" / "stage6_fast_tumor_screening"
RUN_ROOT = ROOT / "runs" / "comsol_runs" / "geometry_stage6" / "outputs"


@dataclass(frozen=True)
class Case:
    key: str
    label: str
    group: str
    output_dir: Path

    @property
    def metrics_path(self) -> Path | None:
        matches = sorted((self.output_dir / "solve").glob("*_metrics.json"))
        return matches[0] if matches else None


CASES = [
    Case(
        "control",
        "Control no tumor",
        "control",
        RUN_ROOT / "output_stage6_fast_tumor_control_xoffset055_025g_preview",
    ),
    Case(
        "small_central",
        "Small central 6 mm",
        "size",
        RUN_ROOT / "output_stage6_fast_tumor_small_central_xoffset055_025g_preview",
    ),
    Case(
        "medium_central",
        "Medium central 12 mm",
        "size",
        RUN_ROOT / "output_stage6_fast_tumor_medium_central_xoffset055_025g_preview",
    ),
    Case(
        "large_central",
        "Large central 20 mm",
        "size",
        RUN_ROOT / "output_stage6_fast_tumor_large_central_xoffset055_025g_preview",
    ),
    Case(
        "small_upper_outer",
        "Small upper outer 6 mm",
        "location",
        RUN_ROOT / "output_stage6_fast_tumor_small_upper_outer_xoffset055_025g_preview",
    ),
    Case(
        "small_subareolar",
        "Small subareolar 6 mm",
        "location",
        RUN_ROOT / "output_stage6_fast_tumor_small_subareolar_xoffset055_025g_preview",
    ),
    Case(
        "small_posterior",
        "Small posterior 6 mm",
        "location",
        RUN_ROOT / "output_stage6_fast_tumor_small_posterior_xoffset055_025g_preview",
    ),
]


def finite_float(value: Any, default: float = math.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def metric_mm(metrics: dict[str, Any], key: str) -> float:
    return 1000.0 * finite_float(metrics.get(key))


def metric_kpa(metrics: dict[str, Any], key: str) -> float:
    return finite_float(metrics.get(key)) / 1000.0


def load_case(case: Case) -> dict[str, Any]:
    metrics_path = case.metrics_path
    if metrics_path is None:
        return {
            "key": case.key,
            "label": case.label,
            "group": case.group,
            "status": "missing_metrics",
        }
    with metrics_path.open("r", encoding="utf-8") as handle:
        metrics = json.load(handle)

    series_length = int(finite_float(metrics.get("series_length"), 0.0))
    tumor_pos = metrics.get("tumor_position_m") or [math.nan, math.nan, math.nan]
    status = "ok"
    if series_length <= 0 or not math.isfinite(finite_float(metrics.get("review_max_displacement_breast"))):
        status = "invalid_or_failed_solve"

    row = {
        "key": case.key,
        "label": case.label,
        "group": case.group,
        "status": status,
        "metrics_path": str(metrics_path),
        "tumor_enabled": metrics.get("tumor_enabled"),
        "tumor_diameter_mm": finite_float(metrics.get("tumor_diameter_mm")),
        "tumor_radius_m": finite_float(metrics.get("tumor_radius_m")),
        "tumor_x_m": finite_float(tumor_pos[0] if len(tumor_pos) > 0 else math.nan),
        "tumor_y_m": finite_float(tumor_pos[1] if len(tumor_pos) > 1 else math.nan),
        "tumor_z_m": finite_float(tumor_pos[2] if len(tumor_pos) > 2 else math.nan),
        "nominal_tumor_volume_ml": 1_000_000.0 * finite_float(metrics.get("tumor_nominal_sphere_volume")),
        "tumor_mask_volume_ml": 1_000_000.0 * finite_float(metrics.get("tumor_volume")),
        "series_length": series_length,
        "review_time_s": finite_float(metrics.get("review_time_s")),
        "review_max_displacement_breast_mm": metric_mm(metrics, "review_max_displacement_breast"),
        "review_avg_displacement_breast_mm": metric_mm(metrics, "review_avg_displacement_breast"),
        "review_max_displacement_tumor_mm": metric_mm(metrics, "review_max_displacement_tumor"),
        "review_avg_displacement_tumor_mm": metric_mm(metrics, "review_avg_displacement_tumor"),
        "review_surface_signed_w_mean_mm": metric_mm(metrics, "review_surface_signed_w_mean"),
        "review_surface_signed_w_min_mm": metric_mm(metrics, "review_surface_signed_w_min"),
        "review_surface_signed_w_max_mm": metric_mm(metrics, "review_surface_signed_w_max"),
        "nipple_review_w_mean_mm": metric_mm(metrics, "landmark_nipple_review_w_mean"),
        "nipple_review_disp_mean_mm": metric_mm(metrics, "landmark_nipple_review_disp_mean"),
        "review_max_von_mises_breast_kpa": metric_kpa(metrics, "review_max_von_mises_breast"),
        "review_avg_von_mises_breast_kpa": metric_kpa(metrics, "review_avg_von_mises_breast"),
        "review_max_von_mises_tumor_kpa": metric_kpa(metrics, "review_max_von_mises_tumor"),
        "review_avg_von_mises_tumor_kpa": metric_kpa(metrics, "review_avg_von_mises_tumor"),
    }
    return row


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    columns = [
        "label",
        "status",
        "tumor_diameter_mm",
        "nominal_tumor_volume_ml",
        "tumor_mask_volume_ml",
        "review_avg_displacement_breast_mm",
        "review_avg_displacement_tumor_mm",
        "review_surface_signed_w_mean_mm",
        "nipple_review_w_mean_mm",
        "review_avg_von_mises_tumor_kpa",
    ]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# Stage 6 fast tumor screening summary\n\n")
        handle.write("| " + " | ".join(columns) + " |\n")
        handle.write("| " + " | ".join(["---"] * len(columns)) + " |\n")
        for row in rows:
            values = []
            for column in columns:
                value = row.get(column, "")
                if isinstance(value, float):
                    values.append("nan" if not math.isfinite(value) else f"{value:.4g}")
                else:
                    values.append(str(value))
            handle.write("| " + " | ".join(values) + " |\n")
        handle.write("\n")
        handle.write("Interpretation note: fast runs are screening diagnostics only. Use them to choose report-ready order-2 reruns, not as final Stage 6 claims.\n")


def plot_bar(rows: list[dict[str, Any]], key: str, ylabel: str, path: Path) -> None:
    valid = [row for row in rows if row.get("status") == "ok" and math.isfinite(finite_float(row.get(key)))]
    if not valid:
        return
    labels = [row["label"].replace(" ", "\n") for row in valid]
    values = [finite_float(row[key]) for row in valid]
    fig, ax = plt.subplots(figsize=(max(7.0, 0.9 * len(valid)), 4.4))
    ax.bar(labels, values, color="#4f7cac")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=0)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_size_sweep(rows: list[dict[str, Any]], path: Path) -> None:
    valid = [
        row
        for row in rows
        if row.get("group") in {"control", "size"}
        and row.get("status") == "ok"
        and math.isfinite(finite_float(row.get("tumor_diameter_mm")))
    ]
    if len(valid) < 2:
        return
    valid.sort(key=lambda row: finite_float(row.get("tumor_diameter_mm")))
    x = [finite_float(row["tumor_diameter_mm"]) for row in valid]
    breast = [finite_float(row["review_avg_displacement_breast_mm"]) for row in valid]
    tumor = [finite_float(row["review_avg_displacement_tumor_mm"]) for row in valid]
    stress = [finite_float(row["review_avg_von_mises_tumor_kpa"]) for row in valid]

    fig, ax1 = plt.subplots(figsize=(6.8, 4.4))
    ax1.plot(x, breast, marker="o", label="Breast avg disp")
    ax1.plot(x, tumor, marker="o", label="Tumor avg disp")
    ax1.set_xlabel("Tumor diameter (mm)")
    ax1.set_ylabel("Displacement (mm)")
    ax1.grid(alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(x, stress, marker="s", color="#c4513b", label="Tumor avg VM")
    ax2.set_ylabel("Tumor avg von Mises (kPa)")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    table_dir = OUTPUT_ROOT / "tables"
    plot_dir = OUTPUT_ROOT / "plots"
    table_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)

    rows = [load_case(case) for case in CASES]
    write_csv(rows, table_dir / "summary_results.csv")
    write_markdown(rows, table_dir / "summary_results.md")

    plot_bar(rows, "review_avg_displacement_breast_mm", "Review avg breast displacement (mm)", plot_dir / "avg_breast_displacement.png")
    plot_bar(rows, "review_avg_displacement_tumor_mm", "Review avg tumor-region displacement (mm)", plot_dir / "avg_tumor_displacement.png")
    plot_bar(rows, "review_surface_signed_w_mean_mm", "Review mean signed surface w (mm)", plot_dir / "signed_surface_w_mean.png")
    plot_bar(rows, "nipple_review_w_mean_mm", "Review nipple signed w (mm)", plot_dir / "nipple_signed_w.png")
    plot_bar(rows, "review_avg_von_mises_tumor_kpa", "Review avg tumor-region von Mises (kPa)", plot_dir / "avg_tumor_von_mises.png")
    plot_size_sweep(rows, plot_dir / "central_size_sweep.png")

    status_path = OUTPUT_ROOT / "README.md"
    invalid = [row for row in rows if row.get("status") != "ok"]
    with status_path.open("w", encoding="utf-8") as handle:
        handle.write("# Stage 6 fast tumor screening evaluation\n\n")
        handle.write(f"- Cases read: {len(rows)}\n")
        handle.write(f"- Valid cases: {len(rows) - len(invalid)}\n")
        handle.write(f"- Invalid/missing cases: {len(invalid)}\n")
        handle.write("- Tables: `tables/summary_results.csv`, `tables/summary_results.md`\n")
        handle.write("- Plots: `plots/`\n\n")
        if invalid:
            handle.write("## Invalid Or Missing Cases\n\n")
            for row in invalid:
                handle.write(f"- {row.get('label')}: {row.get('status')}\n")
            handle.write("\nThese cases should not be interpreted until rerun/postprocessed successfully.\n")

    print(f"Wrote Stage 6 fast tumor evaluation to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
