"""Shelf-edge hangers for PICO 4, its controllers and PICO Motion Trackers, millimetres.

Two independent modules clamp onto the front edge of a shelf board:

- headset: an arm with a raised tip that passes through the strap ring and
  carries the rear battery pack, and a rib lower on the panel that the
  hanging visor leans on, so the headset does not swing;
- accessories: two pegs for the controller tracking rings and five short
  pegs for the Motion Tracker straps.

Use-orientation axes: x along the shelf edge, y from the shelf front face
toward the user (y=0 is the back face of the panel), z up (z=0 is the top of
the shelf board). Each module is exported lying on its left end (x pointing
up), so the C-shaped clamp and the panel stand as vertical walls. Every
feature that starts above the bed has a downward face of at most 45 degrees
from vertical, so the parts print without supports.
"""

import math
from pathlib import Path

import cadquery as cq


DIRECTORY = Path(__file__).resolve().parent

# Shelf board: the clamp gap fits boards up to SHELF_GAP thick.
SHELF_GAP = 21.0
TOP_LEG_DEPTH = 45.0     # behind the panel, resting on the shelf top
TOP_LEG_THICKNESS = 5.0
LOWER_LIP_DEPTH = 25.0   # behind the panel, under the shelf board
LOWER_LIP_THICKNESS = 5.0

PANEL_THICKNESS = 6.0
PANEL_BOTTOM = -230.0
CORNER_CHAMFER = 10.0

# Headset module.
HEADSET_WIDTH = 200.0
ARM_TIP_WIDTH = 50.0     # full-length part, centred on the module
ARM_TOP = -70.0          # z of the top surface; leaves room for the battery pack
ARM_LENGTH = 65.0        # from the panel front face
ARM_THICKNESS = 14.0
ARM_TIP_RISE = 18.0
ARM_TIP_LENGTH = 10.0
ARM_GUSSET = 30.0
# The visor hangs below the arm and leans on this rib instead of swinging.
BUMPER_WIDTH = 150.0
BUMPER_TOP = -195.0
BUMPER_HEIGHT = 24.0
BUMPER_DEPTH = 16.0      # from the panel front face

# Accessories module.
ACCESSORY_WIDTH = 220.0
CONTROLLER_PEG_X = (-55.0, 55.0)
CONTROLLER_PEG_Z = -45.0
CONTROLLER_PEG_RADIUS = 7.0
CONTROLLER_PEG_LENGTH = 55.0
TRACKER_PEG_X = (-88.0, -44.0, 0.0, 44.0, 88.0)
TRACKER_PEG_Z = -205.0
TRACKER_PEG_RADIUS = 5.0
TRACKER_PEG_LENGTH = 30.0
PEG_TILT = math.radians(12.0)  # tip raised above the root
PEG_TAB_HEIGHT = 4.0
PEG_TAB_LENGTH = 6.0

EMBED = 1.0              # overlap of features into the panel for a clean fuse
BED_LIMIT = 250.0        # each printed dimension must stay below this


def yz_prism(points, x_min, x_max, fillet=0.0):
    """Extrude a closed (y, z) polygon along x from x_min to x_max."""
    solid = (cq.Workplane("YZ", origin=(x_min, 0, 0))
             .polyline(points).close().extrude(x_max - x_min))
    if fillet:
        solid = solid.edges("|X").fillet(fillet)
    return solid.val()


def clamp_and_panel(width):
    """Panel with the C-shaped clamp around the shelf front edge."""
    x_min, x_max = -width / 2, width / 2
    top = TOP_LEG_THICKNESS
    lip_top = -SHELF_GAP
    lip_bottom = lip_top - LOWER_LIP_THICKNESS
    profile = [
        (-TOP_LEG_DEPTH, 0.0), (0.0, 0.0), (0.0, lip_top),
        (-LOWER_LIP_DEPTH, lip_top), (-LOWER_LIP_DEPTH, lip_bottom),
        (0.0, lip_bottom), (0.0, PANEL_BOTTOM),
        (PANEL_THICKNESS, PANEL_BOTTOM), (PANEL_THICKNESS, top),
        (-TOP_LEG_DEPTH, top),
    ]
    body = yz_prism(profile, x_min, x_max)
    body = (cq.Workplane().add(body)
            .edges("|Y").edges(cq.selectors.BoxSelector(
                (x_min - 1, -1, PANEL_BOTTOM - 1),
                (x_max + 1, PANEL_THICKNESS + 1, PANEL_BOTTOM + 1)))
            .chamfer(CORNER_CHAMFER).val())
    return body


def print_taper(solid, x_start, x_end):
    """Limit a front feature so that it grows from the panel at 45 degrees.

    At height x above x_start (in print orientation), the feature reaches at
    most x - x_start in front of its root, so its first layers need no support.
    """
    root = PANEL_THICKNESS - EMBED
    reach = x_end + 1 - x_start
    wedge = (cq.Workplane("XY", origin=(0, 0, -400))
             .polyline([(x_start, root), (x_end + 1, root + reach),
                        (x_end + 1, root)])
             .close().extrude(800).val())
    return solid.intersect(wedge)


