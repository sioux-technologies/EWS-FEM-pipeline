"""Rebuild compact comparison tables/plots from manual COMSOL CSV exports.

Manual COMSOL post-processing should store one case per folder under:
analysis_output/comsol_pipeline/manual_postprocess/tables/<case_id>/

Expected per-case files:
- <case_id>_avg_timeseries.csv with time_s, avg_displacement_mm, avg_vm_kpa
- <case_id>_max_timeseries.csv with time_s, max_displacement_mm, max_vm_kpa

The script also accepts direct COMSOL table exports named:
- <case_id>_average.csv
- <case_id>_max.csv

Those exports may contain leading "%" metadata lines and COMSOL headers such as
"Time (s)", "Displacement magnitude (mm)", and "von Mises stress (N/m^2)".
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = ROOT / "analysis_output" / "comsol_pipeline" / "manual_postprocess" / "tables"
FIGURES_DIR = ROOT / "analysis_output" / "comsol_pipeline" / "manual_postprocess" / "comparison_figures"
REPORT_FIGURES_DIR = (
    ROOT
    / "docs"
    / "Traineeship_report___Daan_Kuijpers"
    / "Figures"
    / "stage5_manual_postprocess"
)


LABELS = {
    "stage5_no_skin_100g": "No skin 1.00g",
    "stage5_no_skin_125g": "No skin 1.25g",
    "stage5_volumetric_skin_125g": "Volumetric skin 1.25g",
    "stage5_volumetric_skin_soft_interior_125g": "Vol. skin + soft interior 1.25g",
    "full_gland_088kPa": "Vol. skin 88 kPa + soft interior 1.25g",
    "01mm_skin_soft_interior": "0.1 mm soft skin + soft interior 1.25g",
    "stage5_volumetric_skin_soft_febio_materials_125g": "Vol. skin + soft FEBio materials 1.25g",
    "stage6_tumor_large_central_xoffset055_125g_volumetric_skin_soft_interior_solve": "Large central tumor",
    "stage6_tumor_large_central_hard100kPa": "Large central tumor hard 100 kPa",
    "stage6_tumor_medium_upper_outer_surface_proximal_xoffset055_125g_volumetric_skin_soft_interior_solve": "Medium upper-outer tumor",
    "stage6_tumor_medium_upper_outer_surface": "Medium upper-outer tumor surface",
}


CASE_ORDER = [
    "stage5_no_skin_100g",
    "stage5_no_skin_125g",
    "stage5_volumetric_skin_125g",
    "stage5_volumetric_skin_soft_interior_125g",
    "full_gland_088kPa",
    "01mm_skin_soft_interior",
    "stage5_volumetric_skin_soft_febio_materials_125g",
    "stage6_tumor_medium_upper_outer_surface_proximal_xoffset055_125g_volumetric_skin_soft_interior_solve",
    "stage6_tumor_large_central_xoffset055_125g_volumetric_skin_soft_interior_solve",
    "stage6_tumor_large_central_hard100kPa",
    "stage6_tumor_medium_upper_outer_surface",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_comsol_csv(path: Path, kind: str) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        lines: list[str] = []
        for line in handle:
            stripped = line.lstrip()
            if stripped.startswith("% Time"):
                lines.append(stripped.lstrip("%").lstrip())
            elif not stripped.startswith("%"):
                lines.append(line)
    if not lines:
        return []
    delimiter = "\t" if "\t" in lines[0] else ","
    rows = list(csv.DictReader(lines, delimiter=delimiter))
    normalized: list[dict[str, str]] = []
    for row in rows:
        time_s = row.get("time_s") or row.get("Time (s)")
        disp_mm = row.get("avg_displacement_mm") or row.get("max_displacement_mm") or row.get("Displacement magnitude (mm)")
        disp_m = row.get("Displacement magnitude (m)")
        vm = row.get("avg_vm_kpa") or row.get("max_vm_kpa") or row.get("von Mises stress (N/m^2)")
        if time_s is None or (disp_mm is None and disp_m is None) or vm is None:
            continue
        disp_value_mm = float(str(disp_mm if disp_mm is not None else disp_m).replace(",", "."))
        if disp_m is not None and disp_mm is None:
            disp_value_mm *= 1000.0
        vm_kpa = float(str(vm).replace(",", ".")) / 1000.0 if "von Mises stress (N/m^2)" in row else float(str(vm).replace(",", "."))
        if kind == "avg":
            normalized.append(
                {
                    "time_s": str(time_s),
                    "avg_displacement_mm": f"{disp_value_mm:.12g}",
                    "avg_vm_kpa": f"{vm_kpa:.12g}",
                }
            )
        else:
            normalized.append(
                {
                    "time_s": str(time_s),
                    "max_displacement_mm": f"{disp_value_mm:.12g}",
                    "max_vm_kpa": f"{vm_kpa:.12g}",
                }
            )
    return normalized


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _as_float(row: dict[str, str], key: str) -> float:
    return float(str(row[key]).replace(",", "."))


def _peak(rows: list[dict[str, str]], value_key: str) -> tuple[float, float]:
    best = max(rows, key=lambda row: _as_float(row, value_key))
    return _as_float(best, value_key), _as_float(best, "time_s")


def _available_cases(tables_dir: Path) -> list[str]:
    case_ids = [path.name for path in tables_dir.iterdir() if path.is_dir()]
    ordered = [case_id for case_id in CASE_ORDER if case_id in case_ids]
    ordered.extend(sorted(case_id for case_id in case_ids if case_id not in CASE_ORDER))
    return ordered


def _case_csv_path(case_dir: Path, case_id: str, kind: str) -> Path | None:
    candidates = (
        [case_dir / f"{case_id}_avg_timeseries.csv", case_dir / f"{case_id}_average.csv", case_dir / f"{case_id}_avg.csv"]
        if kind == "avg"
        else [case_dir / f"{case_id}_max_timeseries.csv", case_dir / f"{case_id}_max.csv"]
    )
    for path in candidates:
        if path.exists():
            return path
    return None


def _read_case_rows(path: Path, kind: str) -> list[dict[str, str]]:
    if path.name.endswith("_average.csv") or path.name.endswith("_avg.csv") or path.name.endswith("_max.csv"):
        return _read_comsol_csv(path, kind)
    return _read_csv(path)


def rebuild_tables(tables_dir: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    summary_rows: list[dict[str, object]] = []
    max_long_rows: list[dict[str, object]] = []
    avg_long_rows: list[dict[str, object]] = []

    for case_id in _available_cases(tables_dir):
        case_dir = tables_dir / case_id
        avg_path = _case_csv_path(case_dir, case_id, "avg")
        max_path = _case_csv_path(case_dir, case_id, "max")
        if avg_path is None and max_path is None:
            print(f"[manual postprocess] skip incomplete case: {case_id}")
            continue
        if avg_path is None:
            print(f"[manual postprocess] skip incomplete case: {case_id}")
            continue

        avg_rows = _read_case_rows(avg_path, "avg")
        max_rows = _read_case_rows(max_path, "max") if max_path is not None else []
        if not avg_rows:
            print(f"[manual postprocess] skip empty case: {case_id}")
            continue

        peak_max_disp, peak_max_disp_time = _peak(max_rows, "max_displacement_mm") if max_rows else (float("nan"), float("nan"))
        peak_max_vm, peak_max_vm_time = _peak(max_rows, "max_vm_kpa") if max_rows else (float("nan"), float("nan"))
        peak_avg_disp, peak_avg_disp_time = _peak(avg_rows, "avg_displacement_mm")
        peak_avg_vm, peak_avg_vm_time = _peak(avg_rows, "avg_vm_kpa")

        summary_rows.append(
            {
                "case_id": case_id,
                "label": LABELS.get(case_id, case_id),
                "peak_max_displacement_mm": "" if max_rows == [] else f"{peak_max_disp:.6f}",
                "peak_max_displacement_time_s": "" if max_rows == [] else f"{peak_max_disp_time:.6g}",
                "peak_avg_displacement_mm": f"{peak_avg_disp:.6f}",
                "peak_avg_displacement_time_s": f"{peak_avg_disp_time:.6g}",
                "peak_max_vm_kpa": "" if max_rows == [] else f"{peak_max_vm:.6f}",
                "peak_max_vm_time_s": "" if max_rows == [] else f"{peak_max_vm_time:.6g}",
                "peak_avg_vm_kpa": f"{peak_avg_vm:.6f}",
                "peak_avg_vm_time_s": f"{peak_avg_vm_time:.6g}",
            }
        )

        for row in max_rows:
            max_long_rows.append(
                {
                    "case_id": case_id,
                    "time_s": row["time_s"],
                    "max_displacement_mm": row["max_displacement_mm"],
                    "max_vm_kpa": row["max_vm_kpa"],
                }
            )
        for row in avg_rows:
            avg_long_rows.append(
                {
                    "case_id": case_id,
                    "time_s": row["time_s"],
                    "avg_displacement_mm": row["avg_displacement_mm"],
                    "avg_vm_kpa": row["avg_vm_kpa"],
                }
            )

    return summary_rows, max_long_rows, avg_long_rows


def write_outputs(tables_dir: Path, summary_rows: list[dict[str, object]], max_rows: list[dict[str, object]], avg_rows: list[dict[str, object]]) -> None:
    _write_csv(
        tables_dir / "manual_postprocess_summary.csv",
        summary_rows,
        [
            "case_id",
            "label",
            "peak_max_displacement_mm",
            "peak_max_displacement_time_s",
            "peak_avg_displacement_mm",
            "peak_avg_displacement_time_s",
            "peak_max_vm_kpa",
            "peak_max_vm_time_s",
            "peak_avg_vm_kpa",
            "peak_avg_vm_time_s",
        ],
    )
    _write_csv(
        tables_dir / "stage5_manual_postprocess_summary.csv",
        summary_rows,
        [
            "case_id",
            "label",
            "peak_max_displacement_mm",
            "peak_max_displacement_time_s",
            "peak_avg_displacement_mm",
            "peak_avg_displacement_time_s",
            "peak_max_vm_kpa",
            "peak_max_vm_time_s",
            "peak_avg_vm_kpa",
            "peak_avg_vm_time_s",
        ],
    )
    _write_csv(
        tables_dir / "manual_avg_timeseries_long.csv",
        avg_rows,
        ["case_id", "time_s", "avg_displacement_mm", "avg_vm_kpa"],
    )
    _write_csv(
        tables_dir / "manual_max_timeseries_long.csv",
        max_rows,
        ["case_id", "time_s", "max_displacement_mm", "max_vm_kpa"],
    )
    _write_csv(
        tables_dir / "stage5_manual_max_timeseries_long.csv",
        max_rows,
        ["case_id", "time_s", "max_displacement_mm", "max_vm_kpa"],
    )
    _write_csv(
        tables_dir / "stage5_manual_avg_timeseries_long.csv",
        avg_rows,
        ["case_id", "time_s", "avg_displacement_mm", "avg_vm_kpa"],
    )


def _case_color(index: int) -> str:
    colors = ["#2f78b7", "#39a34a", "#d85a2a", "#7b5ab6", "#7a7a7a", "#c27c0e"]
    return colors[index % len(colors)]


def write_plots(summary_rows: list[dict[str, object]], max_rows: list[dict[str, object]], figures_dir: Path, report_figures_dir: Path | None) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    labels = [str(row["label"]) for row in summary_rows]
    colors = [_case_color(index) for index, _ in enumerate(summary_rows)]

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    for ax, key, title in [
        (axes[0], "peak_max_displacement_mm", "Peak max displacement (mm)"),
        (axes[1], "peak_max_vm_kpa", "Peak max VM stress (kPa)"),
    ]:
        plot_rows = [row for row in summary_rows if str(row[key]) not in {"", "nan"}]
        values = [float(row[key]) for row in plot_rows]
        plot_labels = [str(row["label"]) for row in plot_rows]
        x_values = list(range(len(values)))
        ax.bar(x_values, values, color=[_case_color(index) for index, _ in enumerate(plot_rows)], width=0.65)
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_xticks(x_values)
        ax.set_xticklabels(plot_labels, rotation=30, ha="right", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.2)
        limit = max(values) * 1.18 if values else 1.0
        ax.set_ylim(0, limit)
        for x, value in zip(x_values, values):
            ax.text(x, value + limit * 0.02, f"{value:.2f}", ha="center", va="bottom", fontsize=9)
    fig.suptitle("Stage 5 manual postprocess comparison", x=0.04, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    peak_plot = figures_dir / "stage5_manual_peak_comparison.png"
    fig.savefig(peak_plot, dpi=180)
    plt.close(fig)

    rows_by_case: dict[str, list[dict[str, object]]] = {}
    for row in max_rows:
        rows_by_case.setdefault(str(row["case_id"]), []).append(row)

    fig, ax = plt.subplots(figsize=(12, 6))
    for index, summary in enumerate(summary_rows):
        case_id = str(summary["case_id"])
        rows = sorted(rows_by_case.get(case_id, []), key=lambda row: float(row["time_s"]))
        if not rows:
            continue
        ax.plot(
            [float(row["time_s"]) for row in rows],
            [float(row["max_displacement_mm"]) for row in rows],
            lw=2.2,
            color=_case_color(index),
            label=str(summary["label"]),
        )
    ax.set_title("Stage 5 max displacement time series", loc="left", fontsize=16, fontweight="bold")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Max displacement (mm)")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    timeseries_plot = figures_dir / "stage5_manual_max_displacement_timeseries.png"
    fig.savefig(timeseries_plot, dpi=180)
    plt.close(fig)

    if report_figures_dir is not None:
        report_figures_dir.mkdir(parents=True, exist_ok=True)
        for source in [peak_plot, timeseries_plot]:
            target = report_figures_dir / source.name
            target.write_bytes(source.read_bytes())

    avg_rows_path = TABLES_DIR / "manual_avg_timeseries_long.csv"
    if avg_rows_path.exists():
        avg_rows = _read_csv(avg_rows_path)
        _write_stage6_comparison_plots(summary_rows, max_rows, avg_rows, figures_dir)


def _rows_by_case(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["case_id"]), []).append(row)
    return grouped


def _write_stage6_comparison_plots(
    summary_rows: list[dict[str, object]],
    max_rows: list[dict[str, object]],
    avg_rows: list[dict[str, object]],
    figures_dir: Path,
) -> None:
    baseline = "stage5_volumetric_skin_soft_interior_125g"
    tumor_cases = [
        "stage6_tumor_medium_upper_outer_surface_proximal_xoffset055_125g_volumetric_skin_soft_interior_solve",
        "stage6_tumor_large_central_xoffset055_125g_volumetric_skin_soft_interior_solve",
        "stage6_tumor_large_central_hard100kPa",
    ]
    compare_cases = [baseline] + [case for case in tumor_cases if any(str(row["case_id"]) == case for row in summary_rows)]
    if len(compare_cases) < 2:
        return

    summary_by_case = {str(row["case_id"]): row for row in summary_rows}
    avg_by_case = _rows_by_case(avg_rows)
    max_by_case = _rows_by_case(max_rows)

    fig, ax = plt.subplots(figsize=(11, 6))
    for index, case_id in enumerate(compare_cases):
        rows = sorted(avg_by_case.get(case_id, []), key=lambda row: float(row["time_s"]))
        if not rows:
            continue
        ax.plot(
            [float(row["time_s"]) for row in rows],
            [float(row["avg_displacement_mm"]) for row in rows],
            lw=2.3,
            color=_case_color(index),
            label=LABELS.get(case_id, case_id),
        )
    ax.set_title("Stage 6 tumor comparison: average breast displacement", loc="left", fontsize=15, fontweight="bold")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Average displacement (mm)")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(figures_dir / "stage6_tumor_avg_displacement_timeseries.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6))
    for index, case_id in enumerate(compare_cases):
        rows = sorted(avg_by_case.get(case_id, []), key=lambda row: float(row["time_s"]))
        if not rows:
            continue
        ax.plot(
            [float(row["time_s"]) for row in rows],
            [float(row["avg_vm_kpa"]) for row in rows],
            lw=2.3,
            color=_case_color(index),
            label=LABELS.get(case_id, case_id),
        )
    ax.set_title("Stage 6 tumor comparison: average VM stress", loc="left", fontsize=15, fontweight="bold")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Average VM stress (kPa)")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(figures_dir / "stage6_tumor_avg_vm_timeseries.png", dpi=180)
    plt.close(fig)

    baseline_avg_rows = sorted(avg_by_case.get(baseline, []), key=lambda row: float(row["time_s"]))
    baseline_by_time = {float(row["time_s"]): row for row in baseline_avg_rows}
    for value_key, ylabel, filename, title in [
        ("avg_displacement_mm", "Delta average displacement vs baseline (mm)", "stage6_tumor_delta_avg_displacement.png", "Stage 6 tumor effect: average displacement difference"),
        ("avg_vm_kpa", "Delta average VM stress vs baseline (kPa)", "stage6_tumor_delta_avg_vm.png", "Stage 6 tumor effect: average VM stress difference"),
    ]:
        fig, ax = plt.subplots(figsize=(11, 6))
        for index, case_id in enumerate(tumor_cases, start=1):
            rows = sorted(avg_by_case.get(case_id, []), key=lambda row: float(row["time_s"]))
            if not rows:
                continue
            xs: list[float] = []
            ys: list[float] = []
            for row in rows:
                time_s = float(row["time_s"])
                base_row = baseline_by_time.get(time_s)
                if base_row is None:
                    continue
                xs.append(time_s)
                ys.append(float(row[value_key]) - float(base_row[value_key]))
            ax.plot(xs, ys, lw=2.3, color=_case_color(index), label=LABELS.get(case_id, case_id))
        ax.axhline(0.0, color="#444444", lw=1.0)
        ax.set_title(title, loc="left", fontsize=15, fontweight="bold")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(figures_dir / filename, dpi=180)
        plt.close(fig)

    for case_id in tumor_cases:
        rows = sorted(avg_by_case.get(case_id, []), key=lambda row: float(row["time_s"]))
        if not rows:
            continue
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        axes[0].plot([float(row["time_s"]) for row in rows], [float(row["avg_displacement_mm"]) for row in rows], lw=2.2, color="#2f78b7")
        axes[0].set_title("Average displacement", loc="left")
        axes[0].set_xlabel("Time (s)")
        axes[0].set_ylabel("mm")
        axes[1].plot([float(row["time_s"]) for row in rows], [float(row["avg_vm_kpa"]) for row in rows], lw=2.2, color="#d85a2a")
        axes[1].set_title("Average VM stress", loc="left")
        axes[1].set_xlabel("Time (s)")
        axes[1].set_ylabel("kPa")
        for ax in axes:
            ax.grid(alpha=0.25)
            ax.spines[["top", "right"]].set_visible(False)
        fig.suptitle(LABELS.get(case_id, case_id), x=0.04, ha="left", fontsize=14, fontweight="bold")
        fig.tight_layout(rect=[0, 0, 1, 0.9])
        fig.savefig(figures_dir / f"{case_id}_individual_avg_plots.png", dpi=180)
        plt.close(fig)

    complete_max_cases = [case_id for case_id in compare_cases if max_by_case.get(case_id)]
    if len(complete_max_cases) >= 2:
        fig, ax = plt.subplots(figsize=(11, 6))
        for index, case_id in enumerate(complete_max_cases):
            rows = sorted(max_by_case.get(case_id, []), key=lambda row: float(row["time_s"]))
            ax.plot(
                [float(row["time_s"]) for row in rows],
                [float(row["max_displacement_mm"]) for row in rows],
                lw=2.3,
                color=_case_color(index),
                label=LABELS.get(case_id, case_id),
            )
        ax.set_title("Stage 6 tumor comparison: maximum displacement", loc="left", fontsize=15, fontweight="bold")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Maximum displacement (mm)")
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(figures_dir / "stage6_tumor_max_displacement_timeseries.png", dpi=180)
        plt.close(fig)

    peak_rows = [summary_by_case[case] for case in compare_cases if case in summary_by_case]
    metrics = [
        ("peak_avg_displacement_mm", "Peak average displacement (mm)", "stage6_tumor_peak_avg_displacement.png"),
        ("peak_avg_vm_kpa", "Peak average VM stress (kPa)", "stage6_tumor_peak_avg_vm.png"),
    ]
    for key, title, filename in metrics:
        fig, ax = plt.subplots(figsize=(9, 5))
        values = [float(row[key]) for row in peak_rows]
        labels = [str(row["label"]) for row in peak_rows]
        x_values = list(range(len(values)))
        ax.bar(x_values, values, color=[_case_color(i) for i in x_values], width=0.6)
        ax.set_title(title, loc="left", fontsize=14, fontweight="bold")
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.grid(axis="y", alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
        limit = max(values) * 1.18 if values else 1.0
        ax.set_ylim(0, limit)
        for x, value in zip(x_values, values):
            ax.text(x, value + limit * 0.02, f"{value:.3g}", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()
        fig.savefig(figures_dir / filename, dpi=180)
        plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables-dir", type=Path, default=TABLES_DIR)
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR)
    parser.add_argument(
        "--no-report-copy",
        action="store_true",
        help="Do not copy the generated PNG figures into the traineeship report figure folder.",
    )
    args = parser.parse_args()

    summary_rows, max_rows, avg_rows = rebuild_tables(args.tables_dir)
    if not summary_rows:
        raise SystemExit(f"No complete manual postprocess cases found in {args.tables_dir}")
    write_outputs(args.tables_dir, summary_rows, max_rows, avg_rows)
    write_plots(
        summary_rows,
        max_rows,
        args.figures_dir,
        None if args.no_report_copy else REPORT_FIGURES_DIR,
    )
    print(f"[manual postprocess] wrote {len(summary_rows)} cases")
    print(f"[manual postprocess] tables: {args.tables_dir}")
    print(f"[manual postprocess] figures: {args.figures_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
