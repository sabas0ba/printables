"""One-piece cap variants with integral side or front features, millimetres.

All features lie below the cap top surface, so a variant still prints upside
down without supports. Their outlines follow two rules, both verified by the
checks in generate.py:

- Going down from the cap top (upwards when printed), an outline may widen
  by at most 45 degrees; edges that turn back inwards are free.
- Behind the pitch axis, low points swing down towards the base when the
  head looks up, so the rear lower boundary stays close to the axis.

Side plates stand 1.6 mm off the skirt so that the detent tongue can flex,
and keep to the shell (y >= 1) so that the CoreS3 side ports stay free.
Front frames stand in front of the CoreS3 face plane, outside its outline.
"""

from dataclasses import dataclass
import math
from typing import Callable

import cadquery as cq

import cap
from toppers import Shape2D


SIDE_PLATE_X = (cap.OUTER_HALF + 1.6, cap.OUTER_HALF + 4.6)   # 30.5 ... 33.5
SHOULDER_X0 = 27.0
FRAME_Y = (-17.8, -15.0)
FRAME_INNER_X = 27.6
PLATE_ROUNDING = 1.2


@dataclass
class Variant:
    key: str
    title: str
    build: Callable[[], list[cq.Shape]]


def plate(shape: Shape2D, plane: str, w0: float, w1: float,
          rounding: float = PLATE_ROUNDING) -> cq.Shape:
    """Extrude a 2D outline drawn in (u, v) into a plate.

    plane "yz": u = y, v = z, thickness along x from w0 to w1.
    plane "xz": u = x, v = z, thickness along y from w0 to w1.
    """
    faces = shape.faces(rounding, rounding)
    if len(faces) != 1:
        raise ValueError(f"Plate outline must be one region, got {len(faces)}")
    solid = cq.Solid.extrudeLinear(faces[0], cq.Vector(0, 0, w1 - w0))
    origin = cq.Vector(0, 0, 0)
    # Rx(90) maps (u, v, w) to (u, -w, v).
    solid = solid.rotate(origin, cq.Vector(1, 0, 0), 90)
    if plane == "yz":
        # Rz(90) then maps (u, -w, v) to (w, u, v).
        solid = solid.rotate(origin, cq.Vector(0, 0, 1), 90).translate(
            cq.Vector(w0, 0, 0))
    else:
        solid = solid.translate(cq.Vector(0, w1, 0))
    # Outlines extend above the cap top; clipping there keeps the root flat
    # and sharp on the print bed instead of rounding into an overhang.
    return solid.cut(box(-200, 200, -200, 200, cap.TOP, 200))


def root(shape: Shape2D, u0: float, u1: float) -> Shape2D:
    """Add the part above the cap top that the clip in plate() removes."""
    return shape.rect(((u0 + u1) / 2, cap.TOP + 3.0), u1 - u0, 6.0)


def both_sides(right: list[cq.Shape]) -> list[cq.Shape]:
    return right + [shape.mirror("YZ") for shape in right]


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> cq.Solid:
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def side_feature(outline: Shape2D, root_y: tuple[float, float]) -> list[cq.Shape]:
    """Side plate on both sides, hung from a shoulder at the cap top."""
    shoulder = box(SHOULDER_X0, SIDE_PLATE_X[1], root_y[0], root_y[1],
                   cap.CLEARANCE, cap.TOP)
    side = plate(root(outline, *root_y), "yz", *SIDE_PLATE_X)
    return both_sides([shoulder, side])


def v_groove(y0: float, z0: float, y1: float, z1: float, x: float,
             depth: float = 0.8) -> cq.Shape:
    """90 degree V groove along a line on a face at x (walls at 45 degrees)."""
    length = ((y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5
    side = depth * 2 ** 0.5
    bar = cq.Solid.makeBox(side, length, side, cq.Vector(-side / 2, 0, -side / 2))
    bar = bar.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 45)
    angle = math.degrees(math.atan2(z1 - z0, y1 - y0))
    bar = bar.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), angle)
    return bar.translate(cq.Vector(x, y0, z0))


