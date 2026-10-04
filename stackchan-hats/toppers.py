"""Plug-in decorations for the cap, millimetres.

Each piece is a 3.2 mm plate printed flat. Its outline is drawn in (u, v):
u along the cap width, centred on the slot, and v upwards from the cap top
surface. The tab below v = 0 enters a cap slot. Details are raised or
engraved on the face that is printed upwards; it faces forwards when worn.

Outlines are drawn for the piece on the right-hand slot (+x). The left-hand
piece is its mirror image.
"""

from dataclasses import dataclass, field
import math
from typing import Callable

import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
from OCP.GeomAbs import GeomAbs_Arc
from OCP.TopAbs import TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

import cap


THICKNESS = cap.TAB_THICKNESS
EDGE_RADIUS = 1.0            # rounding of the upper face outline
OUTLINE_RADIUS = 1.2         # 2D rounding of convex outline corners
DETAIL = 0.8                 # relief height and engraving depth
DETAIL_RADIUS = 0.3
DETAIL_OUTLINE_RADIUS = 0.5
FOOT_HEIGHT = 1.2            # body must cover the tab up to this height
BUMP = 0.25                  # crush bump on each tab end
# Outer face of the cap skirt and the gap kept to it, in slot-relative u for
# the side slots: pieces that hang over the edge stay outside this line.
SIDE_CLEAR_U = cap.OUTER_HALF + 1.2 - cap.SLOT_X["right"]


Point = tuple[float, float]


def oval(centre: Point, a: float, b: float, angle: float = 0.0) -> cq.Face:
    """Four-arc approximation of an ellipse with semi-axes a (along u) and b.

    Lines and circular arcs keep the 2D offsets and the 3D edge rounding in
    OCC exact and robust; their offsets are again lines and arcs.
    """
    swap = b > a
    major, minor = (b, a) if swap else (a, b)
    small = min(0.9 * minor, 1.25 * minor * minor / major)
    large = ((major - small) ** 2 + minor ** 2 - small ** 2) / (2 * (minor - small))
    end_centre = (major - small, 0.0)
    side_centre = (0.0, minor - large)
    length = math.hypot(end_centre[0] - side_centre[0], end_centre[1] - side_centre[1])
    tangent = (end_centre[0] + small * (end_centre[0] - side_centre[0]) / length,
               end_centre[1] + small * (end_centre[1] - side_centre[1]) / length)
    tx, ty = tangent
    quarter = [(major, 0.0), (tx, ty), (0.0, minor), (-tx, ty), (-major, 0.0),
               (-tx, -ty), (0.0, -minor), (tx, -ty)]
    mids = []
    for (cx, cy, r), (p0, p1) in zip(
            [(end_centre[0], 0.0, small), (0.0, side_centre[1], large),
             (0.0, side_centre[1], large), (-end_centre[0], 0.0, small),
             (-end_centre[0], 0.0, small), (0.0, -side_centre[1], large),
             (0.0, -side_centre[1], large), (end_centre[0], 0.0, small)],
            zip(quarter, quarter[1:] + quarter[:1])):
        mx, my = (p0[0] + p1[0]) / 2 - cx, (p0[1] + p1[1]) / 2 - cy
        norm = math.hypot(mx, my)
        mids.append((cx + r * mx / norm, cy + r * my / norm))
    rotation = math.radians(angle) + (math.pi / 2 if swap else 0.0)
    c, s = math.cos(rotation), math.sin(rotation)

    def place(point: Point) -> cq.Vector:
        x, y = point
        return cq.Vector(centre[0] + x * c - y * s, centre[1] + x * s + y * c, 0)

    edges = [cq.Edge.makeThreePointArc(place(p0), place(m), place(p1))
             for p0, m, p1 in zip(quarter, mids, quarter[1:] + quarter[:1])]
    return cq.Face.makeFromWires(cq.Wire.assembleEdges(edges))


def baked(face: cq.Face) -> cq.Face:
    """Apply a face's location to its geometry so that offsets do not repeat it."""
    transform = BRepBuilderAPI_Transform(face.located(cq.Location()).wrapped,
                                         face.location().wrapped.Transformation(), True)
    return cq.Face(TopoDS.Face_s(transform.Shape()))


