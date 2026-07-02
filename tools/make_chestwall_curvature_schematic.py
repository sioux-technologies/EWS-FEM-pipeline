from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "Traineeship report - Daan_Kuijpers" / "Figures" / "model_overviews"


def sx(x: float) -> float:
    return 460.0 + 3000.0 * x


def sy(y: float) -> float:
    return 500.0 - 3000.0 * y


def path_from(points: list[tuple[float, float]], close: bool = False) -> str:
    if not points:
        return ""
    first = points[0]
    cmds = [f"M {sx(first[0]):.2f} {sy(first[1]):.2f}"]
    cmds.extend(f"L {sx(x):.2f} {sy(y):.2f}" for x, y in points[1:])
    if close:
        cmds.append("Z")
    return " ".join(cmds)


def text(x: float, y: float, label: str, *, size: int = 22, anchor: str = "middle", weight: str = "normal") -> str:
    return (
        f'<text x="{sx(x):.2f}" y="{sy(y):.2f}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}">'
        f"{escape(label)}</text>"
    )


def line(x1: float, y1: float, x2: float, y2: float, *, cls: str = "line", extra: str = "") -> str:
    return f'<line class="{cls}" x1="{sx(x1):.2f}" y1="{sy(y1):.2f}" x2="{sx(x2):.2f}" y2="{sy(y2):.2f}" {extra}/>'


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Selected Stage 2 report route.
    r_breast = 0.070
    x_offset = 0.055
    curve_depth = 0.021
    support_half_width = 0.092
    support_thickness = 0.006
    outer_scale_x = 1.08

    x_left = -support_half_width
    x_right = support_half_width
    half_span = max(abs(x_left - x_offset), abs(x_right - x_offset))
    r_cyl = (half_span**2 + curve_depth**2) / (2.0 * curve_depth)
    center_y = curve_depth - r_cyl
    display_center_y = -0.085

    def arc_y(x: float) -> float:
        return center_y + max(r_cyl**2 - (x - x_offset) ** 2, 0.0) ** 0.5

    xs = [x_left + (x_right - x_left) * i / 240 for i in range(241)]
    cw = [(x, arc_y(x)) for x in xs]
    lower = [(x, arc_y(x) - support_thickness) for x in xs]

    a = r_breast * outer_scale_x
    b = r_breast
    breast_top: list[tuple[float, float]] = []
    breast_bottom: list[tuple[float, float]] = []
    for x in xs:
        inside = max(1.0 - (x / a) ** 2, 0.0)
        y_outer = b * inside**0.5
        y_cw = arc_y(x)
        if y_outer >= y_cw:
            breast_top.append((x, y_outer))
            breast_bottom.append((x, y_cw))

    breast_path = path_from(breast_top + list(reversed(breast_bottom)), close=True)
    support_path = path_from(lower + list(reversed(cw)), close=True)

    # Simple glandular cap: one smooth clipped ellipsoid-like region.
    gland_center_y = 0.031
    gland_rx = 0.034
    gland_ry = 0.020
    gland_points = []
    for i in range(121):
        t = 3.141592653589793 * i / 120
        gland_points.append((gland_rx * __import__("math").cos(t), gland_center_y + gland_ry * __import__("math").sin(t)))
    gland_points += [(gland_rx, gland_center_y), (-gland_rx, gland_center_y)]
    gland_path = path_from(gland_points, close=True)

    # Radius helper line.
    x_target = x_offset + 0.056
    y_target = arc_y(x_target)

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
  <svg xmlns="http://www.w3.org/2000/svg" width="1100" height="900" viewBox="0 0 1100 900">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L0,6 L8,3 z" fill="#111"/>
    </marker>
    <marker id="arrowStart" markerWidth="10" markerHeight="10" refX="0" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M8,0 L8,6 L0,3 z" fill="#111"/>
    </marker>
    <style>
      .line {{ stroke: #111; stroke-width: 3; fill: none; stroke-linecap: round; stroke-linejoin: round; }}
      .thin {{ stroke: #666; stroke-width: 2; fill: none; stroke-linecap: round; stroke-linejoin: round; }}
      .dash {{ stroke: #555; stroke-width: 2.5; fill: none; stroke-dasharray: 12 9; stroke-linecap: round; }}
      .label {{ font-family: Arial, Helvetica, sans-serif; fill: #111; }}
      .small {{ font-size: 22px; }}
      .math {{ font-size: 24px; font-style: italic; }}
      .title {{ font-size: 25px; font-weight: 700; }}
    </style>
  </defs>

  <rect width="100%" height="100%" fill="white"/>
  <text x="990" y="78" text-anchor="end" class="label title">Transverse chestwall curvature parameters</text>

  <path d="{support_path}" fill="#cfcfcf" stroke="#111" stroke-width="3.2"/>
  <path d="{breast_path}" fill="#f6efe6" stroke="#111" stroke-width="3.5"/>
  <path d="{gland_path}" fill="#f2bfd0" fill-opacity="0.92" stroke="#111" stroke-width="2.5"/>

  <ellipse cx="{sx(0):.2f}" cy="{sy(r_breast + 0.0035):.2f}" rx="18" ry="7" fill="#efefef" stroke="#111" stroke-width="2.4"/>

  {line(0, r_breast - 0.014, 0, display_center_y - 0.002, cls="dash")}
  {line(x_offset, curve_depth + 0.016, x_offset, display_center_y - 0.002, cls="dash")}
  {line(x_left - 0.010, 0, x_right + 0.012, 0, cls="dash")}

  <circle cx="{sx(x_offset):.2f}" cy="{sy(display_center_y):.2f}" r="6.5" fill="#111"/>
  {line(x_offset, display_center_y, x_target, y_target, cls="dash")}

  <line x1="{sx(x_left + 0.014):.2f}" y1="{sy(0):.2f}" x2="{sx(x_left + 0.014):.2f}" y2="{sy(curve_depth):.2f}" class="line" marker-start="url(#arrowStart)" marker-end="url(#arrow)"/>
  {line(x_left + 0.014, curve_depth, x_offset, curve_depth, cls="dash")}
  {line(0, -0.041, x_offset, -0.041, cls="line", extra='marker-start="url(#arrowStart)" marker-end="url(#arrow)"')}

  <text x="{sx(x_left - 0.004):.2f}" y="{sy(curve_depth / 2 + 0.004):.2f}" text-anchor="end" class="label math">d<tspan baseline-shift="sub" font-size="70%">cw</tspan> = 21 mm</text>
  <text x="{sx(x_left - 0.004):.2f}" y="{sy(curve_depth / 2 - 0.005):.2f}" text-anchor="end" class="label small">(curve depth)</text>

  <text x="{sx(x_offset / 2):.2f}" y="{sy(-0.047):.2f}" text-anchor="middle" class="label math">x<tspan baseline-shift="sub" font-size="70%">offset</tspan> = +55 mm</text>
  <text x="{sx((x_offset + x_target) / 2 + 0.006):.2f}" y="{sy((display_center_y + y_target) / 2):.2f}" text-anchor="start" class="label math">R<tspan baseline-shift="sub" font-size="70%">cyl</tspan></text>

  <text x="{sx(0):.2f}" y="{sy(r_breast + 0.011):.2f}" text-anchor="middle" class="label small">nipple</text>
  <text x="{sx(0):.2f}" y="{sy(0.046):.2f}" text-anchor="middle" class="label small">simple glandular region</text>
  <text x="{sx(-0.066):.2f}" y="{sy(0.061):.2f}" text-anchor="start" class="label small">breast outer contour</text>
  <text x="{sx(0.063):.2f}" y="{sy(-0.014):.2f}" text-anchor="middle" class="label small">curved chestwall support</text>

  <line x1="{sx(x_left - 0.020):.2f}" y1="{sy(0.045):.2f}" x2="{sx(x_left - 0.020):.2f}" y2="{sy(0.070):.2f}" class="line" marker-end="url(#arrow)"/>
  <line x1="{sx(x_left - 0.020):.2f}" y1="{sy(0.045):.2f}" x2="{sx(x_left + 0.010):.2f}" y2="{sy(0.045):.2f}" class="line" marker-end="url(#arrow)"/>
  <text x="{sx(x_left - 0.024):.2f}" y="{sy(0.073):.2f}" class="label math">y</text>
  <text x="{sx(x_left + 0.014):.2f}" y="{sy(0.043):.2f}" class="label math">x</text>

  <text x="{sx(x_left):.2f}" y="{sy(-0.110):.2f}" text-anchor="start" class="label small">schematic, not to scale</text>
</svg>
'''

    out = OUT_DIR / "stage2_chestwall_curvature_topview_schematic.svg"
    out.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
