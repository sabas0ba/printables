"""Flat desk dock for the CMF Watch 3 Pro and its magnetic charging cable, mm.

The watch lies face up on an annular seat that carries its case back outside
the sensor dome, so it no longer balances on the small charging head. The
charging head sits in a pocket under the charging pads, which lie near the
rim of the case back on the 6 o'clock side, with its top level with the seat.
The cable leaves the head along its length and runs in an open channel out
through the side of the body. The channel is as wide as the cable, which is
held by friction; there are no retaining lips. The channel edges are filleted
so the cable jacket is not cut.

The body is shorter than the case along the strap axis, and the top is cut
down to the seat across the strap width, so both strap halves hang over the
ends without being removed.

Coordinates: z up, the dock stands on z = 0 in its print orientation. The
strap runs along y (12 o'clock toward +y), the cable leaves toward +x.

The watch dimensions are published values. The position of the charging pads,
the sensor dome and the charging head were scaled from photographs of the
physical parts (see the README) and must be checked with calipers; print
coupon.stl first to check the pocket, the channel and the seat height.
"""

import math
from pathlib import Path

import cadquery as cq


DIRECTORY = Path(__file__).resolve().parent

# Watch, published values (47 x 47 x 14.4 mm, 22 mm straps).
CASE_DIAMETER = 47.0
CASE_THICKNESS = 14.4
STRAP_WIDTH = 22.0

# Watch, scaled from photographs: measure on the physical unit.
CASE_CLEARANCE = 0.5           # diametral clearance of the seat wall
SEAT_INNER_RADIUS = 13.0       # sensor dome radius (about 12) plus clearance
SENSOR_CLEARANCE = 3.0         # drop inside the seat for the sensor dome
PAD_OFFSET = (0.0, -16.7)      # centre of the charging pads from the case centre

# Charging head and cable, scaled from photographs: measure on the physical parts.
PUCK_LENGTH = 20.0             # stadium body along the cable, without the cable boot
PUCK_WIDTH = 8.5
PUCK_HEIGHT = 5.0              # housing only, without the spring pins
PUCK_CLEARANCE = 0.3           # added to length and width of the pocket
PUCK_PROUD = 0.0               # head top above the seat; negative sinks it
PUCK_ANGLE = 0.0               # degrees about z; 0 sends the cable toward +x, 180 toward -x
BOOT_LENGTH = 5.0              # strain relief at the cable end of the head
BOOT_WIDTH = 6.5
CABLE_DIAMETER = 2.6
CABLE_CLEARANCE = 0.4          # added to the channel width; 3.0 mm fits the cable
CHANNEL_EDGE_FILLET = 0.5      # rounding of the channel top edges
EXIT_FILLET = 1.0              # rounding of the channel floor at the body side

# Body.
FOOT_X = 64.0
FOOT_Y = 46.0                  # shorter than the case: the straps hang over the ends
HEIGHT = 14.0
CORNER_RADIUS = 3.0            # keeps the cable exit on the flat side
TOP_FILLET = 1.0
SEAT_WALL = 3.0                # wall height around the case above the seat
STRAP_RELIEF = STRAP_WIDTH + 3.0  # band across the ends cut down to the seat
MIN_FLOOR = 2.5                # material left under the pocket
MIN_WALL = 1.6                 # material between the pocket and the body side
COUPON_SIZE = 34.0

SEAT_Z = HEIGHT - SEAT_WALL
INNER_Z = SEAT_Z - SENSOR_CLEARANCE
POCKET_FLOOR_Z = SEAT_Z + PUCK_PROUD - PUCK_HEIGHT
CHANNEL_WIDTH = CABLE_DIAMETER + CABLE_CLEARANCE
SEAT_RADIUS = (CASE_DIAMETER + CASE_CLEARANCE) / 2


