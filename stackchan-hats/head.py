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
import numpy as np


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


# --------------------------------------------------------------------------
# Motion and surroundings, for clearance and servo load checks.
#
# The pitch axis is the centre of the arm sockets inside both side walls of
# MainBody (arc fit residual 0.003 mm). Body and base positions come from
# ServoBody and Base, whose y and z share one assembly frame in M5_Hardware;
# their pitch pin and yaw bearing align with the socket within 0.4 mm in z.
# The pitch range is the firmware limit in m5stack/StackChan
# (firmware/main/hal/hal_servo.cpp, pitch angleLimit 30 ... 870 in 0.1 deg),
# from the "looking straight forward" zero towards looking up. Yaw is
# limited to +/-128 deg; the base is treated as swept through a full turn,
# so it is described by its top height against the distance from the yaw
# axis.

PITCH_AXIS = (18.4, -27.0)               # (y, z), axis parallel to x
PITCH_RANGE_DEG = (0.0, 87.0)            # 0 = looking straight forward
YAW_AXIS_Y = 19.2                        # vertical axis at x = 0
# ServoBody with its covers, which stay level while the head pitches:
# (z0, z1, y0, y1, half width) per 3 mm band, from sliced contours of the
# STLs. The head itself never meets them; its rear is an open frame through
# which the body passes when looking up (checked locally against voxels).
BODY_BANDS = (
    (-60.0, -57.0, -4.2, 42.0, 23.3), (-57.0, -54.0, -3.6, 42.0, 23.3),
    (-54.0, -51.0, 5.8, 42.0, 23.2), (-51.0, -48.0, 5.8, 41.0, 22.0),
    (-48.0, -30.0, 5.8, 41.0, 19.4), (-30.0, -24.0, 5.8, 41.0, 23.3),
    (-24.0, -21.0, 13.4, 40.1, 18.8), (-18.0, -15.0, 8.2, 41.0, 16.9),
    (-15.0, -9.0, 5.8, 41.0, 18.8), (-9.0, -6.0, 8.6, 37.1, 18.4),
)
# Base top height by distance from the yaw axis (Base STL, max z per band):
# bearing rim, inner deck, outer deck out to the rounded corners.
BASE_PROFILE = ((24.0, -57.8), (28.0, -58.8), (36.8, -60.9))
DESK = -70.5                             # product height below head top
CLEARANCE_MARGIN = 1.0


def pitch(points: np.ndarray, degrees: float) -> np.ndarray:
    """Rotate head-fixed points about the pitch axis; positive looks up."""
    t = np.radians(degrees)
    y0, z0 = PITCH_AXIS
    dy, dz = points[:, 1] - y0, points[:, 2] - z0
    out = points.copy()
    out[:, 1] = y0 + dy * np.cos(t) + dz * np.sin(t)
    out[:, 2] = z0 - dy * np.sin(t) + dz * np.cos(t)
    return out


def shielded(points: np.ndarray) -> np.ndarray:
    """Head-frame points above the head top or the CoreS3, out of the body's reach.

    The head shell's top plate and the solid CoreS3 lie between such points
    and the body, and the head itself clears the body over the pitch range.
    """
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    return ((z > -0.1) & (np.abs(x) < HEAD_WIDTH / 2 + 0.5)
            & (y > CORE_FRONT) & (y < SHELL_DEPTH))


def collisions(points: np.ndarray, exposed: np.ndarray | None = None) -> np.ndarray:
    """Mask of body-frame points closer than the margin to an obstacle.

    ``exposed`` limits the body test to points not shielded by the head.
    """
    m = CLEARANCE_MARGIN
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    radius = np.hypot(x, y - YAW_AXIS_Y)
    base = np.zeros(len(points), dtype=bool)
    inner = 0.0
    for outer, top in BASE_PROFILE:
        base |= (radius >= inner - m) & (radius < outer + m) & (z < top + m)
        inner = outer
    desk = z < DESK + m
    body = np.zeros(len(points), dtype=bool)
    for z0, z1, y0, y1, half in BODY_BANDS:
        body |= ((np.abs(x) < half + m) & (y > y0 - m) & (y < y1 + m)
                 & (z > z0 - m) & (z < z1 + m))
    if exposed is not None:
        body &= exposed
    return base | desk | body


def sweep_clearance(points: np.ndarray, step: float = 1.0) -> dict:
    """Worst case over the pitch range for head-fixed points of an accessory."""
    exposed = ~shielded(points)
    lowest, first, hits = np.inf, None, 0
    angles = np.arange(PITCH_RANGE_DEG[0], PITCH_RANGE_DEG[1] + 1e-9, step)
    for angle in angles:
        moved = pitch(points, angle)
        count = int(collisions(moved, exposed).sum())
        if count and first is None:
            first = float(angle)
        hits += count
        lowest = min(lowest, float(moved[:, 2].min()))
    return {"colliding_samples": hits, "first_collision_deg": first,
            "lowest_z_mm": round(lowest, 2)}
