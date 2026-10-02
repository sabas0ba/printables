"""Eight-position cord hanger, in millimetres. SPDX-License-Identifier: CC-BY-SA-4.0"""

from pathlib import Path
import struct

import cadquery as cq


LENGTH = 220.0
WIDTH = 35.0
THICKNESS = 5.0
PITCH = 27.0
POSITIONS = [(index - 3.5) * PITCH for index in range(8)]
SLOT_WIDTH = 2.2
POCKET_DIAMETER = 6.0
POCKET_DEPTH = 1.5
SUSPENSION = [(x, y) for x in (-102.0, 102.0) for y in (-10.5, 10.5)]


def make_rack():
    rack = cq.Workplane("XY").box(
        LENGTH, WIDTH, THICKNESS, centered=(True, True, False)
    ).edges("|Z").fillet(3.0)
    for x in POSITIONS:
        # A side entry permits loading a pre-tied cord. The knot rests in the
        # shallow top recess; only the cord passes through the narrower slot.
        slot = (cq.Workplane("XY", origin=(x, 0, -1))
                .moveTo(-SLOT_WIDTH / 2, -WIDTH / 2 - 1)
                .lineTo(SLOT_WIDTH / 2, -WIDTH / 2 - 1)
                .lineTo(SLOT_WIDTH / 2, 0)
                .threePointArc((0, SLOT_WIDTH / 2), (-SLOT_WIDTH / 2, 0))
                .close().extrude(THICKNESS + 2))
        pocket = (cq.Workplane("XY", origin=(x, 0, THICKNESS - POCKET_DEPTH))
                  .circle(POCKET_DIAMETER / 2).extrude(POCKET_DEPTH + 1))
        rack = rack.cut(slot).cut(pocket)
    for x, y in SUSPENSION:
        hole = (cq.Workplane("XY", origin=(x, y, -1))
                .circle(2.0).extrude(THICKNESS + 2))
        rack = rack.cut(hole)
    # Small bevels remove sharp cord-contact edges while retaining a flat base.
    rack = rack.faces(">Z").edges().chamfer(0.35)
    rack = rack.faces("<Z").edges().chamfer(0.35)
    shape = rack.val()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("Rack must be one valid solid")
    return shape


def validate(shape):
    bounds = shape.BoundingBox()
    for actual, expected in zip(
        (bounds.xlen, bounds.ylen, bounds.zlen), (LENGTH, WIDTH, THICKNESS)
    ):
        if abs(actual - expected) > 1e-5:
            raise ValueError("Unexpected outside dimensions")
    for x in POSITIONS:
        for y in (-15, -8, 0):
            if shape.isInside(cq.Vector(x, y, 2)):
                raise ValueError("Cord slot is obstructed")
        if not shape.isInside(cq.Vector(x + 2, 0, 2)):
            raise ValueError("Knot support floor is missing")
        if shape.isInside(cq.Vector(x + 2, 0, 4.5)):
            raise ValueError("Knot recess is obstructed")
    for x, y in SUSPENSION:
        if shape.isInside(cq.Vector(x, y, 2)):
            raise ValueError("Suspension hole is obstructed")


def normalize_stl(path):
    """Remove sub-micrometre floating-point noise from the OCC export."""
    data = bytearray(path.read_bytes())
    count = struct.unpack_from("<I", data, 80)[0]
    for index in range(count):
        offset = 84 + index * 50
        values = struct.unpack_from("<12f", data, offset)
        values = [round(value, 6) for value in values]
        # Canonical positive zero also avoids sign-bit differences at zero.
        struct.pack_into("<12f", data, offset, *(value or 0.0 for value in values))
    path.write_bytes(data)


if __name__ == "__main__":
    model = make_rack()
    validate(model)
    output = Path(__file__).with_name("rack.stl")
    cq.exporters.export(model, str(output),
                        tolerance=0.05, angularTolerance=0.15)
    normalize_stl(output)
    print(f"Rack: {model.Volume():.1f} mm^3; one valid solid; feature checks passed")
