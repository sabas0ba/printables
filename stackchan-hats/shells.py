"""Large head-covering shells shaped like a house or food, millimetres.

Each shell is the front silhouette (x, z) of the hat extruded from the rear
of the head to just in front of the face. It is printed standing on its rear
face: every wall then runs straight up, the open front end needs no bridge,
and front details are raised or engraved on the last layers.

A shell replaces the cap. It rests on the head top with the cap's radial
clearance and is held like the cap by a detent on a flexure tongue in each
side wall that snaps into the middle LEGO-compatible side hole, and by its
rear wall, against which it settles when the head looks up. The face, the CoreS3 and
the space beside the CoreS3 side ports stay open. The LED light guides are
covered.

The shells are meant to be printed with sparse infill; the mass model in
generate.py uses two 0.45 mm perimeters and 10 % infill. Their rear wall
reaches the base when the head looks far up, so generate.py reports the
largest pitch angle each shell allows instead of requiring the full range.
"""

from dataclasses import dataclass
import math
from typing import Callable

import cadquery as cq

import cap
import head
from toppers import Shape2D, offset_faces


FRONT = head.CORE_FRONT - 0.6            # -15.4, just in front of the face
BACK = head.SHELL_DEPTH + cap.CLEARANCE + 2.0   # 49.0, rear wall outer face
SIDE_BOTTOM = cap.SKIRT_BOTTOM           # -13, lowest point beside the head
PORT_CLEAR_X = 33.0                      # open beside the CoreS3 side ports
OPEN_TOP = cap.CLEARANCE + cap.CORE_RECESS      # 0.9, above the CoreS3 top
REAR_NOTCH_Z = cap.LIP_BOTTOM            # rear wall open below, as on the cap
ROUNDING = 2.0
FRONT_EDGE = 1.0
DETAIL = 0.8
DETAIL_MARGIN = 0.4

# Flexure tongue in each side wall around the middle side hole. In print
# orientation y is vertical, so every slit face is inclined at SLIT_ANGLE from
# the y axis in plan, and the detent is a ridge whose y flanks are as steep.
TONGUE = cap.SKIRT                       # tongue thickness
GAP = 1.0                                # slit width
TONGUE_HALF = 5.0                        # tongue half width at the outer slit
FLEX_TOP = cap.FLEX_TOP
SLIT_ANGLE = 50.0                        # degrees between slit and x axis
RIDGE_HEIGHT = cap.DETENT_HEIGHT
RIDGE_FLANK = 40.0                       # degrees between ridge flank and wall
RIDGE_Z = (-12.6, -11.0, -9.0, -7.6)     # ramp foot, crest, crest, ramp foot


@dataclass
class Shell:
    key: str
    title: str
    silhouette: Callable[[], Shape2D]
    raised: Callable[[], Shape2D] | None = None
    engraved: Callable[[], Shape2D] | None = None
    # Corner radius of the raised details; None keeps arcs-only shapes, whose
    # concentric offsets OCC does not always resolve, unrounded.
    detail_rounding: float | None = 0.6


def hood() -> Shape2D:
    """Minimum silhouette around the head top and sides."""
    return Shape2D().rect((0, (SIDE_BOTTOM + 6.0) / 2), 62.0, 6.0 - SIDE_BOTTOM)


def along_y(face: cq.Face, y0: float, y1: float) -> cq.Shape:
    """Extrude an (x, z) face drawn on XY over y0 ... y1."""
    solid = cq.Solid.extrudeLinear(face, cq.Vector(0, 0, y1 - y0))
    # Rx(90) maps (u, v, w) to (u, -w, v); shift so that w = 0 lies at y1.
    solid = solid.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90)
    return solid.translate(cq.Vector(0, y1, 0))


def outline_face(silhouette: Shape2D) -> cq.Face:
    """Silhouette joined with the hood, cut at the side bottom and rounded."""
    outline = Shape2D(list(silhouette.ops) + hood().ops)
    outline.rect((0, SIDE_BOTTOM - 100.0), 400.0, 200.0, mode="s")
    faces = outline.faces(ROUNDING, ROUNDING)
    if len(faces) != 1:
        raise ValueError("silhouette must be one region")
    return faces[0]


def notch_region() -> Shape2D:
    """Front area without material: the face and the CoreS3 sides."""
    return Shape2D().rect((0, (OPEN_TOP - 80) / 2), 2 * PORT_CLEAR_X, OPEN_TOP + 80)


def detail_faces(shape: Shape2D, rounding: float | None,
                 outline: cq.Face) -> list[cq.Face]:
    """Front details, kept inside the flat front face and off the open notch
    so that they rest on material."""
    region = Shape2D()
    for face in shape.faces(rounding):
        region.add_face(face)
    for face in offset_faces(outline, -(FRONT_EDGE + DETAIL_MARGIN)):
        region.add_face(face, mode="i")
    for mode, kind, args in notch_region().ops:
        region.ops.append(("s", kind, args))
    return region.faces(None)


