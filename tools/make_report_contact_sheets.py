from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "docs" / "Traineeship_report___Daan_Kuijpers" / "Figures" / "comsol_contact_sheets"
INDEX_PATH = ROOT / "docs" / "report_notes" / "comsol_pipeline" / "report_figures_metrics_index.md"
REVIEW_TIME_S = 1.125


@dataclass(frozen=True)
class Case:
    key: str
    label: str
    output_dir: Path

    @property
    def plot_dir(self) -> Path:
        return self.output_dir / "plot_screens_auto"

    @property
    def solve_dir(self) -> Path:
        return self.output_dir / "solve"

    @property
    def metrics_path(self) -> Path:
        matches = sorted(self.solve_dir.glob("*_metrics.json"))
        if not matches:
            raise FileNotFoundError(f"No metrics JSON found in {self.solve_dir}")
        return matches[0]


CASES = {
    "stage1_baseline": Case(
        "stage1_baseline",
        "Stage 1 fixed-material baseline",
        ROOT
        / "runs"
        / "comsol_runs"
        / "report_fixed_material_suite"
        / "outputs"
        / "output_sensitivity_baseline_fixed_materials_order2",
    ),
    "stage2_slab": Case(
        "stage2_slab",
        "Stage 2 slab reference",
        ROOT
        / "runs"
        / "comsol_runs"
        / "geometry_stage2_chestwall"
        / "outputs"
        / "output_stage2_vp_refined_slab_reference_fixed_order2",
    ),
    "stage2_g1050": Case(
        "stage2_g1050",
        "Stage 2 VP mild g1050",
        ROOT
        / "runs"
        / "comsol_runs"
        / "geometry_stage2_chestwall"
        / "outputs"
        / "output_stage2_vp_refined_mild_g1050_fixed_order2",
    ),
    "stage3_low": Case(
        "stage3_low",
        "Stage 3 low FGT",
        ROOT / "runs" / "comsol_runs" / "geometry_stage3" / "outputs" / "output_stage3_glandular_low_fixed_order2",
    ),
    "stage3_reference": Case(
        "stage3_reference",
        "Stage 3 reference FGT",
        ROOT
        / "runs"
        / "comsol_runs"
        / "geometry_stage3"
        / "outputs"
        / "output_stage3_glandular_reference_fixed_order2",
    ),
    "stage3_high": Case(
        "stage3_high",
        "Stage 3 high FGT",
        ROOT / "runs" / "comsol_runs" / "geometry_stage3" / "outputs" / "output_stage3_glandular_high_fixed_order2",
    ),
    "stage3_very_high": Case(
        "stage3_very_high",
        "Stage 3 very high FGT",
        ROOT
        / "runs"
        / "comsol_runs"
        / "geometry_stage3"
        / "outputs"
        / "output_stage3_glandular_very_high_fixed_order2",
    ),
    "stage4_reference": Case(
        "stage4_reference",
        "Stage 4 reference",
        ROOT
        / "runs"
        / "comsol_runs"
        / "geometry_stage4"
        / "outputs"
        / "output_stage4_simple_gland_reference_fixed_order2",
    ),
    "stage4_visible": Case(
        "stage4_visible",
        "Stage 4 visible profile asym.",
        ROOT
        / "runs"
        / "comsol_runs"
        / "geometry_stage4"
        / "outputs"
        / "output_stage4_simple_gland_visible_profile_asym_fixed_order2",
    ),
    "stage5_baseline": Case(
        "stage5_baseline",
        "Stage 5 no Cooper",
        ROOT
        / "runs"
        / "comsol_runs"
        / "report_fixed_material_suite"
        / "outputs"
        / "output_sensitivity_baseline_fixed_materials_order2",
    ),
    "stage5_stage5b": Case(
        "stage5_stage5b",
        "Stage 5B gland-to-skin",
        ROOT
        / "runs"
        / "comsol_runs"
        / "report_fixed_material_suite"
        / "outputs"
        / "output_sensitivity_stage5b_fixed_materials_order2",
    ),
    "stage5_stage5c": Case(
        "stage5_stage5c",
        "Stage 5C dense network",
        ROOT
        / "runs"
        / "comsol_runs"
        / "report_fixed_material_suite"
        / "outputs"
        / "output_sensitivity_stage5c_fixed_materials_order2",
    ),
}


