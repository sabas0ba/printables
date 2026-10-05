"""Cap variants that dress the head as food, millimetres.

The white head itself stands for the tofu, the rice or the pudding; the
variant is only the topping laid over it: soy sauce or caramel running down
the sides and the rear, or a sheet of nori or a leaf wrapped around it.

Each variant is the cap with extra parts and keeps the cap's detents, LED
windows and decoration slots. The extras follow the rules of integral.py:
everything lies below the cap top, and going down from the cap top (upwards
when printed) an outline widens by at most 45 degrees. Drips therefore end
in drops whose upper flanks rise at DROP_FLANK degrees. Nothing is attached
to the detent tongues, and points behind the pitch axis stay within
REAR_REACH of it so that they clear the base when the head looks up.

On the rear face, nothing may hang below the cap's rear lip: the body passes
just behind it when the head looks up, and test drips ending at z = -5.6 met
it at 84 degrees. The pouring covers only the rear top edge there.
"""

from dataclasses import dataclass
import math
from typing import Callable

import cadquery as cq

import cap
import head
from integral import box, plate, root, v_groove
from toppers import Shape2D


DROP_FLANK = 50.0                     # degrees from horizontal
LAYER = 1.0                           # topping thickness outside the skirt
TONGUE_KEEPOUT = (13.3, 26.3)         # y range of the tongue and its slits
# Gap between neighbouring drips. The outline rounding closes narrower gaps
# with a concave arc whose lower part faces up, an overhang when printed.
DRIP_GAP = 2.6
REAR_REACH = 31.5                     # largest distance behind the pitch axis
SIDE_INNER = cap.INNER_HALF           # drips lie on the head side
SIDE_OUTER = cap.OUTER_HALF + LAYER
REAR_INNER = head.SHELL_DEPTH + cap.CLEARANCE
REAR_OUTER = cap.REAR + LAYER
ROOT_TOP = cap.TOP + 3.0              # above the clip in plate()
BAND_BOTTOM = -2.0                    # thicker layer along the top edges
SHEET = (cap.OUTER_HALF + 1.6, cap.OUTER_HALF + 3.6)   # wrap sheet x range
SHEET_SHOULDER_X = 27.0


@dataclass
class Drape:
    key: str
    title: str
    extras: Callable[[], list[cq.Shape]]          # fused before the cap's cuts
    after: Callable[[], list[cq.Shape]] = lambda: []   # fused after them


def drop(shape: Shape2D, u: float, v_end: float, stem: float,
         radius: float) -> Shape2D:
    """Drip from above the cap top down to a drop whose lowest point is v_end."""
    centre = v_end + radius
    shape.rect((u, (ROOT_TOP + centre) / 2), stem, ROOT_TOP - centre)
    shape.circle((u, centre), radius)
    # Tangents to the drop at DROP_FLANK meet above it on the drip axis.
    t = math.radians(90.0 - DROP_FLANK)
    shape.polygon([(u - radius * math.cos(t), centre + radius * math.sin(t)),
                   (u + radius * math.cos(t), centre + radius * math.sin(t)),
                   (u, centre + radius / math.sin(t))])
    return shape


def rear_clip(shape: Shape2D) -> Shape2D:
    """Remove side-plate area behind the pitch axis beyond REAR_REACH."""
    y0, z0 = head.PITCH_AXIS
    # Points above the axis descend by less than their distance behind it,
    # so only the part below the axis needs the limit.
    region = Shape2D().rect(((y0 + 100.0) / 2, z0 - 100.0), 100.0 - y0, 200.0)
    region.circle((y0, z0), REAR_REACH, mode="s")
    for face in region.faces(None):
        shape.add_face(face, mode="s")
    return shape


def side_drips(drips: list[tuple[float, float, float, float]]) -> cq.Shape:
    """Drips (y, lowest z, stem width, drop radius) on the right head side."""
    s = Shape2D().rect(((cap.SKIRT_Y[0] + cap.SKIRT_Y[1]) / 2,
                        (BAND_BOTTOM + ROOT_TOP) / 2),
                       cap.SKIRT_Y[1] - cap.SKIRT_Y[0], ROOT_TOP - BAND_BOTTOM)
    spans = sorted((y - max(stem / 2, radius), y + max(stem / 2, radius))
                   for y, _, stem, radius in drips)
    for lo, hi in spans:
        if hi > TONGUE_KEEPOUT[0] and lo < TONGUE_KEEPOUT[1]:
            raise ValueError(f"drip at y = {(lo + hi) / 2} touches the detent tongue")
    for (_, hi), (lo, _) in zip(spans, spans[1:]):
        if lo - hi < DRIP_GAP - 1e-6:
            raise ValueError(f"drips at y = {hi} and {lo} are closer than {DRIP_GAP}")
    for y, z, stem, radius in drips:
        drop(s, y, z, stem, radius)
    return plate(s, "yz", SIDE_INNER, SIDE_OUTER)


def rear_edge() -> cq.Shape:
    """Topping layer along the rear top edge, ending above the lip bottom."""
    half = cap.OUTER_HALF - cap.PLAN_RADIUS
    s = Shape2D().rect((0.0, (BAND_BOTTOM + ROOT_TOP) / 2), 2 * half,
                       ROOT_TOP - BAND_BOTTOM)
    return plate(s, "xz", REAR_INNER, REAR_OUTER)


