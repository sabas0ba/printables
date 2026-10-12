#!/usr/bin/env python3
"""Generate A3 spatial, 1:1 three-view and exact-section assembly drawings."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from assembly_r4 import (
    CASE_DEPTH, CORE_IN_CASE_STEP_OFFSET, CORE_STEP_BOUNDS_LOCAL,
    DOCK_STEP_BOUNDS_LOCAL, DOCK_STEP_OFFSET, assembled_parts,
    official_global_bounds, section_segments,
)
from generate_case import BEZEL_T, CASE_H, CASE_W, DOCK_H, DOCK_W, DOCK_X, DOCK_Y, FRONT_DEPTH, LCDS, TRAY_T
from generate_case_r4 import (
    ASSEMBLY_HOLES, DOCK_PCB_T_NOMINAL, DOCK_STANDOFF_H, PIN_HEAD_T,
    PIN_TIP, SERVICE_CAP_DEPTH, STRUCTURAL_DEPTH,
)
from generate_drawings import (
    CASE, CORE, DIM, DOCK, FPC, LCD, LCD_ACTIVE, MM, NOTE, OUTLINE,
    PAGE_H_MM, PAGE_W_MM, calibration, circle, dim_h, dim_v, line,
    notes_block, rect, text, wrapped,
)


PURPLE = HexColor("#7652B4")
SNAP = HexColor("#D06928")
PART_COLORS = {
    "Front shell": CASE,
    "LCD": LCD,
    "LCD retainer": HexColor("#8995A1"),
    "Dock tray": PURPLE,
    "Official Dock": DOCK,
    "M2.5": HexColor("#58616B"),
    "Rear access frame": CASE,
    "Rear service cap": HexColor("#4F6476"),
    "snap pins": SNAP,
}
DOCK_GLOBAL = official_global_bounds(DOCK_STEP_BOUNDS_LOCAL, DOCK_STEP_OFFSET)
CORE_GLOBAL = official_global_bounds(CORE_STEP_BOUNDS_LOCAL, CORE_IN_CASE_STEP_OFFSET)
PCB_Z0 = DOCK_STEP_OFFSET[2]
PCB_Z1 = PCB_Z0 + 1.590
REAR_INNER_Z = CASE_DEPTH - 2.40
FRAME_INNER_Z = STRUCTURAL_DEPTH - 2.40


def page_frame(c: canvas.Canvas, title: str, sheet: str, scale: str) -> None:
    rect(c, 8, 8, PAGE_W_MM - 16, PAGE_H_MM - 16, OUTLINE, None, 0.45)
    text(c, 14, 282, title, 5.3, OUTLINE, True)
    text(c, 405, 282, f"Sheet {sheet}  Scale {scale}  Units mm", 3.1, OUTLINE, align="right")
    line(c, 12, 275, 408, 275, OUTLINE, 0.35)
    text(c, 14, 13, "1:1 SHEETS: PRINT AT 100% / ACTUAL SIZE. DISABLE FIT-TO-PAGE.", 3.0, NOTE, True)
    text(c, 405, 13, "Tang Primer 20K LCD enclosure  R4", 2.8, OUTLINE, align="right")


def spatial_sheet(c: canvas.Canvas, image_path: Path, label: str, sheet: str) -> None:
    page_frame(c, f"{label} SPATIAL ASSEMBLY", sheet, "NTS")
    c.drawImage(ImageReader(str(image_path)), 13 * MM, 28 * MM, 394 * MM, 236 * MM,
                preserveAspectRatio=True, anchor="c", mask="auto")
    text(c, 16, 22, "Transparent left: nested final position. Exploded right: every part stays on the true front-to-rear Z axis.", 3.0, OUTLINE)
    c.showPage()


def lcd_xy(spec_key: str):
    spec = LCDS[spec_key]
    return spec, (CASE_W - spec.module_w) / 2, (CASE_H - spec.module_h) / 2


def front_view(c: canvas.Canvas, spec_key: str, ox: float, oy: float) -> None:
    spec, lx, ly = lcd_xy(spec_key)
    rect(c, ox, oy, CASE_W, CASE_H, OUTLINE, None, 0.65)
    rect(c, ox + lx, oy + ly, spec.module_w, spec.module_h, LCD,
         Color(0.3, 0.61, 0.91, alpha=0.18), 0.45)
    wx = (CASE_W - spec.window_w) / 2
    wy = CASE_H / 2 + spec.window_offset_y - spec.window_h / 2
    rect(c, ox + wx, oy + wy, spec.window_w, spec.window_h, LCD_ACTIVE, None, 0.45)
    rect(c, ox + DOCK_X, oy + DOCK_Y, DOCK_W, DOCK_H, DOCK, None, 0.35, dash=(2, 1))
    rect(c, ox + 14.499 + DOCK_X, oy + 21.344 + DOCK_Y, 67.60, 30.00, CORE, None, 0.45, dash=(3, 1))
    for x, y in ASSEMBLY_HOLES:
        rect(c, ox + x - 2.15, oy + y - 2.15, 4.30, 4.30, SNAP, white, 0.35)
    text(c, ox + 70, oy + CASE_H + 4, "FRONT / XY", 3.3, OUTLINE, True, "center")
    dim_h(c, ox, ox + CASE_W, oy - 8, oy, "140.00")
    dim_v(c, oy, oy + CASE_H, ox - 8, ox, f"{CASE_H:.2f}")


def top_view(c: canvas.Canvas, spec_key: str, ox: float, oy: float) -> None:
    spec, lx, _ = lcd_xy(spec_key)
    rect(c, ox, oy, CASE_W, CASE_DEPTH, OUTLINE, None, 0.65)
    rect(c, ox + lx, oy + BEZEL_T, spec.module_w, spec.module_t, LCD,
         Color(0.3, 0.61, 0.91, alpha=0.20), 0.4)
    rect(c, ox + 4, oy + BEZEL_T + spec.module_t, 132, spec.retainer_t, CASE, None, 0.35)
    rect(c, ox, oy + BEZEL_T + FRONT_DEPTH, CASE_W, TRAY_T, PURPLE, None, 0.4)
    rect(c, ox + DOCK_X, oy + PCB_Z0, DOCK_W, DOCK_PCB_T_NOMINAL, DOCK,
         Color(0.29, 0.65, 0.40, alpha=0.16), 0.45)
    rect(c, ox + CORE_GLOBAL[0][0], oy + CORE_GLOBAL[0][2],
         CORE_GLOBAL[1][0] - CORE_GLOBAL[0][0], CORE_GLOBAL[1][2] - CORE_GLOBAL[0][2],
         CORE, None, 0.45, dash=(2, 1))
    rect(c, ox + DOCK_GLOBAL[0][0], oy + DOCK_GLOBAL[0][2],
         DOCK_GLOBAL[1][0] - DOCK_GLOBAL[0][0], DOCK_GLOBAL[1][2] - DOCK_GLOBAL[0][2],
         DOCK, None, 0.30, dash=(1, 1))
    rect(c, ox, oy + FRAME_INNER_Z, CASE_W, 2.4, CASE, Color(0.3, 0.33, 0.38, alpha=0.18), 0.35)
    rect(c, ox, oy + STRUCTURAL_DEPTH, CASE_W, SERVICE_CAP_DEPTH, HexColor("#4F6476"), None, 0.35, dash=(2, 1))
    rect(c, ox, oy + REAR_INNER_Z, CASE_W, 2.4, HexColor("#4F6476"), Color(0.3, 0.33, 0.38, alpha=0.12), 0.35)
    text(c, ox + 70, oy + CASE_DEPTH + 5, "TOP / XZ", 3.3, OUTLINE, True, "center")
    dim_h(c, ox, ox + CASE_W, oy - 8, oy, "140.00")
    dim_v(c, oy, oy + CASE_DEPTH, ox - 8, ox, f"{CASE_DEPTH:.2f}")


def right_view(c: canvas.Canvas, spec_key: str, ox: float, oy: float) -> None:
    spec, _, ly = lcd_xy(spec_key)
    rect(c, ox, oy, CASE_DEPTH, CASE_H, OUTLINE, None, 0.65)
    rect(c, ox + BEZEL_T, oy + ly, spec.module_t, spec.module_h, LCD,
         Color(0.3, 0.61, 0.91, alpha=0.20), 0.4)
    rect(c, ox + PCB_Z0, oy + DOCK_Y, DOCK_PCB_T_NOMINAL, DOCK_H, DOCK,
         Color(0.29, 0.65, 0.40, alpha=0.16), 0.45)
    rect(c, ox + CORE_GLOBAL[0][2], oy + CORE_GLOBAL[0][1],
         CORE_GLOBAL[1][2] - CORE_GLOBAL[0][2], CORE_GLOBAL[1][1] - CORE_GLOBAL[0][1],
         CORE, None, 0.45, dash=(2, 1))
    rect(c, ox + DOCK_GLOBAL[0][2], oy + DOCK_GLOBAL[0][1],
         DOCK_GLOBAL[1][2] - DOCK_GLOBAL[0][2], DOCK_GLOBAL[1][1] - DOCK_GLOBAL[0][1],
         DOCK, None, 0.30, dash=(1, 1))
    rect(c, ox + FRAME_INNER_Z, oy, 2.4, CASE_H, CASE, Color(0.3, 0.33, 0.38, alpha=0.18), 0.35)
    rect(c, ox + STRUCTURAL_DEPTH, oy, SERVICE_CAP_DEPTH, CASE_H, HexColor("#4F6476"), None, 0.35, dash=(2, 1))
    rect(c, ox + REAR_INNER_Z, oy, 2.4, CASE_H, HexColor("#4F6476"), Color(0.3, 0.33, 0.38, alpha=0.12), 0.35)
    text(c, ox + CASE_DEPTH / 2, oy + CASE_H + 4, "RIGHT / ZY", 3.3, OUTLINE, True, "center")
    dim_h(c, ox, ox + CASE_DEPTH, oy - 8, oy, f"{CASE_DEPTH:.2f}")
    dim_v(c, oy, oy + CASE_H, ox - 8, ox, f"{CASE_H:.2f}")


def three_view_sheet(c: canvas.Canvas, spec_key: str, sheet: str) -> None:
    label = "4.3-INCH" if spec_key == "43" else "5.0-INCH"
    page_frame(c, f"{label} COMPLETE ASSEMBLY - THREE VIEW", sheet, "1:1")
    front_view(c, spec_key, 30, 150)
    top_view(c, spec_key, 30, 82)
    right_view(c, spec_key, 202, 150)
    notes_block(c, 263, 249, "VIEW KEY", [
        "Blue: exact official LCD envelope.",
        "Green solid: official 95 x 73 Dock PCB.",
        "Orange dashed: official installed Core envelope.",
        "Green short-dash: complete Dock STEP envelope.",
        "Purple: printed Dock tray.",
        "Gray: printed enclosure.",
    ], [
        "Orthographic geometry is drawn at true 1:1.",
        "The STEP envelope includes ports extending below PCB.",
    ])
    calibration(c)
    c.showPage()


def draw_section(c: canvas.Canvas, parts, axis: int, value: float, ox: float, oy: float,
                 u_axis: int, v_axis: int, title: str, scale: float = 1.0,
                 u_min: float | None = None, u_max: float | None = None,
                 v_min: float | None = None, v_max: float | None = None) -> None:
    if v_min is not None and v_max is not None:
        height = (v_max - v_min) * scale
    else:
        height = (CASE_DEPTH if v_axis == 2 else CASE_H) * scale
    text(c, ox, oy + height + 5, title, 3.3, OUTLINE, True)
    if u_min is not None and u_max is not None:
        width = (u_max - u_min) * scale
    else:
        width = (CASE_W if u_axis == 0 else CASE_DEPTH) * scale
    c.saveState()
    clip = c.beginPath()
    clip.rect(ox * MM, oy * MM, width * MM, height * MM)
    c.clipPath(clip, stroke=0, fill=0)
    for part in parts:
        color = next((col for key, col in PART_COLORS.items() if key in part.name), OUTLINE)
        for a, b in section_segments(part.triangles, axis, value):
            au, av, bu, bv = a[u_axis], a[v_axis], b[u_axis], b[v_axis]
            if u_min is not None and max(au, bu) < u_min: continue
            if u_max is not None and min(au, bu) > u_max: continue
            if v_min is not None and max(av, bv) < v_min: continue
            if v_max is not None and min(av, bv) > v_max: continue
            base_u = u_min or 0.0
            base_v = v_min or 0.0
            line(c, ox + (au - base_u) * scale, oy + (av - base_v) * scale,
                 ox + (bu - base_u) * scale, oy + (bv - base_v) * scale,
                 color, 0.24 if "Official Dock" in part.name else 0.38)
    c.restoreState()


def section_sheet(c: canvas.Canvas, input_dir: Path, dock_stl: Path | None, spec_key: str, sheet: str) -> None:
    label = "4.3-INCH" if spec_key == "43" else "5.0-INCH"
    page_frame(c, f"{label} COMPLETE ASSEMBLY - EXACT SECTIONS", sheet, "1:1; details 4:1")
    parts = assembled_parts(input_dir, dock_stl, spec_key)
    draw_section(c, parts, 1, 56.0, 25, 211, 0, 2, "A-A  Y=56.00  XZ CENTRAL SECTION - 1:1")
    dim_h(c, 25, 165, 204, 211, "140.00")
    dim_v(c, 211, 211 + CASE_DEPTH, 17, 25, f"{CASE_DEPTH:.2f}")
    draw_section(c, parts, 0, 70.0, 25, 91, 2, 1, "B-B  X=70.00  ZY CENTRAL SECTION - 1:1")
    dim_h(c, 25, 25 + CASE_DEPTH, 83, 91, f"{CASE_DEPTH:.2f}")
    dim_v(c, 91, 91 + CASE_H, 17, 25, f"{CASE_H:.2f}")
    draw_section(c, parts, 1, 5.0, 207, 85, 0, 2,
                 "C-C  CASE SNAP PIN - 4:1", 4.0, 0.0, 15.0, -2.0, 38.0)
    rect(c, 207, 85, 60, 160, NOTE, None, 0.25, dash=(1, 1))
    draw_section(c, parts, 0, 26.5, 285, 35, 1, 2,
                 "D-D  DOCK M2.5 SCREW BOSS - 4:1", 4.0, 2.0, 17.0, 9.0, 26.0)
    rect(c, 285, 35, 60, 68, NOTE, None, 0.25, dash=(1, 1))
    notes_block(c, 285, 249, "Z DATUMS FROM FRONT", [
        "Front outer face: 0.00",
        f"LCD: {BEZEL_T:.2f} to {BEZEL_T + LCDS[spec_key].module_t:.2f}",
        f"Retainer rear: {BEZEL_T + LCDS[spec_key].module_t + LCDS[spec_key].retainer_t:.2f}",
        f"Tray: {BEZEL_T + FRONT_DEPTH:.2f} to {BEZEL_T + FRONT_DEPTH + TRAY_T:.2f}",
        f"Dock PCB: {PCB_Z0:.2f} to {PCB_Z1:.2f}",
        f"Core STEP: {CORE_GLOBAL[0][2]:.3f} to {CORE_GLOBAL[1][2]:.3f}",
        f"Dock+Core STEP: {DOCK_GLOBAL[0][2]:.3f} to {DOCK_GLOBAL[1][2]:.3f}",
        f"Access-frame inner face: {FRAME_INNER_Z:.2f}",
        f"Access-frame latch plane: {STRUCTURAL_DEPTH:.2f}",
        f"Service-cap inner face: {REAR_INNER_Z:.2f}",
        f"Service-cap outer face: {CASE_DEPTH:.2f}",
        f"Pin overall: {PIN_TIP:.2f}; head front: {-PIN_HEAD_T:.2f}",
    ], [
        f"Minimum STEP-to-service-cap clearance: {REAR_INNER_Z - DOCK_GLOBAL[1][2]:.3f}.",
        "Dock: 4 x M2.5 x 6 pan-head; printed square pilot 2.00 x 4.80 deep.",
        ("Dock and Core are drawn as the overall envelope of the official STEP."
         if dock_stl is None else
         "Sections use STL facets generated from Sipeed STEP at 0.35 mm deflection."),
        "Printed parts use their delivered STL facets.",
    ])
    calibration(c)
    c.showPage()


def datum_sheet(c: canvas.Canvas) -> None:
    page_frame(c, "REFERENCE PLANES, ACCURACY AND ASSEMBLY ORIENTATION", "7/7", "1:1 datum bar")
    notes_block(c, 25, 250, "OFFICIAL 3D SOURCES USED", [
        "Tang_Primer_20K_Dock_3713.step - Sipeed official.",
        "Tang_Primer_20K_3690.step - Sipeed official.",
        "Dock STEP already includes Core 3690 in its installed, latched position.",
        "Core standalone-to-Dock translation: X=48.299, Y=36.344, Z=4.180.",
        "Case placement of Dock STEP: X=22.500, Y=14.500, Z=15.000.",
    ], [
        "LCD envelopes use official LCD datasheet dimensions.",
        "Dock PCB thickness measured by STEP: 1.590; support height: 3.200.",
    ])
    notes_block(c, 215, 250, "R4 SERVICE VOLUME", [
        "Pinned structural frame remains at Z=33.800.",
        "Official installed Dock STEP reaches Z=30.165 in case coordinates.",
        "Removable service cap adds 20.000 behind that frame.",
        "Service-cap inner face is Z=51.400; clearance is 21.235.",
        "Overall depth is 53.800; printed pin remains 37.000.",
    ], [
        "Two top hooks and two lower push tabs release the cap independently.",
        "Physical-fit validation is still required for FDM tolerances and cables.",
    ])
    text(c, 25, 119, "1:1 Z DATUM BAR", 4.0, OUTLINE, True)
    x, y = 30, 75
    line(c, x, y, x + CASE_DEPTH, y, OUTLINE, 1.0)
    datums = [(0, "front"), (2.4, "LCD"), (9.4, "tray"), (15.0, "PCB"),
              (22.992, "Core max"), (30.165, "STEP max"), (31.4, "frame inner"),
              (33.8, "frame/cap"), (51.4, "cap inner"), (53.8, "cap outer")]
    for z, label in datums:
        line(c, x + z, y - 4, x + z, y + 7, DIM, 0.4)
        text(c, x + z, y + 10 + (5 if label in ("STEP max", "rear inner") else 0), f"{z:.3f}\n{label}", 2.5, OUTLINE, align="center")
    dim_h(c, x, x + CASE_DEPTH, y - 15, y, f"{CASE_DEPTH:.2f}")
    calibration(c)
    c.showPage()


def generate(path: Path, input_dir: Path, dock_stl: Path | None, image43: Path, image50: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=landscape(A3), pageCompression=1)
    c.setTitle("Tang Primer 20K Case R4 Spatial Assembly, 1:1 Three Views and Sections")
    c.setAuthor("OpenAI Codex")
    spatial_sheet(c, image43, "4.3-INCH", "1/7")
    spatial_sheet(c, image50, "5.0-INCH", "2/7")
    three_view_sheet(c, "43", "3/7")
    three_view_sheet(c, "50", "4/7")
    section_sheet(c, input_dir, dock_stl, "43", "5/7")
    section_sheet(c, input_dir, dock_stl, "50", "6/7")
    datum_sheet(c)
    c.save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output/release"))
    parser.add_argument("--dock-step-stl", type=Path,
                        help="STEP-derived Dock mesh; default: the Dock envelope box")
    parser.add_argument("--image43", type=Path, default=Path("output/release/assembly_43.png"))
    parser.add_argument("--image50", type=Path, default=Path("output/release/assembly_50.png"))
    parser.add_argument("--output", type=Path, default=Path("output/release/Tang_Primer_20K_Case_R4_Spatial_Reference.pdf"))
    args = parser.parse_args()
    generate(args.output, args.input, args.dock_step_stl, args.image43, args.image50)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
