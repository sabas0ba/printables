"""Two-part case for Raspberry Pi 5, M.2 HAT+ and a 2280 NVMe SSD, mm.

SPDX-License-Identifier: CC-BY-SA-4.0

Coordinates follow the Raspberry Pi 5 mechanical drawing: x along the 85 mm
edge (USB/Ethernet at x = 85), y along the 56 mm edge (GPIO at y = 56) and
z up. The tray floor underside is z = 0.

The M.2 HAT+ officially supports 2230 and 2242 only. A 2280 drive overhangs
the HAT and the USB/Ethernet ports, so the tray carries its end on a ledge and
a spring tongue in the lid presses the end onto it.
"""

from pathlib import Path
import math

import cadquery as cq


DIRECTORY = Path(__file__).resolve().parent

# Raspberry Pi 5 and M.2 HAT+ (published reference drawings).
PI_LENGTH, PI_WIDTH = 85.0, 56.0
PI_HOLES = [(x, y) for x in (3.5, 61.5) for y in (3.5, 52.5)]
USB_C_X, HDMI_X = 11.2, (25.8, 39.2)
ETHERNET_Y, USB_Y = 10.2, (29.1, 47.0)
PORT_OVERHANG = 3.0
HAT_LENGTH, HAT_WIDTH = 65.0, 56.5
HAT_GAP = 16.0  # HAT+ specification: 16 mm board-to-board spacers

# Estimated from the drawings; verify against the physical parts.
PCB_THICKNESS = 1.6
USB_TOP_ABOVE_PCB = 15.3
POWER_BUTTON_Y, STATUS_LED_Y = 18.4, 13.3
MICROSD_Y = (22.5, 33.5)
M2_CARD_STANDOFF = 2.25  # HAT top surface to SSD underside
M2_CARD_THICKNESS = 0.8
M2_COMPONENT_HEIGHT = 1.5
M2_2242_END_X = 61.1
M2_CARD_Y = (17.5, 39.5)
M2_CARD_END_X = M2_2242_END_X + 80.0 - 42.0

# Stack heights.
FLOOR = 2.0
BOSS_HEIGHT = 4.0
PCB_BOTTOM = FLOOR + BOSS_HEIGHT
PCB_TOP = PCB_BOTTOM + PCB_THICKNESS
HAT_BOTTOM = PCB_TOP + HAT_GAP
HAT_TOP = HAT_BOTTOM + PCB_THICKNESS
CARD_BOTTOM = HAT_TOP + M2_CARD_STANDOFF

# Case.
WALL = 2.4
LID = 2.0
CORNER_RADIUS = 3.0
INNER_X = (-6.5, 101.5)
INNER_Y = (-2.2, 57.5)
WALL_TOP = 31.0
OUTER_X = (INNER_X[0] - WALL, INNER_X[1] + WALL)
OUTER_Y = (INNER_Y[0] - WALL, INNER_Y[1] + WALL)

LEDGE_DROP = 0.3  # ledge sits slightly low; the lid tongue takes up the gap
LEDGE_TOP = CARD_BOTTOM - LEDGE_DROP
LEDGE_THICKNESS = 2.0
LEDGE_X = (M2_CARD_END_X - 3.6, INNER_X[1])
LEDGE_Y = (M2_CARD_Y[0] - 2.0, M2_CARD_Y[1] + 2.0)
PORTAL_Y = (1.8, 55.8)
PORTAL_Z = (4.0, LEDGE_TOP - LEDGE_THICKNESS)
TONGUE_PRELOAD = 0.4

SCREW_PILOT = 2.5  # M3 self-tapping
SCREW_CLEARANCE = 3.4
SCREWS = [(-5.0, 1.2), (-5.0, 54.5), (99.9, -1.4), (99.9, 57.85)]
COLUMNS = [((INNER_X[0], -1.2), (INNER_Y[0], 7.0)),
           ((INNER_X[0], -1.2), (50.0, INNER_Y[1])),
           ((96.0, INNER_X[1]), (INNER_Y[0], PORTAL_Y[0])),
           ((96.0, INNER_X[1]), (PORTAL_Y[1], INNER_Y[1]))]
FEET = [(-2.5, 12.0), (-2.5, 44.0), (97.0, 8.0), (97.0, 48.0)]


