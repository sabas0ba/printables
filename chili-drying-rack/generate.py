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
BASE_HEIGHT = 38.0
TRAY_Z = 3.0
TRAY_Y = -2.0


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


def make_base():
    # The 45-degree underside grows inward only above the drawer, so the
    # basket support needs no bridge across the full drawer width.
    right = (cq.Workplane("XZ", origin=(0, 82, 0))
             .polyline([(116, 0), (122, 0), (122, 38), (96, 38),
                        (96, 36), (116, 16)]).close().extrude(164).val())
    parts = [right, right.mirror("YZ"), box(0, 79, 0, 244, 6, 8)]
    parts += [box(x, 0, 0, 6, 164, TRAY_Z) for x in (-113, 113)]
    for x, y in POSTS:
        parts.append((cq.Workplane("XY", origin=(x, y, BASE_HEIGHT))
                      .box(PEG_WIDTH, PEG_WIDTH, PEG_HEIGHT,
                           centered=(True, True, False))
                      .faces(">Z").edges().chamfer(0.6).val())
        )
    return parts[0].fuse(*parts[1:]).clean()


def make_tray():
    outer = (cq.Workplane("XY").box(228, 156, 12, centered=(True, True, False))
             .edges("|Z").fillet(2.0).val())
    cavity = (cq.Workplane("XY", origin=(0, 0, 2.4))
              .box(223.2, 151.2, 12, centered=(True, True, False))
              .edges("|Z").fillet(1.0).val())
    grip = (cq.Workplane("XY", origin=(0, -83, 0))
            .box(40, 14, 3, centered=(True, True, False))
            .edges("|Z").fillet(2.0).val())
    return outer.cut(cavity).fuse(grip).clean()


def validate_accessories(rack, base, tray):
    for name, shape, expected in (
        ("base", base, (244, 164, 42.5)),
        ("tray", tray, (228, 168, 12)),
    ):
        if not shape.isValid() or len(shape.Solids()) != 1:
            raise ValueError(f"{name} must be one valid solid")
        bounds = shape.BoundingBox()
        for actual, target in zip((bounds.xlen, bounds.ylen, bounds.zlen), expected):
            if abs(actual - target) > 1e-5:
                raise ValueError(f"{name}: unexpected dimensions")
    mounted_rack = rack.translate((0, 0, BASE_HEIGHT))
    mounted_tray = tray.translate((0, TRAY_Y, TRAY_Z))
    if base.intersect(mounted_rack).Volume() > 1e-6:
        raise ValueError("Basket does not fit base")
    # A continuous swept bounding envelope verifies the whole withdrawal path,
    # including the handle, rather than only a few sample drawer positions.
    bounds = mounted_tray.BoundingBox()
    travel = 180.0
    swept = box((bounds.xmin + bounds.xmax) / 2,
                (bounds.ymin + bounds.ymax - travel) / 2, bounds.zmin,
                bounds.xlen, bounds.ylen + travel, bounds.zlen)
    for obstacle in (base, mounted_rack):
        if obstacle.intersect(swept).Volume() > 1e-6:
            raise ValueError("Drawer withdrawal path is obstructed")
    # The water-holding opening covers the basket's entire vertical footprint.
    if 223.2 / 2 < LENGTH / 2 or 151.2 / 2 - abs(TRAY_Y) < WIDTH / 2:
        raise ValueError("Drip tray does not cover basket footprint")
    if not tray.isInside(cq.Vector(0, 0, 1)) or tray.isInside(cq.Vector(0, 0, 4)):
        raise ValueError("Tray floor/cavity is invalid")


if __name__ == "__main__":
    model = make_rack()
    validate(model)
    base, tray = make_base(), make_tray()
    validate_accessories(model, base, tray)
    for name, shape in (("rack", model), ("base", base), ("drip-tray", tray)):
        output = Path(__file__).with_name(f"{name}.stl")
        cq.exporters.export(shape, str(output), tolerance=0.08, angularTolerance=0.2)
        normalize_stl(output)
        print(f"{name}: {shape.Volume():.1f} mm^3; valid single solid")
    print("Stack, base fit, drip coverage and continuous drawer travel checks passed")