BAT_TIPS = [(43.0, -37.0), (31.0, -45.0), (17.0, -49.0), (3.0, -51.0)]
BAT_WRIST = (6.0, -2.0)


def bat_wings() -> list[cq.Shape]:
    """Folded membrane wing with scallops between the finger tips.

    The finger bones are V grooves on the outer face; their 45 degree walls
    print without support on the vertical plate.
    """
    top = cap.TOP
    tips = BAT_TIPS
    s = Shape2D().polygon([(2.0, top), (42.0, top), (43.5, -8.0), *tips])
    for (y0, z0), (y1, z1) in zip(tips, tips[1:]):
        mid_y, mid_z = (y0 + y1) / 2, (z0 + z1) / 2
        length = ((y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5
        # Unit normal pointing away from the wing (downwards and outwards).
        ny, nz = (z1 - z0) / length, -(y1 - y0) / length
        if nz > 0:
            ny, nz = -ny, -nz
        radius = length * 0.42
        s.circle((mid_y + ny * (radius - 3.2), mid_z + nz * (radius - 3.2)), radius,
                 mode="s")
    right = side_feature(s, (2.0, 42.0))
    outer = SIDE_PLATE_X[1]
    # Grooves run out through the finger tips, so that no end wall faces up.
    grooves = [v_groove(*BAT_WRIST, BAT_WRIST[0] + 1.3 * (tip[0] - BAT_WRIST[0]),
                        BAT_WRIST[1] + 1.3 * (tip[1] - BAT_WRIST[1]), outer)
               for tip in tips[:3]]
    wing = right[1]
    for groove in grooves:
        wing = wing.cut(groove)
    return [right[0], wing, right[2], wing.mirror("YZ")]


def lop_ears() -> list[cq.Shape]:
    """Long floppy ear hanging in front of the pitch axis."""
    s = Shape2D().rect((10.0, -9.0), 14.0, 24.6)
    s.ellipse((10.5, -24.0), 8.2, 21.0)
    return side_feature(s, (3.0, 17.0))


def front_frame(points: list[tuple[float, float]], rounding: float) -> list[cq.Shape]:
    """Frame beside the face, joined to an extended brim and side struts."""
    top = cap.TOP
    brim = box(-cap.OUTER_HALF, cap.OUTER_HALF, FRAME_Y[0], cap.FRONT + 1.0,
               cap.CLEARANCE + cap.CORE_RECESS, top)
    strut = box(FRAME_INNER_X, 34.0, FRAME_Y[0], cap.SKIRT_Y[0] + 1.0,
                cap.CLEARANCE, top)
    outline = Shape2D().polygon([(FRAME_INNER_X, top), *points])
    side = plate(root(outline, FRAME_INNER_X, points[0][0]), "xz", *FRAME_Y,
                 rounding=rounding)
    return [brim, *both_sides([strut, side])]


def lion_mane() -> list[cq.Shape]:
    top = cap.TOP
    points = [(40.0, top), (48.5, -7.5), (44.5, -10.5), (52.0, -19.5), (46.5, -23.0),
              (53.0, -31.5), (47.0, -35.0), (52.0, -43.0), (45.5, -46.0), (48.0, -54.0),
              (40.5, -56.5), (35.0, -61.0), (FRAME_INNER_X, -58.0)]
    return front_frame(points, 0.8)


def petal_frame() -> list[cq.Shape]:
    top = cap.TOP
    points = [(41.0, top), (51.0, -9.0), (45.5, -14.0), (54.0, -25.0), (47.0, -30.0),
              (53.5, -40.0), (45.5, -44.0), (48.5, -54.0), (38.0, -58.0),
              (33.0, -61.0), (FRAME_INNER_X, -58.0)]
    return front_frame(points, 3.2)


VARIANTS = [
    Variant("cap-bat-wings", "Cap with folded bat wings", bat_wings),
    Variant("cap-lop-ears", "Cap with lop ears", lop_ears),
    Variant("cap-lion-mane", "Cap with lion mane", lion_mane),
    Variant("cap-petal-frame", "Cap with petal frame", petal_frame),
]


def build(variant: Variant) -> cq.Solid:
    return cap.make_cap(variant.build())
