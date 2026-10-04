"""Combined vertical stand and display stand for ThinkPad E14 (AMD), millimetres.

One reclined slot serves both uses, one at a time:

- closed: the closed notebook stands on its long edge in the slot;
- open: the front edge of the base half stands in the slot and the display
  rises above it. The hinge angle sets the display tilt.

Two open trays in front of the slot hold the AC adapter and a mouse.
Axes: x along the slot, y from the user side (front, y=0) to the rear, z up.
"""

import math
from pathlib import Path

import cadquery as cq


# ThinkPad E14 Gen 5-8 (AMD), Lenovo PSREF: 313 x 219.3-220.3 mm,
# at most 20.5 mm thick.
NOTEBOOK_WIDTH = 313.0
NOTEBOOK_DEPTH = 220.3
NOTEBOOK_MAX_THICKNESS = 20.5
# Assumed thickness of the base half alone, for the open-use check only.
BASE_HALF_THICKNESS = 15.0

LENGTH = 260.0          # along x; the notebook overhangs both ends
LEAN = math.radians(20.0)  # slot reclined from vertical toward the rear

# Slot cross-section in the reclined frame: u is normal to the back face
# (positive toward the user), w runs up the back face.
SLOT_GAP = 25.0
SLOT_FLOOR = 6.0
BACK_WALL = 8.0
BACK_HEIGHT = 120.0
LIP_THICKNESS = 8.0
LIP_HEIGHT = 22.0
SLOT_ORIGIN_Z = 9.0     # height of the inner rear corner of the slot floor

# The back face is reduced to ribs above RIB_START so that only narrow strips
# touch the bottom cover and the remaining area stays open.
RIB_WIDTH = 24.0
RIB_CENTERS = (22.0, 92.0, 168.0, 238.0)
RIB_START = 28.0
GUSSET_THICKNESS = 8.0
GUSSET_TOP = 95.0       # w position where the gusset meets the back wall

BASE = 4.0
REAR_EXTENT = 96.0      # base depth behind the inner rear corner of the slot

# Trays in front of the slot, interior sizes.
TRAY_WALL = 4.0
TRAY_DEPTH = 72.0       # interior, along y
TRAY_HEIGHT = 20.0      # rim height above the desk
MOUSE_LENGTH = 125.0    # interior, along x; the adapter tray takes the rest
CABLE_NOTCH = 14.0
FINGER_NOTCH = 40.0

def frame_point(u, w, origin_y=None):
    """Map reclined-frame coordinates to (y, z)."""
    origin_y = SLOT_ORIGIN_Y if origin_y is None else origin_y
    y = origin_y - u * math.cos(LEAN) + w * math.sin(LEAN)
    z = SLOT_ORIGIN_Z + u * math.sin(LEAN) + w * math.cos(LEAN)
    return y, z


def frame_coordinates(y, z):
    """Inverse of frame_point: (y, z) to reclined-frame (u, w)."""
    dy, dz = y - SLOT_ORIGIN_Y, z - SLOT_ORIGIN_Z
    return (-dy * math.cos(LEAN) + dz * math.sin(LEAN),
            dy * math.sin(LEAN) + dz * math.cos(LEAN))


def lip_front_y(origin_y=None):
    """Front face of the lip at desk level; the trays end here."""
    top_y, top_z = frame_point(SLOT_GAP + LIP_THICKNESS, -SLOT_FLOOR, origin_y)
    return top_y - top_z * math.tan(LEAN)


# Place the slot so that the lip's front face is the rear wall of the trays.
SLOT_ORIGIN_Y = TRAY_WALL + TRAY_DEPTH - lip_front_y(0.0)


def extrude_profile(points, x0=0.0, length=LENGTH):
    return (cq.Workplane("YZ", origin=(x0, 0, 0))
            .polyline(points).close().extrude(length).val())


