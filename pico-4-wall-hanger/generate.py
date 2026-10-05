"""Wall hangers for PICO 4, its controllers and PICO Motion Trackers, millimetres.

Two independent panels hang on a pair of L- or J-shaped wall hooks each. The
up-turned tip of each hook passes through a tall slot near the top of the
panel; the panel then drops so that the upper edge of the slot rests on the
hook shank. Around each slot the panel is thinned to SLOT_WEB from the front,
so that hooks with a short shank still reach through, and the hook tip sits
in the recess.

- headset: an arm with a raised tip that passes through the strap ring and
  carries the rear battery pack, and a rib lower on the panel that the
  hanging visor leans on, so the headset does not swing;
- accessories: two pegs for the controller tracking rings and five short
  pegs for the Motion Tracker straps.

Use-orientation axes: x along the wall, y from the wall toward the user
(y=0 is the back face of the panel, flat against the wall), z up (z=0 is the
top edge of the panel). Each module is exported lying on its left end (x
pointing up), so that the layers run along the pegs and the arm. Every
feature that starts above the bed has a downward face of at most 45 degrees
from vertical, so the parts print without supports.
"""

import math
from pathlib import Path

import cadquery as cq


DIRECTORY = Path(__file__).resolve().parent

PANEL_THICKNESS = 6.0
PANEL_BOTTOM = -230.0
CORNER_CHAMFER = 10.0

# Hook slots, the same on both modules. The hooks are 5-6 mm thick. The
# left slot locates the panel; the wider right slot absorbs errors in the
# hook spacing. SLOT_HEIGHT admits an up-turned hook tip of up to
# SLOT_HEIGHT - hook diameter - 1 mm.
HOOK_SPACING = 160.0
SLOT_TOP = -24.0         # the hook shank rests here
SLOT_HEIGHT = 22.0
SLOT_WIDTHS = (8.0, 14.0)
SLOT_WEB = 3.0           # panel thickness at the slot
RECESS_MARGIN = 4.0      # around the slot, to the sides and below
RECESS_ABOVE = 16.0      # above the slot, for the hook tip

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
CONTROLLER_PEG_Z = -70.0     # below the hook-slot recesses
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


def xy_prism(points, z_min, z_max):
    """Extrude a closed (x, y) polygon along z from z_min to z_max."""
    return (cq.Workplane("XY", origin=(0, 0, z_min))
            .polyline(points).close().extrude(z_max - z_min).val())


def hook_slot_cutters(x_center, slot_width):
    """Slot through the web and the recess in front of it.

    The +x walls, which face downward in print orientation, slope at 45
    degrees toward the front instead of bridging the slot and the recess.
    """
    x_lo, x_hi = x_center - slot_width / 2, x_center + slot_width / 2
    slot_bottom = SLOT_TOP - SLOT_HEIGHT
    slot = xy_prism([(x_lo, -1.0), (x_hi, -1.0), (x_hi, 0.0),
                     (x_hi + SLOT_WEB + 1, SLOT_WEB + 1), (x_lo, SLOT_WEB + 1)],
                    slot_bottom, SLOT_TOP)
    depth = PANEL_THICKNESS - SLOT_WEB
    r_lo = x_lo - RECESS_MARGIN
    r_hi = x_hi + SLOT_WEB + RECESS_MARGIN
    recess = xy_prism([(r_lo, SLOT_WEB), (r_hi, SLOT_WEB),
                       (r_hi + depth, PANEL_THICKNESS),
                       (r_hi + depth, PANEL_THICKNESS + 1),
                       (r_lo, PANEL_THICKNESS + 1)],
                      slot_bottom - RECESS_MARGIN, SLOT_TOP + RECESS_ABOVE)
    return slot.fuse(recess)


def panel(width):
    """Flat panel with chamfered corners and the two hook slots."""
    x_min, x_max = -width / 2, width / 2
    c = CORNER_CHAMFER
    outline = [(x_min + c, PANEL_BOTTOM), (x_max - c, PANEL_BOTTOM),
               (x_max, PANEL_BOTTOM + c), (x_max, -c), (x_max - c, 0.0),
               (x_min + c, 0.0), (x_min, -c), (x_min, PANEL_BOTTOM + c)]
    body = (cq.Workplane("XZ", origin=(0, PANEL_THICKNESS, 0))
            .polyline(outline).close().extrude(PANEL_THICKNESS).val())
    for x_center, slot_width in zip((-HOOK_SPACING / 2, HOOK_SPACING / 2),
                                    SLOT_WIDTHS):
        body = body.cut(hook_slot_cutters(x_center, slot_width))
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
    body = panel(HEADSET_WIDTH)
    return finish(body.fuse(headset_arm()).fuse(visor_bumper()))


def make_accessory_module():
    body = panel(ACCESSORY_WIDTH)
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