def box(x, y, z):
    """Axis-aligned box from (min, max) ranges."""
    return (cq.Workplane("XY")
            .box(x[1] - x[0], y[1] - y[0], z[1] - z[0])
            .translate(((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2))
            .val())


def cylinder(x, y, z, radius):
    return cq.Solid.makeCylinder(radius, z[1] - z[0], cq.Vector(x, y, z[0]))


def rounded_slot(center, size, axis, depth, radius=None):
    """Rounded rectangle through a wall. axis is the wall normal: 'x', 'y' or 'z'."""
    width, height = size
    radius = min(width, height) / 2 - 0.01 if radius is None else radius
    if axis == "y":
        plane = cq.Plane(origin=(center[0], center[1] - depth / 2, center[2]),
                         xDir=(1, 0, 0), normal=(0, 1, 0))
    elif axis == "z":
        plane = cq.Plane(origin=(center[0], center[1], center[2] - depth / 2),
                         xDir=(1, 0, 0), normal=(0, 0, 1))
    else:
        plane = cq.Plane(origin=(center[0] - depth / 2, center[1], center[2]),
                         xDir=(0, 1, 0), normal=(1, 0, 0))
    return (cq.Workplane(plane).rect(width, height).extrude(depth)
            .edges(f"|{axis.upper()}").fillet(radius).val())


def outline(z):
    sketch = (cq.Workplane("XY", origin=(0, 0, z[0]))
              .center(sum(OUTER_X) / 2, sum(OUTER_Y) / 2)
              .rect(OUTER_X[1] - OUTER_X[0], OUTER_Y[1] - OUTER_Y[0])
              .extrude(z[1] - z[0]))
    return sketch.edges("|Z").fillet(CORNER_RADIUS).val()


def fuse(shape, others):
    for other in others:
        shape = shape.fuse(other)
    return shape


def cut(shape, others):
    for other in others:
        shape = shape.cut(other)
    return shape


def make_tray():
    tray = outline((0.0, WALL_TOP)).cut(box(INNER_X, INNER_Y, (FLOOR, WALL_TOP + 1)))
    additions = [cylinder(x, y, (FLOOR - 0.1, PCB_BOTTOM), 3.0) for x, y in PI_HOLES]
    additions += [box(x, y, (FLOOR - 0.1, WALL_TOP)) for x, y in COLUMNS]
    # Thick block that brings the left wall within 1.2 mm of the power button.
    additions.append(box((INNER_X[0] - 0.1, -1.2), (9.4, 22.0), (FLOOR - 0.1, WALL_TOP)))
    # Ledge carrying the overhanging end of the 2280 drive.
    additions.append(box(LEDGE_X, LEDGE_Y, (PORTAL_Z[1], LEDGE_TOP)))
    tray = fuse(tray, additions)

    hex_diameter = 5.3 / math.cos(math.pi / 6)
    removals = []
    for x, y in PI_HOLES:
        removals.append(cylinder(x, y, (-1, PCB_BOTTOM + 1), 1.4))
        removals.append(cq.Workplane("XY", origin=(x, y, -1))
                        .polygon(6, hex_diameter).extrude(4.0).val())
    removals += [cylinder(x, y, (WALL_TOP - 10, WALL_TOP + 1), SCREW_PILOT / 2)
                 for x, y in SCREWS]
    removals += [cylinder(x, y, (-1, 0.6), 5.25) for x, y in FEET]

    # Front wall: USB-C power and two micro HDMI.
    port_z = PCB_TOP + 1.65
    removals.append(rounded_slot((USB_C_X, INNER_Y[0], port_z), (12.5, 7.5), "y", 8, 1.5))
    removals += [rounded_slot((x, INNER_Y[0], port_z), (11.0, 7.5), "y", 8, 1.5)
                 for x in HDMI_X]
    # Right wall: one open portal for USB and Ethernet plugs.
    removals.append(box((INNER_X[1] - 1, OUTER_X[1] + 1), PORTAL_Y, PORTAL_Z))
    # Left wall: power button, status LED and microSD.
    removals.append(box((OUTER_X[0] - 1, -2.8), (11.0, 20.4), (4.5, 13.0)))
    removals.append(box((-3.0, 0.0), (15.8, 20.2), (PCB_TOP - 1.0, PCB_TOP + 4.4)))
    removals.append(rounded_slot((-2.0, STATUS_LED_Y, PCB_TOP + 1.0), (2.4, 2.4), "x", 3))
    removals.append(box((OUTER_X[0] - 1, 1.0), (MICROSD_Y[0] - 1, MICROSD_Y[1] + 1),
                        (-1, PCB_BOTTOM + 0.2)))

    # Ventilation for passive cooling: floor intake, side slots.
    removals += [rounded_slot((x, 28.0, FLOOR / 2), (2.0, 34.0), "z", FLOOR + 2)
                 for x in range(12, 80, 5)]
    removals += [rounded_slot((x, INNER_Y[0], 17.0), (2.0, 10.0), "y", 8)
                 for x in range(50, 86, 5)]
    removals += [rounded_slot((x, INNER_Y[1], 16.0), (2.0, 12.0), "y", 8)
                 for x in range(6, 86, 5)]
    tray = cut(tray, removals).clean()
    if not tray.isValid() or len(tray.Solids()) != 1:
        raise ValueError("Tray is not a valid single solid")
    return tray


def make_lid():
    lid = outline((WALL_TOP, WALL_TOP + LID))
    removals = [cylinder(x, y, (WALL_TOP - 1, WALL_TOP + LID + 1), SCREW_CLEARANCE / 2)
                for x, y in SCREWS]
    removals += [rounded_slot((x, 26.0, WALL_TOP + LID / 2), (2.0, 36.0), "z", LID + 2)
                 for x in range(10, 80, 5)]
    # GPIO stacking header and camera/display FFC route through the HAT notch.
    removals.append(box((2.0, 56.0), (49.2, 55.8), (WALL_TOP - 1, WALL_TOP + LID + 1)))
    removals.append(box((48.0, 57.0), (1.0, 15.0), (WALL_TOP - 1, WALL_TOP + LID + 1)))

    # Spring tongue: U-shaped slot, thinned from below, root at low x.
    tongue_x, tongue_y = (80.8, M2_CARD_END_X + 0.1), (20.0, 37.0)
    slot = box((tongue_x[0], tongue_x[1] + 1.2), (tongue_y[0] - 1.2, tongue_y[1] + 1.2),
               (WALL_TOP - 1, WALL_TOP + LID + 1)).cut(
        box((tongue_x[0] - 1, tongue_x[1]), tongue_y, (WALL_TOP - 2, WALL_TOP + LID + 2)))
    removals.append(slot)
    removals.append(box((82.0, tongue_x[1] + 0.1), tongue_y, (WALL_TOP - 1, WALL_TOP + 0.6)))
    lid = cut(lid, removals)

    card_top = LEDGE_TOP + M2_CARD_THICKNESS
    lid = lid.fuse(box((M2_CARD_END_X - 2.7, M2_CARD_END_X - 0.5), tongue_y,
                       (card_top - TONGUE_PRELOAD, WALL_TOP + 0.7))).clean()
    if not lid.isValid() or len(lid.Solids()) != 1:
        raise ValueError("Lid is not a valid single solid")
    return lid


def envelopes():
    """Simplified keep-out volumes of the boards, drive and plugs.

    Returns (name, solid, insertion) tuples. insertion=True volumes must also
    clear the tray when swept straight up out of the case.
    """
    port_top = PCB_TOP + USB_TOP_ABOVE_PCB
    port_x = (PI_LENGTH - 18.0, PI_LENGTH + PORT_OVERHANG)
    items = [
        ("pi-pcb", box((0, PI_LENGTH), (0, PI_WIDTH), (PCB_BOTTOM, PCB_TOP)), True),
        ("ethernet", box(port_x, (ETHERNET_Y - 8, ETHERNET_Y + 8),
                         (PCB_BOTTOM, PCB_TOP + 13.5)), True),
        ("usb-c", box((USB_C_X - 4.5, USB_C_X + 4.5), (-1.7, 7.0),
                      (PCB_TOP, PCB_TOP + 3.3)), True),
        ("microsd", box((-1.9, 12.0), MICROSD_Y, (PCB_BOTTOM - 1.4, PCB_BOTTOM)), True),
        ("power-button", box((-0.45, 3.0), (POWER_BUTTON_Y - 1.8, POWER_BUTTON_Y + 1.8),
                             (PCB_TOP, PCB_TOP + 2.0)), True),
        ("pcie-ffc-loop", box((-5.5, 10.5), (25.0, 35.0), (PCB_TOP, HAT_TOP)), True),
        ("hat", box((0, HAT_LENGTH), (0, HAT_WIDTH), (HAT_BOTTOM, HAT_TOP)), True),
        ("gpio-header", box((3.6, 54.4), (49.9, 55.1), (PCB_TOP, HAT_TOP + 8.5)), True),
        ("ssd", box((M2_2242_END_X - 42.0, M2_CARD_END_X), M2_CARD_Y,
                    (LEDGE_TOP, LEDGE_TOP + M2_CARD_THICKNESS)), False),
        ("ssd-components", box((M2_2242_END_X - 39.0, M2_CARD_END_X - 4.0), M2_CARD_Y,
                               (LEDGE_TOP + M2_CARD_THICKNESS,
                                LEDGE_TOP + M2_CARD_THICKNESS + M2_COMPONENT_HEIGHT)), False),
    ]
    items += [(f"usb-{y}", box(port_x, (y - 7.3, y + 7.3), (PCB_TOP, port_top)), True)
              for y in USB_Y]
    items += [(f"hdmi-{x}", box((x - 3.5, x + 3.5), (-1.5, 7.0), (PCB_TOP, PCB_TOP + 3.5)), True)
              for x in HDMI_X]
    items += [(f"spacer-{x}-{y}", cylinder(x, y, (PCB_TOP, HAT_BOTTOM), 2.5), True)
              for x, y in PI_HOLES]
    # Cable plugs: overmolds assumed up to 2 mm larger than the receptacle.
    plug_x = (PI_LENGTH + PORT_OVERHANG, OUTER_X[1] + 10)
    items += [(f"usb-plug-{y}", box(plug_x, (y - 8.5, y + 8.5), (PCB_TOP - 1.0, port_top + 2.0)), False)
              for y in USB_Y]
    items.append(("ethernet-plug", box(plug_x, (ETHERNET_Y - 7.5, ETHERNET_Y + 7.5),
                                       (PCB_TOP, PCB_TOP + 13.5)), False))
    port_z = PCB_TOP + 1.65
    front_y, front_depth = (OUTER_Y[0] - 10 - 1.7) / 2, -1.7 - (OUTER_Y[0] - 10)
    items.append(("usb-c-plug", rounded_slot((USB_C_X, front_y, port_z), (12.0, 6.6), "y",
                                             front_depth, 1.5), False))
    items += [(f"hdmi-plug-{x}", rounded_slot((x, front_y, port_z), (10.4, 6.6), "y",
                                              front_depth, 1.5), False)
              for x in HDMI_X]
    return items


def verify(tray, lid):
    """Check clearances of the keep-out volumes and the tongue preload."""
    items = envelopes()
    for name, solid, insertion in items:
        for part_name, part in (("tray", tray), ("lid", lid)):
            if name == "ssd" and part_name == "lid":
                continue
            volume = solid.intersect(part).Volume()
            if volume > 1e-3:
                raise ValueError(f"{name} intersects {part_name}: {volume:.3f} mm3")
        if insertion:
            # Bounding box swept upward: the assembly is lowered in vertically.
            bounds = solid.BoundingBox()
            path = box((bounds.xmin, bounds.xmax), (bounds.ymin, bounds.ymax),
                       (bounds.zmin, WALL_TOP + 1))
            if path.intersect(tray).Volume() > 1e-3:
                raise ValueError(f"{name} cannot be lowered into the tray")
    ssd = next(solid for name, solid, _ in items if name == "ssd")
    overlap = ssd.intersect(lid).Volume()
    expected = 2.2 * 17.0 * TONGUE_PRELOAD
    if abs(overlap - expected) > 0.05:
        raise ValueError(f"Unexpected tongue preload volume {overlap:.2f} mm3")


def export(shape, name):
    cq.exporters.export(shape, str(DIRECTORY / name), tolerance=0.05, angularTolerance=0.2)


if __name__ == "__main__":
    tray_shape, lid_shape = make_tray(), make_lid()
    verify(tray_shape, lid_shape)
    export(tray_shape, "tray.stl")
    # The lid is exported upside down, in its printing orientation.
    export(lid_shape.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)
           .translate(cq.Vector(0, 0, WALL_TOP + LID)), "lid.stl")
    boards = [solid for name, solid, _ in envelopes() if "plug" not in name]
    reference = fuse(boards[0], boards[1:])
    export(reference, "reference-assembly.stl")
