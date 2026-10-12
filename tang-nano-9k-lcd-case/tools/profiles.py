#!/usr/bin/env python3
"""LCD-dependent enclosure profiles.

All coordinates use the model frame of ``generate_stl``: x and y are measured
from the lower-left corner of the front bezel as seen from the rear, z grows
from the bezel face toward the rear cover.  The USB-C end of the Tang Nano 9K
is at low y and the HDMI end is at high y.  Viewed from the front, model x is
mirrored; datasheet offsets measured from the front-left edge are converted
before they are stored here.

Shared mechanical values such as the wall thickness, bezel thickness, PCB
size, snap geometry and depth datums remain in ``generate_stl``.  A profile
only holds values that depend on the LCD module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


BEZEL_MARGIN = 3.00
WALL = 2.00
PANEL_CUTOUT_CLEARANCE = 0.30
COVER_CLEARANCE = 0.20
RETAINER_CLEARANCE = 0.20
WINDOW_MARGIN = 0.30
PCB_W = 26.00
PCB_H = 70.00


@dataclass(frozen=True)
class LcdModule:
    name: str
    description: str
    width: float
    height: float
    thickness: float
    active_w: float
    active_h: float
    # Active-area offsets from the module edge at model x=0 and y=0.
    active_x: float
    active_y: float
    # Edge from which the FPC leaves the module and the x range, measured
    # from the module edge at model x=0, that the retainer must keep open.
    fpc_side: Literal["top", "bottom"]
    fpc_x0: float
    fpc_x1: float
    source: str


@dataclass(frozen=True)
class PortOpening:
    """Rectangular opening centred on the PCB centreline.

    ``z0`` and ``z1`` are assembled global z coordinates.
    """

    half_w: float
    z0: float
    z1: float

    @property
    def width(self) -> float:
        return self.half_w * 2.0

    @property
    def height(self) -> float:
        return self.z1 - self.z0


@dataclass(frozen=True)
class PortBulkhead:
    """Rear-cover wall that sits at a PCB end when the chassis wall cannot.

    ``notch`` is the connector opening.  It is open toward the LCD so that the
    PCB can be pressed into the carrier with the connector already soldered.
    The bulkhead face toward the PCB is the axial end stop.
    """

    notch: PortOpening
    half_w: float
    thickness: float = 2.00


@dataclass(frozen=True)
class CaseProfile:
    key: str
    title: str
    lcd: LcdModule
    body_w: float
    body_h: float
    retainer_opening_w: float
    retainer_opening_h: float
    # Centres measured from the bottom edge of the part that carries them.
    panel_arm_centres: tuple[float, float]
    retainer_hook_centres: tuple[float, float]
    rear_latch_ys: tuple[float, float]
    usb_opening: PortOpening
    hdmi_opening: PortOpening
    # Rear-cover connector bulkheads; required when the PCB ends are far
    # from the chassis walls.
    usb_bulkhead: PortBulkhead | None
    hdmi_bulkhead: PortBulkhead | None
    rear_hatch_xs: tuple[float, ...]
    rear_hatch_ys: tuple[float, ...]
    # A-A section x position relative to the PCB left edge.
    section_a_offset: float

    # Global enclosure outline.
    @property
    def bezel_w(self) -> float:
        return self.body_w + BEZEL_MARGIN * 2.0

    @property
    def bezel_h(self) -> float:
        return self.body_h + BEZEL_MARGIN * 2.0

    @property
    def body_x(self) -> float:
        return (self.bezel_w - self.body_w) / 2.0

    @property
    def body_y(self) -> float:
        return (self.bezel_h - self.body_h) / 2.0

    @property
    def panel_cutout_w(self) -> float:
        return self.body_w + PANEL_CUTOUT_CLEARANCE * 2.0

    @property
    def panel_cutout_h(self) -> float:
        return self.body_h + PANEL_CUTOUT_CLEARANCE * 2.0

    # LCD placement and display window.
    @property
    def lcd_x(self) -> float:
        return self.body_x + (self.body_w - self.lcd.width) / 2.0

    @property
    def lcd_y(self) -> float:
        return self.body_y + (self.body_h - self.lcd.height) / 2.0

    @property
    def window_x(self) -> float:
        return self.lcd_x + self.lcd.active_x - WINDOW_MARGIN

    @property
    def window_y(self) -> float:
        return self.lcd_y + self.lcd.active_y - WINDOW_MARGIN

    @property
    def window_w(self) -> float:
        return self.lcd.active_w + WINDOW_MARGIN * 2.0

    @property
    def window_h(self) -> float:
        return self.lcd.active_h + WINDOW_MARGIN * 2.0

    # LCD retainer, in its own coordinates and in assembly coordinates.
    @property
    def retainer_w(self) -> float:
        return self.body_w - (WALL + RETAINER_CLEARANCE) * 2.0

    @property
    def retainer_h(self) -> float:
        return self.body_h - (WALL + RETAINER_CLEARANCE) * 2.0

    @property
    def retainer_x(self) -> float:
        return self.body_x + WALL + RETAINER_CLEARANCE

    @property
    def retainer_y(self) -> float:
        return self.body_y + WALL + RETAINER_CLEARANCE

    @property
    def retainer_lcd_dx(self) -> float:
        """LCD x origin relative to the retainer x origin."""
        return (self.retainer_w - self.lcd.width) / 2.0

    # Rear cover.
    @property
    def cover_w(self) -> float:
        return self.body_w - COVER_CLEARANCE * 2.0

    @property
    def cover_h(self) -> float:
        return self.body_h - COVER_CLEARANCE * 2.0

    @property
    def cover_x(self) -> float:
        return (self.bezel_w - self.cover_w) / 2.0

    @property
    def cover_y(self) -> float:
        return (self.bezel_h - self.cover_h) / 2.0

    # Tang Nano 9K, centred in the bezel.
    @property
    def pcb_x(self) -> float:
        return (self.bezel_w - PCB_W) / 2.0

    @property
    def pcb_y(self) -> float:
        return (self.bezel_h - PCB_H) / 2.0

    @property
    def pcb_end_gap(self) -> float:
        """Distance from each PCB end to the inner face of the chassis wall."""
        return (self.body_h - WALL * 2.0 - PCB_H) / 2.0

    def validate(self) -> None:
        lcd_gap_x = (self.body_w - WALL * 2.0 - self.lcd.width) / 2.0
        lcd_gap_y = (self.body_h - WALL * 2.0 - self.lcd.height) / 2.0
        if min(lcd_gap_x, lcd_gap_y) < 0.40:
            raise ValueError(f"{self.key}: LCD clearance below 0.40 mm")
        if self.pcb_end_gap < 0.40:
            raise ValueError(f"{self.key}: PCB end clearance below 0.40 mm")
        if (self.usb_bulkhead is None) != (self.hdmi_bulkhead is None):
            raise ValueError(f"{self.key}: bulkheads must be defined in pairs")
        if self.usb_bulkhead is None and self.pcb_end_gap > 1.0:
            raise ValueError(
                f"{self.key}: connector faces are recessed; define bulkheads"
            )
        for bulkhead, opening in ((self.usb_bulkhead, self.usb_opening),
                                  (self.hdmi_bulkhead, self.hdmi_opening)):
            if bulkhead is None:
                continue
            if bulkhead.notch.half_w > opening.half_w or not (
                opening.z0 <= bulkhead.notch.z0 and bulkhead.notch.z1 <= opening.z1
            ):
                raise ValueError(
                    f"{self.key}: chassis opening must contain the bulkhead notch"
                )
            if bulkhead.half_w >= PCB_W / 2.0:
                raise ValueError(f"{self.key}: bulkhead wider than the PCB")
        if not 0.0 <= self.lcd.fpc_x0 < self.lcd.fpc_x1 <= self.lcd.width:
            raise ValueError(f"{self.key}: FPC relief outside the LCD outline")


# Sipeed "HT043DA-V.0" datasheet, dimensional drawing on page 5: outline
# 105.50 x 67.15 x 2.90, active area 95.04 x 53.856.  The active area is
# 4.04 mm from the edge opposite the FPC (9.25 mm on the FPC side), so with
# active_y=4.04 the FPC edge is at the top of the model frame (HDMI side).
# The 25 mm relief is centred on the module.
HT043DA = LcdModule(
    name="HT043DA-V.0",
    description="4.3-inch 480 x 272 RGB",
    width=105.50,
    height=67.15,
    thickness=2.90,
    active_w=95.04,
    active_h=53.856,
    active_x=5.18,
    active_y=4.04,
    fpc_side="top",
    fpc_x0=(105.50 - 25.00) / 2.0,
    fpc_x1=(105.50 + 25.00) / 2.0,
    source="Sipeed HT043DA-V.0 datasheet (page 5)",
)

# Sipeed "5.0inch_LCD_Datashet _RGB_.pdf", module SH500J01Z, Rev 00
# (2015-10-10), outline drawing on page 4.  Front view, FPC at the bottom:
#   outline 120.70 x 75.90 x 3.05, active area 108.00 x 64.80,
#   active area 6.26 from the right edge and 3.34 from the top edge.
# The model frame is mirrored in x, so the front-right edge is model x=0 and
# the FPC edge is model y=0.  The FPC neck and the backlight lead leave the
# lower edge between 48.2-72.4 mm and 28.1-31.7 mm from the front-left edge;
# its folded component area spans 26.21-78.17 mm.  The relief below covers
# the component area with about 1 mm margin, mirrored to model x.
SH500J01Z = LcdModule(
    name="SH500J01Z",
    description="5-inch 800 x 480 RGB",
    width=120.70,
    height=75.90,
    thickness=3.05,
    active_w=108.00,
    active_h=64.80,
    active_x=6.26,
    active_y=75.90 - 64.80 - 3.34,
    fpc_side="bottom",
    fpc_x0=120.70 - 79.20,
    fpc_x1=120.70 - 25.20,
    source="Sipeed 5.0inch_LCD_Datashet _RGB_.pdf (SH500J01Z Rev 00)",
)


PROFILE_4P3IN = CaseProfile(
    key="4p3in",
    title="4.3-inch",
    lcd=HT043DA,
    # The 70 mm PCB, not the LCD, sets the body height.
    body_w=112.00,
    body_h=75.00,
    retainer_opening_w=97.00,
    retainer_opening_h=56.00,
    panel_arm_centres=(24.0, 51.0),
    retainer_hook_centres=(12.0, 58.0),
    rear_latch_ys=(9.0, 60.0),
    usb_opening=PortOpening(half_w=6.2, z0=15.4, z1=22.8),
    hdmi_opening=PortOpening(half_w=8.2, z0=14.6, z1=23.4),
    usb_bulkhead=None,
    hdmi_bulkhead=None,
    rear_hatch_xs=(7.00, 18.50, 30.00, 73.60, 85.10, 96.60),
    rear_hatch_ys=(7.00, 18.00, 29.00, 40.00, 51.00, 62.00),
    section_a_offset=7.20,
)

# The LCD sets both body dimensions: 0.55 mm nominal clearance per side, which
# leaves at least 0.45 mm at the +0.2 mm outline tolerance.  The PCB ends are
# then 3.5 mm from the chassis walls, so the connector faces are carried by
# rear-cover bulkheads at the same 2.0 mm wall / 0.3 mm gap relationship as the
# 4.3-inch chassis.  The chassis openings are enlarged to admit cable
# overmoulds up to 15.0 x 9.0 mm (USB-C) and 23.0 x 12.0 mm (HDMI).
PROFILE_5P0IN = CaseProfile(
    key="5p0in",
    title="5-inch",
    lcd=SH500J01Z,
    body_w=120.70 + 0.55 * 2.0 + WALL * 2.0,
    body_h=75.90 + 0.55 * 2.0 + WALL * 2.0,
    # 4.5 mm contact band around the LCD rear perimeter.
    retainer_opening_w=120.70 - 9.00,
    retainer_opening_h=75.90 - 9.00,
    panel_arm_centres=(27.0, 54.0),
    retainer_hook_centres=(12.0, 64.6),
    rear_latch_ys=(9.0, 66.0),
    usb_opening=PortOpening(half_w=7.5, z0=14.6, z1=23.6),
    hdmi_opening=PortOpening(half_w=11.5, z0=13.0, z1=25.0),
    usb_bulkhead=PortBulkhead(
        notch=PortOpening(half_w=6.2, z0=15.4, z1=22.8),
        half_w=11.0,
    ),
    hdmi_bulkhead=PortBulkhead(
        notch=PortOpening(half_w=8.2, z0=14.6, z1=23.4),
        half_w=12.5,
    ),
    rear_hatch_xs=(7.00, 18.50, 30.00, 87.40, 98.90, 110.40),
    rear_hatch_ys=(8.80, 19.80, 30.80, 41.80, 52.80, 63.80),
    section_a_offset=6.00,
)

PROFILES: dict[str, CaseProfile] = {
    profile.key: profile for profile in (PROFILE_4P3IN, PROFILE_5P0IN)
}

for _profile in PROFILES.values():
    _profile.validate()


def get_profile(key: str) -> CaseProfile:
    try:
        return PROFILES[key]
    except KeyError as error:
        known = ", ".join(PROFILES)
        raise ValueError(f"unknown profile {key!r}; choose one of: {known}") from error
