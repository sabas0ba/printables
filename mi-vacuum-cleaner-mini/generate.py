"""Continuous open cradle for Mi Vacuum Cleaner Mini, millimetres.

The end apertures stay open for the nozzle and the axial USB-C cable. The
gentle, smaller-radius end portions act as axial stops for the 55 mm body.
"""

import cadquery as cq
from pathlib import Path


LENGTH = 281.0
WIDTH = 68.0
BASE = 4.0
AXIS_Z = 40.0
GRIP_CENTER_X = LENGTH / 2
GRIP_CUT_RADIUS = 51.0
GRIP_CUT_CENTER_Z = 63.0  # lowest point: z=12 mm
GRIP_INNER_Y = 17.0


def smoothstep(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def outside_height(x):
    left = 1.0 - smoothstep(x / 38.0)
    right = smoothstep((x - (LENGTH - 38.0)) / 38.0)
    return 27.0 + 18.0 * max(left, right)


def bore_radius(x):
    left = smoothstep(x / 10.0)
    right = smoothstep((x - (LENGTH - 10.0)) / 10.0)
    return (25.0 + 4.0 * left) * (1.0 - right) + 18.0 * right


def round_contact_edges(shape):
    """Round the exposed edges without reducing the cable/nozzle openings."""
    def outer_rim(edge):
        box = edge.BoundingBox()
        return (abs(edge.Center().y) > 33.9 and box.zmin >= 11.9
                and box.zmax > 20 and edge.Length() < 100)

    def finger_rim(edge):
        center, box = edge.Center(), edge.BoundingBox()
        return (100 < center.x < 181 and 16.9 <= abs(center.y) < 30
                and box.zmax >= 12 and edge.Length() > 15)

    def cradle_rim(edge):
        center, box = edge.Center(), edge.BoundingBox()
        return (25 < box.zmin and box.zmax < 30
                and 23 < abs(center.y) < 31
                and box.xlen > 20 and edge.Length() > 25)

    def end_opening(edge, x):
        return (edge.geomType() == "CIRCLE"
                and abs(edge.Center().x - x) < 0.01
                and edge.Length() > 40)

    def vertical_corner(edge):
        center = edge.Center()
        return (edge.geomType() == "LINE" and edge.Length() > 40
                and abs(center.x - LENGTH / 2) > 130
                and abs(center.y) > 30)

    def bottom_perimeter(edge):
        return (edge.geomType() == "LINE"
                and abs(edge.Center().z) < 0.01 and edge.Length() > 50)

    passes = (
        (1.2, outer_rim),
        (1.2, finger_rim),
        (0.8, cradle_rim),
        (0.8, lambda e: end_opening(e, 0.0)),
        (0.5, lambda e: end_opening(e, LENGTH)),
        (0.5, vertical_corner),
        (1.0, bottom_perimeter),
    )
    for radius, select in passes:
        edges = [edge for edge in shape.Edges() if select(edge)]
        if not edges:
            raise ValueError("Expected rim edge missing")
        shape = shape.fillet(radius, edges)
    return shape


def make_holder():
    # Loft the outer silhouette and the continuously open, varying bore.
    xs = sorted(set([float(x) for x in range(0, 282, 4)] + [LENGTH, 10.0, 271.0]))
    outer_wires = []
    inner_wires = []
    for x in xs:
        top = outside_height(x)
        outer_wires.append(
            cq.Workplane("YZ", origin=(x, 0, 0))
            .polyline([(-WIDTH / 2, BASE), (WIDTH / 2, BASE),
                       (WIDTH / 2, top), (-WIDTH / 2, top)])
            .close().val()
        )
        inner_wires.append(
            cq.Workplane("YZ", origin=(x, 0, AXIS_Z))
            .circle(bore_radius(x)).val()
        )

    shell = cq.Solid.makeLoft(outer_wires, ruled=True)
    opening = cq.Solid.makeLoft(inner_wires, ruled=True)
    base = (cq.Workplane("XY")
            .box(LENGTH, WIDTH, BASE, centered=(False, True, False)).val())
    holder = base.fuse(shell).cut(opening)

    # Two rounded side scallops expose the body near its middle. The material
    # within +/-17 mm of the centerline stays intact to support its underside.
    for y, direction in ((GRIP_INNER_Y, 1), (-GRIP_INNER_Y, -1)):
        finger_cut = cq.Solid.makeCylinder(
            GRIP_CUT_RADIUS, WIDTH / 2 - GRIP_INNER_Y + 2.0,
            cq.Vector(GRIP_CENTER_X, y, GRIP_CUT_CENTER_Z),
            cq.Vector(0, direction, 0),
        )
        holder = holder.cut(finger_cut)
    holder = round_contact_edges(holder.clean())
    if not holder.isValid() or len(holder.Solids()) != 1:
        raise ValueError("The rounded holder is not a valid single solid")
    return holder


if __name__ == "__main__":
    output = Path(__file__).with_name("holder.stl")
    cq.exporters.export(
        make_holder(), str(output), tolerance=0.15, angularTolerance=0.3
    )
