"""Create a compact model option tree preview from existing model screenshots."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "model_pictures" / "model_option_tree" / "model_option_tree_stage_overview.png"


STAGES = [
    {
        "stage": "Stage 1",
        "title": "Motion baseline",
        "image": ROOT
        / "model_pictures"
        / "pipeline_overview"
        / "stage1_fixed_support_pulse_mild_025g_displacement_example.png",
        "main": "0.25g fixed-support acceleration pulse",
        "status": "Motion sanity baseline",
        "branch": "Not final anatomical reference",
        "color": "#5B7FA6",
    },
    {
        "stage": "Stage 2",
        "title": "Chestwall geometry",
        "image": ROOT
        / "model_pictures"
        / "stage2_chestwall"
        / "stage2_chestwall_leftlateral_offset055.png",
        "main": "xoffset055 transverse chestwall",
        "status": "First fair geometry baseline",
        "branch": "Patient-dependent sensitivity",
        "color": "#4E9A8E",
    },
    {
        "stage": "Stage 3",
        "title": "Glandular tissue",
        "image": ROOT
        / "model_pictures"
        / "stage3_glandular"
        / "stage3_glandular_ref_lateral_slice.png",
        "main": "Realistic reference lobule spread",
        "status": "Selected glandular route",
        "branch": "Compact / reference / wide spread",
        "color": "#8A7DBE",
    },
    {
        "stage": "Stage 4",
        "title": "Asymmetry options",
        "image": ROOT
        / "model_pictures"
        / "stage4_asymmetry_nipple"
        / "stage4_asymmetry_widthstretch_anterior_offset055.png",
        "main": "Profile and nipple-position changes",
        "status": "Geometry sensitivity",
        "branch": "Use as diagnostic, not final baseline",
        "color": "#C1894B",
    },
    {
        "stage": "Stage 5",
        "title": "Mechanical support",
        "image": ROOT
        / "model_pictures"
        / "stage5_cooper"
        / "stage5_cooper_variants_schematic.png",
        "main": "Skin shell / Cooper scaffold / no-Cooper control",
        "status": "Current control: no-Cooper",
        "branch": "Skin-on and Cooper require validation",
        "color": "#A45E70",
    },
    {
        "stage": "Stage 6",
        "title": "Tumor / lesion",
        "image": ROOT
        / "model_pictures"
        / "stage6_tumor"
        / "stage6_tumor_medium_upper_outer_surface(0.025;0.056;0.018)_sideview.png",
        "main": "Upper-outer surface-proximal tumor",
        "status": "Next tumor sensitivity route",
        "branch": "Compare matched no-tumor control",
        "color": "#B24D45",
    },
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        img = Image.new("RGB", size, "#F0F0F0")
        draw = ImageDraw.Draw(img)
        draw.text((20, size[1] // 2 - 10), "Image missing", fill="#555555", font=font(24, True))
        return img
    img = Image.open(path).convert("RGB")
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def rounded_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    text_font: ImageFont.FreeTypeFont,
    fill: str,
    max_chars: int,
    line_gap: int = 4,
) -> int:
    x, y = xy
    lines = wrap(text, width=max_chars)
    for line in lines:
        draw.text((x, y), line, fill=fill, font=text_font)
        y += text_font.size + line_gap
    return y


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill: str = "#555555") -> None:
    draw.line((start, end), fill=fill, width=4)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 > x1 else -1
        points = [(x2, y2), (x2 - 14 * direction, y2 - 8), (x2 - 14 * direction, y2 + 8)]
    else:
        direction = 1 if y2 > y1 else -1
        points = [(x2, y2), (x2 - 8, y2 - 14 * direction), (x2 + 8, y2 - 14 * direction)]
    draw.polygon(points, fill=fill)


def main() -> None:
    canvas_w, canvas_h = 1900, 1350
    card_w, card_h = 560, 470
    img_w, img_h = 500, 245
    margin_x, gap_x = 80, 55
    top_y, gap_y = 170, 90
    bg = "#F7F8FA"

    canvas = Image.new("RGB", (canvas_w, canvas_h), bg)
    draw = ImageDraw.Draw(canvas)

    title_font = font(42, True)
    subtitle_font = font(22)
    stage_font = font(24, True)
    card_title_font = font(27, True)
    body_font = font(22)
    small_font = font(19)

    draw.text((80, 55), "Model option tree: staged COMSOL breast-model development", fill="#1F2933", font=title_font)
    draw.text(
        (82, 108),
        "Each stage adds one controlled modelling option before tumor/no-tumor comparisons are interpreted.",
        fill="#4A5563",
        font=subtitle_font,
    )

    positions: list[tuple[int, int]] = []
    for row in range(2):
        for col in range(3):
            x = margin_x + col * (card_w + gap_x)
            y = top_y + row * (card_h + gap_y)
            positions.append((x, y))

    for idx, item in enumerate(STAGES):
        x, y = positions[idx]
        color = item["color"]
        rounded_rect(draw, (x, y, x + card_w, y + card_h), 18, "#FFFFFF", "#D7DBE0")
        draw.rounded_rectangle((x, y, x + card_w, y + 62), radius=18, fill=color)
        draw.rectangle((x, y + 32, x + card_w, y + 62), fill=color)
        draw.text((x + 24, y + 17), item["stage"], fill="#FFFFFF", font=stage_font)
        draw.text((x + 140, y + 15), item["title"], fill="#FFFFFF", font=card_title_font)

        img = fit_image(item["image"], (img_w, img_h))
        canvas.paste(img, (x + 30, y + 82))
        draw.rounded_rectangle((x + 30, y + 82, x + 30 + img_w, y + 82 + img_h), radius=10, outline="#BCC3CC", width=2)

        text_y = y + 350
        text_y = draw_wrapped(draw, item["main"], (x + 28, text_y), body_font, "#1F2933", 38, 3)
        text_y += 4
        text_y = draw_wrapped(draw, item["status"], (x + 28, text_y), small_font, color, 42, 3)
        draw_wrapped(draw, item["branch"], (x + 28, text_y + 2), small_font, "#56616F", 42, 3)

    # Main route arrows.
    for a, b in [(0, 1), (1, 2), (3, 4), (4, 5)]:
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        draw_arrow(draw, (x1 + card_w + 8, y1 + card_h // 2), (x2 - 8, y2 + card_h // 2))
    draw_arrow(
        draw,
        (positions[2][0] + card_w // 2, positions[2][1] + card_h + 10),
        (positions[3][0] + card_w // 2, positions[3][1] - 12),
    )

    # Footer note.
    footer = (
        "Report use: Stage 1 validates excitation; Stages 2-5 define matched anatomy/mechanics; "
        "Stage 6 tests tumor sensitivity against the matched control."
    )
    draw_wrapped(draw, footer, (80, canvas_h - 92), font(22), "#3D4852", 125, 4)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