def check_parameters():
    if POCKET_FLOOR_Z < MIN_FLOOR:
        raise ValueError(f"Pocket floor {POCKET_FLOOR_Z:.1f} mm is thinner than {MIN_FLOOR} mm")
    if POCKET_FLOOR_Z >= INNER_Z:
        raise ValueError("The pocket must start below the sensor clearance recess")
    if FOOT_Y >= CASE_DIAMETER:
        raise ValueError("The body must be shorter than the case so the straps can hang")
    if BOOT_WIDTH + PUCK_CLEARANCE > PUCK_WIDTH or BOOT_WIDTH < CHANNEL_WIDTH:
        raise ValueError("The boot must lie between the channel and the head in width")
    # Pocket outline sampled in the cable frame: the head must lie under the
    # case, and the pocket must leave MIN_WALL to the body sides.
    half_length = (PUCK_LENGTH + PUCK_CLEARANCE) / 2
    half_width = (PUCK_WIDTH + PUCK_CLEARANCE) / 2
    centre = half_length - half_width
    head = [(sign * centre + half_width * math.cos(a), half_width * math.sin(a))
            for sign in (-1, 1)
            for a in (math.radians(d) for d in range(0, 360, 5))]
    boot = [(half_length + BOOT_LENGTH, side * (BOOT_WIDTH + PUCK_CLEARANCE) / 2)
            for side in (-1, 1)]
    for along, across in head + boot:
        x, y = to_global(along, across)
        if (along, across) in head and math.hypot(x, y) > SEAT_RADIUS:
            raise ValueError("The charging head reaches past the seat wall")
        if FOOT_Y / 2 - abs(y) < MIN_WALL or FOOT_X / 2 - abs(x) < MIN_WALL:
            raise ValueError("The pocket leaves less than MIN_WALL to the body side")


def to_global(along, across):
    """Point in the cable frame (along the cable from the pocket centre) to x, y."""
    cos, sin = cable_direction()
    return (PAD_OFFSET[0] + along * cos - across * sin,
            PAD_OFFSET[1] + along * sin + across * cos)


def rounded_block(size_x, size_y, height, corner, top_fillet):
    block = (cq.Workplane("XY").rect(size_x, size_y).extrude(height)
             .edges("|Z").fillet(corner))
    if top_fillet > 0:
        block = block.faces(">Z").edges().fillet(top_fillet)
    return block


def cable_direction():
    angle = math.radians(PUCK_ANGLE)
    return math.cos(angle), math.sin(angle)


def seat_level(z, height):
    """Region whose top is the seat: the case seat and the strap relief band."""
    seat = cq.Workplane("XY", origin=(0, 0, z)).circle(SEAT_RADIUS).extrude(height)
    band = (cq.Workplane("XY", origin=(0, 0, z))
            .rect(STRAP_RELIEF, 2 * FOOT_Y).extrude(height))
    return seat.union(band)


def inner_level(z, height):
    return cq.Workplane("XY", origin=(0, 0, z)).circle(SEAT_INNER_RADIUS).extrude(height)


def seat_cutters():
    """Material removed from the top: seat, strap relief and sensor clearance."""
    return seat_level(SEAT_Z, HEIGHT).union(inner_level(INNER_Z, HEIGHT))


def pocket_cutter():
    """Stadium pocket for the charging head and the boot, turned with the cable."""
    length = PUCK_LENGTH + PUCK_CLEARANCE
    pocket = (cq.Workplane("XY", origin=(0, 0, POCKET_FLOOR_Z))
              .slot2D(length, PUCK_WIDTH + PUCK_CLEARANCE, 0)
              .extrude(HEIGHT))
    boot_end = length / 2 + BOOT_LENGTH
    boot = (cq.Workplane("XY", origin=(0, 0, POCKET_FLOOR_Z))
            .center(boot_end / 2, 0)
            .rect(boot_end, BOOT_WIDTH + PUCK_CLEARANCE)
            .extrude(HEIGHT))
    return to_cable_frame(pocket.union(boot))