def offset_faces(face: cq.Face, distance: float) -> list[cq.Face]:
    """Offset a planar face with arc joins; loops are regrouped into faces."""
    maker = BRepOffsetAPI_MakeOffset(face.wrapped, GeomAbs_Arc)
    maker.Perform(distance)
    if not maker.IsDone():
        raise ValueError("2D offset failed")
    wires = []
    explorer = TopExp_Explorer(maker.Shape(), TopAbs_WIRE)
    while explorer.More():
        wires.append(cq.Wire(TopoDS.Wire_s(explorer.Current())))
        explorer.Next()
    loops = sorted(((cq.Face.makeFromWires(w).Area(), w) for w in wires),
                   key=lambda item: -item[0])
    faces: list[tuple[cq.Face, list[cq.Wire]]] = []
    for _, wire in loops:
        point = cq.Vertex.makeVertex(*wire.startPoint().toTuple())
        for outer, holes in faces:
            if outer.distance(point) < 1e-6:
                holes.append(wire)
                break
        else:
            faces.append((cq.Face.makeFromWires(wire), []))
    return [cq.Face.makeFromWires(outer.outerWire(), holes) for outer, holes in faces]


def round_corners(face: cq.Face, convex: float, concave: float) -> list[cq.Face]:
    """Closing by the concave radius, then opening by the convex radius.

    Features narrower than twice the convex radius disappear in the opening.
    """
    result = []
    for grown in offset_faces(face, concave):
        for core in offset_faces(grown, -(concave + convex)):
            result.extend(offset_faces(core, convex))
    return result


@dataclass
class Shape2D:
    """A list of additive and subtractive primitives for cq.Sketch."""
    ops: list[tuple[str, str, tuple]] = field(default_factory=list)

    def circle(self, centre: Point, radius: float, mode: str = "a") -> "Shape2D":
        self.ops.append((mode, "circle", (centre, radius)))
        return self

    def ellipse(self, centre: Point, a: float, b: float, angle: float = 0.0,
                mode: str = "a") -> "Shape2D":
        self.ops.append((mode, "ellipse", (centre, a, b, angle)))
        return self

    def rect(self, centre: Point, width: float, height: float, angle: float = 0.0,
             mode: str = "a") -> "Shape2D":
        self.ops.append((mode, "rect", (centre, width, height, angle)))
        return self

    def polygon(self, points: list[Point], mode: str = "a") -> "Shape2D":
        area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
                   in zip(points, points[1:] + points[:1]))
        ordered = tuple(points if area > 0 else reversed(points))
        self.ops.append((mode, "polygon", (ordered,)))
        return self

    def mound(self, width: float = 20.0, height: float = 3.4, u: float = 0.0) -> "Shape2D":
        """Low oval base that covers the tab; the cut at v = 0 meets its flank."""
        return self.ellipse((u, -1.2), width / 2 + 1.0, height + 1.2)

    def bar(self, start: Point, end: Point, width: float, mode: str = "a") -> "Shape2D":
        """Rectangle of the given width from start to end."""
        dx, dy = end[0] - start[0], end[1] - start[1]
        centre = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        return self.rect(centre, math.hypot(dx, dy), width,
                         math.degrees(math.atan2(dy, dx)), mode)

    def faces(self, fillet: float | None, blend: float | None = None) -> list[cq.Face]:
        sketch = cq.Sketch()
        for mode, kind, args in self.ops:
            if kind == "circle":
                centre, radius = args
                sketch = sketch.push([centre]).circle(radius, mode=mode).reset()
            elif kind == "ellipse":
                sketch = sketch.face(oval(*args), mode=mode).reset()
            elif kind == "rect":
                centre, width, height, angle = args
                sketch = sketch.push([centre]).rect(width, height, angle,
                                                    mode=mode).reset()
            else:
                points = list(args[0]) + [args[0][0]]
                sketch = sketch.polygon(points, mode=mode).reset()
        faces = [baked(face) for face in sketch.clean()._faces.Faces()]
        if not fillet:
            return faces
        concave = blend if blend is not None else fillet
        return [rounded for face in faces
                for rounded in round_corners(face, fillet, concave)]