def reliefs(shell: Shell, outline: cq.Face) -> list[cq.Shape]:
    """Raised front details as separate solids, also used for the preview."""
    if not shell.raised:
        return []
    return [along_y(face, FRONT - DETAIL, FRONT + 0.4)
            for face in detail_faces(shell.raised(), shell.detail_rounding, outline)]


def engravings(shell: Shell, outline: cq.Face) -> list[cq.Shape]:
    """Cutters of the engraved front details."""
    if not shell.engraved:
        return []
    return [along_y(face, FRONT - 1, FRONT + DETAIL)
            for face in detail_faces(shell.engraved(), None, outline)]


def build(shell: Shell) -> cq.Shape:
    try:
        outline = outline_face(shell.silhouette())
    except ValueError as exc:
        raise ValueError(f"{shell.key}: {exc}") from exc
    body = cq.Workplane("XY").add(along_y(outline, FRONT, BACK))
    body = body.faces("<Y").edges().fillet(FRONT_EDGE)
    solid = body.val()

    solid = solid.cut(head.envelope(cap.CLEARANCE, holes=False))
    # Nothing under the head, nothing in front of the face or beside the
    # CoreS3, and the rear wall open below the lip height of the cap.
    solid = solid.cut(cap.box(-cap.INNER_HALF, cap.INNER_HALF, FRONT - 1, BACK + 1,
                              -100, SIDE_BOTTOM))
    solid = solid.cut(cap.box(-PORT_CLEAR_X, PORT_CLEAR_X, FRONT - 1, cap.SKIRT_Y[0],
                              -100, OPEN_TOP))
    solid = solid.cut(cap.box(-cap.INNER_HALF, cap.INNER_HALF,
                              head.SHELL_DEPTH, BACK + 1, -100, REAR_NOTCH_Z))

    solid = flexure(solid)
    for relief in reliefs(shell, outline):
        solid = solid.fuse(relief)
    for cutter in engravings(shell, outline):
        solid = solid.cut(cutter)
    solid = solid.clean()
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise ValueError(f"{shell.key}: not a valid single solid")
    return solid


def prism_z(points: list[tuple[float, float]], z0: float, z1: float) -> cq.Solid:
    """Prism along z from an x-y polygon."""
    return (cq.Workplane("XY", origin=(0, 0, z0)).polyline(points).close()
            .extrude(z1 - z0).val())


def flexure(solid: cq.Shape) -> cq.Shape:
    """Cut the tongue free on three sides and add the detent ridge."""
    y_hole = head.SIDE_HOLE_Y[1]
    inner = cap.INNER_HALF
    a, b = inner + TONGUE, inner + TONGUE + GAP
    y0, y1 = y_hole - TONGUE_HALF, y_hole + TONGUE_HALF
    slope = math.tan(math.radians(SLIT_ANGLE))
    tip = GAP / 2 * slope
    # Diagonal slit width along y for a slit GAP wide across its direction.
    across = GAP / math.cos(math.radians(SLIT_ANGLE))
    start = inner - 0.6
    z0, z1 = SIDE_BOTTOM - 1.0, FLEX_TOP
    for side in (-1, 1):
        def mirror(points):
            return [(side * x, y) for x, y in points]
        cutters = [
            # Slit behind the tongue, pointed at its upper (small y) end.
            [(a, y0), (a + GAP / 2, y0 - tip), (b, y0), (b, y1), (a, y1)],
            # Upper and lower slits from the cavity to the slit behind.
            [(start, y0 - (b - start) * slope), (b, y0), (b, y0 + across),
             (start, y0 - (b - start) * slope + across)],
            [(start, y1 + (b - start) * slope - across), (b, y1 - across), (b, y1),
             (start, y1 + (b - start) * slope)],
        ]
        for points in cutters:
            solid = solid.cut(prism_z(mirror(points), z0, z1))
        # Detent ridge: x-y section with RIDGE_FLANK flanks, x-z section with
        # lead-in ramps; their intersection.
        run = RIDGE_HEIGHT / math.tan(math.radians(RIDGE_FLANK))
        crest = 0.4
        section_xy = prism_z(mirror([
            (inner + 0.05, y_hole - crest / 2 - run), (inner - RIDGE_HEIGHT, y_hole - crest / 2),
            (inner - RIDGE_HEIGHT, y_hole + crest / 2), (inner + 0.05, y_hole + crest / 2 + run)]),
            RIDGE_Z[0] - 1.0, RIDGE_Z[3] + 1.0)
        section_xz = cap.prism_y([(side * (inner + 0.05), RIDGE_Z[0]),
                                  (side * (inner - RIDGE_HEIGHT), RIDGE_Z[1]),
                                  (side * (inner - RIDGE_HEIGHT), RIDGE_Z[2]),
                                  (side * (inner + 0.05), RIDGE_Z[3])],
                                 y_hole - 3.0, y_hole + 3.0)
        solid = solid.fuse(section_xy.intersect(section_xz))
        # Lead-in chamfer on the inner lower edge of the side wall.
        lead = cap.LEAD_IN
        solid = solid.cut(cap.prism_y([(side * (inner - 0.01), SIDE_BOTTOM - 0.01),
                                       (side * (inner + lead), SIDE_BOTTOM - 0.01),
                                       (side * (inner - 0.01), SIDE_BOTTOM + lead)],
                                      FRONT - 1.0, BACK + 1.0))
    return solid


