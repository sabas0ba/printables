"""Measured head envelope of M5Stack StackChan (SKU K151), millimetres.

Coordinates used throughout this design:

- x: width, centred on the head; the head spans x = -27 ... 27.
- y: depth, 0 at the front face of the printed head shell (MainBody) and
  increasing towards the rear. The CoreS3 face is in front of it (y < 0).
- z: height, 0 at the top surface of the head.

Values below were measured from ``StackChan-MainBody.stl`` in
m5stack/M5_Hardware (commit a240115c94b19ecf647f229c47fa9a8ce46ccdc4,
``Products/K151_StackChan/Structures``) and from the published product size.
See README.md for the derivation and the items that remain unverified.
"""

import cadquery as cq


HEAD_WIDTH = 54.0            # MainBody and CoreS3 width
HEAD_HEIGHT = 54.0           # MainBody and CoreS3 height
SHELL_DEPTH = 46.7           # MainBody depth, y = 0 ... 46.7
SHELL_SIDE_END = 44.7        # side walls and rear top corners end here
PRODUCT_DEPTH = 61.5         # published product size, front face to rear
CORE_FRONT = SHELL_DEPTH - PRODUCT_DEPTH  # -14.8, CoreS3 front face
TOP_EDGE_RADIUS = 4.5        # top-to-side edge radius along y

# LEGO-compatible side holes, three per side at the upper front.
SIDE_HOLE_Y = (11.8, 19.8, 27.8)
SIDE_HOLE_Z = -10.0
SIDE_HOLE_DIAMETER = 6.4

# Top light-guide slots (LED rows) on both upper edges.
LIGHT_SLOT_X = 25.5          # |x| of the slot centre line
LIGHT_SLOT_Y = (5.5, 35.0)   # slot extent along y
LIGHT_SLOT_WIDTH = 1.6


def section(width: float, top: float, radius: float, bottom: float) -> cq.Workplane:
    """Closed x-z profile with rounded top corners, on the XZ plane."""
    half = width / 2
    return (cq.Workplane("XZ")
            .moveTo(-half, bottom)
            .lineTo(half, bottom)
            .lineTo(half, top - radius)
            .radiusArc((half - radius, top), -radius)
            .lineTo(-half + radius, top)
            .radiusArc((-half, top - radius), -radius)
            .close())


def extrude_y(profile: cq.Workplane, y0: float, y1: float) -> cq.Solid:
    """Extrude an XZ-plane profile over y0 ... y1 (XZ normal points to -y)."""
    solid = profile.extrude(-(y1 - y0)).val()
    return solid.translate(cq.Vector(0, y0, 0))


def envelope(offset: float = 0.0, holes: bool = True) -> cq.Solid:
    """Conservative solid occupied by the head, optionally grown by offset.

    The CoreS3 region uses the same section as the shell; its own corner
    radius is larger in photographs, which only leaves additional clearance.
    With ``holes`` the side holes are subtracted so that the cap's detents
    may enter them without counting as interference.
    """
    profile = section(HEAD_WIDTH + 2 * offset, offset,
                      TOP_EDGE_RADIUS + offset, -HEAD_HEIGHT)
    head = extrude_y(profile, CORE_FRONT - offset, SHELL_DEPTH + offset)
    if not holes:
        return head
    for side in (-1, 1):
        for y in SIDE_HOLE_Y:
            hole = cq.Solid.makeCylinder(
                SIDE_HOLE_DIAMETER / 2, 1.2 + offset,
                cq.Vector(side * (HEAD_WIDTH / 2 + offset), y, SIDE_HOLE_Z),
                cq.Vector(-side, 0, 0))
            head = head.cut(hole)
    return head