@dataclass
class Piece:
    name: str
    outline: Callable[[], Shape2D]
    raised: Callable[[], Shape2D] | None = None
    engraved: Callable[[], Shape2D] | None = None
    slot: str = "right"            # "right" pieces are mirrored for "left"
    row: str = "front"
    fillet: float = OUTLINE_RADIUS
    hangs: bool = False            # may extend below v = 0 outside the skirt
    blend: float = 2.0             # concave corner radius


@dataclass
class TopperSet:
    key: str
    title: str
    pieces: list[Piece]


def extrude(shape: Shape2D, height: float, z: float = 0.0,
            fillet: float | None = OUTLINE_RADIUS, single: bool = False,
            blend: float | None = None) -> cq.Workplane:
    faces = shape.faces(fillet, blend)
    if single and len(faces) != 1:
        raise ValueError(f"Outline must be one connected region, got {len(faces)}")
    solids = [cq.Solid.extrudeLinear(face.translate(cq.Vector(0, 0, z)),
                                     cq.Vector(0, 0, height)) for face in faces]
    return cq.Workplane("XY").add(cq.Compound.makeCompound(solids)
                                  if len(solids) > 1 else solids[0])


def tab() -> cq.Solid:
    """Tab below v = 0 with crush bumps on both ends and a lead-in."""
    half = cap.TAB_LENGTH / 2
    depth = cap.TAB_DEPTH
    lead = 0.4
    mid = -depth / 2
    points = [(-half, 0.5), (-half, mid + 0.6), (-half - BUMP, mid),
              (-half, mid - 0.6), (-half, -depth + lead), (-half + lead, -depth),
              (half - lead, -depth), (half, -depth + lead), (half, mid - 0.6),
              (half + BUMP, mid), (half, mid + 0.6), (half, 0.5)]
    return (cq.Workplane("XY").polyline(points).close()
            .extrude(THICKNESS).val())


def build_body(piece: Piece) -> cq.Shape:
    """Decoration plate without tab, upper face rounded, details applied."""
    outline = piece.outline().mound(cap.TAB_LENGTH + 6, 3.6)
    # Nothing may extend below the cap top, except outside the skirt for
    # pieces that hang down beside the head.
    limit = SIDE_CLEAR_U if piece.hangs else 200.0
    outline.rect((limit - 200, -50), 400, 100, mode="s")
    body = extrude(outline, THICKNESS, fillet=piece.fillet, single=True,
                   blend=piece.blend)
    body = body.faces(">Z").edges().fillet(EDGE_RADIUS)
    if piece.raised:
        relief = extrude(piece.raised(), DETAIL + 0.5, THICKNESS - 0.5,
                         fillet=DETAIL_OUTLINE_RADIUS)
        relief = relief.faces(">Z").edges().fillet(DETAIL_RADIUS)
        body = body.union(relief)
    if piece.engraved:
        cut = extrude(piece.engraved(), DETAIL + 2, THICKNESS - DETAIL, fillet=None)
        body = body.cut(cut)
    return body.val()


def build_piece(piece: Piece) -> tuple[cq.Shape, cq.Shape]:
    """Return (piece with tab, body only) in print orientation."""
    body = build_body(piece)
    full = body.fuse(tab())
    if not full.isValid() or len(full.Solids()) != 1:
        raise ValueError(f"{piece.name}: not a valid single solid")
    return full, body


def mirrored(shape: cq.Shape) -> cq.Shape:
    return shape.mirror("YZ")


# --------------------------------------------------------------------------
# Animal ears and other pairs, outlines for the right-hand slot.

def cat_ear() -> Shape2D:
    return Shape2D().polygon([(-8, 0), (9, 0), (4.5, 17)])


def cat_inner() -> Shape2D:
    return Shape2D().polygon([(-3.6, 3), (5.4, 3), (3.6, 11.4)])


def dog_ear() -> Shape2D:
    """Floppy ear: rises from the slot, folds over the edge and hangs down."""
    s = Shape2D().mound(18)
    s.circle((3.0, 6.5), 6.5)
    return s.ellipse((12.5, -1.5), 6.8, 15.0, 36.5)