def headset_arm():
    y0 = PANEL_THICKNESS - EMBED
    y1 = PANEL_THICKNESS + ARM_LENGTH
    bottom = ARM_TOP - ARM_THICKNESS
    profile = [
        (y0, bottom - ARM_GUSSET), (y0 + ARM_GUSSET + EMBED, bottom),
        (y1, bottom), (y1, ARM_TOP + ARM_TIP_RISE),
        (y1 - ARM_TIP_LENGTH, ARM_TOP + ARM_TIP_RISE),
        (y1 - ARM_TIP_LENGTH, ARM_TOP), (y0, ARM_TOP),
    ]
    # The left side widens at 45 degrees toward the panel (see print_taper),
    # so the root is longer than the full-length tip.
    x_end = ARM_TIP_WIDTH / 2
    x_start = -ARM_TIP_WIDTH / 2 - (y1 - y0)
    arm = yz_prism(profile, x_start, x_end, fillet=2.0)
    return print_taper(arm, x_start, x_end)


def visor_bumper():
    y0 = PANEL_THICKNESS - EMBED
    y1 = PANEL_THICKNESS + BUMPER_DEPTH
    bottom = BUMPER_TOP - BUMPER_HEIGHT
    profile = [(y0, bottom), (y1, bottom), (y1, BUMPER_TOP), (y0, BUMPER_TOP)]
    bumper = yz_prism(profile, -BUMPER_WIDTH / 2, BUMPER_WIDTH / 2)
    bumper = (cq.Workplane().add(bumper)
              .edges("|X").edges(">Y").fillet(6.0).val())
    return print_taper(bumper, -BUMPER_WIDTH / 2, BUMPER_WIDTH / 2)


def peg(x, z, radius, length):
    """Upward-tilted peg with a small stop at the tip.

    The cross-section in the x-z plane is a square with a 45-degree point
    toward -x, which is downward in print orientation.
    """
    r, h = radius, PEG_TAB_HEIGHT
    section = [(r, -r), (r, r), (-r, r), (-2 * r, 0.0), (-r, -r)]
    tab_section = [(r, -r), (r, r + h), (-r, r + h), (-2 * r, h),
                   (-2 * r, 0.0), (-r, -r)]

    def prism(points, y_start, y_length):
        return (cq.Workplane("XZ", origin=(0, y_start, 0))
                .polyline([(px, pz) for px, pz in points]).close()
                .extrude(-y_length).val())

    shaft = prism(section, -EMBED, length + EMBED)
    tab = prism(tab_section, length - PEG_TAB_LENGTH, PEG_TAB_LENGTH)
    body = shaft.fuse(tab).clean()
    body = body.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0),
                       math.degrees(PEG_TILT))
    return body.translate(cq.Vector(x, PANEL_THICKNESS, z))


def make_headset_module():
    body = clamp_and_panel(HEADSET_WIDTH)
    return finish(body.fuse(headset_arm()).fuse(visor_bumper()))


def make_accessory_module():
    body = clamp_and_panel(ACCESSORY_WIDTH)
    for x in CONTROLLER_PEG_X:
        body = body.fuse(peg(x, CONTROLLER_PEG_Z, CONTROLLER_PEG_RADIUS,
                             CONTROLLER_PEG_LENGTH))
    for x in TRACKER_PEG_X:
        body = body.fuse(peg(x, TRACKER_PEG_Z, TRACKER_PEG_RADIUS,
                             TRACKER_PEG_LENGTH))
    return finish(body)


def finish(shape):
    shape = shape.clean()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("The module is not a valid single solid")
    return shape


def to_print_orientation(shape):
    """Lay the module on its -x end: use-x becomes print-z."""
    turned = shape.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)
    box = turned.BoundingBox()
    placed = turned.translate(cq.Vector(-box.xmin, -box.ymin, -box.zmin))
    box = placed.BoundingBox()
    for size in (box.xlen, box.ylen, box.zlen):
        if size > BED_LIMIT:
            raise ValueError(f"Part exceeds {BED_LIMIT} mm: {size:.1f}")
    return placed


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


# The only accepted horizontal faces are the short bridges under the peg tip
# stops, PEG_TAB_HEIGHT x PEG_TAB_LENGTH each, plus tessellation slack.
PEG_COUNT = len(CONTROLLER_PEG_X) + len(TRACKER_PEG_X)
OVERHANG_ALLOWANCE = {
    "headset.stl": 1.0,
    "accessories.stl": PEG_COUNT * PEG_TAB_HEIGHT * PEG_TAB_LENGTH * 1.1,
}


if __name__ == "__main__":
    for name, make in (("headset.stl", make_headset_module),
                       ("accessories.stl", make_accessory_module)):
        part = to_print_orientation(make())
        overhang = overhang_area(part)
        if overhang > OVERHANG_ALLOWANCE[name]:
            raise ValueError(f"{name}: {overhang:.1f} mm^2 needs support")
        cq.exporters.export(part, str(DIRECTORY / name),
                            tolerance=0.1, angularTolerance=0.2)
