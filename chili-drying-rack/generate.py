"""Stackable drawer frame, drying basket and printed date wheels, mm. SPDX-License-Identifier: CC-BY-SA-4.0"""

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
    # Open front; two low rails carry a separately printed sliding basket.
    parts = [box(x, 0, 0, 18, WIDTH, 5) for x in (-101, 101)]
    parts += [box(x, 0, 0, 3, WIDTH, RIM_TOP) for x in (-108.5, 108.5)]
    parts += [box(0, 68.5, 0, LENGTH, 3, RIM_TOP)]
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
    if shape.isInside(cq.Vector(0, -68, 4)):
        raise ValueError("Drawer entrance must remain open")
    for x in (-94, 94):
        if not shape.isInside(cq.Vector(x, 0, 2)):
            raise ValueError("Drawer support rail is missing")
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


DRAWER_Y = 2.0
DRAWER_Z = 5.0
# Month and day axes on the handle, in basket-local coordinates.
DIALS = ((-30.0, -98.0, 14.0, 12), (18.0, -98.0, 28.0, 31))


def cylinder(x, y, z, radius, height):
    return cq.Workplane("XY", origin=(x, y, z)).circle(radius).extrude(height).val()


def make_basket():
    parts = [box(x, 0, 0, 2, 130, 3) for x in range(-90, 91, 6)]
    parts += [box(0, y, 0, 190, 2, 3) for y in range(-60, 61, 6)]
    parts += [box(x, 0, 0, 3, 130, 12) for x in (-93.5, 93.5)]
    parts += [box(0, y, 0, 190, 3, 12) for y in (-63.5, 63.5)]
    # Eight open V saddles, repeated at two short support stations. Valleys
    # stay above the mesh, rather than forming long water-holding troughs.
    profile = [(-88, 3), (-88, 9)]
    for i in range(8):
        profile += [(-77 + 22*i, 4.5), (-66 + 22*i, 9)]
    profile += [(88, 3)]
    for y in (-30, 30):
        parts.append(cq.Workplane("XZ", origin=(0, y + 1.2, 0))
                     .polyline(profile).close().extrude(2.4).val())
    parts.append(box(0, -96, 0, 100, 68, 3))
    for x, y, radius, count in DIALS:
        parts.append(cylinder(x, y, 3, 4, 3.8))
        parts.append(cylinder(x, y, 6.8, 2.5, 2))
        # 45-degree head underside, no large unsupported overhang.
        parts.append(cq.Solid.makeCone(2.5, 4, 1.5, cq.Vector(x, y, 8.8)))
        # Arrow points toward the top of each wheel, outside its sweep.
        parts.append(cq.Workplane("XY", origin=(x, y + radius + 0.8, 3))
                     .polyline([(0, 0), (-1.5, 2), (1.5, 2)])
                     .close().extrude(0.8).val())
    return parts[0].fuse(*parts[1:]).clean()


# Seven-segment numerals avoid host font dependencies in the CAD outputs.
SEGMENTS = {'0':'abcdef', '1':'bc', '2':'abdeg', '3':'abcdg',
            '4':'bcfg', '5':'acdfg', '6':'acdefg', '7':'abc',
            '8':'abcdefg', '9':'abcdfg'}
SEGMENT_BOXES = {'a':(0,1.4,1.6,.45), 'b':(.8,.7,.45,1.4),
                 'c':(.8,-.7,.45,1.4), 'd':(0,-1.4,1.6,.45),
                 'e':(-.8,-.7,.45,1.4), 'f':(-.8,.7,.45,1.4),
                 'g':(0,0,1.6,.45)}


