"""Flat desk dock for the CMF Watch 3 Pro and its magnetic charging cable, mm.

The watch lies face up on an annular seat that carries its case back at the
rim, so it no longer balances on the small charging head. The charging head
sits in a pocket below the seat, offset toward 6 o'clock where the charging
pads are, and its cable is held in an open channel so it cannot pull the head
out of place. Short lips reach over the channel from alternate walls; the
cable is snaked in under them and cannot lift straight out. Their edges are
rounded and the channel edges are filleted so the cable jacket is not cut.
The body is shorter than the case along the strap axis, so both strap halves
hang over the ends without being removed.

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

# Retaining lips over the channel. Positions are distances from the pocket
# centre along the cable; the sign gives the wall the lip grows from, across
# the cable direction (-1: right-hand wall seen along the cable toward the
# exit, which is the 6 o'clock side with PUCK_ANGLE = 0). Alternate the signs.
LIP_POSITIONS = ((20.8, -1), (25.5, 1), (30.0, -1))
LIP_LENGTH = 2.0               # along the cable
LIP_REACH = 1.5                # across the channel from its wall
LIP_TIP = 0.6                  # thickness at the tip; the underside rises at 45 deg
LIP_FILLET = 0.25              # rounding of the tip edges
LIP_EMBED = 1.0                # root extended into the wall, past the rounded edge
CHANNEL_EDGE_FILLET = 0.5      # rounding of the channel top edges
EXIT_FILLET = 1.0              # rounding of the channel floor at the body side

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
LIP_ROOT = LIP_TIP + LIP_REACH  # thickness at the wall: 45 degree underside
SEAT_RADIUS = (CASE_DIAMETER + CASE_CLEARANCE) / 2


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
    if LIP_REACH >= CHANNEL_WIDTH - CABLE_DIAMETER / 2:
        raise ValueError("The lip gap must let the cable be snaked in")
    previous = None
    for position, side in LIP_POSITIONS:
        if side not in (-1, 1) or (previous is not None and side == previous):
            raise ValueError("Lips must alternate between the channel walls")
        previous = side
        top = lip_top(position)
        if top - LIP_ROOT - POCKET_FLOOR_Z < CABLE_DIAMETER + 0.2:
            raise ValueError(f"Lip at {position} mm leaves no room for the cable")


def to_global(along, across):
    """Point in the cable frame (along the cable from the pocket centre) to x, y."""
    cos, sin = cable_direction()
    return (PAD_OFFSET[0] + along * cos - across * sin,
            PAD_OFFSET[1] + along * sin + across * cos)


def surface_top(x, y):
    """Height of the dock top at a point, before the channel is cut."""
    radius = math.hypot(x, y)
    if radius < SEAT_INNER_RADIUS:
        return INNER_Z
    if radius < SEAT_RADIUS:
        return SEAT_Z
    if abs(x) > FOOT_X / 2 or abs(y) > FOOT_Y / 2:
        raise ValueError(f"({x:.1f}, {y:.1f}) lies outside the body")
    return HEIGHT


def lip_top(position):
    """Top of the channel walls over a lip; the lip must not straddle a step."""
    corners = [to_global(position + d_along, d_across)
               for d_along in (-LIP_LENGTH / 2, LIP_LENGTH / 2)
               for d_across in (-CHANNEL_WIDTH / 2, CHANNEL_WIDTH / 2)]
    tops = {surface_top(x, y) for x, y in corners}
    if len(tops) != 1:
        raise ValueError(f"Lip at {position} mm straddles a step in the top surface")
    return tops.pop()


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
    return to_cable_frame(pocket)


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
    inner = cq.Workplane("XY", origin=(0, 0, -HEIGHT)).circle(SEAT_INNER_RADIUS).extrude(tall)
    seat = cq.Workplane("XY", origin=(0, 0, -HEIGHT)).circle(SEAT_RADIUS).extrude(tall)
    everything = (cq.Workplane("XY", origin=(0, 0, -HEIGHT))
                  .rect(4 * reach, 4 * reach).extrude(tall))
    regions = ((INNER_Z, inner), (SEAT_Z, seat.cut(inner)), (HEIGHT, everything.cut(seat)))
    cutter = None
    for top, region in regions:
        piece = to_cable_frame(channel_profile(top, reach)).intersect(region)
        cutter = piece if cutter is None else cutter.union(piece)
    return cutter


def lip(position, side):
    """Lip reaching over the channel from one wall, 45 degree underside."""
    top = lip_top(position)
    wall = side * CHANNEL_WIDTH / 2
    tip = wall - side * LIP_REACH
    root = wall + side * LIP_EMBED
    profile = [(root, top), (tip, top), (tip, top - LIP_TIP), (root, top - LIP_ROOT - LIP_EMBED)]
    solid = (cq.Workplane("YZ", origin=(position - LIP_LENGTH / 2, 0, 0))
             .polyline(profile).close().extrude(LIP_LENGTH))
    tip_edges = solid.edges("|X").edges(cq.selectors.BoxSelector(
        (position - LIP_LENGTH, tip - 0.01, top - LIP_TIP - 0.01),
        (position + LIP_LENGTH, tip + 0.01, top + 0.01)))
    return to_cable_frame(tip_edges.fillet(LIP_FILLET))


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
    for position, side in LIP_POSITIONS:
        dock = dock.union(lip(position, side))
    return finish(round_exit_floor(dock.val()))


def make_coupon(dock):
    """Window of the dock from the pocket to the cable exit, including the lips."""
    along_start = -PUCK_LENGTH / 2 - 3.0
    along_end = max(position for position, _ in LIP_POSITIONS) + LIP_LENGTH + 2.0
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