def poured(right: list[tuple[float, float, float, float]],
           left: list[tuple[float, float, float, float]]) -> list[cq.Shape]:
    """A pouring over the head top; the left list is given with y as on the right."""
    return [side_drips(right), side_drips(left).mirror("YZ"), rear_edge()]


def wrap(outline: Shape2D, y0: float, y1: float) -> list[cq.Shape]:
    """Sheet on both head sides, standing off the skirt so the tongue can flex."""
    shoulder = box(SHEET_SHOULDER_X, SHEET[1], y0, y1, cap.CLEARANCE, cap.TOP)
    side = plate(root(rear_clip(outline), y0, y1), "yz", *SHEET)
    return [shoulder, side, shoulder.mirror("YZ"), side.mirror("YZ")]


# --------------------------------------------------------------------------

def soy_sauce() -> list[cq.Shape]:
    return poured(
        right=[(3.2, -27.0, 3.0, 2.2), (10.8, -16.0, 3.0, 2.2),
               (29.2, -30.0, 3.2, 2.6), (38.8, -20.0, 3.0, 2.2)],
        left=[(3.4, -19.0, 3.0, 2.0), (10.6, -31.0, 3.0, 2.4),
              (29.0, -21.0, 3.0, 2.2), (36.4, -34.0, 3.2, 2.6)])


def caramel() -> list[cq.Shape]:
    """Short, even drips like caramel sauce running off a pudding."""
    side = [(3.0, -15.5, 3.4, 2.0), (9.6, -14.0, 3.4, 2.0), (28.4, -15.5, 3.4, 2.0),
            (35.0, -14.0, 3.4, 2.0), (41.6, -16.0, 3.4, 2.0)]
    return poured(side, side)


def nori_band() -> list[cq.Shape]:
    """Nori across the top and down both sides of a rice-ball head."""
    s = Shape2D().rect((20.0, (cap.TOP - 40.0) / 2), 26.0, cap.TOP + 40.0)
    return wrap(s, 7.0, 33.0)


def nori_wrap() -> list[cq.Shape]:
    """Nori around the norimaki; the face is the cut end showing the rice."""
    s = Shape2D().rect((22.5, (cap.TOP - 52.0) / 2), 43.0, cap.TOP + 52.0)
    return wrap(s, 1.0, 44.0)


LEAF_CENTRE = (22.0, cap.TOP)
LEAF_HALF = (20.5, 50.0)


def sakura_leaf() -> list[cq.Shape]:
    """Salted cherry leaf wrapped down the right side, veins as V grooves."""
    s = Shape2D().ellipse(LEAF_CENTRE, *LEAF_HALF)
    s.rect((LEAF_CENTRE[0], cap.TOP + 30.0), 60.0, 60.0, mode="s")
    y0, y1 = LEAF_CENTRE[0] - LEAF_HALF[0] + 0.5, LEAF_CENTRE[0] + LEAF_HALF[0] - 0.5
    shoulder = box(SHEET_SHOULDER_X, SHEET[1], y0, y1, cap.CLEARANCE, cap.TOP)
    leaf = plate(root(rear_clip(s), y0, y1), "yz", *SHEET)
    # Grooves run out through the leaf edge at their lower ends, so that no
    # groove end wall faces up.
    outer = SHEET[1]
    y, top = LEAF_CENTRE[0], cap.TOP - 4.0
    grooves = [v_groove(y, top, y, -60.0, outer)]
    for z in (-6.0, -16.0, -26.0):
        for side in (-1.0, 1.0):
            grooves.append(v_groove(y, z, y + side * 30.0, z - 30.0, outer))
    for groove in grooves:
        leaf = leaf.cut(groove)
    return [shoulder, leaf]


def crust() -> list[cq.Shape]:
    """Bread crust beside the face; the screen is the cut face of the slice."""
    top = cap.TOP
    brim = box(-cap.OUTER_HALF, cap.OUTER_HALF, -17.8, cap.FRONT + 1.0,
               cap.CLEARANCE + cap.CORE_RECESS, top)
    strut = box(27.6, 33.0, -17.8, cap.SKIRT_Y[0] + 1.0, cap.CLEARANCE, top)
    outline = Shape2D().rect((30.3, (top - 55.0) / 2), 5.4, top + 55.0)
    side = plate(root(outline, 27.6, 33.0), "xz", -17.8, -15.0)
    return [brim, strut, side, strut.mirror("YZ"), side.mirror("YZ")]


DRAPES = [
    Drape("drape-soy-sauce", "Soy sauce (head as tofu)", lambda: [], soy_sauce),
    Drape("drape-caramel", "Caramel (head as pudding)", lambda: [], caramel),
    Drape("drape-nori-band", "Nori band (head as onigiri)", nori_band),
    Drape("drape-nori-wrap", "Nori wrap (head as norimaki)", nori_wrap),
    Drape("drape-sakura-leaf", "Cherry leaf (head as sakuramochi)", sakura_leaf),
    Drape("drape-crust", "Crust (head as sliced bread)", crust),
]


def build(drape: Drape) -> cq.Solid:
    """Cap with the drape. Parts in ``after`` lie on the skirt and are fused
    after the cap's lead-in chamfer and slits so that those do not notch them;
    they are cut to the head clearance first and avoid the tongue."""
    solid = cap.make_cap(drape.extras() or None)
    clearance = head.envelope(cap.CLEARANCE, holes=False)
    for part in drape.after():
        solid = solid.fuse(part.cut(clearance))
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise ValueError(f"{drape.key}: not a valid single solid")
    return solid