CONTACT_SHEETS = [
    (
        "stage1_baseline_contact_sheet.png",
        "Stage 1 fixed-material baseline",
        [("stage1_baseline", f) for f in ["01_total_displacement_mm.png", "04_breast_von_mises_kpa.png", "05_glandular_von_mises_kpa.png", "07_sagittal_cut_total_displacement_mm.png"]],
        2,
    ),
    (
        "stage2_chestwall_contact_sheet.png",
        "Stage 2 slab reference versus volume-preserving g1050 chestwall",
        [
            (case, f)
            for case in ["stage2_slab", "stage2_g1050"]
            for f in ["01_total_displacement_mm.png", "04_breast_von_mises_kpa.png", "07_sagittal_cut_total_displacement_mm.png"]
        ],
        3,
    ),
    (
        "stage3_glandular_fraction_contact_sheet.png",
        "Stage 3 simple glandular fraction sweep",
        [
            (case, f)
            for case in ["stage3_low", "stage3_reference", "stage3_high", "stage3_very_high"]
            for f in ["01_total_displacement_mm.png", "05_glandular_von_mises_kpa.png", "07_sagittal_cut_total_displacement_mm.png"]
        ],
        3,
    ),
    (
        "stage4_asymmetry_contact_sheet.png",
        "Stage 4 simple-gland visible-profile asymmetry",
        [
            (case, f)
            for case in ["stage4_reference", "stage4_visible"]
            for f in ["01_total_displacement_mm.png", "03_anterior_posterior_displacement_v_mm.png", "07_sagittal_cut_total_displacement_mm.png"]
        ],
        3,
    ),
    (
        "stage5_cooper_contact_sheet.png",
        "Stage 5 Cooper scaffold sensitivity",
        [
            (case, f)
            for case in ["stage5_baseline", "stage5_stage5b", "stage5_stage5c"]
            for f in ["01_total_displacement_mm.png", "04_breast_von_mises_kpa.png", "10_cooper_gland_patch_load_arrows.png"]
        ],
        3,
    ),
]


DISPLAY_NAMES = {
    "01_total_displacement_mm.png": "total disp.",
    "03_anterior_posterior_displacement_v_mm.png": "AP disp.",
    "04_breast_von_mises_kpa.png": "breast VM",
    "05_glandular_von_mises_kpa.png": "gland VM",
    "07_sagittal_cut_total_displacement_mm.png": "sagittal disp.",
    "10_cooper_gland_patch_load_arrows.png": "Cooper gland load",
}


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fit_image(path: Path, width: int, height: int) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), "white")
    x = (width - image.width) // 2
    y = (height - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont, fill: str, max_width: int) -> int:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    line_height = font.size + 4 if hasattr(font, "size") else 16
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def make_contact_sheet(filename: str, title: str, entries: list[tuple[str, str]], columns: int) -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    cell_w, cell_h = 560, 360
    header_h = 58
    gutter = 24
    margin = 38
    title_h = 72
    rows = (len(entries) + columns - 1) // columns
    width = margin * 2 + columns * cell_w + (columns - 1) * gutter
    height = margin * 2 + title_h + rows * (cell_h + header_h) + (rows - 1) * gutter
    sheet = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(30, bold=True)
    label_font = load_font(20, bold=True)
    sub_font = load_font(17)
    draw.text((margin, margin), title, font=title_font, fill=(20, 20, 20))
    for idx, (case_key, image_name) in enumerate(entries):
        case = CASES[case_key]
        row = idx // columns
        col = idx % columns
        x = margin + col * (cell_w + gutter)
        y = margin + title_h + row * (cell_h + header_h + gutter)
        draw.rounded_rectangle((x, y, x + cell_w, y + header_h + cell_h), radius=8, fill="white", outline=(210, 210, 210))
        draw_wrapped(draw, (x + 14, y + 10), case.label, label_font, (25, 25, 25), cell_w - 28)
        draw.text((x + 14, y + 34), DISPLAY_NAMES.get(image_name, image_name), font=sub_font, fill=(70, 70, 70))
        image = fit_image(case.plot_dir / image_name, cell_w - 24, cell_h - 20)
        sheet.paste(image, (x + 12, y + header_h + 10))
    out = FIGURE_DIR / filename
    sheet.save(out, optimize=True)
    return out


def metric_value(metrics: dict, key: str) -> float | None:
    value = metrics.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def series_at_review_time(metrics: dict, series_key: str) -> float | None:
    time_values = metrics.get("time_s")
    series_values = metrics.get(series_key)
    if not isinstance(time_values, list) or not isinstance(series_values, list) or not time_values or not series_values:
        return None
    usable_len = min(len(time_values), len(series_values))
    idx = min(range(usable_len), key=lambda i: abs(float(time_values[i]) - REVIEW_TIME_S))
    if abs(float(time_values[idx]) - REVIEW_TIME_S) > 1e-6:
        return None
    return float(series_values[idx])