def dog_inner() -> Shape2D:
    return Shape2D().ellipse((15.6, -5.6), 3.0, 8.0, 36.5)


def rabbit_ear() -> Shape2D:
    return Shape2D().mound(19, 3.6).ellipse((2.5, 20), 6.5, 20.5, -6)


def rabbit_inner() -> Shape2D:
    return Shape2D().ellipse((2.8, 21.5), 3.0, 14.5, -6)


def bear_ear() -> Shape2D:
    return Shape2D().mound(20).circle((3, 8), 8.5)


def bear_inner() -> Shape2D:
    return Shape2D().circle((3.4, 8.8), 4.6)


def fox_ear() -> Shape2D:
    return Shape2D().polygon([(-9.5, 0), (10, 0), (5, 23)])


def fox_inner() -> Shape2D:
    return Shape2D().polygon([(-4.5, 3), (2.0, 4.6), (6.4, 3), (4.3, 15)])


def mouse_ear() -> Shape2D:
    return Shape2D().mound(22, 3.6, 1.5).circle((5, 11.5), 11.0)


def mouse_inner() -> Shape2D:
    return Shape2D().circle((5.6, 12.4), 7.2)


def panda_ear() -> Shape2D:
    return Shape2D().mound(20, 3.4, 1.5).circle((6, 6.5), 7.2)


def panda_inner() -> Shape2D:
    return Shape2D().circle((6.3, 7.0), 4.4)


def frog_eye() -> Shape2D:
    return Shape2D().mound(22, 3.6).circle((0, 8), 8.5)


def frog_pupil() -> Shape2D:
    return Shape2D().circle((0.6, 8.6), 4.2)


def frog_highlight() -> Shape2D:
    return Shape2D().circle((2.0, 10.4), 1.2)


def pig_ear() -> Shape2D:
    return Shape2D().polygon([(-9, 0), (8, 0), (14.5, 11), (5, 9.5)])


def pig_inner() -> Shape2D:
    return Shape2D().polygon([(-2.5, 2.6), (5, 2.6), (9.6, 7.8), (3.6, 6.6)])


def devil_horn() -> Shape2D:
    return Shape2D().mound(20).polygon([(-6, 0), (6, 0), (8, 6), (10.5, 15.5),
                                        (5.5, 10), (-1, 5)])


def sheep_horn() -> Shape2D:
    s = Shape2D().mound(22, 3.6, 2)
    s.circle((6.5, 9), 8.5)
    s.circle((6.5, 9), 4.6, mode="s")
    s.circle((6.2, 9.6), 2.6)
    s.bar((6.2, 9.6), (2.0, 9.6), 2.4)
    return s


def sheep_groove() -> Shape2D:
    return Shape2D().circle((6.5, 9), 7.1).circle((6.5, 9), 6.1, mode="s")


def heart(centre: Point, size: float, angle: float = 0.0) -> list[tuple[str, tuple]]:
    """Heart from two circles and a triangle, scaled and rotated."""
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def at(x: float, y: float) -> Point:
        return (centre[0] + size * (x * c - y * s), centre[1] + size * (x * s + y * c))

    return [("circle", (at(-0.48, 0.3), 0.54 * size)),
            ("circle", (at(0.48, 0.3), 0.54 * size)),
            ("polygon", ([at(-1.0, 0.12), at(1.0, 0.12), at(0, -1.1)],))]


def add_heart(shape: Shape2D, centre: Point, size: float, angle: float = 0.0,
              mode: str = "a") -> Shape2D:
    for kind, args in heart(centre, size, angle):
        if kind == "circle":
            shape.circle(*args, mode=mode)
        else:
            shape.polygon(list(args[0]), mode=mode)
    return shape


def heart_antenna() -> Shape2D:
    s = Shape2D().mound(15, 3.0)
    s.bar((0, 0), (3.2, 14), 2.6)
    return add_heart(s, (4.4, 20.0), 6.2, -10)


def heart_antenna_inner() -> Shape2D:
    return add_heart(Shape2D(), (4.4, 20.4), 3.2, -10)


