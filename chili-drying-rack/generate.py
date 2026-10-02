"""Stackable one-piece drying basket, mm. SPDX-License-Identifier: CC-BY-SA-4.0"""

from pathlib import Path
import struct

import cadquery as cq


LENGTH = 220.0
WIDTH = 140.0
PITCH = 6.0
RIB = 2.0
FLOOR_TOP = 5.0
UNDERPASS = 2.0
RIM_TOP = 18.0
STACK_PITCH = 75.0
POST_WIDTH = 14.0
PEG_WIDTH = 6.0
PEG_HEIGHT = 4.5
SOCKET_WIDTH = 6.8
SOCKET_DEPTH = 5.0
POSTS = [(x, y) for x in (-103.0, 103.0) for y in (-63.0, 63.0)]


def box(x, y, z, length, width, height):
    return (cq.Workplane("XY", origin=(x, y, z))
            .box(length, width, height, centered=(True, True, False)).val())


def make_rack():
    # Long ribs begin on the build plate. Cross ribs begin at z=2 and bridge
    # only 4 mm, leaving front-to-back air channels beneath the lowest basket.
    parts = [box(x, 0, 0, RIB, WIDTH, FLOOR_TOP) for x in range(-102, 103, 6)]
    parts += [box(0, y, UNDERPASS, LENGTH, RIB, FLOOR_TOP - UNDERPASS)
              for y in range(-60, 61, 6)]
    parts += [box(x, 0, 0, 3, WIDTH, RIM_TOP) for x in (-108.5, 108.5)]
    parts += [box(0, y, UNDERPASS, LENGTH, 3, RIM_TOP - UNDERPASS)
              for y in (-68.5, 68.5)]
    for x, y in POSTS:
        post = (cq.Workplane("XY", origin=(x, y, 0))
                .box(POST_WIDTH, POST_WIDTH, STACK_PITCH,
                     centered=(True, True, False)).edges("|Z").fillet(1.0).val())
        peg = (cq.Workplane("XY", origin=(x, y, STACK_PITCH))
               .box(PEG_WIDTH, PEG_WIDTH, PEG_HEIGHT, centered=(True, True, False))
               .faces(">Z").edges().chamfer(0.6).val())
        parts.extend((post, peg))
    shape = parts[0].fuse(*parts[1:]).clean()
    sockets = []
    for x, y in POSTS:
        sockets.append(box(x, y, -1, SOCKET_WIDTH, SOCKET_WIDTH, SOCKET_DEPTH + 1))
        # Lead-in widens the underside mouth without changing the working fit.
        sockets.append((cq.Workplane("XY", origin=(x, y, 0))
                        .rect(SOCKET_WIDTH + 0.8, SOCKET_WIDTH + 0.8)
                        .workplane(offset=0.4).rect(SOCKET_WIDTH, SOCKET_WIDTH)
                        .loft().val()))
    return shape.cut(*sockets).clean()


def validate(shape):
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("Basket must be one valid solid")
    bounds = shape.BoundingBox()
    for actual, expected in zip((bounds.xlen, bounds.ylen, bounds.zlen),
                                (LENGTH, WIDTH, STACK_PITCH + PEG_HEIGHT)):
        if abs(actual - expected) > 1e-5:
            raise ValueError("Unexpected outside dimensions")
    # Verify representative air channels, mesh openings and load-bearing ribs.
    for x in (-87, -3, 87):
        for y in (-69, -30, 0, 30, 69):
            if shape.isInside(cq.Vector(x, y, 1)):
                raise ValueError("Underfloor air channel is obstructed")
        if shape.isInside(cq.Vector(x, 3, 4)):
            raise ValueError("Mesh opening is obstructed")
        if not shape.isInside(cq.Vector(x, 0, 4)):
            raise ValueError("Cross rib is missing")
    for x, y in POSTS:
        if shape.isInside(cq.Vector(x, y, 2)):
            raise ValueError("Stacking socket is obstructed")
        if not shape.isInside(cq.Vector(x, y, 77)):
            raise ValueError("Stacking peg is missing")
    upper = shape.translate((0, 0, STACK_PITCH))
    if shape.intersect(upper).Volume() > 1e-6:
        raise ValueError("Stacked baskets intersect")
    if SOCKET_DEPTH <= PEG_HEIGHT or SOCKET_WIDTH <= PEG_WIDTH:
        raise ValueError("Stacking clearance is missing")


def normalize_stl(path):
    """Remove sub-micrometre floating-point noise from the OCC export."""
    data = bytearray(path.read_bytes())
    count = struct.unpack_from("<I", data, 80)[0]
    for index in range(count):
        offset = 84 + index * 50
        values = [round(value, 6) for value in struct.unpack_from("<12f", data, offset)]
        struct.pack_into("<12f", data, offset, *(value or 0.0 for value in values))
    path.write_bytes(data)


if __name__ == "__main__":
    model = make_rack()
    validate(model)
    output = Path(__file__).with_name("rack.stl")
    cq.exporters.export(model, str(output), tolerance=0.08, angularTolerance=0.2)
    normalize_stl(output)
    print(f"Basket: {model.Volume():.1f} mm^3; valid solid; stack/feature checks passed")