def review_or_peak(metrics: dict, review_key: str, series_key: str, peak_key: str) -> tuple[float | None, str]:
    if metrics.get(review_key) is not None:
        return metric_value(metrics, review_key), f"{REVIEW_TIME_S:.3f} s review"
    series_value = series_at_review_time(metrics, series_key)
    if series_value is not None:
        return series_value, f"{REVIEW_TIME_S:.3f} s review"
    return metric_value(metrics, peak_key), "peak/global"


def format_metrics(case: Case) -> list[str]:
    metrics = json.loads(case.metrics_path.read_text(encoding="utf-8"))
    breast_ml = metric_value(metrics, "breast_volume")
    gland_ml = metric_value(metrics, "glandular_volume")
    disp_m, disp_basis = review_or_peak(
        metrics, "review_max_displacement_breast", "max_displacement_breast_series", "max_displacement_breast"
    )
    vm_pa, vm_basis = review_or_peak(
        metrics, "review_max_von_mises_breast", "max_von_mises_breast_series", "max_von_mises_breast"
    )
    gland_vm_pa, gland_basis = review_or_peak(
        metrics, "review_max_von_mises_glandular", "max_von_mises_glandular_series", "max_von_mises_glandular"
    )
    time_label = " / ".join(dict.fromkeys([disp_basis, vm_basis, gland_basis]))
    gland_pct = None
    if breast_ml and gland_ml:
        gland_pct = 100.0 * gland_ml / breast_ml
    return [
        case.label,
        f"{breast_ml * 1_000_000.0:.2f}" if breast_ml is not None else "n/a",
        f"{gland_ml * 1_000_000.0:.2f}" if gland_ml is not None else "n/a",
        f"{gland_pct:.2f}" if gland_pct is not None else "n/a",
        f"{disp_m * 1000.0:.3f}" if disp_m is not None else "n/a",
        f"{vm_pa / 1000.0:.3f}" if vm_pa is not None else "n/a",
        f"{gland_vm_pa / 1000.0:.3f}" if gland_vm_pa is not None else "n/a",
        time_label,
        str(case.output_dir.relative_to(ROOT)).replace("\\", "/"),
        str(case.metrics_path.relative_to(ROOT)).replace("\\", "/"),
    ]


def write_index(generated: Iterable[Path]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Report Figures And Metrics Index",
        "",
        "Generated by `tools/make_report_contact_sheets.py` from existing COMSOL `plot_screens_auto` PNGs and `*_metrics.json` files. No COMSOL build or solve is run by this step.",
        "",
        "## Generated Contact Sheets",
        "",
        "| Figure | Report path |",
        "| --- | --- |",
    ]
    for path in generated:
        lines.append(f"| {path.name} | `{path.relative_to(ROOT).as_posix()}` |")
    lines.extend(
        [
            "",
            "## Metrics Sources",
            "",
            "Values are shown in report units. When `review_time_s` exists, displacement and stress use the shared review-time values; otherwise the available global/peak values are reported.",
            "",
            "| Case | Breast mL | Gland mL | Gland % | Max disp mm | Breast VM kPa | Gland VM kPa | Time basis | Output folder | Metrics JSON |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    ordered_keys = [
        "stage1_baseline",
        "stage2_slab",
        "stage2_g1050",
        "stage3_low",
        "stage3_reference",
        "stage3_high",
        "stage3_very_high",
        "stage4_reference",
        "stage4_visible",
        "stage5_baseline",
        "stage5_stage5b",
        "stage5_stage5c",
    ]
    for key in ordered_keys:
        lines.append("| " + " | ".join(format_metrics(CASES[key])) + " |")
    lines.extend(
        [
            "",
            "## Figure Source PNGs",
            "",
            "| Contact sheet | Source cases and PNG panels |",
            "| --- | --- |",
        ]
    )
    for filename, _, entries, _ in CONTACT_SHEETS:
        sources = []
        for case_key, image_name in entries:
            case = CASES[case_key]
            sources.append(f"`{(case.plot_dir / image_name).relative_to(ROOT).as_posix()}`")
        lines.append(f"| `{filename}` | {'<br>'.join(sources)} |")
    INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated = [make_contact_sheet(*spec) for spec in CONTACT_SHEETS]
    write_index(generated)
    print(f"Wrote {len(generated)} contact sheets to {FIGURE_DIR}")
    print(f"Wrote index to {INDEX_PATH}")


if __name__ == "__main__":
    main()
