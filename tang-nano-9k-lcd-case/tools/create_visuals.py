#!/usr/bin/env python3
"""Create rendered images, orthographic views, and a drawing PDF.

Inputs are the generated binary STL files.  Proxy solids for the LCD and PCB
are dimensionally derived from the same reference values as the case model and
are used only to explain the assembly.
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Table, TableStyle

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import generate_stl as model
from tools.create_scale_drawing import dim_text
from tools.font_paths import dejavu_sans
from tools.profiles import PROFILES, CaseProfile, get_profile


BEZEL_T = model.BEZEL_T
BODY_D = model.BODY_D
WALL = model.WALL
PCB_W = model.PCB_W
PCB_H = model.PCB_H
PCB_T = model.PCB_T
# The standard rear-cover plate rests on the chassis rear edge at z=27 and
# adds its 2 mm thickness to the overall depth.
TOTAL_DEPTH = model.overall_depth(model.STANDARD_REAR_CLEARANCE)


@dataclass
class SceneItem:
    triangles: np.ndarray
    color: str
    alpha: float
    label: str


def read_binary_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise ValueError(f"invalid binary STL: {path}")
    mesh = np.empty((count, 3, 3), dtype=float)
    offset = 84
    for index in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        mesh[index] = (values[3:6], values[6:9], values[9:12])
        offset += 50
    return mesh


def box_mesh(x0, y0, z0, x1, y1, z1) -> np.ndarray:
    vertices = np.array(
        [
            [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
            [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
        ],
        dtype=float,
    )
    faces = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    )
    return np.array([[vertices[i] for i in face] for face in faces])


def translate(mesh: np.ndarray, x=0.0, y=0.0, z=0.0) -> np.ndarray:
    return mesh + np.array([x, y, z])


def assembled_rear_cover(p: CaseProfile, mesh: np.ndarray, extra_z=0.0) -> np.ndarray:
    result = mesh.copy()
    result[:, :, 0] += p.cover_x
    result[:, :, 1] += p.cover_y
    result[:, :, 2] = TOTAL_DEPTH - result[:, :, 2] + extra_z
    return result


def lcd_proxy(p: CaseProfile, z0=BEZEL_T) -> np.ndarray:
    lcd = p.lcd
    return box_mesh(p.lcd_x, p.lcd_y, z0, p.lcd_x + lcd.width,
                    p.lcd_y + lcd.height, z0 + lcd.thickness)


def pcb_proxy(p: CaseProfile, z0=model.PCB_REAR_Z - PCB_T) -> np.ndarray:
    x0, y0 = p.pcb_x, p.pcb_y
    return box_mesh(x0, y0, z0, x0 + PCB_W, y0 + PCB_H, z0 + PCB_T)


def render_scene(items: list[SceneItem], output: Path, title: str, elev=27, azim=-52) -> None:
    fig = plt.figure(figsize=(12, 8), dpi=220, facecolor="white")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_proj_type("ortho")
    for item in items:
        poly = Poly3DCollection(
            item.triangles,
            facecolor=item.color,
            edgecolor="#263238",
            linewidth=0.08,
            alpha=item.alpha,
        )
        ax.add_collection3d(poly)

    points = np.concatenate([item.triangles.reshape(-1, 3) for item in items])
    lows = points.min(axis=0)
    highs = points.max(axis=0)
    centre = (lows + highs) / 2
    radius = max(highs - lows) / 2 * 1.05
    ax.set_xlim(centre[0] - radius, centre[0] + radius)
    ax.set_ylim(centre[1] - radius, centre[1] + radius)
    ax.set_zlim(centre[2] - radius, centre[2] + radius)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, fontsize=18, color="#263238", pad=12)

    legend = [plt.Line2D([0], [0], color=item.color, lw=8, label=item.label)
              for item in items if item.label]
    if legend:
        ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.02),
                  ncol=min(5, len(legend)), frameon=False, fontsize=10)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def dimension_h(ax, x0, x1, y, source_y, text):
    color = "#1976d2"
    ax.annotate("", xy=(x1, y), xytext=(x0, y),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.0))
    ax.plot([x0, x0], [source_y, y], color=color, lw=0.7)
    ax.plot([x1, x1], [source_y, y], color=color, lw=0.7)
    ax.text((x0 + x1) / 2, y + 1.2, text, ha="center", va="bottom",
            color=color, fontsize=8)


def dimension_v(ax, y0, y1, x, source_x, text):
    color = "#1976d2"
    ax.annotate("", xy=(x, y1), xytext=(x, y0),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.0))
    ax.plot([source_x, x], [y0, y0], color=color, lw=0.7)
    ax.plot([source_x, x], [y1, y1], color=color, lw=0.7)
    ax.text(x - 1.2, (y0 + y1) / 2, text, ha="right", va="center",
            rotation=90, color=color, fontsize=8)


def setup_drawing_axis(ax, title):
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=12, fontweight="bold", color="#263238")
    ax.axis("off")


def create_three_view(output: Path, p: CaseProfile) -> None:
    fig = plt.figure(figsize=(16, 10), dpi=220, facecolor="white")
    grid = fig.add_gridspec(2, 2, height_ratios=(1.25, 0.75), hspace=0.28, wspace=0.18)
    front = fig.add_subplot(grid[0, :])
    top = fig.add_subplot(grid[1, 0])
    side = fig.add_subplot(grid[1, 1])

    # Front view.
    setup_drawing_axis(front, "FRONT VIEW")
    bezel_w, bezel_h = p.bezel_w, p.bezel_h
    window_x, window_y = p.window_x, p.window_y
    window_w, window_h = p.window_w, p.window_h
    front.add_patch(Rectangle((0, 0), bezel_w, bezel_h, fill=False, lw=2.0, color="#263238"))
    front.add_patch(Rectangle((window_x, window_y), window_w, window_h,
                              fill=False, lw=1.8, color="#263238"))
    cut_x = (bezel_w - p.panel_cutout_w) / 2
    cut_y = (bezel_h - p.panel_cutout_h) / 2
    front.add_patch(Rectangle((cut_x, cut_y), p.panel_cutout_w, p.panel_cutout_h,
                              fill=False, lw=1.0, ls="--", color="#78909c"))
    dimension_h(front, 0, bezel_w, -9, 0, f"{bezel_w:.1f}")
    dimension_v(front, 0, bezel_h, -11, 0, f"{bezel_h:.1f}")
    dimension_h(front, window_x, window_x + window_w, window_y - 5, window_y,
                f"{window_w:.2f}")
    dimension_v(front, window_y, window_y + window_h, window_x - 5, window_x,
                f"{window_h:.2f}")
    front.text(bezel_w + 3, bezel_h - 2,
               f"Dashed: panel cutout\n{p.panel_cutout_w:.1f} x {p.panel_cutout_h:.1f}",
               va="top", fontsize=8, color="#546e7a")
    front.set_xlim(-16, bezel_w + 28)
    front.set_ylim(-13, bezel_h + 5)

    # Top view: X-Z.
    setup_drawing_axis(top, "TOP VIEW")
    hdmi = p.hdmi_opening
    top.add_patch(Rectangle((0, 0), bezel_w, BEZEL_T, fill=False, lw=2.0, color="#263238"))
    top.add_patch(Rectangle((p.body_x, BEZEL_T), p.body_w, BODY_D - BEZEL_T,
                            fill=False, lw=1.7, color="#263238"))
    top.add_patch(Rectangle((p.cover_x, BODY_D), p.cover_w, model.COVER_PLATE_T,
                            fill=False, lw=1.7, color="#263238"))
    # HDMI opening on the top wall.
    top.add_patch(Rectangle((bezel_w / 2 - hdmi.half_w, hdmi.z0), hdmi.width, hdmi.height,
                            fill=False, lw=1.2, color="#d84315"))
    dimension_h(top, 0, bezel_w, -8, 0, f"{bezel_w:.1f}")
    dimension_v(top, 0, TOTAL_DEPTH, -10, 0, f"{TOTAL_DEPTH:.1f}")
    top.text(bezel_w / 2, hdmi.z0 - 1.0, "HDMI opening", ha="center", va="top",
             color="#d84315", fontsize=8)
    top.set_xlim(-15, bezel_w + 5)
    top.set_ylim(-11, TOTAL_DEPTH + 5)

    # Right side view: Z-Y.
    setup_drawing_axis(side, "RIGHT SIDE VIEW")
    side.add_patch(Rectangle((0, 0), BEZEL_T, bezel_h, fill=False, lw=2.0, color="#263238"))
    side.add_patch(Rectangle((BEZEL_T, p.body_y), BODY_D - BEZEL_T, p.body_h,
                             fill=False, lw=1.7, color="#263238"))
    side.add_patch(Rectangle((BODY_D, p.cover_y), model.COVER_PLATE_T, p.cover_h,
                             fill=False, lw=1.7, color="#263238"))
    dimension_h(side, 0, TOTAL_DEPTH, -9, 0, f"{TOTAL_DEPTH:.1f}")
    dimension_v(side, 0, bezel_h, -11, 0, f"{bezel_h:.1f}")
    side.set_xlim(-16, TOTAL_DEPTH + 6)
    side.set_ylim(-12, bezel_h + 5)

    fig.suptitle(f"Tang Nano 9K + {p.title} LCD Panel Case - Orthographic Drawing",
                 fontsize=17, fontweight="bold", color="#263238", y=0.98)
    fig.text(0.5, 0.012,
             "Units: mm | Projection: orthographic | Scale: NTS | "
             f"Reference panel: {p.lcd.description.replace(' RGB', '')}",
             ha="center", fontsize=9, color="#546e7a")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def create_pdf(pdf_path: Path, p: CaseProfile, three_view: Path, assembly: Path,
               exploded: Path) -> None:
    font_path = dejavu_sans()
    pdfmetrics.registerFont(TTFont("DejaVu", str(font_path)))
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = landscape(A4)
    canvas = pdf_canvas.Canvas(
        str(pdf_path), pagesize=(page_w, page_h), invariant=1
    )
    canvas.setTitle("Tang Nano 9K Panel Case Drawing")
    canvas.setAuthor("OpenAI Codex")

    def draw_fitted_image(path: Path, x, y, max_w, max_h):
        image = ImageReader(str(path))
        source_w, source_h = image.getSize()
        scale = min(max_w / source_w, max_h / source_h)
        draw_w, draw_h = source_w * scale, source_h * scale
        canvas.drawImage(image, x + (max_w - draw_w) / 2, y + (max_h - draw_h) / 2,
                         width=draw_w, height=draw_h, preserveAspectRatio=True, mask="auto")

    # Page 1: mechanical drawing. The PNG contains its own title and footer.
    draw_fitted_image(three_view, 10 * mm, 7 * mm, page_w - 20 * mm, page_h - 14 * mm)
    canvas.showPage()

    # Page 2: explanatory renders and dimensions.
    canvas.setFont("DejaVu", 18)
    canvas.setFillColor(colors.HexColor("#263238"))
    canvas.drawString(12 * mm, page_h - 14 * mm, "Assembly and exploded views")
    draw_fitted_image(assembly, 12 * mm, 100 * mm, 128 * mm, 86 * mm)
    draw_fitted_image(exploded, 151 * mm, 100 * mm, 128 * mm, 86 * mm)

    table = Table(
        [
            ["Item", "Nominal value"],
            ["LCD module", f"{dim_text(p.lcd.width)} x {dim_text(p.lcd.height)}"
                           f" x {dim_text(p.lcd.thickness)} mm"],
            ["PCB", "70.00 x 26.00 x 1.60 mm"],
            ["Front bezel", f"{dim_text(p.bezel_w)} x {dim_text(p.bezel_h)} mm"],
            ["Recommended panel cutout",
             f"{dim_text(p.panel_cutout_w)} x {dim_text(p.panel_cutout_h)} mm;"
             " trim after test fit"],
            ["Overall depth",
             f"{dim_text(TOTAL_DEPTH)} mm; rear cover plate seats on the chassis rear edge"],
            ["Panel clip variants", "1.5 / 2.0 / 3.0 mm panel thickness"],
        ],
        colWidths=[75 * mm, 185 * mm],
        rowHeights=[7 * mm] * 7,
        style=TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263238")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#90a4ae")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eceff1")]),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ]),
    )
    table.wrapOn(canvas, 260 * mm, 49 * mm)
    table.drawOn(canvas, 18 * mm, 39 * mm)
    canvas.setFont("DejaVu", 8)
    canvas.setFillColor(colors.HexColor("#455a64"))
    canvas.drawString(12 * mm, 25 * mm,
                      f"Design basis: Sipeed Tang Nano 9K and {p.lcd.name} {p.title} LCD.")
    canvas.drawString(12 * mm, 19 * mm,
                      "Verify connector height and clip fit on physical hardware before final panel machining.")
    canvas.save()


def create_profile_visuals(stl_dir: Path, output_dir: Path, p: CaseProfile) -> list[Path]:
    front = read_binary_stl(stl_dir / "front_chassis_panel_2p0mm.stl")
    retainer = read_binary_stl(stl_dir / "lcd_retainer.stl")
    cover = read_binary_stl(stl_dir / "rear_cover.stl")
    retainer_closed = translate(retainer, p.retainer_x, p.retainer_y,
                                model.retainer_assembly_z(p))
    cover_closed = assembled_rear_cover(p, cover)

    image_dir = output_dir / "images"
    pdf_dir = output_dir / "pdf"
    assembly_path = image_dir / "assembly_render.png"
    exploded_path = image_dir / "exploded_render.png"
    three_view_path = image_dir / "orthographic_three_view.png"
    pdf_path = pdf_dir / "tang-nano-9k-panel-case-drawing.pdf"
    lcd_label = f"{p.title} LCD"

    render_scene(
        [
            SceneItem(front, "#90a4ae", 0.23, "Front chassis"),
            SceneItem(lcd_proxy(p), "#29b6f6", 0.82, lcd_label),
            SceneItem(retainer_closed, "#ffb74d", 0.82, "LCD retainer"),
            SceneItem(pcb_proxy(p), "#43a047", 0.90, "Tang Nano 9K"),
            SceneItem(cover_closed, "#607d8b", 0.28, "Rear cover"),
        ],
        assembly_path,
        "Assembled cutaway render",
    )

    exploded_retainer = translate(retainer, p.retainer_x, p.retainer_y, 43.0)
    exploded_lcd = lcd_proxy(p, 34.0)
    exploded_pcb = pcb_proxy(p, 52.0)
    exploded_cover = assembled_rear_cover(p, cover, extra_z=53.0)
    render_scene(
        [
            SceneItem(front, "#90a4ae", 0.42, "Front chassis"),
            SceneItem(exploded_lcd, "#29b6f6", 0.88, lcd_label),
            SceneItem(exploded_retainer, "#ffb74d", 0.90, "LCD retainer"),
            SceneItem(exploded_pcb, "#43a047", 0.92, "Tang Nano 9K"),
            SceneItem(exploded_cover, "#607d8b", 0.50, "Rear cover"),
        ],
        exploded_path,
        "Exploded render - front to rear",
        elev=24,
        azim=-55,
    )
    create_three_view(three_view_path, p)
    create_pdf(pdf_path, p, three_view_path, assembly_path, exploded_path)
    return [assembly_path, exploded_path, three_view_path, pdf_path]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stl-dir", type=Path, default=Path("build"),
                        help="root directory with one sub-directory per profile")
    parser.add_argument("--output-dir", type=Path, default=Path("output"),
                        help="root directory; one sub-directory per profile")
    parser.add_argument("--profile", action="append", choices=sorted(PROFILES),
                        help="profile to render; repeatable, default: all")
    args = parser.parse_args()
    for key in args.profile or PROFILES:
        paths = create_profile_visuals(args.stl_dir / key, args.output_dir / key,
                                       get_profile(key))
        for path in paths:
            print(path)


if __name__ == "__main__":
    main()