def to_print(shape: cq.Shape) -> cq.Shape:
    """Stand the shell on its rear face: y = BACK goes to z = 0."""
    return shape.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), -90).translate(
        cq.Vector(0, 0, BACK))


# --------------------------------------------------------------------------
# Silhouettes and front details, in (x, z) with z = 0 at the head top.

def house() -> Shape2D:
    s = Shape2D().rect((0, -2.5), 68.0, 21.0)
    s.polygon([(-41.0, 4.0), (41.0, 4.0), (0.0, 45.0)])
    return s.rect((21.0, 32.0), 8.0, 20.0)


def house_raised() -> Shape2D:
    s = Shape2D()
    # Eaves along the roof edges, inside the rounded outline.
    s.bar((-37.5, 2.0), (2.5, 42.0), 3.0)
    s.bar((37.5, 2.0), (-2.5, 42.0), 3.0)
    s.circle((0.0, 24.0), 6.0)
    return s


def house_engraved() -> Shape2D:
    s = Shape2D().circle((0.0, 24.0), 4.2)
    return s


def roof() -> Shape2D:
    """Gable roof only; the head below is the house."""
    return Shape2D().polygon([(-41.0, 2.0), (41.0, 2.0), (0.0, 40.0)])


def roof_raised() -> Shape2D:
    s = Shape2D()
    # Eaves along the roof edges and a gable vent, inside the rounded outline.
    s.bar((-37.5, 0.5), (2.0, 37.0), 3.0)
    s.bar((37.5, 0.5), (-2.0, 37.0), 3.0)
    return s.circle((0.0, 20.0), 5.0)


def roof_engraved() -> Shape2D:
    return Shape2D().circle((0.0, 20.0), 3.4)


def tofu() -> Shape2D:
    return Shape2D().rect((0, 6.5), 72.0, 39.0)


TOFU_DRIPS = [(-29.0, 6.0), (-17.0, 10.0), (-4.0, 4.0), (9.0, 12.0), (22.0, 7.0),
              (34.5, -9.0), (-34.5, -4.0)]


def tofu_raised() -> Shape2D:
    s = Shape2D()
    s.polygon([(-33.0, 25.0), (33.0, 25.0), (31.0, 17.0), (20.0, 15.5), (8.0, 18.0),
               (-6.0, 15.0), (-18.0, 17.5), (-31.0, 15.5)])
    for x, z in TOFU_DRIPS:
        top = 17.0 if abs(x) < 33 else 12.0
        s.bar((x, top), (x, z), 3.2)
        s.circle((x, z), 2.4)
    return s


def tofu_engraved() -> Shape2D:
    s = Shape2D()
    for x, z in ((-20.0, 21.0), (-8.0, 22.0), (12.0, 21.0), (24.0, 22.5)):
        s.circle((x, z), 1.8)
        s.circle((x, z), 0.9, mode="s")
    return s


def pudding() -> Shape2D:
    s = Shape2D().polygon([(-40.0, -13.0), (40.0, -13.0), (30.0, 30.0), (-30.0, 30.0)])
    s.rect((0, -10.5), 92.0, 5.0)
    s.circle((0.0, 33.5), 5.0)
    return s.bar((0.0, 33.5), (4.0, 44.0), 2.4)


def pudding_raised() -> Shape2D:
    s = Shape2D().polygon([(-30.0, 30.0), (30.0, 30.0), (31.0, 25.0), (25.0, 23.0),
                           (17.0, 24.5), (8.0, 21.5), (-2.0, 24.0), (-12.0, 21.0),
                           (-22.0, 23.5), (-31.0, 25.0)])
    for x, z in ((-25.0, 15.0), (-6.0, 17.0), (14.0, 14.0), (27.0, 18.0)):
        s.bar((x, 24.0), (x, z), 3.0)
        s.circle((x, z), 2.2)
    return s