def ball_antenna() -> Shape2D:
    s = Shape2D().mound(15, 3.0)
    s.bar((0, 0), (3.0, 16), 2.6)
    return s.circle((3.4, 19), 4.6)


def ball_antenna_inner() -> Shape2D:
    return Shape2D().circle((4.6, 20.4), 1.4)


def wing() -> Shape2D:
    s = Shape2D().mound(20)
    s.ellipse((7, 6), 10, 5.2, 20)
    s.ellipse((9, 10.5), 9.5, 4.2, 38)
    s.ellipse((4, 3), 9, 3.6, 6)
    return s


def wing_lines() -> Shape2D:
    s = Shape2D()
    s.bar((1.5, 4.4), (11.5, 8.8), 0.9)
    s.bar((4.5, 8.0), (13.5, 14.0), 0.9)
    return s


# --------------------------------------------------------------------------
# Centre pieces, outlines centred on the middle slot.

def ribbon() -> Shape2D:
    s = Shape2D()
    s.polygon([(-2, 8.5), (-15.5, 16.5), (-14.5, 1.5)])
    s.polygon([(2, 8.5), (15.5, 16.5), (14.5, 1.5)])
    s.polygon([(-7.5, 0), (7.5, 0), (3, 7), (-3, 7)])
    s.rect((0, 8.5), 7.5, 9)
    return s


def ribbon_knot() -> Shape2D:
    return Shape2D().rect((0, 8.5), 4.6, 6.2)


def ribbon_folds() -> Shape2D:
    s = Shape2D()
    s.bar((-5.5, 8.6), (-11.5, 12.6), 0.9)
    s.bar((5.5, 8.6), (11.5, 12.6), 0.9)
    s.bar((-5.5, 8.4), (-11.0, 5.0), 0.9)
    s.bar((5.5, 8.4), (11.0, 5.0), 0.9)
    return s


def crown() -> Shape2D:
    s = Shape2D()
    s.polygon([(-15, 0), (15, 0), (17, 13), (8.5, 7), (0, 16), (-8.5, 7),
               (-17, 13)])
    for point in ((-16.5, 12.6), (0, 15.4), (16.5, 12.6)):
        s.circle(point, 2.7)
    return s


def crown_band() -> Shape2D:
    return Shape2D().rect((0, 3.4), 27, 2.6)


def crown_gems() -> Shape2D:
    s = Shape2D().circle((0, 9.5), 1.8)
    for x in (-7.5, 0.0, 7.5):
        s.circle((x, 3.4), 0.8)
    return s


def flower() -> Shape2D:
    s = Shape2D().mound(20, 3.6)
    s.bar((0, 0), (0, 12), 2.8)
    s.ellipse((-5, 4.6), 5.2, 2.4, 28)
    centre = (0, 17)
    for k in range(5):
        a = math.radians(90 + 72 * k)
        s.circle((centre[0] + 6.2 * math.cos(a), centre[1] + 6.2 * math.sin(a)), 4.9)
    s.circle(centre, 5)
    return s


def flower_centre() -> Shape2D:
    return Shape2D().circle((0, 17), 3.4)


def sprout() -> Shape2D:
    s = Shape2D().mound(16, 3.2)
    s.bar((0, 0), (0, 12.5), 2.8)
    s.ellipse((-6.4, 14.6), 6.6, 3.6, -32)
    s.ellipse((6.4, 14.6), 6.6, 3.6, 32)
    return s


def sprout_veins() -> Shape2D:
    s = Shape2D()
    s.bar((-2.6, 12.4), (-10.2, 17.2), 0.9)
    s.bar((2.6, 12.4), (10.2, 17.2), 0.9)
    return s


def ahoge() -> Shape2D:
    s = Shape2D().mound(15, 3.0)
    s.bar((0, 0), (1.8, 10), 3.0)
    s.circle((5.6, 15), 7.4)
    s.circle((5.6, 15), 4.4, mode="s")
    s.polygon([(5.6, 15), (14, 8), (14, 1), (6, 1)], mode="s")
    return s