def make_dial(radius, count):
    parts = [cylinder(0, 0, 0, radius, 2.4).cut(cylinder(0, 0, -1, 4.3, 5))]
    for number in range(1, count + 1):
        digits = str(number)
        glyphs = []
        for index, digit in enumerate(digits):
            for segment in SEGMENTS[digit]:
                x, y, w, h = SEGMENT_BOXES[segment]
                glyphs.append(box(x + (index-(len(digits)-1)/2)*2.4,
                                  y + radius - 3.2, 2.4, w, h, .6))
        label = glyphs[0].fuse(*glyphs[1:]).rotate((0,0,0), (0,0,1),
                                                -(number-1)*360/count)
        parts.append(label)
    return parts[0].fuse(*parts[1:]).clean()


def make_clip():
    # Flat C clip: 5.4 mm bore around a 5 mm neck; mouth 4.6 mm.
    ring = cylinder(0, 0, 0, 6, 1.6).cut(cylinder(0, 0, -1, 2.7, 4))
    return ring.cut(box(0, 5, -1, 4.6, 10, 4)).clean()


def validate_drawers(rack, basket, month, day, clip):
    for name, shape in (("basket", basket), ("month", month),
                        ("day", day), ("clip", clip)):
        if not shape.isValid() or len(shape.Solids()) != 1:
            raise ValueError(f"{name}: expected one valid solid")
    for shape, expected in ((basket, (190,195,12)), (month, (28,28,3)),
                            (day, (56,56,3))):
        bounds = shape.BoundingBox()
        if any(abs(actual-target) > 1e-5 for actual, target in
               zip((bounds.xlen,bounds.ylen,bounds.zlen), expected)):
            raise ValueError("Unexpected basket/date-wheel dimensions")
    # Continuous withdrawal envelope including dial platform and all fittings.
    # Exclude touching rail contact at z=5 using a tiny numerical tolerance.
    swept = box(0, (67 - 314)/2, DRAWER_Z + 1e-5, 190, 67+314, 12)
    if rack.intersect(swept).Volume() > 1e-6:
        raise ValueError("Drying basket travel is obstructed")
    if basket.isInside(cq.Vector(3, 3, 1)):
        raise ValueError("Mesh opening obstructed")
    for i in range(8):
        if not basket.isInside(cq.Vector(-77 + i*22, 30, 4)):
            raise ValueError("V saddle valley missing")
    for (x, y, radius, _), wheel in zip(DIALS, (month, day)):
        # Rotational envelope proves clearance for every date, not just one.
        rotation = cylinder(x, y, 3.4, radius, 3).cut(cylinder(x, y, 3, 4.3, 5))
        if basket.intersect(rotation).Volume() > 1e-6:
            raise ValueError("Date wheel cannot rotate freely")
        keeper = clip.translate((x, y, 6.9))
        if basket.intersect(keeper).Volume() > 1e-6:
            raise ValueError("Installed retaining clip interference")
        if wheel.translate((x,y,3.4)).intersect(keeper).Volume() > 1e-6:
            raise ValueError("Wheel and retaining clip intersect")
    mounted = basket.translate((0, DRAWER_Y, BASE_HEIGHT + DRAWER_Z))
    if mounted.intersect(make_base()).Volume() > 1e-6:
        raise ValueError("Drying drawer intersects base")


if __name__ == "__main__":
    model = make_rack()
    validate(model)
    base, tray = make_base(), make_tray()
    validate_accessories(model, base, tray)
    basket = make_basket()
    month, day, clip = make_dial(14, 12), make_dial(28, 31), make_clip()
    validate_drawers(model, basket, month, day, clip)
    for name, shape in (("rack", model), ("base", base), ("drip-tray", tray),
                        ("basket", basket), ("month-dial", month),
                        ("day-dial", day), ("dial-clip", clip)):
        output = Path(__file__).with_name(f"{name}.stl")
        cq.exporters.export(shape, str(output), tolerance=0.08, angularTolerance=0.2)
        normalize_stl(output)
        print(f"{name}: {shape.Volume():.1f} mm^3; valid single solid")
    print("Stack, drawer travel, drip coverage and wheel rotation checks passed")