NORI_CENTRE = (0.0, -8.0)
NORI_RADIUS = 42.0


def norimaki() -> Shape2D:
    return Shape2D().circle(NORI_CENTRE, NORI_RADIUS)


def norimaki_raised() -> Shape2D:
    s = Shape2D().circle(NORI_CENTRE, NORI_RADIUS - 0.8)
    return s.circle(NORI_CENTRE, NORI_RADIUS - 5.0, mode="s")


def norimaki_engraved() -> Shape2D:
    s = Shape2D()
    for k in range(14):
        a = math.radians(15 + 150 * k / 13)
        r = 31.0 + 3.0 * (k % 2)
        centre = (NORI_CENTRE[0] + r * math.cos(a), NORI_CENTRE[1] + r * math.sin(a))
        s.ellipse(centre, 2.2, 1.1, math.degrees(a) + 60)
    return s


def sakuramochi() -> Shape2D:
    return Shape2D().ellipse((0.0, -10.0), 40.0, 47.0)


def sakuramochi_raised() -> Shape2D:
    return Shape2D().ellipse((-16.0, 20.0), 20.0, 10.0, 28.0)


def sakuramochi_engraved() -> Shape2D:
    s = Shape2D().bar((-32.0, 12.0), (0.0, 28.0), 1.0)
    for t in (0.3, 0.55, 0.8):
        x, z = -32.0 + 32.0 * t, 12.0 + 16.0 * t
        s.bar((x, z), (x - 4.0, z + 6.5), 0.8)
        s.bar((x, z), (x + 4.5, z - 5.0), 0.8)
    return s


def omurice() -> Shape2D:
    s = Shape2D().ellipse((0.0, -6.0), 46.0, 34.0)
    return s.rect((0, -11.5), 106.0, 3.0)


def omurice_raised() -> Shape2D:
    s = Shape2D()
    points = [(-26.0, 14.0), (-18.0, 22.0), (-10.0, 13.0), (-2.0, 22.0), (6.0, 13.0),
              (14.0, 22.0), (22.0, 13.0), (28.0, 19.0)]
    for a, b in zip(points, points[1:]):
        s.bar(a, b, 3.2)
    for p in points:
        s.circle(p, 1.6)
    return s


def onigiri_triangle() -> Shape2D:
    return Shape2D().polygon([(-46.0, -13.0), (46.0, -13.0), (0.0, 50.0)])


def onigiri_round() -> Shape2D:
    return Shape2D().circle((0.0, 4.0), 40.0)


def nori_strip() -> Shape2D:
    return Shape2D().rect((0.0, 11.0), 30.0, 18.0)


def shumai() -> Shape2D:
    s = Shape2D().rect((0, 4.5), 72.0, 35.0)
    for k in range(7):
        s.circle((-30.0 + 10.0 * k, 24.5), 3.6, mode="s")
    return s.circle((0.0, 26.0), 6.0)


def shumai_engraved() -> Shape2D:
    s = Shape2D()
    for k in range(6):
        x = -25.0 + 10.0 * k
        s.bar((x, 10.0), (x + 1.5, 19.0), 0.9)
    return s


def bread() -> Shape2D:
    s = Shape2D().rect((0, 4.5), 76.0, 35.0)
    s.circle((-17.0, 22.0), 21.0)
    return s.circle((17.0, 22.0), 21.0)


def bread_raised() -> Shape2D:
    """Crust: a 3.5 mm band along the outline."""
    face = outline_face(bread())
    inner = offset_faces(face, -3.5)
    band = Shape2D().add_face(offset_faces(face, -0.6)[0])
    for core in inner:
        band.add_face(core, mode="s")
    return band


SHELLS = [
    Shell("shell-house", "House", house, house_raised, house_engraved),
    Shell("shell-house-roof", "House roof (head as house)", roof, roof_raised,
          roof_engraved),
    Shell("shell-tofu", "Tofu with soy sauce", tofu, tofu_raised, tofu_engraved),
    Shell("shell-pudding", "Pudding", pudding, pudding_raised),
    Shell("shell-norimaki", "Norimaki", norimaki, norimaki_raised, norimaki_engraved,
          detail_rounding=None),
    Shell("shell-sakuramochi", "Sakuramochi", sakuramochi, sakuramochi_raised,
          sakuramochi_engraved),
    Shell("shell-omurice", "Omurice", omurice, omurice_raised),
    Shell("shell-onigiri-triangle", "Triangle onigiri", onigiri_triangle, nori_strip),
    Shell("shell-onigiri-round", "Round onigiri", onigiri_round, nori_strip),
    Shell("shell-shumai", "Shumai", shumai, None, shumai_engraved),
    Shell("shell-bread", "Sliced bread", bread, bread_raised),
]