def star_points(centre: Point, outer: float, inner: float, angle: float = 0.0) -> list[Point]:
    points = []
    for k in range(10):
        r = outer if k % 2 == 0 else inner
        a = math.radians(90 + angle + 36 * k)
        points.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)))
    return points


def star_wand() -> Shape2D:
    s = Shape2D().mound(15, 3.0)
    s.bar((0, 0), (-2.0, 17), 2.8)
    return s.polygon(star_points((-2.6, 20), 9.5, 4.4, 8))


def star_inner() -> Shape2D:
    return Shape2D().polygon(star_points((-2.6, 20), 5.0, 2.4, 8))


def witch_hat() -> Shape2D:
    s = Shape2D().ellipse((0, 0.6), 21.5, 4.4)
    s.polygon([(-11, 3), (11, 3), (6, 16), (13.5, 27), (2, 19.5), (-3, 15)])
    return s


def witch_band() -> Shape2D:
    return Shape2D().polygon([(-8.8, 4.8), (8.8, 4.8), (7.9, 7.6), (-8.0, 7.6)])


def santa_hat() -> Shape2D:
    s = Shape2D().rect((0, 2.8), 32, 5.6)
    s.polygon([(-13, 5), (13, 5), (12, 13), (17.5, 17), (15, 20.5), (3, 21),
               (-6, 17)])
    return s.circle((17.5, 20), 4.4)


def santa_fur() -> Shape2D:
    return Shape2D().rect((0, 2.9), 29.4, 3.6).circle((17.5, 20), 2.6)


def chick() -> Shape2D:
    s = Shape2D().mound(22, 3.6).circle((0, 10.5), 10)
    s.ellipse((-1.2, 21), 1.7, 3.4, 110)
    s.ellipse((1.4, 21.2), 1.7, 3.6, 70)
    return s


def chick_face() -> Shape2D:
    s = Shape2D()
    s.polygon([(-1.8, 11), (1.8, 11), (0, 8.2)])
    s.ellipse((5.4, 8.6), 1.9, 2.8, 30)
    s.ellipse((-5.4, 8.6), 1.9, 2.8, -30)
    return s


def chick_eyes() -> Shape2D:
    return Shape2D().circle((-3.8, 13.6), 1.4).circle((3.8, 13.6), 1.4)


def unicorn_horn() -> Shape2D:
    s = Shape2D().mound(16, 3.0)
    return s.polygon([(-5.2, 1), (5.2, 1), (0.8, 25)])


def unicorn_grooves() -> Shape2D:
    s = Shape2D()
    for k, v in enumerate((5.0, 9.5, 14.0, 18.5)):
        half = 4.6 * (1 - (v - 1) / 24) - 0.8
        s.bar((-half, v - 1.2), (half, v + 1.2), 0.8)
    return s


def halo() -> Shape2D:
    s = Shape2D().mound(16, 3.0)
    s.bar((0, 0), (0, 13), 2.6)
    s.ellipse((0, 17), 14, 5.6)
    s.ellipse((0, 17), 10.6, 2.8, mode="s")
    return s


# --------------------------------------------------------------------------

def pair(name: str, outline, raised=None, engraved=None, row: str = "front",
         fillet: float = OUTLINE_RADIUS, hangs: bool = False,
         blend: float = 2.0) -> list[Piece]:
    return [Piece(f"{name}-{side}", outline, raised, engraved, side, row, fillet,
                  hangs, blend) for side in ("left", "right")]


def centre(name: str, outline, raised=None, engraved=None, row: str = "front",
           fillet: float = OUTLINE_RADIUS, blend: float = 2.0) -> list[Piece]:
    return [Piece(name, outline, raised, engraved, "centre", row, fillet,
                  False, blend)]


