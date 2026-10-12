#!/usr/bin/env python3
"""Generate the R4 enclosure design specification PDF."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from assembly_r4 import CASE_DEPTH, DOCK_STEP_BOUNDS_LOCAL, DOCK_STEP_OFFSET, official_global_bounds
from generate_case import CASE_H
from generate_case_r4 import ACCESS_OPENING, PIN_TIP, REAR_FRAME_DEPTH, SERVICE_CAP_DEPTH, STRUCTURAL_DEPTH


FONT = "DejaVuSans"
FONT_PATH = os.environ.get(
    "DEJAVU_FONT_PATH",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
BLUE = colors.HexColor("#246B9B")
GREEN = colors.HexColor("#348A52")
ORANGE = colors.HexColor("#C97524")
MAGENTA = colors.HexColor("#A63B89")
DARK = colors.HexColor("#252A31")
LIGHT = colors.HexColor("#EDF2F6")
WARN = colors.HexColor("#8C3516")
DOCK_GLOBAL = official_global_bounds(DOCK_STEP_BOUNDS_LOCAL, DOCK_STEP_OFFSET)
REAR_INNER_Z = CASE_DEPTH - 2.40
STEP_CLEARANCE = REAR_INNER_Z - DOCK_GLOBAL[1][2]


class AssemblyDiagram(Flowable):
    def __init__(self, width: float = 170 * mm, height: float = 88 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        c = self.canv
        c.setFont(FONT, 8.5)
        layers = [
            ("FRONT SHELL + 6 RETAINER HOOKS", colors.HexColor("#667281")),
            ("LCD", BLUE),
            ("LCD RETAINER", colors.HexColor("#667281")),
            ("DOCK TRAY + 4 M2.5 BLIND PILOT BOSSES", GREEN),
            ("DOCK + CORE / 4 x M2.5 x 6 SCREWS", ORANGE),
            ("PINNED REAR ACCESS FRAME", colors.HexColor("#667281")),
            ("REMOVABLE 20 mm SERVICE CAP", colors.HexColor("#4F6476")),
        ]
        box_w = 100 * mm
        box_h = 9 * mm
        x = 5 * mm
        y = self.height - 12 * mm
        for index, (label, color) in enumerate(layers):
            yy = y - index * 11 * mm
            c.setStrokeColor(color)
            c.setFillColor(colors.Color(color.red, color.green, color.blue, alpha=0.12))
            c.rect(x, yy, box_w, box_h, stroke=1, fill=1)
            c.setFillColor(color)
            c.drawCentredString(x + box_w / 2, yy + 3 * mm, label)
            if index < len(layers) - 1:
                c.setStrokeColor(DARK)
                c.line(x + box_w / 2, yy, x + box_w / 2, yy - 3 * mm)
        c.setFillColor(DARK)
        c.setFont(FONT, 8)
        c.drawString(112 * mm, self.height - 15 * mm, "4 PRINTED SNAP PINS")
        c.drawString(112 * mm, self.height - 21 * mm, "pass through every structural layer")
        c.setStrokeColor(MAGENTA)
        for yy in (y + 4 * mm, y - 5 * 11 * mm + 4 * mm):
            c.line(109 * mm, yy, 159 * mm, yy)
        c.line(159 * mm, y + 4 * mm, 159 * mm, y - 5 * 11 * mm + 4 * mm)
        c.setFillColor(WARN)
        c.drawString(112 * mm, 7 * mm, "One common axis prevents layer shear and separation")


def make_styles():
    pdfmetrics.registerFont(TTFont(FONT, FONT_PATH))
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=base["BodyText"], fontName=FONT, fontSize=9.2,
        leading=13.5, textColor=DARK, spaceAfter=3 * mm,
    )
    h1 = ParagraphStyle(
        "h1", parent=body, fontSize=16, leading=21, textColor=BLUE,
        spaceBefore=3 * mm, spaceAfter=4 * mm,
    )
    h2 = ParagraphStyle(
        "h2", parent=body, fontSize=12, leading=16, textColor=DARK,
        spaceBefore=2 * mm, spaceAfter=2 * mm,
    )
    title = ParagraphStyle(
        "title", parent=body, fontSize=23, leading=31, alignment=TA_CENTER,
        textColor=DARK, spaceAfter=8 * mm,
    )
    subtitle = ParagraphStyle(
        "subtitle", parent=body, fontSize=12, leading=18, alignment=TA_CENTER,
        textColor=BLUE,
    )
    warning = ParagraphStyle(
        "warning", parent=body, textColor=WARN, backColor=colors.HexColor("#FFF3EC"),
        borderColor=WARN, borderWidth=0.5, borderPadding=6,
        spaceBefore=2 * mm, spaceAfter=4 * mm,
    )
    small = ParagraphStyle(
        "small", parent=body, fontSize=7.6, leading=10.5, spaceAfter=1.2 * mm,
    )
    return body, h1, h2, title, subtitle, warning, small


def p(value: str, style) -> Paragraph:
    return Paragraph(value, style)


def bullets(items: list[str], body) -> list[Paragraph]:
    return [p(f"- {item}", body) for item in items]


def table(data, widths, style, header=True) -> Table:
    rows = [[p(str(cell), style) for cell in row] for row in data]
    result = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#8B96A3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ])
    for row in range(1 if header else 0, len(data)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), LIGHT))
    result.setStyle(TableStyle(commands))
    return result


def decorate(c, doc) -> None:
    c.saveState()
    c.setStrokeColor(colors.HexColor("#AAB3BC"))
    c.line(16 * mm, 282 * mm, 194 * mm, 282 * mm)
    c.setFont(FONT, 7.5)
    c.setFillColor(colors.HexColor("#5B6570"))
    c.drawString(16 * mm, 287 * mm, "Tang Primer 20K LCD enclosure R4")
    c.drawRightString(194 * mm, 10 * mm, str(doc.page))
    c.drawString(16 * mm, 10 * mm, "Units: mm / prototype design / 2026-08-29")
    c.restoreState()


def generate(path: Path) -> None:
    body, h1, h2, title, subtitle, warning, small = make_styles()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=20 * mm, bottomMargin=17 * mm,
        title="Tang Primer 20K LCD enclosure R4 design specification",
        author="OpenAI Codex",
    )
    story = [
        Spacer(1, 28 * mm),
        p("Tang Primer 20K<br/>Integrated LCD Enclosure R4", title),
        p("Retention, assembly, tolerance and verification specification", subtitle),
        Spacer(1, 15 * mm),
        AssemblyDiagram(),
        Spacer(1, 8 * mm),
        p("The LCD retainer, outer case and rear service cap are tool-less. The Dock uses its four official corner holes and M2.5 screws; no printed peg passes through the PCB.", body),
        p("PROTOTYPE STATUS: official Dock 3713 and Core 3690 STEP assemblies now define the installed SODIMM position and component envelope. Physical hardware must still verify PCB revision, FPC routing and FDM fit. Drop, vehicle vibration and safety certification are outside this revision.", warning),
        PageBreak(),
        p("1. Requirements and retention paths", h1),
        p("No internal part may move freely during a light hand-shake test. The pinned access frame remains structural while the 20 mm service cap can be removed independently for SODIMM and PMOD access.", body),
        AssemblyDiagram(height=82 * mm),
        p("Retention summary", h2),
        table([
            ["Target", "Primary retention", "Release"],
            ["LCD", "Outline pocket + edge retainer + six hooks", "Deflect hooks outward and lift"],
            ["Dock", "4 x M2.5 x 6 screws through official holes", "Remove screws; lift vertically"],
            ["Core", "SODIMM contacts + both connector latches", "Open both latches together"],
            ["FPC", "Connector lock + open guide + polyimide tape", "Remove tape; unlock connector"],
            ["Case", "Four printed split pins through 4.30 square paths", "Squeeze rear tips and push forward"],
            ["Service cap", "Two upper hooks + two lower push tabs", "Press lower tabs, rotate out, lift"],
        ], [28 * mm, 92 * mm, 58 * mm], small),
        PageBreak(),
        p("2. Printed parts and assembly stack", h1),
        table([
            ["STL", "Qty", "Function"],
            ["front_shell_43_snap / 50_snap", "1", "LCD pocket, six hooks and front enclosure"],
            ["lcd_retainer_43_snap / 50_snap", "1", "Loads LCD metal perimeter"],
            ["dock_tray_screw_common", "1", "Dock support, blind pilots and open FPC guide"],
            ["rear_access_frame_common", "1", "Pinned structure with 120 x 92 access opening"],
            ["rear_service_cap_common", "1", "20 mm service bay, hooks, tabs and cable exits"],
            ["case_snap_pin", "4", "Aligns and clamps all structural layers"],
            ["fit_coupon", "1", "Case-pin and M2.5-pilot calibration"],
        ], [78 * mm, 16 * mm, 84 * mm], small),
        p("Stack order", h2),
        p("Front to rear: front shell, LCD, LCD retainer, Dock tray, Dock with latched Core, pinned rear access frame, and removable service cap. Four printed pins stop at the frame; the cap has its own release tabs.", body),
        p("The access frame has a 120.00 x 92.00 central opening. Removing only the cap exposes the SODIMM latches and PMOD area without disturbing the LCD, tray, Dock screws or case pins.", body),
        p("Retainer hooks are placed two per side and two along the upper edge. The lower edge remains free for the 80 mm FPC route.", body),
        p("The Dock lands on four 7 x 7 x 3.2 support bosses. Four M2.5 x 6 pan-head screws pass through the official PCB holes and self-tap into 2.00 mm square, 4.80 mm deep blind pilots.", body),
        p("The 48 mm roof bridge in the former FPC tunnel has been removed. The release tray has two open rails and removable polyimide tape strain relief.", warning),
        PageBreak(),
        p("3. Dimensions and tolerances", h1),
        table([
            ["Item", "Dimension", "Basis"],
            ["Case", f"140.00 x {CASE_H:.2f} x {CASE_DEPTH:.2f}", "R4: Y +20, Z +20"],
            ["Structural frame plane", f"Z={STRUCTURAL_DEPTH:.2f}", "Original 37 mm pins retained"],
            ["Service extension", f"{SERVICE_CAP_DEPTH:.2f}", "Removable cap"],
            ["Access opening", f"{ACCESS_OPENING[2]:.2f} x {ACCESS_OPENING[3]:.2f}", "SODIMM / PMOD access"],
            ["Dock", "95.00 x 73.00", "Official"],
            ["Dock hole pitch", "87.00 x 65.00", "Official"],
            ["Core PCB", "67.60 x 30.00", "Official"],
            ["4.3 LCD", "105.40 x 67.10 x 2.90", "Official"],
            ["5.0 LCD", "120.70 x 75.90 x 3.05", "Official"],
            ["LCD pocket", "LCD outline +0.50", "0.25 per side"],
            ["Case hole / pin", "4.30 square / 3.50 square", "0.40 per side"],
            ["Dock PCB thickness", "1.590 STEP", "Official STEP"],
            ["Dock boss / pilot", "7.00 square / 2.00 square x 4.80 deep", "Design"],
            ["Dock screw", "M2.5 x 6 pan-head, quantity 4", "Hardware requirement"],
            ["FPC guide", "50.00 between outer rail faces; open top", "Design - verify"],
        ], [52 * mm, 62 * mm, 64 * mm], small),
        p(f"R4 retains the {REAR_FRAME_DEPTH:.2f} mm structural rear frame and {PIN_TIP:.2f} mm case pin, then adds a separate {SERVICE_CAP_DEPTH:.2f} mm service bay. Overall depth is {CASE_DEPTH:.2f} mm. Minimum STEP-envelope clearance to the service-cap inner face is {STEP_CLEARANCE:.3f} mm.", warning),
        p("Fit adjustment", h2),
        *bullets([
            "Increase PIN_HOLE in 0.10 increments if insertion is too tight.",
            "Decrease PIN_HOLE in 0.10 increments if lateral play is excessive.",
            "Adjust DOCK_PILOT in 0.10 mm increments using the coupon; do not enlarge the PCB holes.",
            "Never reduce the LCD pocket to create clamping pressure on the display.",
        ], body),
        PageBreak(),
        p("4. Printing and assembly", h1),
        table([
            ["Part", "Material", "Layer", "Walls / infill", "Orientation"],
            ["Case parts", "PETG", "0.20 max", "4 / 20-30%", "Largest flat face down"],
            ["Service cap", "PETG", "0.16-0.20", "4 / 25-35%", "Rear lattice down"],
            ["Dock tray", "PETG", "0.16 preferred", "4 / 30%", "Tray plane down"],
            ["Snap pins", "PETG, PA or PP", "0.16", "4 / 100%", "As supplied: flat"],
            ["Coupon", "Production material", "Production profile", "Same", "Do not rotate"],
        ], [34 * mm, 34 * mm, 29 * mm, 42 * mm, 39 * mm], small),
        p("Do not use PLA for repeated operation of retainer hooks or snap pins. Enable elephant-foot compensation. Determine horizontal-hole compensation from the coupon.", warning),
        p("Assembly sequence", h2),
        *bullets([
            "Print the coupon and one case pin first; verify insertion and release.",
            "Place the LCD from the rear with FPC toward the lower edge.",
            "Insert the retainer from the upper edge; engage four side and two upper hooks.",
            "Lay the FPC between the open guide rails and add removable polyimide tape without tension.",
            "Place the Dock on all four bosses, then tighten four M2.5 x 6 screws evenly by hand.",
            "Insert the Core into SODIMM and close both side latches.",
            "Connect and lock the FPC without a sharp fold.",
            "Install the rear access frame and insert four case snap pins from the front.",
            "Insert both upper cap hooks, rotate the lower edge inward, and confirm both lower tabs click.",
        ], body),
        PageBreak(),
        p("5. Disassembly and verification", h1),
        p("Disassembly", h2),
        *bullets([
            "Disconnect power and all external cables.",
            "Press both lower service-cap tabs, rotate the lower edge outward, then lift off the upper hooks.",
            "For routine SODIMM or PMOD access, leave the four case pins, frame and Dock tray installed.",
            "For full teardown, squeeze each frame-side pin tip and push the pin toward the front.",
            "Unlock FPC and SODIMM latches before removing either board.",
            "Release side retainer hooks before the upper hooks. Never press the display area.",
        ], body),
        p("Acceptance checks", h2),
        table([
            ["Stage", "Check", "Pass criterion"],
            ["PDF", "100 mm bar and 20 x 20 square", "Printed dimensions match a ruler"],
            ["Coupon", "Case pin", "Finger insertion; removable by squeezing tips"],
            ["Coupon", "M2.5 pilot", "Screw holds without splitting or bottoming"],
            ["Assembly", "6 LCD hooks, 4 screws, 4 pins", "All retainers seated; no board bending"],
            ["Rear cap", "2 hooks + 2 push tabs", "Both detents click; finger release works"],
            ["Hand shake", "Three axes, 10 seconds each", "No rattle or part movement"],
            ["FPC", "Connector and bend", "No tension and no sharp crease"],
            ["Powered", "30 minutes", "No heat deformation"],
        ], [28 * mm, 65 * mm, 85 * mm], small),
        PageBreak(),
        p("6. Constraints and primary sources", h1),
        p("Open verification items", h2),
        *bullets([
            "Official 2D drawings omit the SODIMM datum; the official Dock 3713 STEP supplies the installed Core position used here.",
            "Dock PCB is 1.590 mm in STEP; actual hole diameter and screw fit must be confirmed on hardware.",
            "Confirm FPC thickness, stiffener thickness and bend allowance for both LCD variants.",
            "Retention force depends on material, print orientation, moisture and extrusion accuracy.",
            "Drop, vehicle and long-duration vibration are untested. Use metal fasteners when required.",
        ], body),
        p("Primary sources", h2),
        p("Sipeed Tang Primer 20K Wiki:<br/><link href='https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html'>https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html</link>", small),
        p("Sipeed Dock/Core dimensions:<br/><link href='https://dl.sipeed.com/shareURL/TANG/Primer_20K/08_Dimensions'>https://dl.sipeed.com/shareURL/TANG/Primer_20K/08_Dimensions</link>", small),
        p("Sipeed LCD datasheets:<br/><link href='https://dl.sipeed.com/shareURL/TANG/Nano%209K/6_Chip_Manual/EN/LCD_Datasheet'>https://dl.sipeed.com/shareURL/TANG/Nano%209K/6_Chip_Manual/EN/LCD_Datasheet</link>", small),
        Spacer(1, 8 * mm),
        p("DESIGN_R4.md is the Japanese companion specification. STL files, 1:1 drawings, manifest and tests shall be updated in the same commit whenever retention dimensions change.", warning),
    ]
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path("output/release/Tang_Primer_20K_Case_R4_Design_Specification.pdf"),
    )
    args = parser.parse_args()
    generate(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
