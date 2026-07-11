"""Create one clean COMSOL case plot from existing postprocess CSV output."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_CASE_DIR = (
    ROOT
    / "runs"
    / "comsol_runs"
    / "geometry_stage1"
    / "outputs"
    / "output_stage1_fixed_support_acceleration_pulse_mild_025g"
)
DEFAULT_OUTPUT = (
    ROOT
    / "model_pictures"
    / "pipeline_overview"
    / "stage1_fixed_support_pulse_mild_025g_displacement_example.png"
)


def _find_one(directory: Path, suffix: str) -> Path:
    matches = sorted(directory.glob(f"*{suffix}"))
    if not matches:
        raise FileNotFoundError(f"No *{suffix} found in {directory}")
    return matches[0]


def _read_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed: dict[str, float] = {}
            for key, value in row.items():
                try:
                    parsed[key] = float(value)
                except (TypeError, ValueError):
                    continue
            rows.append(parsed)
    return rows


def _read_metrics(path: Path) -> dict[str, float | str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def make_plot(case_dir: Path, output: Path, title: str) -> None:
    solve_dir = case_dir / "solve"
    time_series = _find_one(solve_dir, "_time_series.csv")
    metrics = _read_metrics(_find_one(solve_dir, "_metrics.json"))
    rows = _read_rows(time_series)
    if not rows:
        raise ValueError(f"No rows found in {time_series}")

    time_s = [row["time_s"] for row in rows if "time_s" in row]
    disp_max = [row.get("disp_max_mm", float("nan")) for row in rows]
    disp_avg = [row.get("disp_avg_mm", float("nan")) for row in rows]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(7.2, 4.1), dpi=180)
    ax.plot(time_s, disp_max, color="#174A7C", linewidth=2.2, label="Max displacement")
    ax.plot(time_s, disp_avg, color="#C43B3B", linewidth=2.0, label="Mean displacement")

    pulse_start = metrics.get("jump_start_time_s")
    pulse_duration = metrics.get("pulse_duration_s")
    if isinstance(pulse_start, (int, float)) and isinstance(pulse_duration, (int, float)):
        ax.axvspan(
            pulse_start,
            pulse_start + pulse_duration,
            color="#E8C547",
            alpha=0.22,
            label="0.25g pulse window",
        )

    peak_time = metrics.get("time_of_peak_displacement_breast")
    if isinstance(peak_time, (int, float)):
        ax.axvline(peak_time, color="#333333", linewidth=1.0, linestyle="--", alpha=0.7)
        ax.text(
            peak_time,
            ax.get_ylim()[1] * 0.96,
            "peak",
            ha="right",
            va="top",
            fontsize=8,
            color="#333333",
            rotation=90,
        )

    ax.set_title(title, fontsize=11, pad=10)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Displacement magnitude (mm)")
    ax.legend(loc="upper right", fontsize=8, frameon=True)
    ax.set_xlim(min(time_s), max(time_s))
    ax.margins(y=0.08)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    plt.close(fig)
    print(f"Wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create one clean displacement plot for a single COMSOL case."
    )
    parser.add_argument(
        "--case-dir",
        type=Path,
        default=DEFAULT_CASE_DIR,
        help="Case output directory containing a solve folder.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output PNG path.",
    )
    parser.add_argument(
        "--title",
        default="Stage 1 fixed-support 0.25g acceleration pulse",
        help="Figure title.",
    )
    args = parser.parse_args()
    make_plot(args.case_dir.resolve(), args.output.resolve(), args.title)


if __name__ == "__main__":
    main()
