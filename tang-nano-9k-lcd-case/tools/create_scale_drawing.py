#!/usr/bin/env python3
"""Create an A4 vector drawing pack whose mechanical views are true 1:1.

All drawing coordinates are expressed in millimetres and converted directly
to PDF points through reportlab.lib.units.mm.  Decorative title blocks are not
to scale; every mechanical view is explicitly labelled SCALE 1:1.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.assembly_sections import (  # noqa: E402
    assembly_parts,
    mechanical_cells,
    section_by_code,
    section_definitions,
)
from tools import generate_stl as model  # noqa: E402
from tools.font_paths import dejavu_sans  # noqa: E402
from tools.profiles import PROFILES, CaseProfile, get_profile  # noqa: E402


# Profile-independent reference dimensions (mm).  LCD-dependent values are
# read from the CaseProfile passed to each drawing function.
BOARD_L = model.PCB_H
BOARD_W = model.PCB_W
BOARD_T = model.PCB_T  # nominal PCB thickness; connector heights require hardware check
BEZEL_T = model.BEZEL_T
BODY_D = model.BODY_D
RETAINER_T = 2.0
COVER_T = 2.0

INK = colors.HexColor("#263238")
DIM = colors.HexColor("#1565c0")
HIDDEN = colors.HexColor("#78909c")
LCD = colors.HexColor("#b3e5fc")
PCB = colors.HexColor("#a5d6a7")
PART = colors.HexColor("#eceff1")
RETAINER = colors.HexColor("#ffe0b2")
ALERT = colors.HexColor("#c62828")
REFERENCE = colors.HexColor("#ef6c00")
REFERENCE_FILL = colors.HexColor("#fff3e0")
FPC = colors.HexColor("#f9a825")
TOTAL_PAGES = 10

SECTION_FILLS = {
    "chassis": colors.HexColor("#cfd8dc"),
    "lcd": LCD,
    "retainer": RETAINER,
    "pcb": PCB,
    "cover": colors.HexColor("#b0bec5"),
}


# Drawing extents, recorded in millimetres while ``recorded_bounds`` runs so
# that tests can check every view against the sheet frame.
Bounds = tuple[int, float, float, float, float]
_RECORDED: list[Bounds] | None = None
_RECORD_PAUSED = 0


def record_bounds(c: Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
    if _RECORDED is not None and not _RECORD_PAUSED:
        _RECORDED.append((c.getPageNumber(), min(x0, x1), min(y0, y1),
                          max(x0, x1), max(y0, y1)))


@contextmanager
def unrecorded() -> Iterator[None]:
    """Exclude sheet furniture such as the frame and title block."""
    global _RECORD_PAUSED
    _RECORD_PAUSED += 1
    try:
        yield
    finally:
        _RECORD_PAUSED -= 1


def recorded_bounds(draw: Callable[[], None]) -> list[Bounds]:
    """Run ``draw`` and return the extents of every recorded primitive."""
    global _RECORDED
    _RECORDED = []
    try:
        draw()
        return _RECORDED
    finally:
        _RECORDED = None


def text_bounds(c: Canvas, x: float, y: float, text: str, size: float,
                font: str, align: str) -> None:
    width = pdfmetrics.stringWidth(text, font, size) / mm
    x0 = {"left": x, "center": x - width / 2.0, "right": x - width}[align]
    height = size / mm
    record_bounds(c, x0, y - 0.25 * height, x0 + width, y + 0.8 * height)


def tx(value: float) -> float:
    return value * mm


def dim_text(value: float) -> str:
    """Format a dimension with two decimals, or three when required."""
    return f"{value:.2f}" if abs(round(value, 2) - value) < 1e-9 else f"{value:.3f}"


def rect(c: Canvas, x: float, y: float, w: float, h: float, *,
         stroke=INK, fill=None, width=0.35, dash=None, radius=0.0) -> None:
    record_bounds(c, x, y, x + w, y + h)
    c.saveState()
    c.setStrokeColor(stroke)
    c.setLineWidth(width)
    if dash:
        c.setDash(*dash)
    if fill is not None:
        c.setFillColor(fill)
    if radius:
        c.roundRect(tx(x), tx(y), tx(w), tx(h), tx(radius),
                    stroke=1, fill=int(fill is not None))
    else:
        c.rect(tx(x), tx(y), tx(w), tx(h), stroke=1, fill=int(fill is not None))
    c.restoreState()


def line(c: Canvas, x0: float, y0: float, x1: float, y1: float,
         *, color=INK, width=0.35, dash=None) -> None:
    record_bounds(c, x0, y0, x1, y1)
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(width)
    if dash:
        c.setDash(*dash)
    c.line(tx(x0), tx(y0), tx(x1), tx(y1))
    c.restoreState()


def label(c: Canvas, x: float, y: float, text: str, size=7.0,
          *, color=INK, align="left", font="DejaVu") -> None:
    text_bounds(c, x, y, text, size, font, align)
    c.saveState()
    c.setFillColor(color)
    c.setFont(font, size)
    method = {"left": c.drawString, "center": c.drawCentredString,
              "right": c.drawRightString}[align]
    method(tx(x), tx(y), text)
    c.restoreState()


def arrow(c: Canvas, x0: float, y0: float, x1: float, y1: float,
          *, color=DIM, width=0.6) -> None:
    line(c, x0, y0, x1, y1, color=color, width=width)
    import math
    angle = math.atan2(y1 - y0, x1 - x0)
    for px, py, a in ((x0, y0, angle), (x1, y1, angle + math.pi)):
        wing = 2.0
        for delta in (-0.45, 0.45):
            line(c, px, py, px + wing * math.cos(a + delta),
                 py + wing * math.sin(a + delta), color=color, width=width)


def dim_h(c: Canvas, x0: float, x1: float, y: float, source_y: float,
          text: str) -> None:
    line(c, x0, source_y, x0, y, color=DIM, width=0.25)
    line(c, x1, source_y, x1, y, color=DIM, width=0.25)
    arrow(c, x0, y, x1, y, color=DIM, width=0.35)
    label(c, (x0 + x1) / 2, y + 1.3, text, 6.5, color=DIM, align="center",
          font="Helvetica")


def dim_v(c: Canvas, y0: float, y1: float, x: float, source_x: float,
          text: str) -> None:
    line(c, source_x, y0, x, y0, color=DIM, width=0.25)
    line(c, source_x, y1, x, y1, color=DIM, width=0.25)
    arrow(c, x, y0, x, y1, color=DIM, width=0.35)
    width = pdfmetrics.stringWidth(text, "Helvetica", 6.5) / mm
    height = 6.5 / mm
    record_bounds(c, x - 1.3 - 0.8 * height, (y0 + y1 - width) / 2,
                  x - 1.3 + 0.25 * height, (y0 + y1 + width) / 2)
    c.saveState()
    c.translate(tx(x - 1.3), tx((y0 + y1) / 2))
    c.rotate(90)
    c.setFillColor(DIM)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def page_header(c: Canvas, page: int, title: str, subtitle: str) -> None:
    with unrecorded():
        _page_header(c, page, title, subtitle)


def _page_header(c: Canvas, page: int, title: str, subtitle: str) -> None:
    page_w, page_h = landscape(A4)
    c.setStrokeColor(INK)
    c.setLineWidth(0.5)
    c.rect(tx(7), tx(7), page_w - tx(14), page_h - tx(14), stroke=1, fill=0)
    label(c, 11, 198, title, 13)
    label(c, 11, 192.5, subtitle, 7, color=HIDDEN)
    label(c, 286, 198, f"SHEET {page}/{TOTAL_PAGES}", 7, align="right", font="Helvetica")
    label(c, 286, 192.5, "UNITS mm   SCALE 1:1", 7, align="right", font="Helvetica")
    line(c, 7, 188.5, 290, 188.5, width=0.5)
    label(c, 11, 10.2,
          "PRINT: A4 LANDSCAPE / ACTUAL SIZE (100%) / FIT TO PAGE OFF. VERIFY THE 100 mm LINE.",
          6.5, color=ALERT)
    line(c, 181, 11.0, 281, 11.0, color=INK, width=1.0)
    for x in range(181, 282, 10):
        tick = 2.7 if x in (181, 281) else 1.7
        line(c, x, 11.0, x, 11.0 + tick, color=INK, width=0.5)
    label(c, 231, 14.3, "CALIBRATION 100.0 mm", 6.5, align="center", font="Helvetica")


def finish_page(c: Canvas) -> None:
    c.showPage()


def polyline(c: Canvas, points: tuple[tuple[float, float], ...], *,
             color=INK, width=0.35, dash=None) -> None:
    for start, end in zip(points, points[1:]):
        line(c, *start, *end, color=color, width=width, dash=dash)


def draw_exact_section(c: Canvas, p: CaseProfile, code: str, x: float, y: float,
                       *, scale: float = 1.0,
                       clip_h: tuple[float, float] | None = None,
                       clip_z: tuple[float, float] | None = None,
                       show_reference_envelopes: bool = True,
                       rear_clearance: float = model.STANDARD_REAR_CLEARANCE) -> None:
    """Draw a section evaluated from the same CSG boxes as the STL files."""
    section = section_by_code(p, code)
    default_h = (0.0, p.bezel_h) if section.plane == "x" else (0.0, p.bezel_w)
    h_min, h_max = clip_h or default_h
    z_min, z_max = clip_z or (0.0, model.overall_depth(rear_clearance))

    assembled = assembly_parts(p, rear_clearance=rear_clearance)
    for part, cells in mechanical_cells(section, assembled):
        fill = SECTION_FILLS[part.fill_key]
        for h0, z0, w, h in cells:
            ch0, ch1 = max(h0, h_min), min(h0 + w, h_max)
            cz0, cz1 = max(z0, z_min), min(z0 + h, z_max)
            if ch0 < ch1 and cz0 < cz1:
                rect(c, x + (ch0 - h_min) * scale,
                     y + (cz0 - z_min) * scale,
                     (ch1 - ch0) * scale, (cz1 - cz0) * scale,
                     fill=fill, width=0.22)

    # These dashed volumes describe electronics only. Their dimensions are
    # deliberately separated from verified PCB/LCD mechanical geometry.
    if show_reference_envelopes:
        if code == "A-A":
            for y0, z0, w, h, text_value in (
                (p.pcb_y - 3.0, 16.4, 4.0, 5.8, "USB-C REF"),
                (p.pcb_y + BOARD_L - 1.0, 15.8, 4.0, 6.6, "HDMI REF"),
                (p.pcb_y + 4.5, 14.4, 61.0, 4.0, "COMPONENT ENVELOPE"),
                (p.pcb_y + 24.5, 20.0, 20.0, 2.4, "microSD REF"),
            ):
                rect(c, x + (y0 - h_min) * scale, y + (z0 - z_min) * scale,
                     w * scale, h * scale, stroke=REFERENCE, fill=REFERENCE_FILL,
                     dash=(2, 1), width=0.45)
                if scale >= 1.0:
                    label(c, x + (y0 + w / 2 - h_min) * scale,
                          y + (z0 + h + 1.2 - z_min) * scale,
                          text_value, 5.0, color=REFERENCE,
                          align="center", font="Helvetica")
            # Reference FPC corridor from the LCD edge that carries the FPC
            # toward the PCB.
            if p.lcd.fpc_side == "top":
                fpc_y, inward = p.lcd_y + p.lcd.height - 1.075, -1.0
            else:
                fpc_y, inward = p.lcd_y + 1.075, 1.0
            lcd_rear_z = BEZEL_T + p.lcd.thickness
            polyline(c, (
                (x + (fpc_y - h_min) * scale, y + (lcd_rear_z - z_min) * scale),
                (x + (fpc_y - h_min) * scale, y + (12.0 - z_min) * scale),
                (x + (fpc_y + inward * 16.0 - h_min) * scale, y + (16.0 - z_min) * scale),
            ), color=FPC, width=0.7, dash=(2, 1))
            label(c, x + (fpc_y + inward * 8.0 - h_min) * scale,
                  y + (12.8 - z_min) * scale, "FPC ROUTE (REF)", 5.0,
                  color=FPC, font="Helvetica")
        elif code in ("B-B", "C-C"):
            rect(c, x + (p.pcb_x - h_min) * scale,
                 y + (14.4 - z_min) * scale,
                 BOARD_W * scale, 4.0 * scale, stroke=REFERENCE, fill=REFERENCE_FILL,
                 dash=(2, 1), width=0.45)
            rect(c, x + (p.pcb_x + 5.0 - h_min) * scale,
                 y + (20.0 - z_min) * scale,
                 16.0 * scale, 2.4 * scale, stroke=REFERENCE, fill=REFERENCE_FILL,
                 dash=(2, 1), width=0.45)
        elif code == "D-D":
            rect(c, x + (p.pcb_x + 5.0 - h_min) * scale,
                 y + (20.0 - z_min) * scale,
                 16.0 * scale, 2.4 * scale, stroke=REFERENCE, fill=REFERENCE_FILL,
                 dash=(2, 1), width=0.45)
        elif code == "E-E":
            # M2 screws are optional hardware, shown as reference shafts.  The
            # boss and pilot-bore geometry underneath is STL-derived.
            for screw_x in (p.pcb_x + model.PCB_MOUNT_HOLE_EDGE_OFFSET,
                            p.pcb_x + BOARD_W - model.PCB_MOUNT_HOLE_EDGE_OFFSET):
                rect(c, x + (screw_x - h_min - 1.0) * scale,
                     y + (17.40 - z_min) * scale,
                     2.0 * scale, 8.60 * scale,
                     stroke=DIM, fill=colors.HexColor("#e3f2fd"),
                     dash=(2, 1), width=0.40)

    # Datum axes are outside the material and remain true to the view scale.
    line(c, x, y - 1.5, x + (h_max - h_min) * scale, y - 1.5,
         color=HIDDEN, width=0.25)
    line(c, x - 1.5, y, x - 1.5, y + (z_max - z_min) * scale,
         color=HIDDEN, width=0.25)


def section_legend(c: Canvas, x: float, y: float) -> None:
    items = (
        (SECTION_FILLS["chassis"], "FRONT CHASSIS"),
        (LCD, "LCD VERIFIED BODY"),
        (RETAINER, "LCD RETAINER"),
        (PCB, "PCB 70 x 26 x 1.6"),
        (SECTION_FILLS["cover"], "REAR COVER / CARRIER"),
    )
    for index, (fill, text_value) in enumerate(items):
        yy = y - index * 7.0
        rect(c, x, yy - 1.0, 6.0, 4.0, fill=fill, width=0.25)
        label(c, x + 9.0, yy, text_value, 5.8, font="Helvetica")
    rect(c, x, y - 36.0, 6.0, 4.0, stroke=REFERENCE, dash=(2, 1))
    label(c, x + 9.0, y - 35.0, "REFERENCE ENVELOPE — VERIFY ON HARDWARE",
          5.8, color=REFERENCE, font="Helvetica")


def draw_lcd(c: Canvas, p: CaseProfile, x: float, y: float, with_dims=True) -> None:
    lcd = p.lcd
    rect(c, x, y, lcd.width, lcd.height, fill=LCD, radius=1.0)
    rect(c, x + lcd.active_x, y + lcd.active_y,
         lcd.active_w, lcd.active_h, fill=colors.white, width=0.5)
    label(c, x + lcd.width / 2, y + lcd.height / 2 + 1.2,
          f"{lcd.name} reference LCD", 7, align="center", font="Helvetica")
    label(c, x + lcd.width / 2, y + lcd.height / 2 - 2.2,
          f"ACTIVE AREA {dim_text(lcd.active_w)} x {dim_text(lcd.active_h)}",
          6.2, color=HIDDEN, align="center", font="Helvetica")
    # FPC tail location is diagrammatic; width relief is the enclosure value.
    fpc_w = lcd.fpc_x1 - lcd.fpc_x0
    fpc_y = y + lcd.height if lcd.fpc_side == "top" else y - 4.0
    rect(c, x + lcd.fpc_x0, fpc_y, fpc_w, 4.0,
         stroke=HIDDEN, fill=colors.HexColor("#fff9c4"), dash=(2, 1))
    label(c, x + lcd.fpc_x0 + fpc_w / 2, fpc_y + 0.8, "FPC", 5.5,
          align="center", font="Helvetica")
    if with_dims:
        dim_h(c, x, x + lcd.width, y - 8.5, y, dim_text(lcd.width))
        dim_v(c, y, y + lcd.height, x - 8.5, x, dim_text(lcd.height))


def draw_board(c: Canvas, x: float, y: float, vertical=False,
               with_dims=True, ports=True) -> None:
    w, h = (BOARD_W, BOARD_L) if vertical else (BOARD_L, BOARD_W)
    rect(c, x, y, w, h, fill=PCB, radius=2.5)
    # Two 2.2 mm mounting holes at the HDMI end; the 20.8 mm spacing is used by
    # the optional M2 bosses in the rear-cover carrier.
    # Tang Nano 9K has two mounting holes, both at the HDMI end.
    hole_points = (
        ((2.6, h - 2.6), (w - 2.6, h - 2.6))
        if vertical
        else ((w - 2.6, 2.6), (w - 2.6, h - 2.6))
    )
    c.saveState()
    c.setLineWidth(0.35)
    c.setStrokeColor(INK)
    c.setFillColor(colors.white)
    for hx, hy in hole_points:
        c.circle(tx(x + hx), tx(y + hy), tx(1.1), stroke=1, fill=1)
    c.restoreState()
    if vertical:
        # The board is rotated 90 degrees in the enclosure: USB-C down, HDMI up.
        if ports:
            rect(c, x + 7.0, y - 2.5, 12.0, 4.0,
                 fill=colors.HexColor("#cfd8dc"), width=0.3)
            rect(c, x + 5.0, y + h - 1.5, 16.0, 4.5,
                 fill=colors.HexColor("#cfd8dc"), width=0.3)
            label(c, x + w / 2, y - 5.2, "USB-C", 6, align="center", font="Helvetica")
            label(c, x + w / 2, y + h + 4.2, "HDMI", 6, align="center", font="Helvetica")
        label(c, x + w / 2, y + h / 2, "TANG NANO 9K", 6.5,
              align="center", font="Helvetica")
        if with_dims:
            dim_h(c, x, x + w, y - 9.0, y, "26.00")
            dim_v(c, y, y + h, x - 8.0, x, "70.00")
    else:
        if ports:
            rect(c, x - 2.5, y + 7.0, 4.0, 12.0,
                 fill=colors.HexColor("#cfd8dc"), width=0.3)
            rect(c, x + w - 1.5, y + 5.0, 4.5, 16.0,
                 fill=colors.HexColor("#cfd8dc"), width=0.3)
            label(c, x - 4.0, y + h / 2, "USB-C", 5.8, align="right", font="Helvetica")
            label(c, x + w + 4.0, y + h / 2, "HDMI", 5.8, font="Helvetica")
        label(c, x + w / 2, y + h / 2, "TANG NANO 9K", 6.5,
              align="center", font="Helvetica")
        if with_dims:
            dim_h(c, x, x + w, y - 8.5, y, "70.00")
            dim_v(c, y, y + h, x - 8.0, x, "26.00")


def draw_front_chassis(c: Canvas, p: CaseProfile, x: float, y: float) -> None:
    rect(c, x, y, p.bezel_w, p.bezel_h, fill=PART)
    rect(c, x + p.body_x, y + p.body_y,
         p.body_w, p.body_h, stroke=HIDDEN, dash=(3, 2))
    rect(c, x + p.window_x, y + p.window_y, p.window_w, p.window_h,
         fill=colors.white, width=0.6)
    dim_h(c, x, x + p.bezel_w, y - 7.0, y, dim_text(p.bezel_w))
    dim_v(c, y, y + p.bezel_h, x - 7.0, x, dim_text(p.bezel_h))
    label(c, x + p.bezel_w / 2, y + 3.0, "FRONT CHASSIS / BEZEL",
          6.5, align="center", font="Helvetica")


def draw_retainer(c: Canvas, p: CaseProfile, x: float, y: float) -> None:
    retainer_w, retainer_h = p.retainer_w, p.retainer_h
    rect(c, x, y, retainer_w, retainer_h, fill=RETAINER)
    bx = (retainer_w - p.retainer_opening_w) / 2
    by = (retainer_h - p.retainer_opening_h) / 2
    rect(c, x + bx, y + by, p.retainer_opening_w, p.retainer_opening_h,
         fill=colors.white)
    relief_x = p.retainer_lcd_dx + p.lcd.fpc_x0
    relief_w = p.lcd.fpc_x1 - p.lcd.fpc_x0
    relief_y = retainer_h - by if p.lcd.fpc_side == "top" else -0.2
    rect(c, x + relief_x, y + relief_y,
         relief_w, by + 0.2, fill=colors.white)
    # Projected hook heads, shown from the rear.
    for cy in p.retainer_hook_centres:
        rect(c, x - 0.6, y + cy - 3.0, 1.8, 6.0,
             fill=colors.HexColor("#ffcc80"), width=0.25)
        rect(c, x + retainer_w - 1.2, y + cy - 3.0, 1.8, 6.0,
             fill=colors.HexColor("#ffcc80"), width=0.25)
    dim_h(c, x, x + retainer_w, y - 7.0, y, dim_text(retainer_w))
    dim_v(c, y, y + retainer_h, x - 7.0, x, dim_text(retainer_h))
    # Label the bar opposite the FPC relief.
    label_y = y + 2.7 if p.lcd.fpc_side == "top" else y + retainer_h - by / 2 - 1.0
    label(c, x + retainer_w / 2, label_y, "LCD RETAINER, t=2.00",
          6.5, align="center", font="Helvetica")


def draw_rear_hatches(c: Canvas, p: CaseProfile, x: float, y: float) -> None:
    """Draw the through-slot pattern defined by the printable STL source."""
    for hatch_x in p.rear_hatch_xs:
        for hatch_y in p.rear_hatch_ys:
            rect(c, x + hatch_x, y + hatch_y,
                 model.REAR_HATCH_SLOT_W, model.REAR_HATCH_SLOT_H,
                 fill=colors.white, stroke=HIDDEN, width=0.25)


def draw_end_stops(c: Canvas, p: CaseProfile, board_x: float, board_y: float,
                   draw_rect: Callable[..., None] | None = None) -> None:
    """Draw the PCB end stops, or the connector bulkheads that replace them."""
    draw = draw_rect or rect
    stop_fill = colors.HexColor("#ce93d8")
    gap = model.PCB_AXIAL_CLEARANCE
    if p.usb_bulkhead is None:
        # Paired axial stops leave both connector centrelines clear.
        for stop_x0, stop_x1 in model.PCB_END_STOP_XS:
            w = stop_x1 - stop_x0
            t = model.PCB_END_STOP_T
            draw(c, board_x + stop_x0, board_y - gap - t, w, t,
                 fill=stop_fill, width=0.25)
            draw(c, board_x + stop_x0, board_y + BOARD_L + gap, w, t,
                 fill=stop_fill, width=0.25)
        return
    centre_x = board_x + BOARD_W / 2.0
    for bulkhead, y0 in (
        (p.usb_bulkhead, board_y - gap - p.usb_bulkhead.thickness),
        (p.hdmi_bulkhead, board_y + BOARD_L + gap),
    ):
        draw(c, centre_x - bulkhead.half_w, y0, bulkhead.half_w * 2.0,
             bulkhead.thickness, fill=stop_fill, width=0.25)
        draw(c, centre_x - bulkhead.notch.half_w, y0, bulkhead.notch.width,
             bulkhead.thickness, stroke=HIDDEN, dash=(1, 1), width=0.25)


def draw_rear_cover(c: Canvas, p: CaseProfile, x: float, y: float, board=False) -> None:
    cover_w, cover_h = p.cover_w, p.cover_h
    rect(c, x, y, cover_w, cover_h, fill=PART)
    draw_rear_hatches(c, p, x, y)
    rim_x = 2.0
    rim_y = 2.0
    rect(c, x + rim_x, y + rim_y, cover_w - 2 * rim_x, cover_h - 2 * rim_y,
         stroke=HIDDEN, dash=(3, 2))
    board_x = x + (cover_w - BOARD_W) / 2
    board_y = y + (cover_h - BOARD_L) / 2
    # Service aperture.
    rect(c, board_x + 3.5, board_y + 12.0, BOARD_W - 7.0, 46.0,
         fill=colors.white, stroke=HIDDEN, dash=(2, 1))
    # Left fixed rails and right flexible clips.
    for y0, y1 in ((board_y + 9.0, board_y + 28.0),
                   (board_y + 42.0, board_y + 61.0)):
        rect(c, board_x - 0.7, y0, 1.9, y1 - y0,
             fill=colors.HexColor("#ffcc80"), width=0.25)
        rect(c, board_x + BOARD_W - 1.2, y0, 1.9, y1 - y0,
             fill=colors.HexColor("#ef9a9a"), width=0.25)
    draw_end_stops(c, p, board_x, board_y)
    if board:
        draw_board(c, board_x, board_y, vertical=True, with_dims=False)
        label(c, board_x + BOARD_W + 3.0, board_y + BOARD_L / 2,
              "FIXED LEFT / SNAP RIGHT", 5.8, color=ALERT, font="Helvetica")
    dim_h(c, x, x + cover_w, y - 7.0, y, dim_text(cover_w))
    dim_v(c, y, y + cover_h, x - 7.0, x, dim_text(cover_h))


def page_1(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 1, f"Tang Nano 9K + {p.title} LCD panel case",
                "Assembly placement — rear-facing views at true 1:1 scale")
    # Left: board installed in cover rails before closing.
    x0, y0 = 19.0, 69.0
    draw_rear_cover(c, p, x0, y0, board=True)
    label(c, x0, 176.0, "STEP 1  INSTALL PCB IN REAR-COVER RAILS", 8)
    label(c, x0, 53.0, "Component side faces LCD; microSD side faces rear service aperture.", 6.5)
    # Right: assembled rear view, kept inside the sheet frame.
    x1, y1 = min(166.0, 286.0 - p.bezel_w), 68.0
    rect(c, x1, y1, p.bezel_w, p.bezel_h, fill=PART)
    cover_x = x1 + p.cover_x
    cover_y = y1 + p.cover_y
    draw_rear_cover(c, p, cover_x, cover_y, board=False)
    board_x = cover_x + (p.cover_w - BOARD_W) / 2
    board_y = cover_y + (p.cover_h - BOARD_L) / 2
    rect(c, board_x, board_y, BOARD_W, BOARD_L, stroke=HIDDEN, dash=(3, 2), radius=2.5)
    label(c, x1, 176.0, "STEP 2  FLIP COVER AND SNAP INTO CHASSIS", 8)
    label(c, x1 + p.bezel_w / 2, 53.0, "Dashed: Tang Nano 9K behind rear cover",
          6.5, color=HIDDEN, align="center")
    label(c, x1 + p.bezel_w / 2, 44.0,
          "HDMI = TOP / USB-C = BOTTOM / microSD = REAR APERTURE",
          6.3, align="center", font="Helvetica")
    finish_page(c)


def page_2(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 2, "Printed part A: front chassis", "Front outline, centre section, and panel cutout — true 1:1")
    # Left column: front outline above the X-Z centre section.
    cx, cy = 20.0, 180.0 - p.bezel_h
    draw_front_chassis(c, p, cx, cy)
    sx, sy = cx, cy - 50.0
    rect(c, sx, sy, p.bezel_w, BEZEL_T, fill=PART)
    rect(c, sx + p.body_x, sy + BEZEL_T, p.body_w, BODY_D - BEZEL_T, fill=PART)
    # Hollow interior overlay.
    rect(c, sx + p.body_x + 2.0, sy + 5.0, p.body_w - 4.0, BODY_D - 7.0,
         fill=colors.white, stroke=HIDDEN)
    dim_h(c, sx, sx + p.bezel_w, sy - 7.0, sy, dim_text(p.bezel_w))
    dim_v(c, sy, sy + BODY_D, sx - 7.0, sx, dim_text(BODY_D))
    label(c, sx + p.bezel_w / 2, sy + BODY_D + 6.0,
          f"CENTRE SECTION X-Z / CHASSIS DEPTH {dim_text(BODY_D)}",
          6.5, align="center", font="Helvetica")
    # Right column: panel opening template (separate 1:1 rectangle).
    px, py = 286.0 - p.panel_cutout_w, 180.0 - p.panel_cutout_h
    rect(c, px, py, p.panel_cutout_w, p.panel_cutout_h,
         stroke=DIM, dash=(4, 2))
    label(c, px + p.panel_cutout_w / 2, py + p.panel_cutout_h / 2,
          f"PANEL CUTOUT {dim_text(p.panel_cutout_w)} x {dim_text(p.panel_cutout_h)}",
          7, color=DIM, align="center", font="Helvetica")
    label(c, sx, sy - 18.0,
          "STL variants: 1.5 / 2.0 / 3.0 mm panels. Outer geometry is common; snap catch depth changes.",
          6.5)
    finish_page(c)


def page_3(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 3, "Printed parts B/C", "LCD retainer and rear cover with integrated PCB carrier — true 1:1")
    draw_retainer(c, p, 18.0, 92.0)
    label(c, 18.0, 174.0, "B  LCD RETAINER", 8, font="Helvetica")
    cover_x = min(165.0, 286.0 - p.cover_w)
    draw_rear_cover(c, p, cover_x, 90.0, board=False)
    label(c, cover_x, 174.0, "C  REAR COVER + PCB CARRIER", 8, font="Helvetica")
    # Actual-size thickness blocks and notes.
    rect(c, 25.0, 41.0, RETAINER_T, 25.0, fill=RETAINER)
    dim_h(c, 25.0, 27.0, 35.0, 41.0, "2.00")
    label(c, 34.0, 51.0, "RETAINER THICKNESS", 6.5)
    rect(c, 92.0, 41.0, COVER_T, 25.0, fill=PART)
    dim_h(c, 92.0, 94.0, 35.0, 41.0, "2.00")
    label(c, 101.0, 51.0, "COVER PLATE THICKNESS", 6.5)
    label(c, cover_x, 68.0, "Orange: fixed guide. Red: two flexible PCB snap clips.", 6.5)
    label(c, cover_x, 61.0, "Centre aperture: microSD access, ventilation, and board removal.", 6.5)
    stop_name = "end stops" if p.usb_bulkhead is None else "connector bulkheads"
    label(c, cover_x, 54.0, f"Purple: {stop_name} resist USB-C/HDMI insertion loads.", 6.5)
    finish_page(c)


def page_4(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 4, "Physical hardware check templates", "LCD, Tang Nano 9K, and panel cutout — all true 1:1")
    lcd = p.lcd
    fpc_above = 4.0 if lcd.fpc_side == "top" else 0.0
    lx, ly = 24.0, 178.0 - fpc_above - lcd.height
    draw_lcd(c, p, lx, ly)
    label(c, lx, 182.0, "LCD REFERENCE", 8, font="Helvetica")
    draw_board(c, 178.0, 140.0, vertical=False)
    label(c, 178.0, 182.0, "TANG NANO 9K PCB", 8, font="Helvetica")
    # Panel cutout template.
    cut_x, cut_y = 286.0 - p.panel_cutout_w, 22.0
    rect(c, cut_x, cut_y, p.panel_cutout_w, p.panel_cutout_h,
         stroke=DIM, dash=(4, 2))
    dim_h(c, cut_x, cut_x + p.panel_cutout_w, cut_y + p.panel_cutout_h + 4.4,
          cut_y + p.panel_cutout_h, dim_text(p.panel_cutout_w))
    dim_v(c, cut_y, cut_y + p.panel_cutout_h, cut_x - 7.0, cut_x,
          dim_text(p.panel_cutout_h))
    label(c, cut_x + p.panel_cutout_w / 2, cut_y + p.panel_cutout_h / 2,
          "PANEL CUTOUT", 8, color=DIM, align="center", font="Helvetica")
    # Status legend below the LCD template.
    tx0, ty0 = lx, ly - 22.0
    label(c, tx0, ty0, "DIMENSION STATUS", 8)
    label(c, tx0, ty0 - 10.0, "VERIFIED: PCB outline 70.00 x 26.00 mm", 6.5)
    label(c, tx0, ty0 - 17.5,
          f"VERIFIED: LCD outline {dim_text(lcd.width)} x {dim_text(lcd.height)}"
          f" x {dim_text(lcd.thickness)} mm ({lcd.name})", 6.5)
    label(c, tx0, ty0 - 25.0,
          f"DESIGN VALUE: panel cutout {dim_text(p.panel_cutout_w)}"
          f" x {dim_text(p.panel_cutout_h)} mm", 6.5)
    label(c, tx0, ty0 - 32.5, "CHECK HARDWARE: connector height/projection and LCD FPC shape", 6.5,
          color=ALERT)
    label(c, tx0, ty0 - 45.0,
          "Do not print the STL if your LCD does not match this template.",
          6.5, color=ALERT)
    finish_page(c)


def page_5(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 5, "Assembly section index",
                "Cutting planes are positioned to pass through the actual hooks, clips, connectors and service aperture")
    sections = {section.code: section for section in section_definitions(p)}
    x0, y0 = 20.0, 158.0 - p.bezel_h
    draw_front_chassis(c, p, x0, y0)
    board_x = x0 + p.pcb_x
    board_y = y0 + p.pcb_y
    rect(c, board_x, board_y, BOARD_W, BOARD_L,
         stroke=HIDDEN, dash=(3, 2), radius=2.0)
    # A-A is a longitudinal Y-Z cut. B-D are transverse X-Z cuts.
    ax = x0 + sections["A-A"].coordinate
    line(c, ax, y0 - 4.0, ax, y0 + p.bezel_h + 4.0,
         color=ALERT, width=0.7, dash=(5, 2))
    label(c, ax, y0 + p.bezel_h + 6.0, "A", 7, color=ALERT,
          align="center", font="Helvetica")
    label(c, ax, y0 - 7.0, "A", 7, color=ALERT,
          align="center", font="Helvetica")
    for code in ("C", "B", "D"):
        cy = y0 + sections[f"{code}-{code}"].coordinate
        line(c, x0 - 4.0, cy, x0 + p.bezel_w + 4.0, cy,
             color=DIM, width=0.65, dash=(5, 2))
        label(c, x0 - 6.0, cy - 1.0, code, 7, color=DIM,
              align="center", font="Helvetica")
        label(c, x0 + p.bezel_w + 6.0, cy - 1.0, code, 7, color=DIM,
              align="center", font="Helvetica")
    label(c, x0 + p.bezel_w / 2.0, 169.0,
          "REAR PROJECTION / SECTION LOCATIONS / SCALE 1:1",
          7, align="center", font="Helvetica")

    label(c, 164.0, 170.0, "SECTION PURPOSE", 8)
    for index, section in enumerate(sections.values()):
        yy = 159.0 - index * 15.0
        label(c, 164.0, yy, f"{section.code}  {section.title}", 6.5,
              color=ALERT if section.code == "A-A" else DIM,
              font="Helvetica")
        label(c, 164.0, yy - 6.0, section.purpose, 5.8,
              color=HIDDEN, font="Helvetica")
    section_legend(c, 164.0, 72.0)
    label(c, 164.0, 26.0,
          "SOLID FILLS: evaluated directly from STL CSG geometry.",
          6.2, font="Helvetica")
    label(c, 164.0, 19.0,
          "DASHED ORANGE: electronics envelope only; measure the physical board.",
          6.2, color=REFERENCE, font="Helvetica")
    finish_page(c)


def page_6(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 6, "Exact assembly sections A-A / B-B",
                "Solid geometry is evaluated from the STL source; all mechanical sections are true 1:1")
    sections = {section.code: section for section in section_definitions(p)}
    depth = model.overall_depth(model.STANDARD_REAR_CLEARANCE)
    # A-A: longitudinal Y-Z section.
    ax, ay = 23.0, 126.0
    draw_exact_section(c, p, "A-A", ax, ay)
    label(c, ax + p.bezel_h / 2.0, ay + 33.0,
          f"A-A  Y-Z @ X={sections['A-A'].coordinate:.2f} mm  /  USB-C → HDMI",
          7, align="center", font="Helvetica")
    dim_h(c, ax, ax + p.bezel_h, ay - 8.0, ay, dim_text(p.bezel_h))
    dim_v(c, ay, ay + depth, ax - 8.0, ax, dim_text(depth))
    label(c, 116.0, 162.0, "WHAT THIS CUT PASSES THROUGH", 8)
    notes = (
        "- verified PCB edge-stop at both connector ends",
        "- USB-C and HDMI wall openings",
        "- LCD body, retainer plate and rear cover",
        "- reference-only connector/component envelopes",
        "- reference FPC routing corridor",
    )
    for index, text_value in enumerate(notes):
        label(c, 116.0, 151.0 - index * 7.2, text_value, 6.2,
              color=REFERENCE if "reference" in text_value else INK)
    section_legend(c, 218.0, 158.0)

    # B-B: transverse section through both PCB rail segments.
    bx, by = 23.0, 45.0
    draw_exact_section(c, p, "B-B", bx, by)
    label(c, bx + p.bezel_w / 2.0, by + 33.0,
          f"B-B  X-Z @ Y={sections['B-B'].coordinate:.2f} mm  /  FIXED LIP ← PCB → FLEX CLIP",
          7, align="center", font="Helvetica")
    dim_h(c, bx, bx + p.bezel_w, by - 8.0, by, dim_text(p.bezel_w))
    dim_v(c, by, by + depth, bx - 8.0, bx, dim_text(depth))
    nx = max(158.0, bx + p.bezel_w + 6.0)
    label(c, nx, 73.0, "The PCB is not floating:", 7.2)
    label(c, nx, 65.0, "z=18.40 support shelves under both edges", 6.3)
    label(c, nx, 58.0, "left fixed lip + right 1.20 mm cantilever clip", 6.3)
    label(c, nx, 51.0, "dashed volumes above/below PCB are unverified components", 6.1,
          color=REFERENCE)
    finish_page(c)


def page_7(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 7, "Exact assembly sections C-C / D-D",
                "LCD hook engagement and microSD access are shown at their actual cutting planes")
    sections = {section.code: section for section in section_definitions(p)}
    window_z0, window_z1 = model.retainer_window_z(p)
    cx, cy = 20.0, 128.0
    draw_exact_section(c, p, "C-C", cx, cy)
    label(c, cx + p.bezel_w / 2.0, cy + 33.0,
          f"C-C  X-Z @ Y={sections['C-C'].coordinate:.2f} mm  /  BOTH LCD HOOKS",
          7, align="center", font="Helvetica")
    dim_h(c, cx, cx + p.bezel_w, cy - 7.0, cy, dim_text(p.bezel_w))
    # Exact 4:1 left-hook detail, clipped from the same section cells.
    zx, zy = 170.0, 119.0
    draw_exact_section(c, p, "C-C", zx, zy, scale=4.0,
                       clip_h=(0.0, 14.0), clip_z=(4.0, 15.0),
                       show_reference_envelopes=False)
    label(c, zx + 28.0, zy + 48.0, "LEFT HOOK DETAIL 4:1", 7,
          align="center", font="Helvetica")
    label(c, zx, zy - 7.0, "orange: retainer arm/head", 5.8,
          color=colors.HexColor("#e65100"), font="Helvetica")
    label(c, zx, zy - 13.0,
          f"grey gap: chassis window z={window_z0:.2f}..{window_z1:.2f}", 5.8,
          font="Helvetica")

    dx, dy = 20.0, 48.0
    draw_exact_section(c, p, "D-D", dx, dy)
    label(c, dx + p.bezel_w / 2.0, dy + 33.0,
          f"D-D  X-Z @ Y={sections['D-D'].coordinate:.2f} mm  /  microSD SERVICE APERTURE",
          7, align="center", font="Helvetica")
    dim_h(c, dx, dx + p.bezel_w, dy - 7.0, dy, dim_text(p.bezel_w))
    label(c, 159.0, 74.0, "At D-D the rear-cover plate is intentionally absent", 6.4)
    label(c, 159.0, 67.0, "under the PCB. This is the service aperture, not a hollow error.", 6.4)
    label(c, 159.0, 58.0, "The dashed microSD socket is a reference envelope;", 6.2,
          color=REFERENCE)
    label(c, 159.0, 51.0, "verify its exact location and height on the physical board.", 6.2,
          color=REFERENCE)
    finish_page(c)


def page_8(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 8, "Section interpretation and assembly",
                "The section set distinguishes verified printable geometry from hardware values requiring measurement")
    lcd_rear_z = BEZEL_T + p.lcd.thickness
    label(c, 18.0, 171.0, "ASSEMBLY ORDER", 9)
    steps = (
        f"1. Install the selected front chassis in the {dim_text(p.panel_cutout_w)}"
        f" x {dim_text(p.panel_cutout_h)} panel cutout.",
        f"2. Place the LCD at z={BEZEL_T:.2f}..{lcd_rear_z:.2f} with its display toward the bezel.",
        "3. Push the retainer until all four C-C hook heads engage their wall windows.",
        "4. Insert the PCB left edge below the B-B fixed lips and press the right edge into both clips.",
        ("5. Confirm the PCB rests on four shelves and between four A-A end stops."
         if p.usb_bulkhead is None else
         "5. Confirm the PCB rests on four shelves and between both connector bulkheads."),
        "6. Connect the FPC, verify the measured connector/component envelopes, then latch the cover.",
    )
    for index, text_value in enumerate(steps):
        yy = 158.0 - index * 13.0
        rect(c, 18.0, yy - 2.0, 8.0, 8.0,
             fill=(RETAINER if index == 2 else PCB if index in (3, 4) else PART))
        label(c, 31.0, yy, text_value, 6.6)

    label(c, 18.0, 69.0, "SECTION READING RULES", 8)
    rules = (
        "Filled regions are exact intersections of the generated STL CSG solids.",
        "Empty regions may be intentional openings: display window, latch window, port opening or service aperture.",
        "Orange dashed regions are not printable geometry and are not dimensionally certified.",
        "A-A through E-E coordinates are measured from the bezel left/bottom/front datums.",
    )
    for index, text_value in enumerate(rules):
        label(c, 18.0, 59.0 - index * 8.0, f"- {text_value}", 6.3,
              color=REFERENCE if index == 2 else INK)
    label(c, 166.0, 171.0, "MEASUREMENT HOLD POINTS", 9)
    holds = [
        "USB-C shell: width, height, projection",
        "HDMI shell: width, height, projection",
        "microSD socket: x/y position and rear height",
        "maximum component height on both PCB faces",
        "LCD FPC exit point, width and bend radius",
    ]
    if p.usb_bulkhead is not None:
        holds.append(
            f"cable overmould: USB-C {p.usb_opening.width:.1f} x {p.usb_opening.height:.1f},"
            f" HDMI {p.hdmi_opening.width:.1f} x {p.hdmi_opening.height:.1f} max"
        )
    for index, text_value in enumerate(holds):
        label(c, 166.0, 158.0 - index * 10.0, f"□  {text_value}", 6.5,
              color=REFERENCE)
    label(c, 166.0, 95.0, "Do not treat dashed envelopes as production dimensions.",
          7, color=ALERT)
    section_legend(c, 166.0, 78.0)
    finish_page(c)


def page_9(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 9, "Expanded rear-cover sections",
                "HDMI-end E-E cut through both M2 bosses; PCB and connector planes remain unchanged")

    x20, y20 = 20.0, 116.0
    draw_exact_section(c, p, "E-E", x20, y20, rear_clearance=20.0)
    label(c, x20 + p.bezel_w / 2.0, y20 + 48.0,
          "20 mm CLEARANCE VARIANT / E-E X-Z / SCALE 1:1",
          7, align="center", font="Helvetica")
    dim_h(c, x20, x20 + p.bezel_w, y20 - 7.0, y20, dim_text(p.bezel_w))
    dim_v(c, y20, y20 + 42.0, x20 - 8.0, x20, "42.00")

    x30, y30 = 20.0, 31.0
    draw_exact_section(c, p, "E-E", x30, y30, rear_clearance=30.0)
    label(c, x30 + p.bezel_w / 2.0, y30 + 58.0,
          "30 mm CLEARANCE VARIANT / E-E X-Z / SCALE 1:1",
          7, align="center", font="Helvetica")
    dim_h(c, x30, x30 + p.bezel_w, y30 - 7.0, y30, dim_text(p.bezel_w))
    dim_v(c, y30, y30 + 52.0, x30 - 8.0, x30, "52.00")

    label(c, 157.0, 165.0, "E-E CUT CONTENT", 8)
    notes = (
        "- two HDMI-end mounting holes only",
        "- two 6.00 mm square printed bosses",
        "- 1.70 x 1.70 mm M2 self-tapping pilot",
        "- 6.00 mm effective thread depth",
        "- optional M2x8 screws from PCB front side",
        "- fixed lip and flex clips remain active",
    )
    for index, text_value in enumerate(notes):
        label(c, 157.0, 154.0 - index * 8.0, text_value, 6.3)
    label(c, 157.0, 97.0, "DEPTH DATUM", 8)
    label(c, 157.0, 88.0, "PCB rear surface: z=20.00 mm in every variant", 6.3)
    label(c, 157.0, 80.0, "20 mm cover inner face: z=40.00 mm", 6.3)
    label(c, 157.0, 72.0, "30 mm cover inner face: z=50.00 mm", 6.3)
    label(c, 157.0, 60.0,
          "Blue dashed shafts are screw references; grey bosses are STL geometry.",
          6.1, color=DIM)
    label(c, 157.0, 49.0,
          "Verify the physical daughterboard outline and cable bend space.",
          6.3, color=ALERT)
    finish_page(c)


def page_10(c: Canvas, p: CaseProfile) -> None:
    page_header(c, 10, "HDMI-end two-hole mounting layout",
                "Rear projection at true 1:1; screw fixation is optional and supplements the snap carrier")
    cover_w, cover_h = p.cover_w, p.cover_h
    x0, y0 = 22.0, min(82.0, 156.6 - cover_h)
    rect(c, x0, y0, cover_w, cover_h, fill=PART)
    draw_rear_hatches(c, p, x0, y0)
    board_x = x0 + (cover_w - BOARD_W) / 2.0
    board_y = y0 + (cover_h - BOARD_L) / 2.0
    rect(c, board_x + 3.5, board_y + 12.0, BOARD_W - 7.0, 46.0,
         fill=colors.white, stroke=HIDDEN, dash=(2, 1))

    hole_y = board_y + BOARD_L - 2.6
    hole_xs = (board_x + 2.6, board_x + BOARD_W - 2.6)
    for hole_x in hole_xs:
        rect(c, hole_x - 3.0, hole_y - 3.0, 6.0, 6.0,
             fill=colors.HexColor("#bbdefb"), stroke=DIM, width=0.45)
    rect(c, board_x, board_y, BOARD_W, BOARD_L,
         stroke=colors.HexColor("#2e7d32"), dash=(4, 2), width=0.65, radius=2.0)
    c.saveState()
    c.setStrokeColor(INK)
    c.setFillColor(colors.white)
    for hole_x in hole_xs:
        c.circle(tx(hole_x), tx(hole_y), tx(1.1), stroke=1, fill=1)
    c.restoreState()

    dim_h(c, x0, x0 + cover_w, y0 - 7.0, y0, dim_text(cover_w))
    dim_v(c, y0, y0 + cover_h, x0 - 7.0, x0, dim_text(cover_h))
    dim_h(c, hole_xs[0], hole_xs[1], y0 + cover_h + 9.0,
          hole_y, "20.80 HOLE CENTRES")
    label(c, x0 + cover_w / 2.0, 169.0,
          "REAR-COVER INBOARD VIEW / HDMI END AT TOP",
          7, align="center", font="Helvetica")
    label(c, x0 + cover_w / 2.0, y0 - 12.0,
          "Blue: printed bosses / Green dashed: Tang Nano 9K PCB",
          6.2, align="center", font="Helvetica")

    label(c, 157.0, 169.0, "MOUNTING SPECIFICATION", 8)
    rows = (
        ("PCB holes", "2 only, HDMI end"),
        ("Hole reference", "diameter 2.20 mm"),
        ("Hole-centre spacing", "20.80 mm"),
        ("Printed boss", "6.00 x 6.00 mm"),
        ("Pilot bore", "1.70 x 1.70 mm square"),
        ("Recommended screw", "M2x8 self-tapping"),
        ("Rear clearance variants", "20.00 / 30.00 mm"),
        ("Overall case depth", "42.00 / 52.00 mm"),
    )
    for index, (key, value) in enumerate(rows):
        yy = 157.0 - index * 10.0
        label(c, 157.0, yy, key, 6.2, color=HIDDEN)
        label(c, 218.0, yy, value, 6.3, font="Helvetica")

    label(c, 157.0, 67.0, "ASSEMBLY", 8)
    assembly_notes = (
        "1. Insert PCB under the fixed lips and engage both flex clips.",
        "2. Align the two HDMI-end PCB holes with the printed pilots.",
        "3. Install M2x8 screws without compressing or bowing the PCB.",
        "4. Confirm 20/30 mm daughterboard height and cable clearance.",
    )
    for index, text_value in enumerate(assembly_notes):
        label(c, 157.0, 57.0 - index * 8.0, text_value, 6.2)
    label(c, 157.0, 20.0,
          "Do not use screws longer than required; the pilot thread depth is 6.00 mm.",
          6.2, color=ALERT)
    finish_page(c)


PAGES = (page_1, page_2, page_3, page_4, page_5,
         page_6, page_7, page_8, page_9, page_10)
OUTPUT_NAME = "tang-nano-9k-panel-case-1to1.pdf"


def create_pdf(output: Path, p: CaseProfile) -> None:
    pdfmetrics.registerFont(TTFont("DejaVu", str(dejavu_sans())))
    output.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(
        str(output), pagesize=landscape(A4), pageCompression=1, invariant=1
    )
    c.setTitle("Tang Nano 9K Panel Case 1-to-1 Drawing")
    c.setAuthor("OpenAI Codex")
    c.setSubject("A4 true-scale mechanical and assembly drawing")
    for draw_page in PAGES:
        draw_page(c, p)
    c.save()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("output"),
                        help="root directory; one sub-directory per profile")
    parser.add_argument("--profile", action="append", choices=sorted(PROFILES),
                        help="profile to draw; repeatable, default: all")
    args = parser.parse_args()
    for key in args.profile or PROFILES:
        output = args.output_dir / key / "pdf" / OUTPUT_NAME
        create_pdf(output, get_profile(key))
        print(output)


if __name__ == "__main__":
    main()