def make_cradle():
    gap, lip = SLOT_GAP, SLOT_GAP + LIP_THICKNESS
    corners = [
        (-BACK_WALL, BACK_HEIGHT), (0.0, BACK_HEIGHT), (0.0, 0.0),
        (gap, 0.0), (gap, LIP_HEIGHT), (lip, LIP_HEIGHT),
    ]
    points = [frame_point(u, w) for u, w in corners]
    front_y, rear_y = lip_front_y(), frame_point(-BACK_WALL, -SLOT_FLOOR)[0]
    lip_y, lip_z = frame_point(lip, -SLOT_FLOOR)
    points += [(lip_y, lip_z), (front_y, 0.0), (rear_y, 0.0),
               frame_point(-BACK_WALL, -SLOT_FLOOR)]
    return extrude_profile(points)


def reclined_box(x0, x1, u0, u1, w0, w1):
    corners = [frame_point(u, w) for u, w in ((u0, w0), (u1, w0), (u1, w1), (u0, w1))]
    return extrude_profile(corners, x0, x1 - x0)


def rib_windows():
    """Open-topped windows between the back-face ribs."""
    edges = [0.0]
    for center in RIB_CENTERS:
        edges += [center - RIB_WIDTH / 2, center + RIB_WIDTH / 2]
    edges.append(LENGTH)
    windows = [reclined_box(x0, x1, -BACK_WALL - 1.0, 1.0, RIB_START, BACK_HEIGHT + 1.0)
               for x0, x1 in zip(edges[0::2], edges[1::2]) if x1 - x0 > 1.0]
    return windows


def make_gusset(center):
    top = frame_point(-BACK_WALL + 0.5, GUSSET_TOP)
    foot = frame_point(-BACK_WALL + 0.5, -SLOT_FLOOR)
    rear = (SLOT_ORIGIN_Y + REAR_EXTENT - 6.0, BASE)
    points = [top, (foot[0], 0.0), (rear[0], 0.0), rear]
    return extrude_profile(points, center - GUSSET_THICKNESS / 2, GUSSET_THICKNESS)


def make_trays():
    walls = cq.Workplane("XY").box(LENGTH, tray_junction_y() + 2.0, TRAY_HEIGHT,
                                   centered=False).val()
    mouse = cq.Workplane("XY").box(MOUSE_LENGTH, TRAY_DEPTH, TRAY_HEIGHT,
                                   centered=False).val().translate(
                                       cq.Vector(TRAY_WALL, TRAY_WALL, BASE))
    adapter_x = 2 * TRAY_WALL + MOUSE_LENGTH
    adapter = cq.Workplane("XY").box(LENGTH - adapter_x - TRAY_WALL, TRAY_DEPTH,
                                     TRAY_HEIGHT, centered=False).val().translate(
                                         cq.Vector(adapter_x, TRAY_WALL, BASE))
    trays = walls.cut(mouse).cut(adapter)

    # U notches: a finger gap at the mouse, and cable exits at the adapter's
    # front and outer side.
    notch_floor = BASE + 6.0
    finger = cq.Solid.makeBox(FINGER_NOTCH, TRAY_WALL + 2.0, TRAY_HEIGHT).translate(
        cq.Vector(TRAY_WALL + (MOUSE_LENGTH - FINGER_NOTCH) / 2, -1.0, notch_floor))
    front_cable = cq.Solid.makeBox(CABLE_NOTCH, TRAY_WALL + 2.0, TRAY_HEIGHT).translate(
        cq.Vector(LENGTH - TRAY_WALL - 12.0 - CABLE_NOTCH, -1.0, notch_floor))
    side_cable = cq.Solid.makeBox(TRAY_WALL + 2.0, CABLE_NOTCH, TRAY_HEIGHT).translate(
        cq.Vector(LENGTH - TRAY_WALL - 1.0, TRAY_WALL + 12.0, notch_floor))
    for notch in (finger, front_cable, side_cable):
        trays = trays.cut(notch)
    return trays


