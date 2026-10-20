"""Flat desk dock for the CMF Watch 3 Pro and its magnetic charging cable, mm.

The watch lies face up on an annular seat that carries its case back at the
rim, so it no longer balances on the small charging head. The charging head
sits in a pocket below the seat, offset toward 6 o'clock where the charging
pads are, and its cable is held in an open channel so it cannot pull the head
out of place. The body is shorter than the case along the strap axis, so both
strap halves hang over the ends without being removed.

Coordinates: z up, the dock stands on z = 0 in its print orientation. The
strap runs along y (12 o'clock toward +y), the cable leaves toward +x.

The watch dimensions are published values. The charging head, its cable and
the position of the charging pads are placeholders (see the README) and must
be replaced by measurements of the physical parts before the dock is printed;
print coupon.stl first to check the pocket, the channel and the seat height.
"""

import math
from pathlib import Path

import cadquery as cq


DIRECTORY = Path(__file__).resolve().parent

# Watch, published values (47 x 47 x 14.4 mm, 22 mm straps).
CASE_DIAMETER = 47.0
CASE_THICKNESS = 14.4
STRAP_WIDTH = 22.0

# Watch, assumed: measure on the physical unit.
CASE_CLEARANCE = 0.5           # diametral clearance of the seat wall
SEAT_INNER_RADIUS = 19.0       # inner edge of the annular seat under the case back
SENSOR_CLEARANCE = 2.0         # drop inside the seat for the sensor dome
PAD_OFFSET = (0.0, -7.0)       # centre of the charging pads from the case centre

# Charging head and cable, placeholders: measure on the physical parts.
PUCK_LENGTH = 18.0             # along the cable
PUCK_WIDTH = 8.0
PUCK_HEIGHT = 5.0              # housing only, without the spring pins
PUCK_CLEARANCE = 0.3           # added to length and width of the pocket
PUCK_PROUD = 0.0               # head top above the seat; negative sinks it
PUCK_ANGLE = 0.0               # degrees about z; 0 sends the cable toward +x
CABLE_DIAMETER = 2.6
CABLE_CLEARANCE = 0.4          # added to the channel width

# Body.
FOOT_X = 64.0
FOOT_Y = 40.0                  # shorter than the case: the straps hang over the ends
HEIGHT = 14.0
CORNER_RADIUS = 6.0
TOP_FILLET = 1.0
SEAT_WALL = 3.0                # wall height around the case above the seat
MIN_FLOOR = 2.5                # material left under the pocket
COUPON_SIZE = 30.0

SEAT_Z = HEIGHT - SEAT_WALL
INNER_Z = SEAT_Z - SENSOR_CLEARANCE
POCKET_FLOOR_Z = SEAT_Z + PUCK_PROUD - PUCK_HEIGHT
CHANNEL_WIDTH = CABLE_DIAMETER + CABLE_CLEARANCE


def check_parameters():
    if POCKET_FLOOR_Z < MIN_FLOOR:
        raise ValueError(f"Pocket floor {POCKET_FLOOR_Z:.1f} mm is thinner than {MIN_FLOOR} mm")
    if POCKET_FLOOR_Z >= INNER_Z:
        raise ValueError("The pocket must start below the sensor clearance recess")
    pocket_reach = math.hypot(*PAD_OFFSET) + math.hypot(PUCK_LENGTH, PUCK_WIDTH) / 2
    if pocket_reach + PUCK_CLEARANCE > SEAT_INNER_RADIUS:
        raise ValueError("The pocket reaches into the annular seat")
    if FOOT_Y >= CASE_DIAMETER:
        raise ValueError("The body must be shorter than the case so the straps can hang")


def rounded_block(size_x, size_y, height, corner, top_fillet):
    block = (cq.Workplane("XY").rect(size_x, size_y).extrude(height)
             .edges("|Z").fillet(corner))
    if top_fillet > 0:
        block = block.faces(">Z").edges().fillet(top_fillet)
    return block


