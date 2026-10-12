#!/usr/bin/env python3
"""Generate print-ready STL files for the Tang Nano 9K panel enclosure.

The generator intentionally uses only the Python standard library.  Geometry is
constructed as rectilinear CSG, evaluated on an exact coordinate grid, and
written as binary STL.  This keeps the build reproducible without a CAD kernel.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import profiles  # noqa: E402
from tools.profiles import PROFILES, CaseProfile, get_profile  # noqa: E402


EPS = 1.0e-9


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float

    def __post_init__(self) -> None:
        if not (self.x0 < self.x1 and self.y0 < self.y1 and self.z0 < self.z1):
            raise ValueError(f"invalid box: {self}")


class RectilinearSolid:
    def __init__(self, name: str) -> None:
        self.name = name
        self.additions: list[Box] = []
        self.subtractions: list[Box] = []

    def add(self, *coords: float) -> None:
        self.additions.append(Box(*(round(value, 6) for value in coords)))

    def cut(self, *coords: float) -> None:
        self.subtractions.append(Box(*(round(value, 6) for value in coords)))

    def contains(self, x: float, y: float, z: float) -> bool:
        """Return whether a point is inside the evaluated CSG solid.

        Section drawings use this same positive-minus-negative definition as
        the STL mesher, so a drawn section cannot silently omit a slot, hook,
        rail, or service aperture that exists in the printable model.
        """

        def inside(box: Box) -> bool:
            return (
                box.x0 - EPS <= x <= box.x1 + EPS
                and box.y0 - EPS <= y <= box.y1 + EPS
                and box.z0 - EPS <= z <= box.z1 + EPS
            )

        return any(inside(box) for box in self.additions) and not any(
            inside(box) for box in self.subtractions
        )

    def _occupancy(self):
        """Evaluate the CSG on the grid formed by all box coordinates."""
        boxes = self.additions + self.subtractions
        if not self.additions:
            raise ValueError(f"{self.name}: no positive geometry")

        xs = sorted({v for b in boxes for v in (b.x0, b.x1)})
        ys = sorted({v for b in boxes for v in (b.y0, b.y1)})
        zs = sorted({v for b in boxes for v in (b.z0, b.z1)})
        xi = {v: i for i, v in enumerate(xs)}
        yi = {v: i for i, v in enumerate(ys)}
        zi = {v: i for i, v in enumerate(zs)}

        occupied: set[tuple[int, int, int]] = set()

        def cells(box: Box) -> Iterable[tuple[int, int, int]]:
            for i in range(xi[box.x0], xi[box.x1]):
                for j in range(yi[box.y0], yi[box.y1]):
                    for k in range(zi[box.z0], zi[box.z1]):
                        yield i, j, k

        for box in self.additions:
            occupied.update(cells(box))
        for box in self.subtractions:
            occupied.difference_update(cells(box))
        return xs, ys, zs, occupied

    def cells(self) -> list[Box]:
        """Return the evaluated solid as disjoint axis-aligned boxes."""
        xs, ys, zs, occupied = self._occupancy()
        return [
            Box(xs[i], ys[j], zs[k], xs[i + 1], ys[j + 1], zs[k + 1])
            for i, j, k in sorted(occupied)
        ]

    def triangles(self) -> list[tuple[tuple[float, float, float], ...]]:
        xs, ys, zs, occupied = self._occupancy()

        tris: list[tuple[tuple[float, float, float], ...]] = []

        def quad(a, b, c, d) -> None:
            tris.append((a, b, c))
            tris.append((a, c, d))

        for i, j, k in sorted(occupied):
            x0, x1 = xs[i], xs[i + 1]
            y0, y1 = ys[j], ys[j + 1]
            z0, z1 = zs[k], zs[k + 1]

            if (i - 1, j, k) not in occupied:
                quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0))
            if (i + 1, j, k) not in occupied:
                quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))
            if (i, j - 1, k) not in occupied:
                quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
            if (i, j + 1, k) not in occupied:
                quad((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0))
            if (i, j, k - 1) not in occupied:
                quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))
            if (i, j, k + 1) not in occupied:
                quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))

        return tris


def normal(tri: tuple[tuple[float, float, float], ...]) -> tuple[float, float, float]:
    a, b, c = tri
    u = tuple(b[n] - a[n] for n in range(3))
    v = tuple(c[n] - a[n] for n in range(3))
    n = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    length = math.sqrt(sum(value * value for value in n))
    if length < EPS:
        raise ValueError(f"degenerate triangle: {tri}")
    return tuple(value / length for value in n)


def write_binary_stl(path: Path, name: str, triangles) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"Tang Nano 9K panel case: {name}".encode("ascii")[:80].ljust(80, b"\0")
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(struct.pack("<I", len(triangles)))
        for tri in triangles:
            values = (*normal(tri), *tri[0], *tri[1], *tri[2])
            stream.write(struct.pack("<12fH", *values, 0))


# Shared reference dimensions, millimetres.  LCD-dependent values are in
# tools/profiles.py.
PCB_W = profiles.PCB_W
PCB_H = profiles.PCB_H
PCB_T = 1.60

BEZEL_T = 3.00
BODY_D = 27.00
WALL = profiles.WALL

RETAINER_HOOK_ARM_Z = 6.50
RETAINER_HOOK_STEP_Z0 = 4.70
RETAINER_HOOK_STEP_H = 0.60
RETAINER_HOOK_PROJECTIONS = (0.00, 0.20, 0.60)
# Chassis hook windows relative to the retainer rear face.  The outermost
# hook step clears each window edge by 0.10 mm.
RETAINER_WINDOW_DZ0 = 5.80
RETAINER_WINDOW_DZ1 = 6.60

PCB_SIDE_CLEARANCE = 0.25
PCB_AXIAL_CLEARANCE = 0.30
PCB_MOUNT_HOLE_D = 2.20
PCB_MOUNT_HOLE_EDGE_OFFSET = 2.60
M2_PILOT_SQUARE = 1.70
M2_BOSS_SIZE = 6.00
M2_THREAD_DEPTH = 6.00
# The rear-cover plate rests on the rear end of the chassis walls.  Its inner
# face is therefore at z=BODY_D for the standard cover, 7.00 mm behind the PCB
# rear surface.  Deeper covers keep the same seat through perimeter posts.
PCB_REAR_Z = 20.00
COVER_PLATE_T = 2.00
STANDARD_REAR_CLEARANCE = BODY_D - PCB_REAR_Z
EXPANDED_REAR_CLEARANCES = (20.00, 30.00)
COVER_SEAT_POST_LENGTH = 6.00
# Rear-cover PCB end stops, x ranges relative to the PCB left edge.
PCB_END_STOP_XS = ((4.50, 7.50), (18.50, 21.50))
PCB_END_STOP_T = 0.30
# Clearance between a rear-cover feature and the chassis wall pocket around it.
WALL_POCKET_CLEARANCE = 0.10

# Through-slots remove material from the broad, non-load-bearing regions of
# the rear plate.  The profile pattern stays outside the PCB carrier, screw
# bosses, perimeter rim, and connector-stop buttresses.
REAR_HATCH_SLOT_W = 8.00
REAR_HATCH_SLOT_H = 6.00


def overall_depth(rear_clearance: float) -> float:
    """Distance from the bezel face to the outer face of the rear cover."""
    return PCB_REAR_Z + rear_clearance + COVER_PLATE_T


def retainer_assembly_z(profile: CaseProfile) -> float:
    """Global z of the retainer face that rests on the LCD rear."""
    return BEZEL_T + profile.lcd.thickness


def retainer_window_z(profile: CaseProfile) -> tuple[float, float]:
    base = retainer_assembly_z(profile)
    return base + RETAINER_WINDOW_DZ0, base + RETAINER_WINDOW_DZ1


def add_side_with_snap_arms(
    solid: RectilinearSolid,
    profile: CaseProfile,
    side: str,
    panel_t: float,
) -> None:
    """Add one long side wall with two inward-deflecting panel clips."""
    body_x, body_y = profile.body_x, profile.body_y
    body_w, body_h = profile.body_w, profile.body_h
    arm_centres = profile.panel_arm_centres
    slot_half = 5.0
    arm_half = 4.0
    arm_z0 = 4.2
    arm_anchor_z = 17.0

    if side == "left":
        wall_x0, wall_x1 = body_x, body_x + WALL
        arm_x0, arm_x1 = body_x + 0.55, body_x + 1.55
        head_ranges = (
            (body_x - 0.80, body_x + 1.55),
            (body_x - 0.50, body_x + 1.55),
            (body_x - 0.20, body_x + 1.55),
        )
    elif side == "right":
        wall_x0, wall_x1 = body_x + body_w - WALL, body_x + body_w
        arm_x0, arm_x1 = body_x + body_w - 1.55, body_x + body_w - 0.55
        head_ranges = (
            (body_x + body_w - 1.55, body_x + body_w + 0.80),
            (body_x + body_w - 1.55, body_x + body_w + 0.50),
            (body_x + body_w - 1.55, body_x + body_w + 0.20),
        )
    else:
        raise ValueError(side)

    # Continuous wall at the front and rear of the flexible-arm zone.
    solid.add(wall_x0, body_y, BEZEL_T, wall_x1, body_y + body_h, arm_z0)
    solid.add(wall_x0, body_y, arm_anchor_z, wall_x1, body_y + body_h, BODY_D)

    # Wall segments between the arm clearance slots.
    bounds = [body_y]
    for centre in arm_centres:
        bounds.extend((body_y + centre - slot_half, body_y + centre + slot_half))
    bounds.append(body_y + body_h)
    for start, end in zip(bounds[0::2], bounds[1::2]):
        solid.add(wall_x0, start, arm_z0, wall_x1, end, arm_anchor_z)

    catch_z = BEZEL_T + panel_t + 0.40
    for centre in arm_centres:
        y0 = body_y + centre - arm_half
        y1 = body_y + centre + arm_half
        solid.add(arm_x0, y0, arm_z0, arm_x1, y1, arm_anchor_z + 1.0)
        for step, (x0, x1) in enumerate(head_ranges):
            z0 = catch_z + step * 0.8
            solid.add(x0, y0, z0, x1, y1, z0 + 0.8)


def front_chassis(profile: CaseProfile, panel_t: float) -> RectilinearSolid:
    solid = RectilinearSolid(f"front-chassis-{panel_t:.1f}mm-panel")
    body_x, body_y = profile.body_x, profile.body_y
    body_w, body_h = profile.body_w, profile.body_h

    # Front bezel and active-area window.
    solid.add(0.0, 0.0, 0.0, profile.bezel_w, profile.bezel_h, BEZEL_T)
    solid.cut(
        profile.window_x,
        profile.window_y,
        -0.1,
        profile.window_x + profile.window_w,
        profile.window_y + profile.window_h,
        BEZEL_T + 0.1,
    )

    add_side_with_snap_arms(solid, profile, "left", panel_t)
    add_side_with_snap_arms(solid, profile, "right", panel_t)

    # Top and bottom walls. The generous openings accept moulding variation in
    # USB-C and HDMI shells while keeping the connector faces recessed.
    solid.add(body_x, body_y, BEZEL_T, body_x + body_w, body_y + WALL, BODY_D)
    solid.add(
        body_x,
        body_y + body_h - WALL,
        BEZEL_T,
        body_x + body_w,
        body_y + body_h,
        BODY_D,
    )
    port_centre_x = profile.bezel_w / 2.0
    usb = profile.usb_opening
    hdmi = profile.hdmi_opening
    solid.cut(
        port_centre_x - usb.half_w,
        body_y - 0.1,
        usb.z0,
        port_centre_x + usb.half_w,
        body_y + WALL + 0.1,
        usb.z1,
    )
    solid.cut(
        port_centre_x - hdmi.half_w,
        body_y + body_h - WALL - 0.1,
        hdmi.z0,
        port_centre_x + hdmi.half_w,
        body_y + body_h + 0.1,
        hdmi.z1,
    )

    # The rear-cover end stops sit closer to the wall than the wall inner face
    # allows.  Shallow pockets, open toward the rear, receive them.
    stop_outer_y = (
        profile.pcb_y - PCB_AXIAL_CLEARANCE - PCB_END_STOP_T,
        profile.pcb_y + PCB_H + PCB_AXIAL_CLEARANCE + PCB_END_STOP_T,
    )
    if stop_outer_y[0] - WALL_POCKET_CLEARANCE < body_y + WALL:
        gap = WALL_POCKET_CLEARANCE
        for stop_x0, stop_x1 in PCB_END_STOP_XS:
            x0 = profile.pcb_x + stop_x0 - gap
            x1 = profile.pcb_x + stop_x1 + gap
            z0 = PCB_REAR_Z - PCB_T - gap
            solid.cut(x0, stop_outer_y[0] - gap, z0,
                      x1, body_y + WALL + 0.1, BODY_D + 0.1)
            solid.cut(x0, body_y + body_h - WALL - 0.1, z0,
                      x1, stop_outer_y[1] + gap, BODY_D + 0.1)

    # Four windows accept the independent LCD-retainer snap hooks.  The hook
    # centres deliberately avoid the panel-mount flex arms so the two snap
    # systems do not weaken the same wall sections.
    window_z0, window_z1 = retainer_window_z(profile)
    for centre in profile.retainer_hook_centres:
        y0 = profile.retainer_y + centre - 3.20
        y1 = profile.retainer_y + centre + 3.20
        solid.cut(body_x - 0.1, y0, window_z0,
                  body_x + WALL + 0.1, y1, window_z1)
        solid.cut(body_x + body_w - WALL - 0.1, y0, window_z0,
                  body_x + body_w + 0.1, y1, window_z1)

    # Rear-cover latch windows, two on each long wall.
    for latch_y in profile.rear_latch_ys:
        y0 = body_y + latch_y
        solid.cut(body_x - 0.1, y0, 23.2, body_x + WALL + 0.1, y0 + 6.0, 25.7)
        solid.cut(
            body_x + body_w - WALL - 0.1,
            y0,
            23.2,
            body_x + body_w + 0.1,
            y0 + 6.0,
            25.7,
        )

    return solid


def lcd_retainer(profile: CaseProfile) -> RectilinearSolid:
    solid = RectilinearSolid("lcd-retainer")
    outer_w = profile.retainer_w
    outer_h = profile.retainer_h
    thickness = 2.00
    inner_w = profile.retainer_opening_w
    inner_h = profile.retainer_opening_h
    bx = (outer_w - inner_w) / 2.0
    by = (outer_h - inner_h) / 2.0

    solid.add(0.0, 0.0, 0.0, outer_w, outer_h, thickness)
    solid.cut(bx, by, -0.1, bx + inner_w, by + inner_h, thickness + 0.1)
    # 40-pin FPC tail relief on the edge where the FPC leaves the LCD.
    relief_x0 = profile.retainer_lcd_dx + profile.lcd.fpc_x0
    relief_x1 = profile.retainer_lcd_dx + profile.lcd.fpc_x1
    if profile.lcd.fpc_side == "top":
        relief_y0, relief_y1 = outer_h - by - 0.1, outer_h + 0.1
    else:
        relief_y0, relief_y1 = -0.1, by + 0.1
    solid.cut(relief_x0, relief_y0, -0.1,
              relief_x1, relief_y1, thickness + 0.1)

    # Four rear-facing cantilever hooks make the retainer independent of the
    # removable rear cover.  The 1.2 mm arms flex inward during insertion and
    # the stepped 0.6 mm heads engage the chassis windows.
    arm_w = 1.20
    arm_z = RETAINER_HOOK_ARM_Z
    for centre in profile.retainer_hook_centres:
        y0 = centre - 3.0
        y1 = centre + 3.0

        # Left and right cantilever arms.
        solid.add(0.0, y0, 0.0, arm_w, y1, arm_z)
        solid.add(outer_w - arm_w, y0, 0.0, outer_w, y1, arm_z)

        # Three rectilinear ramp steps on each outward-facing hook head.
        for step, projection in enumerate(RETAINER_HOOK_PROJECTIONS):
            z0 = RETAINER_HOOK_STEP_Z0 + step * RETAINER_HOOK_STEP_H
            z1 = z0 + RETAINER_HOOK_STEP_H
            solid.add(-projection, y0, z0, arm_w, y1, z1)
            solid.add(outer_w - arm_w, y0, z0,
                      outer_w + projection, y1, z1)
    return solid


def rear_cover(profile: CaseProfile,
               rear_clearance: float = STANDARD_REAR_CLEARANCE) -> RectilinearSolid:
    """Build a cover while keeping the PCB and connector planes unchanged.

    ``rear_clearance`` is measured from the PCB rear surface at global z=20
    to the inner face of the rear plate.  Increasing it extends only the rear
    shell and the carrier columns; USB-C, HDMI, LCD, and PCB global positions
    remain identical across variants.

    Cover coordinates start at the outer face of the plate.  Features inside
    the chassis are positioned from the chassis rear end at cover
    z=``depth_extension``.
    """
    if rear_clearance < STANDARD_REAR_CLEARANCE:
        raise ValueError(
            f"rear clearance cannot be less than {STANDARD_REAR_CLEARANCE:.0f} mm"
        )
    depth_extension = overall_depth(rear_clearance) - BODY_D
    solid = RectilinearSolid(
        f"rear-cover-pcb-carrier-{rear_clearance:.0f}mm-clearance"
    )
    cover_w = profile.cover_w
    cover_h = profile.cover_h
    plate_t = COVER_PLATE_T
    rim_w = cover_w - 4.00
    rim_h = cover_h - 4.00
    rim_x = (cover_w - rim_w) / 2.0
    rim_y = (cover_h - rim_h) / 2.0
    rim_t = 1.50
    rim_hz = 4.50 + depth_extension

    solid.add(0.0, 0.0, 0.0, cover_w, cover_h, plate_t)
    solid.add(rim_x, rim_y, plate_t, rim_x + rim_t, rim_y + rim_h, rim_hz)
    solid.add(rim_x + rim_w - rim_t, rim_y, plate_t,
              rim_x + rim_w, rim_y + rim_h, rim_hz)
    solid.add(rim_x, rim_y, plate_t, rim_x + rim_w, rim_y + rim_t, rim_hz)
    solid.add(rim_x, rim_y + rim_h - rim_t, plate_t,
              rim_x + rim_w, rim_y + rim_h, rim_hz)

    # Four shallow bumps engage the chassis latch windows.  The window
    # positions are defined from the chassis body edge, so convert them into
    # cover coordinates instead of measuring from the rim.
    latch_z0 = 2.25 + depth_extension
    latch_z1 = 3.85 + depth_extension
    for latch_y in profile.rear_latch_ys:
        y0 = profile.body_y + latch_y - profile.cover_y
        solid.add(rim_x - 0.35, y0, latch_z0,
                  rim_x + 0.35, y0 + 6.0, latch_z1)
        solid.add(rim_x + rim_w - 0.35, y0, latch_z0,
                  rim_x + rim_w + 0.35, y0 + 6.0, latch_z1)

    board_x = (cover_w - PCB_W) / 2.0
    board_y = (cover_h - PCB_H) / 2.0
    support_z = 7.00 + depth_extension
    board_top = support_z + PCB_T
    rail_top = board_top + 0.60
    side_clearance = PCB_SIDE_CLEARANCE

    for y0, y1 in ((board_y + 9.0, board_y + 28.0),
                   (board_y + 42.0, board_y + 61.0)):
        # Four shelves support the PCB without loading components.
        solid.add(board_x - side_clearance - 0.80, y0, plate_t,
                  board_x + 1.20, y1, support_z)
        solid.add(board_x + PCB_W - 1.20, y0, plate_t,
                  board_x + PCB_W + side_clearance, y1, support_z)

        # Left side: fixed guide and lip.  Insert this PCB edge first.
        solid.add(board_x - side_clearance - 0.80, y0, support_z,
                  board_x - side_clearance, y1, rail_top)
        solid.add(board_x - side_clearance, y0, board_top,
                  board_x + 0.55, y1, rail_top)

        # Right side: 1.2 mm cantilever clip rooted at the cover plate.  Its
        # stepped head cams outward as the second PCB edge is pressed down.
        clip_x0 = board_x + PCB_W + side_clearance
        clip_x1 = clip_x0 + 1.20
        solid.add(clip_x0, y0, plate_t, clip_x1, y1, board_top)
        for step, overlap in enumerate((0.55, 0.35, 0.15)):
            z0 = board_top + step * 0.20
            solid.add(board_x + PCB_W - overlap, y0, z0,
                      clip_x1, y1, z0 + 0.20)

    if profile.usb_bulkhead is None:
        # Paired end stops take USB-C/HDMI insertion loads instead of
        # transferring them through the PCB connector solder joints.  Each
        # stop is carried by a buttress that overlaps the perimeter rim, so
        # the STL contains one connected printable part instead of four
        # floating stop bodies.
        stop_y_ranges = (
            (board_y - PCB_AXIAL_CLEARANCE - PCB_END_STOP_T,
             board_y - PCB_AXIAL_CLEARANCE),
            (board_y + PCB_H + PCB_AXIAL_CLEARANCE,
             board_y + PCB_H + PCB_AXIAL_CLEARANCE + PCB_END_STOP_T),
        )
        for stop_x0, stop_x1 in PCB_END_STOP_XS:
            x0, x1 = board_x + stop_x0, board_x + stop_x1
            lower_y0, lower_y1 = stop_y_ranges[0]
            upper_y0, upper_y1 = stop_y_ranges[1]
            solid.add(x0, lower_y0, support_z, x1, lower_y1, board_top)
            solid.add(x0, upper_y0, support_z, x1, upper_y1, board_top)

            # These supports remain outside the PCB outline.  Their overlap
            # with the bottom/top rim gives a volumetric union that survives
            # importers which do not merge bodies that merely share a
            # coplanar face.
            solid.add(x0, lower_y0, plate_t,
                      x1, rim_y + rim_t, support_z)
            solid.add(x0, rim_y + rim_h - rim_t, plate_t,
                      x1, upper_y1, support_z)
    else:
        _add_port_bulkheads(solid, profile, board_x, board_y, rim_y, rim_t,
                            rim_hz, depth_extension)

    # Deep covers stand behind the chassis.  Perimeter posts reach forward to
    # the chassis wall end so every variant has the same positive seat as
    # the standard cover plate.  Each post overlaps the rim for a volumetric
    # union.
    seat_z = depth_extension
    if seat_z > plate_t:
        post = COVER_SEAT_POST_LENGTH
        rim_overlap = rim_t / 2.0
        for centre_y in (cover_h * 0.2, cover_h * 0.8):
            y0, y1 = centre_y - post / 2.0, centre_y + post / 2.0
            solid.add(0.0, y0, plate_t, rim_x + rim_overlap, y1, seat_z)
            solid.add(cover_w - rim_x - rim_overlap, y0, plate_t,
                      cover_w, y1, seat_z)
        for centre_x in (cover_w * 0.2, cover_w * 0.8):
            x0, x1 = centre_x - post / 2.0, centre_x + post / 2.0
            solid.add(x0, 0.0, plate_t, x1, rim_y + rim_overlap, seat_z)
            solid.add(x0, cover_h - rim_y - rim_overlap, plate_t,
                      x1, cover_h, seat_z)

    # Tang Nano 9K has two mounting holes at the HDMI end.  Square 1.70 mm
    # pilot bores are intentional: they are printable without circular CSG and
    # give an M2 self-tapping screw four gripping flats.  The optional screws
    # supplement the fixed lip and flex clips; screwless use remains possible.
    hdmi_hole_y = board_y + PCB_H - PCB_MOUNT_HOLE_EDGE_OFFSET
    boss_half = M2_BOSS_SIZE / 2.0
    pilot_half = M2_PILOT_SQUARE / 2.0
    for hole_x in (
        board_x + PCB_MOUNT_HOLE_EDGE_OFFSET,
        board_x + PCB_W - PCB_MOUNT_HOLE_EDGE_OFFSET,
    ):
        solid.add(hole_x - boss_half, hdmi_hole_y - boss_half, plate_t,
                  hole_x + boss_half, hdmi_hole_y + boss_half, support_z)
        solid.cut(hole_x - pilot_half, hdmi_hole_y - pilot_half,
                  support_z - M2_THREAD_DEPTH,
                  hole_x + pilot_half, hdmi_hole_y + pilot_half,
                  support_z + 0.10)

    # Large service aperture exposes the underside TF/microSD socket and also
    # provides ventilation. It deliberately avoids the PCB edge rails.
    solid.cut(board_x + 3.50, board_y + 12.0, -0.1,
              board_x + PCB_W - 3.50, board_y + 58.0, plate_t + 0.1)

    # Explicit rear-plate perforations reduce submitted model volume even
    # when the print service does not expose slicer infill settings.  The
    # remaining orthogonal webs keep the plate and all integrated features in
    # one connected component.
    for hatch_x in profile.rear_hatch_xs:
        for hatch_y in profile.rear_hatch_ys:
            solid.cut(hatch_x, hatch_y, -0.1,
                      hatch_x + REAR_HATCH_SLOT_W,
                      hatch_y + REAR_HATCH_SLOT_H,
                      plate_t + 0.1)

    return solid


def _add_port_bulkheads(
    solid: RectilinearSolid,
    profile: CaseProfile,
    board_x: float,
    board_y: float,
    rim_y: float,
    rim_t: float,
    rim_hz: float,
    depth_extension: float,
) -> None:
    """Add connector bulkheads at both PCB ends of a rear cover.

    Used when the LCD makes the chassis taller than the PCB.  Each bulkhead
    reproduces the chassis wall of the compact profile 0.30 mm from the PCB
    end: its inner face is the axial end stop and its U-shaped notch is the
    connector opening.  The notch is open toward the LCD so the PCB can be
    pressed into the carrier.  The rim is cut back in front of each bulkhead
    so that a cable overmould entering the enlarged chassis opening reaches
    the bulkhead face.
    """
    seat_z = depth_extension
    centre_x = board_x + PCB_W / 2.0
    ends = (
        (profile.usb_bulkhead, profile.usb_opening, -1.0),
        (profile.hdmi_bulkhead, profile.hdmi_opening, 1.0),
    )
    for bulkhead, opening, direction in ends:
        if bulkhead is None:
            raise ValueError(f"{profile.key}: bulkheads must be defined in pairs")
        # The notch cut overshoots only toward the chassis wall, so it cannot
        # touch the M2 bosses or shelves on the PCB side.
        if direction < 0:
            inner_y = board_y - PCB_AXIAL_CLEARANCE
            y0, y1 = inner_y - bulkhead.thickness, inner_y
            rim_cut = (rim_y - 0.1, y0)
            notch_y = (y0 - 0.1, y1)
        else:
            inner_y = board_y + PCB_H + PCB_AXIAL_CLEARANCE
            y0, y1 = inner_y, inner_y + bulkhead.thickness
            rim_cut = (y1, profile.cover_h - rim_y + 0.1)
            notch_y = (y0, y1 + 0.1)
        # Global z maps to cover z as seat_z + BODY_D - z.
        free_end_z = seat_z + BODY_D - bulkhead.notch.z0
        notch_floor_z = seat_z + BODY_D - bulkhead.notch.z1
        rim_half = opening.half_w + 0.30

        solid.cut(centre_x - rim_half, rim_cut[0], COVER_PLATE_T,
                  centre_x + rim_half, rim_cut[1], rim_hz + 0.1)
        solid.add(centre_x - bulkhead.half_w, y0, COVER_PLATE_T,
                  centre_x + bulkhead.half_w, y1, free_end_z)
        solid.cut(centre_x - bulkhead.notch.half_w, notch_y[0], notch_floor_z,
                  centre_x + bulkhead.notch.half_w, notch_y[1], free_end_z + 0.1)
        # The rim is removed only in front of the bulkhead; the remaining rim
        # must overlap it so the cover stays one connected part.
        rim_overlaps = (y0 < rim_y + rim_t if direction < 0
                        else y1 > profile.cover_h - rim_y - rim_t)
        if not rim_overlaps:
            raise ValueError(f"{profile.key}: bulkhead does not reach the rim")


def _translated_triangles(triangles, dx: float, dy: float, dz: float):
    return [
        tuple((x + dx, y + dy, z + dz) for x, y, z in triangle)
        for triangle in triangles
    ]


def _assembled_cover_triangles(
    triangles,
    overall_depth: float,
    dx: float,
    dy: float,
):
    """Reflect a rear-cover mesh into assembly coordinates.

    Reflection reverses handedness, so the second and third vertices are
    swapped to retain outward winding and positive signed volume.
    """
    assembled = []
    for triangle in triangles:
        mapped = tuple(
            (x + dx, y + dy, overall_depth - z)
            for x, y, z in triangle
        )
        assembled.append((mapped[0], mapped[2], mapped[1]))
    return assembled


def lcd_proxy(profile: CaseProfile) -> RectilinearSolid:
    lcd = RectilinearSolid("assembly-reference-lcd-proxy")
    lcd.add(profile.lcd_x, profile.lcd_y, BEZEL_T,
            profile.lcd_x + profile.lcd.width,
            profile.lcd_y + profile.lcd.height,
            BEZEL_T + profile.lcd.thickness)
    return lcd


def pcb_proxy(profile: CaseProfile) -> RectilinearSolid:
    pcb_x, pcb_y = profile.pcb_x, profile.pcb_y
    pcb = RectilinearSolid("assembly-reference-pcb-proxy")
    pcb.add(pcb_x, pcb_y, 18.40,
            pcb_x + PCB_W, pcb_y + PCB_H, 18.40 + PCB_T)
    hdmi_hole_y = pcb_y + PCB_H - PCB_MOUNT_HOLE_EDGE_OFFSET
    hole_half = PCB_MOUNT_HOLE_D / 2.0
    for hdmi_hole_x in (
        pcb_x + PCB_MOUNT_HOLE_EDGE_OFFSET,
        pcb_x + PCB_W - PCB_MOUNT_HOLE_EDGE_OFFSET,
    ):
        pcb.cut(hdmi_hole_x - hole_half, hdmi_hole_y - hole_half, 18.30,
                hdmi_hole_x + hole_half, hdmi_hole_y + hole_half, 20.10)
    return pcb


def assembly_reference_triangles(profile: CaseProfile, rear_clearance: float):
    """Return a non-print assembly reference containing five closed shells."""
    triangles = list(front_chassis(profile, 2.0).triangles())

    retainer = lcd_retainer(profile).triangles()
    triangles.extend(_translated_triangles(
        retainer,
        profile.retainer_x,
        profile.retainer_y,
        retainer_assembly_z(profile),
    ))

    triangles.extend(_assembled_cover_triangles(
        rear_cover(profile, rear_clearance).triangles(),
        overall_depth(rear_clearance),
        profile.cover_x,
        profile.cover_y,
    ))
    triangles.extend(lcd_proxy(profile).triangles())
    triangles.extend(pcb_proxy(profile).triangles())
    return triangles


PRINTABLE_STL_NAMES = (
    "front_chassis_panel_1p5mm.stl",
    "front_chassis_panel_2p0mm.stl",
    "front_chassis_panel_3p0mm.stl",
    "lcd_retainer.stl",
    "rear_cover.stl",
    "rear_cover_clearance_20mm.stl",
    "rear_cover_clearance_30mm.stl",
)
REFERENCE_STL_NAMES = tuple(
    f"assembly_reference_clearance_{clearance:.0f}mm.stl"
    for clearance in EXPANDED_REAR_CLEARANCES
)


def printable_models(profile: CaseProfile) -> dict[str, RectilinearSolid]:
    models = {
        "front_chassis_panel_1p5mm.stl": front_chassis(profile, 1.5),
        "front_chassis_panel_2p0mm.stl": front_chassis(profile, 2.0),
        "front_chassis_panel_3p0mm.stl": front_chassis(profile, 3.0),
        "lcd_retainer.stl": lcd_retainer(profile),
        "rear_cover.stl": rear_cover(profile),
        "rear_cover_clearance_20mm.stl": rear_cover(profile, 20.0),
        "rear_cover_clearance_30mm.stl": rear_cover(profile, 30.0),
    }
    assert tuple(models) == PRINTABLE_STL_NAMES
    return models


def generate(output_dir: Path, profile: CaseProfile) -> None:
    """Write all STL files for one profile into ``output_dir``."""
    for filename, solid in printable_models(profile).items():
        triangles = solid.triangles()
        write_binary_stl(output_dir / filename, solid.name, triangles)
        print(f"{profile.key}/{filename}: {len(triangles)} triangles")

    for rear_clearance, filename in zip(EXPANDED_REAR_CLEARANCES,
                                        REFERENCE_STL_NAMES):
        triangles = assembly_reference_triangles(profile, rear_clearance)
        write_binary_stl(
            output_dir / filename,
            f"REFERENCE-ONLY assembled case {rear_clearance:.0f}mm clearance",
            triangles,
        )
        print(f"{profile.key}/{filename}: {len(triangles)} triangles "
              "(REFERENCE ONLY)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("build"),
                        help="root directory; one sub-directory per profile")
    parser.add_argument("--profile", action="append", choices=sorted(PROFILES),
                        help="profile to generate; repeatable, default: all")
    args = parser.parse_args()
    for key in args.profile or PROFILES:
        generate(args.output / key, get_profile(key))


if __name__ == "__main__":
    main()
