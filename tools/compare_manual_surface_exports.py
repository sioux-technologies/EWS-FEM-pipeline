"""Compare two COMSOL outer-surface manual export CSV files.

The script is intended for manually exported COMSOL `Export > Data` tables
containing x/y/z, u/v/w, solid.disp and solid.mises for all time points.
It writes time-series delta summaries and a few report-ready diagnostic plots.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


COLUMN_RE = re.compile(
    r"^(?P<var>x|y|z|u|v|w|solid\.disp|solid\.mises) \([^)]*\) @ t=(?P<t>[0-9.Ee+\-]+)$"
)


def _read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for line in handle:
            if line.startswith("% X,"):
                return next(csv.reader([line[1:].strip()]))
    raise RuntimeError(f"No COMSOL export header found in {path}")


def _load_matrix(path: Path) -> np.ndarray:
    return np.genfromtxt(path, delimiter=",", comments="%", dtype=np.float64)


def _parse_time_columns(header: list[str]) -> dict[float, dict[str, int]]:
    columns: dict[float, dict[str, int]] = {}
    for idx, name in enumerate(header):
        if idx < 3:
            continue
        match = COLUMN_RE.match(name.strip())
        if not match:
            continue
        time_s = round(float(match.group("t")), 10)
        columns.setdefault(time_s, {})[match.group("var")] = idx
    required = {"x", "y", "z", "u", "v", "w", "solid.disp", "solid.mises"}
    return {time_s: cols for time_s, cols in columns.items() if required.issubset(cols)}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _plot_lines(out_path: Path, title: str, ylabel: str, time: np.ndarray, series: list[tuple[str, list[float]]]) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, values in series:
        ax.plot(time, values, label=label, linewidth=1.8)
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _scatter_delta(
    out_path: Path,
    title: str,
    colorbar_label: str,
    x_m: np.ndarray,
    z_m: np.ndarray,
    values: np.ndarray,
) -> None:
    limit = float(np.nanpercentile(np.abs(values), 99))
    if not np.isfinite(limit) or limit == 0.0:
        limit = float(np.nanmax(np.abs(values))) or 1e-12
    fig, ax = plt.subplots(figsize=(7, 7))
    scatter = ax.scatter(
        x_m * 1000.0,
        z_m * 1000.0,
        c=values,
        s=7,
        cmap="coolwarm",
        vmin=-limit,
        vmax=limit,
        linewidths=0,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("z (mm)")
    ax.set_title(title)
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.82)
    cbar.set_label(colorbar_label)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def compare_exports(control_csv: Path, test_csv: Path, out_dir: Path, label: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    control_header = _read_header(control_csv)
    test_header = _read_header(test_csv)
    if control_header != test_header:
        raise RuntimeError("CSV headers differ; compare only matching COMSOL exports.")

    control = _load_matrix(control_csv)
    test = _load_matrix(test_csv)
    if control.shape != test.shape:
        raise RuntimeError(f"CSV shapes differ: {control.shape} vs {test.shape}")

    cols_by_time = _parse_time_columns(control_header)
    times = sorted(cols_by_time)
    if not times:
        raise RuntimeError("No complete time-dependent COMSOL columns found.")

    x_m, y_m, z_m = control[:, 0], control[:, 1], control[:, 2]
    coordinate_delta_m = float(np.nanmax(np.abs(control[:, :3] - test[:, :3])))
    coordinate_match_mode = "row_order"
    nearest_coordinate_distance_m = 0.0
    if coordinate_delta_m > 1e-9:
        coordinate_match_mode = "nearest_coordinate"
        # COMSOL can export the same surface nodes in a different row order.
        # Use a chunked nearest-neighbour match so pointwise deltas remain meaningful.
        control_xyz = control[:, :3]
        test_xyz = test[:, :3]
        matched_indices: list[int] = []
        matched_distances: list[float] = []
        for start in range(0, control_xyz.shape[0], 256):
            chunk = control_xyz[start : start + 256]
            deltas = chunk[:, None, :] - test_xyz[None, :, :]
            dist2 = np.sum(deltas * deltas, axis=2)
            idx = np.argmin(dist2, axis=1)
            matched_indices.extend(idx.tolist())
            matched_distances.extend(np.sqrt(dist2[np.arange(dist2.shape[0]), idx]).tolist())
        test = test[np.array(matched_indices, dtype=int), :]
        nearest_coordinate_distance_m = float(np.nanmax(matched_distances))

    rows: list[dict[str, object]] = []
    for time_s in times:
        cols = cols_by_time[time_s]
        du = (test[:, cols["u"]] - control[:, cols["u"]]) * 1000.0
        dv = (test[:, cols["v"]] - control[:, cols["v"]]) * 1000.0
        dw = (test[:, cols["w"]] - control[:, cols["w"]]) * 1000.0
        ddisp = (test[:, cols["solid.disp"]] - control[:, cols["solid.disp"]]) * 1000.0
        dvm = (test[:, cols["solid.mises"]] - control[:, cols["solid.mises"]]) / 1000.0
        dvec = np.sqrt(du * du + dv * dv + dw * dw)
        rows.append(
            {
                "time_s": time_s,
                "mean_delta_w_mm": float(np.nanmean(dw)),
                "mean_abs_delta_w_mm": float(np.nanmean(np.abs(dw))),
                "p95_abs_delta_w_mm": float(np.nanpercentile(np.abs(dw), 95)),
                "p99_abs_delta_w_mm": float(np.nanpercentile(np.abs(dw), 99)),
                "max_abs_delta_w_mm": float(np.nanmax(np.abs(dw))),
                "min_delta_w_mm": float(np.nanmin(dw)),
                "max_delta_w_mm": float(np.nanmax(dw)),
                "mean_abs_delta_disp_mag_mm": float(np.nanmean(np.abs(ddisp))),
                "p95_abs_delta_disp_mag_mm": float(np.nanpercentile(np.abs(ddisp), 95)),
                "max_abs_delta_disp_mag_mm": float(np.nanmax(np.abs(ddisp))),
                "mean_delta_vector_mm": float(np.nanmean(dvec)),
                "p95_delta_vector_mm": float(np.nanpercentile(dvec, 95)),
                "max_delta_vector_mm": float(np.nanmax(dvec)),
                "mean_abs_delta_vm_kpa": float(np.nanmean(np.abs(dvm))),
                "p95_abs_delta_vm_kpa": float(np.nanpercentile(np.abs(dvm), 95)),
                "max_abs_delta_vm_kpa": float(np.nanmax(np.abs(dvm))),
            }
        )

    _write_csv(out_dir / "surface_delta_timeseries.csv", rows)

    central_roi = np.sqrt(x_m * x_m + z_m * z_m) <= 0.025
    anterior_central_roi = central_roi & (y_m >= np.nanmedian(y_m))
    roi_rows: list[dict[str, object]] = []
    for roi_name, mask in [
        ("central_xz_radius_25mm", central_roi),
        ("central_xz_radius_25mm_anterior_half", anterior_central_roi),
    ]:
        for time_s in times:
            cols = cols_by_time[time_s]
            dw = (test[:, cols["w"]] - control[:, cols["w"]]) * 1000.0
            ddisp = (test[:, cols["solid.disp"]] - control[:, cols["solid.disp"]]) * 1000.0
            dvm = (test[:, cols["solid.mises"]] - control[:, cols["solid.mises"]]) / 1000.0
            if np.any(mask):
                roi_rows.append(
                    {
                        "roi": roi_name,
                        "time_s": time_s,
                        "n_points": int(np.sum(mask)),
                        "mean_abs_delta_w_mm": float(np.nanmean(np.abs(dw[mask]))),
                        "p95_abs_delta_w_mm": float(np.nanpercentile(np.abs(dw[mask]), 95)),
                        "max_abs_delta_w_mm": float(np.nanmax(np.abs(dw[mask]))),
                        "mean_abs_delta_disp_mag_mm": float(np.nanmean(np.abs(ddisp[mask]))),
                        "p95_abs_delta_disp_mag_mm": float(np.nanpercentile(np.abs(ddisp[mask]), 95)),
                        "max_abs_delta_disp_mag_mm": float(np.nanmax(np.abs(ddisp[mask]))),
                        "mean_abs_delta_vm_kpa": float(np.nanmean(np.abs(dvm[mask]))),
                        "p95_abs_delta_vm_kpa": float(np.nanpercentile(np.abs(dvm[mask]), 95)),
                        "max_abs_delta_vm_kpa": float(np.nanmax(np.abs(dvm[mask]))),
                    }
                )
            else:
                roi_rows.append(
                    {
                        "roi": roi_name,
                        "time_s": time_s,
                        "n_points": 0,
                        "mean_abs_delta_w_mm": math.nan,
                        "p95_abs_delta_w_mm": math.nan,
                        "max_abs_delta_w_mm": math.nan,
                        "mean_abs_delta_disp_mag_mm": math.nan,
                        "p95_abs_delta_disp_mag_mm": math.nan,
                        "max_abs_delta_disp_mag_mm": math.nan,
                        "mean_abs_delta_vm_kpa": math.nan,
                        "p95_abs_delta_vm_kpa": math.nan,
                        "max_abs_delta_vm_kpa": math.nan,
                    }
                )
    _write_csv(out_dir / "surface_delta_roi_timeseries.csv", roi_rows)

    peak_w = max(rows, key=lambda row: row["max_abs_delta_w_mm"])
    peak_disp = max(rows, key=lambda row: row["max_abs_delta_disp_mag_mm"])
    peak_vec = max(rows, key=lambda row: row["max_delta_vector_mm"])
    peak_vm = max(rows, key=lambda row: row["max_abs_delta_vm_kpa"])
    summary = [
        {
            "comparison": label,
            "control_csv": str(control_csv),
            "test_csv": str(test_csv),
            "n_surface_points": int(control.shape[0]),
            "n_timepoints": int(len(times)),
            "max_coordinate_difference_m": coordinate_delta_m,
            "coordinate_match_mode": coordinate_match_mode,
            "max_nearest_coordinate_distance_m": nearest_coordinate_distance_m,
            "peak_abs_delta_w_mm": peak_w["max_abs_delta_w_mm"],
            "peak_abs_delta_w_time_s": peak_w["time_s"],
            "peak_p95_abs_delta_w_mm_at_that_time": peak_w["p95_abs_delta_w_mm"],
            "peak_abs_delta_disp_mag_mm": peak_disp["max_abs_delta_disp_mag_mm"],
            "peak_abs_delta_disp_mag_time_s": peak_disp["time_s"],
            "peak_delta_vector_mm": peak_vec["max_delta_vector_mm"],
            "peak_delta_vector_time_s": peak_vec["time_s"],
            "peak_abs_delta_vm_kpa": peak_vm["max_abs_delta_vm_kpa"],
            "peak_abs_delta_vm_time_s": peak_vm["time_s"],
            "central_roi_points": int(np.sum(central_roi)),
            "central_anterior_roi_points": int(np.sum(anterior_central_roi)),
        }
    ]
    _write_csv(out_dir / "surface_delta_summary.csv", summary)

    time_array = np.array([row["time_s"] for row in rows])
    _plot_lines(
        out_dir / "delta_w_timeseries.png",
        "Outer-surface vertical displacement difference (tumor - control)",
        "Delta w (mm)",
        time_array,
        [
            ("mean |Delta w|", [row["mean_abs_delta_w_mm"] for row in rows]),
            ("p95 |Delta w|", [row["p95_abs_delta_w_mm"] for row in rows]),
            ("max |Delta w|", [row["max_abs_delta_w_mm"] for row in rows]),
        ],
    )
    _plot_lines(
        out_dir / "delta_disp_timeseries.png",
        "Outer-surface displacement magnitude difference (tumor - control)",
        "Delta |u| (mm)",
        time_array,
        [
            ("mean |Delta |u||", [row["mean_abs_delta_disp_mag_mm"] for row in rows]),
            ("p95 |Delta |u||", [row["p95_abs_delta_disp_mag_mm"] for row in rows]),
            ("max |Delta |u||", [row["max_abs_delta_disp_mag_mm"] for row in rows]),
        ],
    )
    _plot_lines(
        out_dir / "delta_vector_timeseries.png",
        "Outer-surface vector displacement-field difference",
        "Vector difference (mm)",
        time_array,
        [
            ("mean vector Delta", [row["mean_delta_vector_mm"] for row in rows]),
            ("p95 vector Delta", [row["p95_delta_vector_mm"] for row in rows]),
            ("max vector Delta", [row["max_delta_vector_mm"] for row in rows]),
        ],
    )
    _plot_lines(
        out_dir / "delta_vm_timeseries.png",
        "Outer-surface von Mises stress difference (tumor - control)",
        "Delta VM (kPa)",
        time_array,
        [
            ("mean |Delta VM|", [row["mean_abs_delta_vm_kpa"] for row in rows]),
            ("p95 |Delta VM|", [row["p95_abs_delta_vm_kpa"] for row in rows]),
            ("max |Delta VM|", [row["max_abs_delta_vm_kpa"] for row in rows]),
        ],
    )

    for plot_time, tag in [(float(peak_w["time_s"]), f"peak_t{float(peak_w['time_s']):.3f}")]:
        cols = cols_by_time[plot_time]
        delta_w = (test[:, cols["w"]] - control[:, cols["w"]]) * 1000.0
        delta_disp = (test[:, cols["solid.disp"]] - control[:, cols["solid.disp"]]) * 1000.0
        delta_vm = (test[:, cols["solid.mises"]] - control[:, cols["solid.mises"]]) / 1000.0
        _scatter_delta(out_dir / f"delta_w_surface_xz_{tag}.png", f"Delta w on outer surface, t={plot_time:.3f}s", "Delta w (mm)", x_m, z_m, delta_w)
        _scatter_delta(out_dir / f"delta_disp_surface_xz_{tag}.png", f"Delta displacement magnitude on outer surface, t={plot_time:.3f}s", "Delta |u| (mm)", x_m, z_m, delta_disp)
        _scatter_delta(out_dir / f"delta_vm_surface_xz_{tag}.png", f"Delta von Mises on outer surface, t={plot_time:.3f}s", "Delta VM (kPa)", x_m, z_m, delta_vm)

    print(f"Wrote: {out_dir}")
    print(f"Surface points: {control.shape[0]}; time points: {len(times)}")
    print(f"Max coordinate difference: {coordinate_delta_m:.3e} m")
    print(f"Coordinate match mode: {coordinate_match_mode}; max nearest distance: {nearest_coordinate_distance_m:.3e} m")
    print(f"Peak |Delta w|: {peak_w['max_abs_delta_w_mm']:.6g} mm at t={peak_w['time_s']}")
    print(f"Peak |Delta disp mag|: {peak_disp['max_abs_delta_disp_mag_mm']:.6g} mm at t={peak_disp['time_s']}")
    print(f"Peak vector delta: {peak_vec['max_delta_vector_mm']:.6g} mm at t={peak_vec['time_s']}")
    print(f"Peak |Delta VM|: {peak_vm['max_abs_delta_vm_kpa']:.6g} kPa at t={peak_vm['time_s']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", required=True, type=Path)
    parser.add_argument("--test", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--label", default="test_minus_control")
    args = parser.parse_args()
    compare_exports(args.control, args.test, args.out, args.label)


if __name__ == "__main__":
    main()