SETS: list[TopperSet] = [
    TopperSet("cat-ears", "Cat ears", pair("cat-ear", cat_ear, engraved=cat_inner,
                                         fillet=1.4)),
    TopperSet("dog-ears", "Dog ears (floppy)", pair("dog-ear", dog_ear,
                                                 engraved=dog_inner, hangs=True,
                                                 blend=3.0)),
    TopperSet("rabbit-ears", "Rabbit ears", pair("rabbit-ear", rabbit_ear,
                                               engraved=rabbit_inner)),
    TopperSet("bear-ears", "Bear ears", pair("bear-ear", bear_ear, engraved=bear_inner)),
    TopperSet("fox-ears", "Fox ears", pair("fox-ear", fox_ear, engraved=fox_inner,
                                         fillet=1.4)),
    TopperSet("mouse-ears", "Mouse ears", pair("mouse-ear", mouse_ear,
                                             engraved=mouse_inner)),
    TopperSet("panda-ears", "Panda ears", pair("panda-ear", panda_ear,
                                             raised=panda_inner)),
    TopperSet("frog-eyes", "Frog eyes", pair("frog-eye", frog_eye, raised=frog_pupil,
                                           engraved=frog_highlight)),
    TopperSet("pig-ears", "Pig ears", pair("pig-ear", pig_ear, engraved=pig_inner)),
    TopperSet("sheep-horns", "Sheep horns", pair("sheep-horn", sheep_horn,
                                               engraved=sheep_groove, fillet=1.2)),
    TopperSet("devil-horns", "Devil horns", pair("devil-horn", devil_horn)),
    TopperSet("heart-antennae", "Heart antennae",
              pair("heart-antenna", heart_antenna, engraved=heart_antenna_inner,
                   fillet=1.0)),
    TopperSet("ball-antennae", "Ball antennae",
              pair("ball-antenna", ball_antenna, engraved=ball_antenna_inner,
                   fillet=1.0)),
    TopperSet("angel-wings", "Angel wings", pair("wing", wing, engraved=wing_lines,
                                               row="rear", fillet=1.2)),
    TopperSet("ribbon", "Ribbon", centre("ribbon", ribbon, raised=ribbon_knot,
                                         engraved=ribbon_folds)),
    TopperSet("crown", "Crown", centre("crown", crown, raised=crown_band,
                                       engraved=crown_gems, fillet=1.2)),
    TopperSet("flower", "Flower", centre("flower", flower, raised=flower_centre,
                                         fillet=1.2, blend=0.6)),
    TopperSet("sprout", "Sprout", centre("sprout", sprout, engraved=sprout_veins,
                                         fillet=1.2, blend=1.0)),
    TopperSet("ahoge", "Hair curl", centre("ahoge", ahoge, fillet=1.2)),
    TopperSet("star-wand", "Star antenna", centre("star", star_wand,
                                                 raised=star_inner, fillet=1.0)),
    TopperSet("witch-hat", "Witch hat", centre("witch-hat", witch_hat,
                                               raised=witch_band, fillet=1.4)),
    TopperSet("santa-hat", "Santa hat", centre("santa-hat", santa_hat,
                                               raised=santa_fur, fillet=1.4)),
    TopperSet("chick", "Chick", centre("chick", chick, raised=chick_face,
                                       engraved=chick_eyes, fillet=1.0)),
    TopperSet("unicorn-horn", "Unicorn horn", centre("unicorn-horn", unicorn_horn,
                                                     engraved=unicorn_grooves,
                                                     fillet=1.2)),
    TopperSet("halo", "Halo", centre("halo", halo, row="rear", fillet=1.0)),
]


def placement(piece: Piece) -> cq.Location:
    """Location that moves a print-oriented piece into head coordinates."""
    x = cap.SLOT_X[piece.slot]
    y = cap.SLOT_Y[piece.row] + THICKNESS / 2
    return (cq.Location(cq.Vector(x, y, cap.TOP))
            * cq.Location(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90))


def build_set(topper: TopperSet) -> list[tuple[Piece, cq.Shape, cq.Shape]]:
    """Return (piece, solid, body) in print orientation; left pieces mirrored."""
    built = []
    cache: dict[str, tuple[cq.Shape, cq.Shape]] = {}
    for piece in topper.pieces:
        base = piece.name.removesuffix("-left").removesuffix("-right")
        if base not in cache:
            cache[base] = build_piece(piece)
        full, body = cache[base]
        if piece.slot == "left":
            full, body = mirrored(full), mirrored(body)
        built.append((piece, full, body))
    return built
