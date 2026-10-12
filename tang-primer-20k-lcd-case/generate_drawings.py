#!/usr/bin/env python3
"""Generate A3 1:1 assembly and part drawings for the enclosure."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

from generate_case import (
    ASSEMBLY_HOLES,
    BEZEL_T,
    CASE_H,
    CASE_W,
    DOCK_H,
    DOCK_HOLES,
    DOCK_W,
    DOCK_X,
    DOCK_Y,
    FRONT_DEPTH,
    LCDS,
    REAR_DEPTH,
    TRAY_T,
    WALL,
)


MM = 72.0 / 25.4
PAGE_W_MM, PAGE_H_MM = 420.0, 297.0
OUTLINE = HexColor("#20252B")
CASE = HexColor("#4B5563")
LCD = HexColor("#4C9BE8")
LCD_ACTIVE = HexColor("#B9E2FF")
DOCK = HexColor("#4AA564")
CORE = HexColor("#E8933A")
FPC = HexColor("#CC4AA3")
DIM = HexColor("#333333")
NOTE = HexColor("#8A3B12")


def mm(v: float) -> float:
    return v * MM


def rect(c: canvas.Canvas, x: float, y: float, w: float, h: float,
         stroke=OUTLINE, fill=None, width: float = 0.35, dash=None) -> None:
    c.saveState()
    c.setLineWidth(mm(width))
    c.setStrokeColor(stroke)
    if fill is not None:
        c.setFillColor(fill)
    if dash:
        c.setDash(*[mm(v) for v in dash])
    c.rect(mm(x), mm(y), mm(w), mm(h), stroke=1, fill=int(fill is not None))
    c.restoreState()


def line(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float,
         color=OUTLINE, width: float = 0.35, dash=None) -> None:
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(mm(width))
    if dash:
        c.setDash(*[mm(v) for v in dash])
    c.line(mm(x1), mm(y1), mm(x2), mm(y2))
    c.restoreState()


def circle(c: canvas.Canvas, x: float, y: float, radius: float,
           stroke=OUTLINE, fill=None, width: float = 0.35) -> None:
    c.saveState()
    c.setLineWidth(mm(width))
    c.setStrokeColor(stroke)
    if fill is not None:
        c.setFillColor(fill)
    c.circle(mm(x), mm(y), mm(radius), stroke=1, fill=int(fill is not None))
    c.restoreState()


def text(c: canvas.Canvas, x: float, y: float, value: str, size: float = 3.2,
         color=OUTLINE, bold: bool = False, align: str = "left") -> None:
    c.saveState()
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", mm(size))
    fn = {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align]
    fn(mm(x), mm(y), value)
    c.restoreState()


def wrapped(c: canvas.Canvas, x: float, y: float, lines: list[str],
            size: float = 3.4, leading: float = 5.1, color=OUTLINE,
            bullets: bool = False) -> float:
    for value in lines:
        text(c, x, y, ("- " if bullets else "") + value, size=size, color=color)
        y -= leading
    return y


def arrow(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float,
          color=OUTLINE, width: float = 0.45) -> None:
    line(c, x1, y1, x2, y2, color, width)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    for offset in (2.6, -2.6):
        a = angle + math.pi + math.radians(offset * 10)
        line(c, x2, y2, x2 + 3.0 * math.cos(a), y2 + 3.0 * math.sin(a), color, width)


def dim_h(c: canvas.Canvas, x1: float, x2: float, y: float, ref_y: float,
          label: str) -> None:
    line(c, x1, ref_y, x1, y, DIM, 0.25)
    line(c, x2, ref_y, x2, y, DIM, 0.25)
    line(c, x1, y, x2, y, DIM, 0.25)
    arrow(c, x1 + 4.0, y, x1, y, DIM, 0.3)
    arrow(c, x2 - 4.0, y, x2, y, DIM, 0.3)
    text(c, (x1 + x2) / 2, y + 1.8, label, 3.0, DIM, align="center")


def dim_v(c: canvas.Canvas, y1: float, y2: float, x: float, ref_x: float,
          label: str) -> None:
    line(c, ref_x, y1, x, y1, DIM, 0.25)
    line(c, ref_x, y2, x, y2, DIM, 0.25)
    line(c, x, y1, x, y2, DIM, 0.25)
    arrow(c, x, y1 + 4.0, x, y1, DIM, 0.3)
    arrow(c, x, y2 - 4.0, x, y2, DIM, 0.3)
    c.saveState()
    c.translate(mm(x - 1.8), mm((y1 + y2) / 2))
    c.rotate(90)
    c.setFillColor(DIM)
    c.setFont("Helvetica", mm(3.0))
    c.drawCentredString(0, 0, label)
    c.restoreState()


def page_frame(c: canvas.Canvas, title: str, sheet: str, scale: str = "1:1") -> None:
    rect(c, 8, 8, PAGE_W_MM - 16, PAGE_H_MM - 16, OUTLINE, None, 0.45)
    text(c, 14, 282, title, 5.5, OUTLINE, True)
    text(c, 405, 282, f"Sheet {sheet}  Scale {scale}  Units mm", 3.2, OUTLINE, align="right")
    line(c, 12, 275, 408, 275, OUTLINE, 0.35)
    text(c, 14, 13, "PRINT AT 100% / ACTUAL SIZE. DISABLE FIT-TO-PAGE.", 3.2, NOTE, True)
    text(c, 405, 13, "Tang Primer 20K integrated LCD enclosure", 2.8, OUTLINE, align="right")


def calibration(c: canvas.Canvas) -> None:
    x, y = 284.0, 24.0
    text(c, x, y + 8.0, "100 mm calibration bar", 3.0, OUTLINE)
    rect(c, x, y, 100.0, 4.0, OUTLINE, white, 0.35)
    for i in range(10):
        rect(c, x + i * 10.0, y, 10.0, 4.0, OUTLINE,
             black if i % 2 == 0 else white, 0.2)
    rect(c, 255.0, 20.0, 20.0, 20.0, OUTLINE, None, 0.4)
    text(c, 265.0, 42.0, "20 x 20", 2.8, OUTLINE, align="center")


def case_outline(c: canvas.Canvas, ox: float, oy: float, fill=None) -> None:
    rect(c, ox, oy, CASE_W, CASE_H, OUTLINE, fill, 0.55)
    for x, y in ASSEMBLY_HOLES:
        circle(c, ox + x, oy + y, 2.05, OUTLINE, white, 0.35)


def lcd_geometry(spec_key: str):
    spec = LCDS[spec_key]
    mx = (CASE_W - spec.module_w) / 2.0
    my = (CASE_H - spec.module_h) / 2.0
    wx = (CASE_W - spec.window_w) / 2.0
    wy = CASE_H / 2.0 + spec.window_offset_y - spec.window_h / 2.0
    return spec, mx, my, wx, wy


def draw_front_shell(c: canvas.Canvas, spec_key: str, ox: float, oy: float) -> None:
    spec, mx, my, wx, wy = lcd_geometry(spec_key)
    case_outline(c, ox, oy)
    rect(c, ox + wx, oy + wy, spec.window_w, spec.window_h, OUTLINE, None, 0.55)
    rect(c, ox + mx - 0.25, oy + my - 0.25,
         spec.module_w + 0.50, spec.module_h + 0.50,
         CASE, None, 0.3, dash=(2.0, 1.2))
    text(c, ox + CASE_W / 2, oy + CASE_H + 5.0,
         "BACK VIEW - LCD locator pocket shown dashed", 3.0, CASE, align="center")


def draw_retainer(c: canvas.Canvas, spec_key: str, ox: float, oy: float) -> None:
    spec = LCDS[spec_key]
    rect(c, ox + 4, oy + 4, 132, 84, OUTLINE, None, 0.45)
    rect(c, ox + 8, oy + 8, 124, 76, OUTLINE, None, 0.35)
    outer_w, outer_h = spec.module_w + 0.30, spec.module_h + 0.30
    inner_w, inner_h = spec.module_w - 5.0, spec.module_h - 5.0
    x = ox + (CASE_W - outer_w) / 2
    y = oy + (CASE_H - outer_h) / 2
    ix = ox + (CASE_W - inner_w) / 2
    iy = oy + (CASE_H - inner_h) / 2
    rect(c, x, y, outer_w, outer_h, OUTLINE, None, 0.45)
    rect(c, ix, iy, inner_w, inner_h, OUTLINE, None, 0.35)
    rect(c, ox + CASE_W / 2 - 40, y - 0.4, 80, 4.0, FPC, white, 0.35)
    text(c, ox + CASE_W / 2, y - 5.3, "80 FPC opening", 2.8, FPC, align="center")


def draw_dock_tray(c: canvas.Canvas, ox: float, oy: float) -> None:
    rect(c, ox, oy, CASE_W, CASE_H, OUTLINE, None, 0.55)
    rect(c, ox + 3, oy + 3, CASE_W - 6, CASE_H - 6, OUTLINE, None, 0.35)
    for x, y in ASSEMBLY_HOLES:
        circle(c, ox + x, oy + y, 1.70, OUTLINE, white, 0.35)
        circle(c, ox + x, oy + y, 4.0, CASE, None, 0.25)
    for x, y in DOCK_HOLES:
        circle(c, ox + x, oy + y, 1.05, OUTLINE, white, 0.35)
        circle(c, ox + x, oy + y, 4.0, DOCK, None, 0.25)
    rect(c, ox + 3, oy + 6, 27.5, 5, CASE, Color(0.6, 0.62, 0.65, alpha=0.25), 0.25)
    rect(c, ox + 109.5, oy + 6, 27.5, 5, CASE, Color(0.6, 0.62, 0.65, alpha=0.25), 0.25)
    rect(c, ox + 3, oy + 71, 134, 5, CASE, Color(0.6, 0.62, 0.65, alpha=0.25), 0.25)


def draw_rear(c: canvas.Canvas, ox: float, oy: float) -> None:
    rect(c, ox, oy, CASE_W, CASE_H, OUTLINE, None, 0.55)
    rect(c, ox + 3, oy + 3, CASE_W - 6, CASE_H - 6, OUTLINE, None, 0.35)
    for x, y in ASSEMBLY_HOLES:
        circle(c, ox + x, oy + y, 1.70, OUTLINE, white, 0.35)
        circle(c, ox + x, oy + y, 4.0, CASE, None, 0.25)
    for yy in (16, 24, 32, 40, 48, 56, 64, 72):
        for xx, ww in ((10, 16), (37, 71), (120, 10)):
            rect(c, ox + xx, oy + yy, ww, 2, CASE, CASE, 0.2)
    rect(c, ox + 68.5, oy + 8, 3, 76, CASE, CASE, 0.2)
    rect(c, ox + 16.6, oy - 0.4, 105.4, 4.0, NOTE, white, 0.4)
    text(c, ox + 69.3, oy - 5.5, "105.4 connector bay opening", 2.8, NOTE, align="center")


def draw_assembly_plan(c: canvas.Canvas, spec_key: str, ox: float, oy: float) -> None:
    spec, mx, my, wx, wy = lcd_geometry(spec_key)
    case_outline(c, ox, oy)
    rect(c, ox + mx, oy + my, spec.module_w, spec.module_h, LCD, Color(0.30, 0.61, 0.91, alpha=0.18), 0.55)
    rect(c, ox + wx, oy + wy, spec.window_w, spec.window_h, LCD_ACTIVE,
         Color(0.73, 0.89, 1.0, alpha=0.35), 0.35)
    rect(c, ox + DOCK_X, oy + DOCK_Y, DOCK_W, DOCK_H, DOCK,
         Color(0.29, 0.65, 0.40, alpha=0.16), 0.55, dash=(2.0, 1.2))
    for x, y in DOCK_HOLES:
        circle(c, ox + x, oy + y, 1.25, DOCK, white, 0.4)
    # Core outline is accurate. Its centered plan position is explanatory only
    # because the official 2D dimension sheet does not give the SODIMM datum.
    core_w, core_h = 67.60, 30.00
    core_x = DOCK_X + (DOCK_W - core_w) / 2.0
    core_y = DOCK_Y + (DOCK_H - core_h) / 2.0
    rect(c, ox + core_x, oy + core_y, core_w, core_h, CORE,
         Color(0.91, 0.58, 0.23, alpha=0.22), 0.6)
    arrow(c, ox + CASE_W / 2, oy + my + 1.0, ox + CASE_W / 2,
          oy + DOCK_Y + 6.0, FPC, 0.8)
    text(c, ox + CASE_W / 2 + 2, oy + DOCK_Y + 8, "RGB FPC", 2.8, FPC)
    text(c, ox + mx + 2, oy + my + spec.module_h - 5, f"{spec.module_w:.2f} x {spec.module_h:.2f} LCD", 3.0, LCD, True)
    text(c, ox + DOCK_X + 2, oy + DOCK_Y + DOCK_H - 5, "95 x 73 Dock", 3.0, DOCK, True)
    text(c, ox + core_x + core_w / 2, oy + core_y + core_h / 2 - 1,
         "67.60 x 30.00", 3.0, CORE, True, "center")
    text(c, ox + core_x + core_w / 2, oy + core_y + core_h / 2 - 5,
         "Tang Primer core", 2.8, CORE, False, "center")


def notes_block(c: canvas.Canvas, x: float, y: float, title: str, lines: list[str],
                warning: list[str] | None = None) -> None:
    text(c, x, y, title, 4.2, OUTLINE, True)
    y -= 7
    y = wrapped(c, x, y, lines, 3.2, 5.3, OUTLINE, True)
    if warning:
        y -= 2
        text(c, x, y, "VERIFY BEFORE FINAL PRINT", 3.4, NOTE, True)
        y -= 6
        wrapped(c, x, y, warning, 3.1, 5.0, NOTE, True)


def sheet_overview(c: canvas.Canvas) -> None:
    page_frame(c, "ASSEMBLY ORDER AND SIZE STATUS", "1/10", "1:1 section + NTS guide")
    # Exploded stack guide, deliberately not to scale.
    x, y = 30, 239
    layers = [
        ("FRONT SHELL", CASE),
        ("LCD", LCD),
        ("LCD RETAINER", CASE),
        ("DOCK TRAY", CASE),
        ("DOCK PCB", DOCK),
        ("TANG PRIMER CORE", CORE),
        ("REAR COVER", CASE),
    ]
    for i, (label, color) in enumerate(layers):
        yy = y - i * 20
        rect(c, x, yy, 110, 10, color, Color(color.red, color.green, color.blue, alpha=0.15), 0.55)
        text(c, x + 55, yy + 3.2, label, 3.0, color, True, "center")
        if i < len(layers) - 1:
            arrow(c, x + 55, yy - 1, x + 55, yy - 8, OUTLINE, 0.5)
    text(c, x + 55, 109, "Exploded order - visual guide, NTS", 3.0, NOTE, True, "center")
    # Explicitly show the action that was easy to miss in a simple layer stack.
    text(c, 25, 88, "CORE INSTALLATION DETAIL - NTS", 3.3, OUTLINE, True)
    rect(c, 25, 56, 80, 26, DOCK, Color(0.29, 0.65, 0.40, alpha=0.15), 0.45)
    rect(c, 67, 65, 5, 8, OUTLINE, Color(0.20, 0.22, 0.25, alpha=0.35), 0.35)
    text(c, 27, 58, "Dock PCB", 2.8, DOCK, True)
    rect(c, 113, 63, 30, 12, CORE, Color(0.91, 0.58, 0.23, alpha=0.20), 0.45)
    text(c, 128, 67, "Core", 2.8, CORE, True, "center")
    arrow(c, 112, 69, 73, 69, CORE, 0.7)
    text(c, 84, 76, "Insert card edge into Dock SODIMM", 2.8, CORE, True, "center")
    text(c, 25, 49, "Do this before fitting the rear cover; Dock component side faces rear.", 2.8, NOTE)
    notes_block(c, 175, 250, "WHAT IS DIMENSIONALLY LOCKED", [
        "Case envelope: 140.00 x 92.00 x 29.80 nominal.",
        "Dock PCB: 95.00 x 73.00; M2.5 pitch 87.00 x 65.00.",
        "Tang Primer core PCB outline: 67.60 x 30.00.",
        "4.3 LCD: 105.40 x 67.10 x 2.90.",
        "5.0 LCD: 120.70 x 75.90 x 3.05.",
        "LCD pocket clearance: 0.25 per side nominal.",
    ], [
        "Core plan placement is schematic; official 2D sheet lacks",
        "the Dock SODIMM connector datum and component-height stack.",
        "Ethernet, DC jack and FPC bend need a physical test fit.",
    ])
    text(c, 175, 112, "INSTALLATION", 4.2, OUTLINE, True)
    wrapped(c, 175, 105, [
        "1. Put LCD into front shell from the rear; FPC exits downward.",
        "2. Add matching LCD retainer, then common Dock tray.",
        "3. Fix Dock to four printed M2.5 standoffs, component side rearward.",
        "4. Insert Tang Primer core into Dock SODIMM connector.",
        "5. Route LCD FPC through tray window to DISPLAY connector.",
        "6. Close rear cover with four M3 x 25 screws.",
    ], 3.2, 5.5, OUTLINE)
    calibration(c)
    c.showPage()


def sheet_assembly(c: canvas.Canvas, spec_key: str, sheet: str) -> None:
    label = "4.3-INCH" if spec_key == "43" else "5.0-INCH"
    page_frame(c, f"{label} COMPLETE ASSEMBLY - FRONT PROJECTION", sheet)
    ox, oy = 22, 83
    draw_assembly_plan(c, spec_key, ox, oy)
    dim_h(c, ox, ox + CASE_W, oy - 9, oy, "140.00")
    dim_v(c, oy, oy + CASE_H, ox - 9, ox, "92.00")
    spec = LCDS[spec_key]
    notes_block(c, 182, 247, "COLOR KEY / ASSEMBLY RELATION", [
        f"Blue: official {label.lower()} LCD outer envelope.",
        "Green dashed: official Dock PCB outer envelope.",
        "Orange: Tang Primer 20K core PCB envelope.",
        "Magenta arrow: LCD FPC route toward Dock DISPLAY connector.",
        "Four corner circles: M3 case screws.",
        "Four green circles: M2.5 Dock mounting holes.",
    ], [
        "Core outline size is 1:1, but its orange plan location is",
        "schematic until verified against the Dock STEP or hardware.",
        f"LCD thickness is {spec.module_t:.2f}; see side section on sheet 10.",
    ])
    text(c, 182, 118, "PARTS USED", 4.2, OUTLINE, True)
    wrapped(c, 182, 111, [
        f"front_shell_{spec_key}.stl",
        f"lcd_retainer_{spec_key}.stl",
        "dock_tray_common.stl",
        "rear_cover_common.stl",
    ], 3.3, 5.5, OUTLINE, True)
    calibration(c)
    c.showPage()


def sheet_front(c: canvas.Canvas, spec_key: str, sheet: str) -> None:
    label = "4.3-INCH" if spec_key == "43" else "5.0-INCH"
    page_frame(c, f"FRONT SHELL {label} - PART DRAWING", sheet)
    ox, oy = 22, 83
    draw_front_shell(c, spec_key, ox, oy)
    dim_h(c, ox, ox + CASE_W, oy - 9, oy, "140.00")
    dim_v(c, oy, oy + CASE_H, ox - 9, ox, "92.00")
    spec, mx, my, wx, wy = lcd_geometry(spec_key)
    dim_h(c, ox + wx, ox + wx + spec.window_w, oy + wy - 7, oy + wy, f"window {spec.window_w:.2f}")
    dim_v(c, oy + wy, oy + wy + spec.window_h, ox + wx - 7, ox + wx, f"window {spec.window_h:.2f}")
    notes_block(c, 182, 247, f"front_shell_{spec_key}.stl", [
        f"LCD pocket: {spec.module_w + 0.50:.2f} x {spec.module_h + 0.50:.2f}.",
        "Nominal LCD clearance: 0.25 each side.",
        f"Bezel plate: {BEZEL_T:.2f} thick.",
        f"Rear wall depth from bezel: {FRONT_DEPTH:.2f}.",
        f"Overall part depth: {BEZEL_T + FRONT_DEPTH:.2f}.",
        "M3 insert pilot: 4.10 diameter, four places.",
        "FPC locator opening: 80.00 wide at lower edge.",
    ], [
        "Print this PDF at 100% and place the real LCD over the",
        "dashed pocket outline before committing to the full print.",
    ])
    calibration(c)
    c.showPage()


def sheet_retainer(c: canvas.Canvas, spec_key: str, sheet: str) -> None:
    label = "4.3-INCH" if spec_key == "43" else "5.0-INCH"
    page_frame(c, f"LCD RETAINER {label} - PART DRAWING", sheet)
    ox, oy = 22, 83
    draw_retainer(c, spec_key, ox, oy)
    dim_h(c, ox + 4, ox + 136, oy - 9, oy + 4, "132.00 outer pressure ring")
    dim_v(c, oy + 4, oy + 88, ox - 9, ox + 4, "84.00")
    spec = LCDS[spec_key]
    notes_block(c, 182, 247, f"lcd_retainer_{spec_key}.stl", [
        "Outer pressure ring: 132.00 x 84.00.",
        f"LCD edge ring outer: {spec.module_w + 0.30:.2f} x {spec.module_h + 0.30:.2f}.",
        f"LCD edge ring inner: {spec.module_w - 5.0:.2f} x {spec.module_h - 5.0:.2f}.",
        f"Part thickness: {spec.retainer_t:.2f}.",
        "Lower FPC opening: 80.00 wide.",
        "Four spokes transfer tray pressure to LCD edge ring.",
    ], [
        "Use thin PET or polyimide insulation at the LCD metal edge.",
        "Retainer should contact the LCD edge, not the active area.",
    ])
    calibration(c)
    c.showPage()


def sheet_tray(c: canvas.Canvas) -> None:
    page_frame(c, "COMMON DOCK TRAY - PART + BOARD OVERLAY", "8/10")
    ox, oy = 22, 83
    draw_dock_tray(c, ox, oy)
    rect(c, ox + DOCK_X, oy + DOCK_Y, DOCK_W, DOCK_H, DOCK, None, 0.55, dash=(2, 1.2))
    for x, y in DOCK_HOLES:
        circle(c, ox + x, oy + y, 1.25, DOCK, white, 0.4)
    dim_h(c, ox, ox + CASE_W, oy - 9, oy, "140.00")
    dim_v(c, oy, oy + CASE_H, ox - 9, ox, "92.00")
    dim_h(c, ox + DOCK_HOLES[0][0], ox + DOCK_HOLES[1][0], oy + 16, oy + 8.5, "87.00 M2.5 pitch")
    dim_v(c, oy + DOCK_HOLES[0][1], oy + DOCK_HOLES[2][1], ox + 119, ox + DOCK_HOLES[1][0], "65.00")
    notes_block(c, 182, 247, "dock_tray_common.stl", [
        "Tray envelope: 140.00 x 92.00 x 2.40.",
        "Green dashed Dock envelope: 95.00 x 73.00.",
        "Dock location from case lower-left: 22.50, 4.50.",
        "Dock mounting: M2.5 x 4; pilot diameter 2.10.",
        "Printed standoff: 8.00 outer diameter x 3.20 high.",
        "Lower crossbar split leaves 79.00 nominal FPC route.",
    ], [
        "Dock PCB outline and hole pitch are from official drawing.",
        "Check port reach and component clearance on actual PCB revision.",
    ])
    calibration(c)
    c.showPage()


def sheet_rear(c: canvas.Canvas) -> None:
    page_frame(c, "COMMON REAR COVER - PART DRAWING", "9/10")
    ox, oy = 22, 83
    draw_rear(c, ox, oy)
    dim_h(c, ox, ox + CASE_W, oy - 11, oy, "140.00")
    dim_v(c, oy, oy + CASE_H, ox - 9, ox, "92.00")
    notes_block(c, 182, 247, "rear_cover_common.stl", [
        "Envelope: 140.00 x 92.00 x 18.00.",
        "Wall and rear-face thickness: 2.40 nominal.",
        "Bottom connector bay: x=16.60 to 122.00.",
        "Rear slots provide ventilation and control access.",
        "M3 screw clearance: 3.40 diameter, four places.",
        "Internal screw bosses: 8.00 outer diameter.",
    ], [
        "The bottom bay intentionally groups DC, Ethernet and USB",
        "access. Verify each plug shell and cable bend on hardware.",
    ])
    calibration(c)
    c.showPage()


def sheet_section(c: canvas.Canvas) -> None:
    page_frame(c, "COMPLETE ASSEMBLY - 1:1 SIDE SECTION", "10/10")
    ox, oy = 54, 78
    # Full section: horizontal is enclosure depth, vertical is case height.
    rect(c, ox, oy, BEZEL_T, CASE_H, CASE, Color(0.30, 0.33, 0.38, alpha=0.30), 0.45)
    rect(c, ox + BEZEL_T, oy, FRONT_DEPTH, CASE_H, CASE, Color(0.30, 0.33, 0.38, alpha=0.12), 0.45)
    rect(c, ox + BEZEL_T + FRONT_DEPTH, oy, TRAY_T, CASE_H, CASE, Color(0.30, 0.33, 0.38, alpha=0.28), 0.45)
    rect(c, ox + BEZEL_T + FRONT_DEPTH + TRAY_T, oy, REAR_DEPTH, CASE_H, CASE, Color(0.30, 0.33, 0.38, alpha=0.10), 0.45)
    # Representative LCD and retainer stack inside front cavity.
    rect(c, ox + BEZEL_T, oy + 11, 3.05, 75.90, LCD, Color(0.30, 0.61, 0.91, alpha=0.45), 0.45)
    rect(c, ox + BEZEL_T + 3.05, oy + 11, 3.85, 75.90, CASE, Color(0.30, 0.33, 0.38, alpha=0.28), 0.35)
    tray_back = ox + BEZEL_T + FRONT_DEPTH + TRAY_T
    rect(c, tray_back + 3.2, oy + DOCK_Y, 1.6, DOCK_H, DOCK,
         Color(0.29, 0.65, 0.40, alpha=0.35), 0.45)
    rect(c, tray_back + 6.0, oy + 31, 1.6, 30, CORE,
         Color(0.91, 0.58, 0.23, alpha=0.42), 0.45)
    line(c, ox + BEZEL_T + 1.5, oy + 13, tray_back + 4.0, oy + 16, FPC, 0.9)
    dim_h(c, ox, ox + 29.8, oy - 10, oy, "29.80 nominal assembled depth")
    dim_v(c, oy, oy + CASE_H, ox - 10, ox, "92.00")
    text(c, ox + 1.2, oy + 95, "FRONT", 3.0, OUTLINE, True, "center")
    text(c, ox + 20.8, oy + 95, "REAR", 3.0, OUTLINE, True, "center")
    # Layer leader labels.
    labels = [
        (BEZEL_T / 2, "2.40 bezel"),
        (BEZEL_T + FRONT_DEPTH / 2, "7.00 front cavity"),
        (BEZEL_T + FRONT_DEPTH + TRAY_T / 2, "2.40 tray"),
        (BEZEL_T + FRONT_DEPTH + TRAY_T + REAR_DEPTH / 2, "18.00 rear cover"),
    ]
    for idx, (dx, label) in enumerate(labels):
        arrow(c, 112, 237 - idx * 13, ox + dx, oy + 88 - idx * 5, OUTLINE, 0.4)
        text(c, 115, 235 - idx * 13, label, 3.1, OUTLINE)
    notes_block(c, 182, 247, "SECTION INTERPRETATION", [
        "Section geometry and enclosure depth are drawn at true 1:1.",
        "Blue: worst-case 5.0 LCD, 3.05 thick.",
        "Green: nominal Dock PCB, assumed 1.60 PCB thickness.",
        "Orange: core PCB, shown as 1.60 nominal thickness.",
        "Magenta: representative FPC route, bend shape not controlled.",
        "LCD and retainer occupy the 7.00 front cavity.",
        "Dock standoffs project 3.20 into the rear cavity.",
    ], [
        "Dock/core connector height and component envelopes are not",
        "defined by the official 2D sheets. The colored board stack",
        "is an explanatory envelope and must be checked physically.",
    ])
    calibration(c)
    c.showPage()


def generate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=landscape(A3), pageCompression=1)
    c.setTitle("Tang Primer 20K Case 1:1 Drawings")
    c.setAuthor("OpenAI Codex")
    sheet_overview(c)
    sheet_assembly(c, "43", "2/10")
    sheet_assembly(c, "50", "3/10")
    sheet_front(c, "43", "4/10")
    sheet_retainer(c, "43", "5/10")
    sheet_front(c, "50", "6/10")
    sheet_retainer(c, "50", "7/10")
    sheet_tray(c)
    sheet_rear(c)
    sheet_section(c)
    c.save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path("output/pdf/Tang_Primer_20K_Case_1to1_Drawings.pdf"))
    args = parser.parse_args()
    generate(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