def tray_junction_y():
    """Where the tray rims meet the lip's front face."""
    return lip_front_y() + TRAY_HEIGHT * math.tan(LEAN)


def make_base():
    depth = SLOT_ORIGIN_Y + REAR_EXTENT
    return cq.Workplane("XY").box(LENGTH, depth, BASE, centered=False).val()


def round_edges(shape):
    """Round the edges that touch the notebook or the hand."""
    top_z = frame_point(0.0, BACK_HEIGHT)[1]
    lip_top_z = frame_point(SLOT_GAP, LIP_HEIGHT)[1]

    def rib_top(edge):
        return edge.Center().z > top_z - 4.0

    def lip_top(edge):
        center = edge.Center()
        return (abs(center.z - lip_top_z) < 4.0 and edge.geomType() == "LINE"
                and edge.BoundingBox().xlen > LENGTH - 1.0)

    def rib_face_side(edge):
        # Long edges of the rib faces that the notebook leans on.
        u, w = frame_coordinates(edge.Center().y, edge.Center().z)
        return (edge.geomType() == "LINE" and abs(u) < 0.01 and w > RIB_START
                and edge.BoundingBox().xlen < 0.01)

    def tray_rim(edge):
        # Edges ending on the reclined lip face are left sharp.
        box = edge.BoundingBox()
        return (abs(box.zmin - TRAY_HEIGHT) < 0.01 and abs(box.zmax - TRAY_HEIGHT) < 0.01
                and box.ymax < tray_junction_y() - 0.5)

    def bottom_perimeter(edge):
        box = edge.BoundingBox()
        return box.zmax < 0.01 and edge.geomType() == "LINE"

    passes = ((2.0, rib_top), (1.5, rib_face_side), (2.0, lip_top), (1.2, tray_rim), (0.8, bottom_perimeter))
    for radius, select in passes:
        edges = [edge for edge in shape.Edges() if select(edge)]
        if not edges:
            raise ValueError("Expected edge missing for rounding")
        shape = shape.fillet(radius, edges)
    return shape


def notebook_proxies():
    """Boxes (u0, u1, w0, w1) for the notebook resting on the back face.

    Closed: the whole notebook. Open: the base half; the display above it is
    not checked because it is clear of the stand.
    """
    return {
        "closed": (0.05, 0.05 + NOTEBOOK_MAX_THICKNESS, 0.05, NOTEBOOK_DEPTH),
        "open": (0.05, 0.05 + BASE_HALF_THICKNESS, 0.05, NOTEBOOK_DEPTH),
    }


def check_clearance(stand):
    x0 = (LENGTH - NOTEBOOK_WIDTH) / 2
    for name, (u0, u1, w0, w1) in notebook_proxies().items():
        proxy = reclined_box(x0, x0 + NOTEBOOK_WIDTH, u0, u1, w0, w1)
        overlap = stand.intersect(proxy).Volume()
        if overlap > 1e-3:
            raise ValueError(f"{name} notebook overlaps the stand by {overlap:.3f} mm3")


def make_stand():
    if SLOT_GAP < NOTEBOOK_MAX_THICKNESS + 3.0:
        raise ValueError("Slot is too narrow for the thickest supported model")
    stand = make_base().fuse(make_cradle()).fuse(make_trays())
    for center in RIB_CENTERS:
        stand = stand.fuse(make_gusset(center))
    for window in rib_windows():
        stand = stand.cut(window)
    stand = round_edges(stand.clean())
    if not stand.isValid() or len(stand.Solids()) != 1:
        raise ValueError("The stand is not a valid single solid")
    check_clearance(stand)
    return stand


if __name__ == "__main__":
    output = Path(__file__).with_name("stand.stl")
    shape = make_stand()
    box = shape.BoundingBox()
    print(f"bounding box: {box.xlen:.1f} x {box.ylen:.1f} x {box.zlen:.1f} mm")
    cq.exporters.export(shape, str(output), tolerance=0.15, angularTolerance=0.3)