def to_cable_frame(shape):
    """Place a shape built along +x from the origin onto the cable direction."""
    return (shape.rotate((0, 0, 0), (0, 0, 1), PUCK_ANGLE)
            .translate((PAD_OFFSET[0], PAD_OFFSET[1], 0)))


def channel_profile(top, reach):
    """Channel cross-section with rounded top edges, extruded along +x."""
    half = CHANNEL_WIDTH / 2
    r = CHANNEL_EDGE_FILLET
    diagonal = r * (1 - math.cos(math.radians(45)))
    profile = (cq.Workplane("YZ")
               .moveTo(-half, POCKET_FLOOR_Z).lineTo(half, POCKET_FLOOR_Z)
               .lineTo(half, top - r)
               .threePointArc((half + diagonal, top - diagonal), (half + r, top))
               .lineTo(half + r, top + HEIGHT).lineTo(-half - r, top + HEIGHT)
               .lineTo(-half - r, top)
               .threePointArc((-half - diagonal, top - diagonal), (-half, top - r))
               .close())
    return profile.extrude(reach)


def channel_cutter():
    """Open channel from the pocket centre out through the body side.

    The top edges are rounded for the cable jacket. The top surface steps at
    the sensor recess and at the seat, so the profile is cut per region.
    """
    reach = math.hypot(FOOT_X, FOOT_Y)
    tall = 3 * HEIGHT
    inner = inner_level(-HEIGHT, tall)
    seat = seat_level(-HEIGHT, tall)
    everything = (cq.Workplane("XY", origin=(0, 0, -HEIGHT))
                  .rect(4 * reach, 4 * reach).extrude(tall))
    regions = ((INNER_Z, inner), (SEAT_Z, seat.cut(inner)), (HEIGHT, everything.cut(seat)))
    cutter = None
    for top, region in regions:
        piece = to_cable_frame(channel_profile(top, reach)).intersect(region)
        cutter = piece if cutter is None else cutter.union(piece)
    return cutter


def in_cable_frame(point):
    """Inverse of to_global."""
    cos, sin = cable_direction()
    dx, dy = point.x - PAD_OFFSET[0], point.y - PAD_OFFSET[1]
    return dx * cos + dy * sin, -dx * sin + dy * cos


def along_cable(edge):
    if edge.geomType() != "LINE":
        return False
    cos, sin = cable_direction()
    start, end = edge.startPoint(), edge.endPoint()
    direction = (end - start).normalized()
    return abs(abs(direction.x * cos + direction.y * sin) - 1.0) < 1e-6


def round_exit_floor(shape):
    """Fillet the channel floor edge where the cable leaves the body."""
    def exit_floor(edge):
        along, across = in_cable_frame(edge.Center())
        return (edge.geomType() == "LINE" and not along_cable(edge)
                and abs(edge.Center().z - POCKET_FLOOR_Z) < 0.01
                and abs(across) < 0.01 and along > SEAT_RADIUS)

    edges = [edge for edge in shape.Edges() if exit_floor(edge)]
    if len(edges) != 1:
        raise ValueError(f"Expected one channel exit floor edge, found {len(edges)}")
    return shape.fillet(EXIT_FILLET, edges)


def make_dock():
    body = rounded_block(FOOT_X, FOOT_Y, HEIGHT, CORNER_RADIUS, TOP_FILLET)
    dock = body.cut(seat_cutters()).cut(pocket_cutter()).cut(channel_cutter())
    return finish(round_exit_floor(dock.val()))


def make_coupon(dock):
    """Window of the dock from the pocket to the cable exit, with part of the seat."""
    along_start = -PUCK_LENGTH / 2 - 3.0
    along_end = math.hypot(FOOT_X, FOOT_Y) / 2 + 1.0
    window = to_cable_frame(cq.Workplane("XY")
                            .center((along_start + along_end) / 2, 0)
                            .rect(along_end - along_start, COUPON_SIZE).extrude(HEIGHT))
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