def cable_direction():
    angle = math.radians(PUCK_ANGLE)
    return math.cos(angle), math.sin(angle)


def seat_cutters():
    """Cylinders removed from the top: the case seat and the sensor clearance."""
    seat = (cq.Workplane("XY", origin=(0, 0, SEAT_Z))
            .circle((CASE_DIAMETER + CASE_CLEARANCE) / 2).extrude(HEIGHT))
    inner = (cq.Workplane("XY", origin=(0, 0, INNER_Z))
             .circle(SEAT_INNER_RADIUS).extrude(HEIGHT))
    return seat.union(inner)


def pocket_cutter():
    """Stadium pocket for the charging head, turned with the cable direction."""
    pocket = (cq.Workplane("XY", origin=(0, 0, POCKET_FLOOR_Z))
              .slot2D(PUCK_LENGTH + PUCK_CLEARANCE, PUCK_WIDTH + PUCK_CLEARANCE, 0)
              .extrude(HEIGHT))
    return (pocket.rotate((0, 0, 0), (0, 0, 1), PUCK_ANGLE)
            .translate((PAD_OFFSET[0], PAD_OFFSET[1], 0)))


def channel_cutter():
    """Open channel from the pocket centre out through the body side."""
    reach = math.hypot(FOOT_X, FOOT_Y)
    channel = (cq.Workplane("XY", origin=(0, 0, POCKET_FLOOR_Z))
               .center(reach / 2, 0).rect(reach, CHANNEL_WIDTH).extrude(HEIGHT))
    return (channel.rotate((0, 0, 0), (0, 0, 1), PUCK_ANGLE)
            .translate((PAD_OFFSET[0], PAD_OFFSET[1], 0)))


def make_dock():
    body = rounded_block(FOOT_X, FOOT_Y, HEIGHT, CORNER_RADIUS, TOP_FILLET)
    dock = body.cut(seat_cutters()).cut(pocket_cutter()).cut(channel_cutter())
    return finish(dock.val())


def make_coupon(dock):
    """Window of the dock around the pocket: checks the head, cable and seat fit."""
    window = (cq.Workplane("XY", origin=(PAD_OFFSET[0], PAD_OFFSET[1], 0))
              .rect(COUPON_SIZE, COUPON_SIZE).extrude(HEIGHT))
    return finish(dock.intersect(window.val()))


def finish(shape):
    shape = shape.clean()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("The part is not a valid single solid")
    return shape


def overhang_area(shape, limit_deg=45.0, tolerance=0.1):
    """Area (mm^2) of faces steeper than limit_deg from vertical, off the bed."""
    vertices, triangles = shape.tessellate(tolerance, 0.2)
    threshold = -math.cos(math.radians(limit_deg)) - 1e-3
    total = 0.0
    for a, b, c in triangles:
        p, q, s = vertices[a], vertices[b], vertices[c]
        normal = (q - p).cross(s - p)
        area = normal.Length / 2
        if area < 1e-9:
            continue
        if normal.z / normal.Length < threshold and min(p.z, q.z, s.z) > 0.2:
            total += area
    return total


def report(name, shape):
    box = shape.BoundingBox()
    grams = shape.Volume() / 1000 * 1.24  # solid PLA
    print(f"{name}: {box.xlen:.1f} x {box.ylen:.1f} x {box.zlen:.1f} mm, "
          f"{shape.Volume() / 1000:.1f} cm^3, {grams:.0f} g solid PLA")


if __name__ == "__main__":
    check_parameters()
    dock = make_dock()
    coupon = make_coupon(dock)
    for name, part in (("dock.stl", dock), ("coupon.stl", coupon)):
        overhang = overhang_area(part)
        if overhang > 1.0:
            raise ValueError(f"{name}: {overhang:.1f} mm^2 needs support")
        report(name, part)
        cq.exporters.export(part, str(DIRECTORY / name),
                            tolerance=0.05, angularTolerance=0.2)
