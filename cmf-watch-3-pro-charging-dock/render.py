"""Render dock.stl into orthographic views, sections, a preview and a usage image.

The STL is stored in its use orientation (z up). usage.png adds simplified
stand-ins for the watch, its straps, the charging head and the cable, built
from prisms and boxes with the estimated dimensions of generate.py; they
show the intended placement, not the product shapes.
"""

from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from generate import (BOOT_LENGTH, BOOT_WIDTH, CABLE_DIAMETER, CASE_DIAMETER,
                      CASE_THICKNESS, FOOT_X, PAD_OFFSET, POCKET_FLOOR_Z, PUCK_ANGLE,
                      PUCK_HEIGHT, PUCK_LENGTH, PUCK_WIDTH, SEAT_Z, STRAP_WIDTH)


DIRECTORY = Path(__file__).resolve().parent
LIGHT = np.array([-0.30, 0.55, 0.78])
LIGHT /= np.linalg.norm(LIGHT)
PART_COLOR = (213, 227, 231)
WATCH_COLOR = (70, 74, 80)
GLASS_COLOR = (28, 30, 34)
STRAP_COLOR = (226, 112, 48)
CABLE_COLOR = (40, 42, 46)
STRAP_THICKNESS = 3.0
STRAP_DROP = 14.0          # hanging part: vertical reach of the sloped segment
STRAP_SLOPE_RUN = 10.0
STRAP_FLAT = 40.0
CABLE_RUN = 40.0           # cable shown beyond the body edge


def read_binary_stl(path):
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("STL is truncated")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError("Expected an unmodified binary STL")
    records = np.frombuffer(
        data, dtype=np.dtype([("normal", "<f4", (3,)),
                              ("vertices", "<f4", (3, 3)),
                              ("attribute", "<u2")]), offset=84,
    )
    return records["vertices"].astype(np.float64), records["normal"].astype(np.float64)


def font(size):
    return ImageFont.load_default(size=size)


def with_color(vertices, normals, color):
    return (vertices, normals, np.array(color, dtype=np.float64))


def prism(ring, extrusion, color):
    """Extrude a convex planar polygon (counter-clockwise seen from +extrusion)."""
    ring = [np.asarray(p, dtype=np.float64) for p in ring]
    extrusion = np.asarray(extrusion, dtype=np.float64)
    top = [p + extrusion for p in ring]
    axis = extrusion / np.linalg.norm(extrusion)
    triangles, normals = [], []
    count = len(ring)
    for i in range(1, count - 1):
        triangles += [[ring[0], ring[i + 1], ring[i]], [top[0], top[i], top[i + 1]]]
        normals += [-axis, axis]
    for i in range(count):
        j = (i + 1) % count
        normal = np.cross(ring[j] - ring[i], axis)
        normal /= np.linalg.norm(normal)
        triangles += [[ring[i], ring[j], top[j]], [ring[i], top[j], top[i]]]
        normals += [normal, normal]
    return with_color(np.array(triangles), np.array(normals), color)


def oriented_box(center, axes, color):
    """Box with the given centre and three orthogonal half-axis vectors."""
    center = np.asarray(center, dtype=np.float64)
    axes = [np.asarray(a, dtype=np.float64) for a in axes]
    triangles, normals = [], []
    for i in range(3):
        a, b, c = axes[i], axes[(i + 1) % 3], axes[(i + 2) % 3]
        for sign in (1.0, -1.0):
            face = center + sign * a
            p = [face - b - c, face + b - c, face + b + c, face - b + c]
            normal = sign * a / np.linalg.norm(a)
            if np.dot(np.cross(p[1] - p[0], p[2] - p[0]), normal) < 0:
                p = p[::-1]
            triangles += [[p[0], p[1], p[2]], [p[0], p[2], p[3]]]
            normals += [normal, normal]
    return with_color(np.array(triangles), np.array(normals), color)


def disc(center, radius, height, color, segments=64):
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ring = [np.array([center[0] + radius * np.cos(a), center[1] + radius * np.sin(a),
                      center[2]]) for a in angles]
    return prism(ring, (0, 0, height), color)


def watch_stand_in():
    """Case disc on the seat with a darker glass disc, and the two strap halves."""
    radius = CASE_DIAMETER / 2
    parts = [disc((0, 0, SEAT_Z), radius, CASE_THICKNESS - 1.0, WATCH_COLOR),
             disc((0, 0, SEAT_Z + CASE_THICKNESS - 1.0), radius - 4.0, 1.0, GLASS_COLOR)]
    half = STRAP_WIDTH / 2
    for sign in (1.0, -1.0):
        # Sloped segment from the lug down toward the desk, then a flat tail.
        start = np.array([0.0, sign * (radius - 2.0), SEAT_Z + 2.0])
        end = np.array([0.0, sign * (radius + STRAP_SLOPE_RUN), STRAP_THICKNESS / 2])
        along = end - start
        length = np.linalg.norm(along)
        direction = along / length
        normal = np.array([0.0, -direction[2], direction[1]])
        parts.append(oriented_box((start + end) / 2,
                                  [direction * length / 2, (half, 0, 0),
                                   normal * STRAP_THICKNESS / 2], STRAP_COLOR))
        tail_start = end[1]
        parts.append(oriented_box((0, tail_start + sign * STRAP_FLAT / 2, STRAP_THICKNESS / 2),
                                  [(half, 0, 0), (0, STRAP_FLAT / 2, 0),
                                   (0, 0, STRAP_THICKNESS / 2)], STRAP_COLOR))
    return parts


def charger_stand_in():
    """Charging head in its pocket and the cable along the channel and beyond."""
    angle = np.radians(PUCK_ANGLE)
    along = np.array([np.cos(angle), np.sin(angle), 0.0])
    across = np.array([-np.sin(angle), np.cos(angle), 0.0])
    centre = np.array([PAD_OFFSET[0], PAD_OFFSET[1], POCKET_FLOOR_Z + PUCK_HEIGHT / 2])
    head = oriented_box(centre, [along * PUCK_LENGTH / 2, across * PUCK_WIDTH / 2,
                                 (0, 0, PUCK_HEIGHT / 2)], CABLE_COLOR)
    boot_centre = (np.array([PAD_OFFSET[0], PAD_OFFSET[1], POCKET_FLOOR_Z + BOOT_WIDTH / 4])
                   + along * (PUCK_LENGTH + BOOT_LENGTH) / 2)
    boot = oriented_box(boot_centre, [along * BOOT_LENGTH / 2, across * BOOT_WIDTH / 2,
                                      (0, 0, BOOT_WIDTH / 4)], CABLE_COLOR)
    run = FOOT_X / 2 + CABLE_RUN
    cable_centre = (np.array([PAD_OFFSET[0], PAD_OFFSET[1], POCKET_FLOOR_Z + CABLE_DIAMETER / 2])
                    + along * run / 2)
    cable = oriented_box(cable_centre, [along * run / 2, across * CABLE_DIAMETER / 2,
                                        (0, 0, CABLE_DIAMETER / 2)], CABLE_COLOR)
    return [head, boot, cable]


def draw_scene(image, parts, region, u, v, depth, label, padding=60):
    """Z-buffered flat shading with a colour per part."""
    x0, y0, width, height = region
    u, v, depth = (np.asarray(axis, dtype=np.float64) for axis in (u, v, depth))
    u, v, depth = u / np.linalg.norm(u), v / np.linalg.norm(v), depth / np.linalg.norm(depth)
    vertices = np.concatenate([part[0] for part in parts])
    normals = np.concatenate([part[1] for part in parts])
    colors = np.concatenate([np.tile(part[2], (len(part[0]), 1)) for part in parts])

    projected = np.stack([vertices @ u, vertices @ v], axis=-1)
    lo, hi = projected.min(axis=(0, 1)), projected.max(axis=(0, 1))
    scale = min((width - 2 * padding) / (hi[0] - lo[0]),
                (height - 2 * padding - 24) / (hi[1] - lo[1]))
    points = (projected - (lo + hi) / 2) * scale
    points[..., 0] += x0 + width / 2
    points[..., 1] = y0 + height / 2 - points[..., 1] + 12
    depths = vertices @ depth

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x0, y0, x0 + width, y0 + height), radius=18, fill="#ffffff")
    z_buffer = np.full((image.height, image.width), -np.inf)
    pixels = np.asarray(image).copy()
    for triangle, triangle_depth, normal, color in zip(points, depths, normals, colors):
        min_x = max(x0, int(np.floor(triangle[:, 0].min())))
        max_x = min(x0 + width - 1, int(np.ceil(triangle[:, 0].max())))
        min_y = max(y0, int(np.floor(triangle[:, 1].min())))
        max_y = min(y0 + height - 1, int(np.ceil(triangle[:, 1].max())))
        if min_x > max_x or min_y > max_y:
            continue
        a, b, c = triangle
        denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denominator) < 1e-8:
            continue
        yy, xx = np.ogrid[min_y:max_y + 1, min_x:max_x + 1]
        x, y = xx + 0.5, yy + 0.5
        wa = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
        wb = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
        wc = 1.0 - wa - wb
        z = wa * triangle_depth[0] + wb * triangle_depth[1] + wc * triangle_depth[2]
        current = z_buffer[min_y:max_y + 1, min_x:max_x + 1]
        visible = (wa >= 0) & (wb >= 0) & (wc >= 0) & (z > current)
        if not np.any(visible):
            continue
        brightness = float(np.clip(0.68 + 0.28 * abs(np.dot(normal, LIGHT)), 0.39, 0.96))
        current[visible] = z[visible]
        pixels[min_y:max_y + 1, min_x:max_x + 1][visible] = (color * brightness).astype(np.uint8)
    image.paste(Image.fromarray(pixels))
    ImageDraw.Draw(image).text((x0 + 22, y0 + 16), label, fill="#25333c", font=font(21))


def section_segments(vertices, axis, value):
    """Line segments where the plane axis = value cuts the mesh, as (u, v) pairs."""
    others = [i for i in range(3) if i != axis]
    segments = []
    for triangle in vertices:
        side = triangle[:, axis] - value
        points = []
        for i in range(3):
            a, b = triangle[i], triangle[(i + 1) % 3]
            sa, sb = side[i], side[(i + 1) % 3]
            if (sa < 0) != (sb < 0):
                t = sa / (sa - sb)
                point = a + t * (b - a)
                points.append((point[others[0]], point[others[1]]))
        if len(points) == 2:
            segments.append(points)
    return segments


def draw_section(image, segments, circles, region, label, padding=70):
    """Draw section segments and reference circles, scaled to fit the region."""
    x0, y0, width, height = region
    flat = np.array([p for segment in segments for p in segment])
    lo, hi = flat.min(axis=0), flat.max(axis=0)
    scale = min((width - 2 * padding) / (hi[0] - lo[0]),
                (height - 2 * padding - 24) / (hi[1] - lo[1]))
    centre = (lo + hi) / 2

    def to_pixel(point):
        return (x0 + width / 2 + (point[0] - centre[0]) * scale,
                y0 + height / 2 + 12 - (point[1] - centre[1]) * scale)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x0, y0, x0 + width, y0 + height), radius=18, fill="#ffffff")
    for a, b in segments:
        draw.line([to_pixel(a), to_pixel(b)], fill="#25333c", width=3)
    for (cx, cy), radius, color in circles:
        px, py = to_pixel((cx, cy))
        r = radius * scale
        draw.ellipse((px - r, py - r, px + r, py + r), outline=color, width=3)
    draw.text((x0 + 22, y0 + 16), label, fill="#25333c", font=font(21))


def render_sections(vertices):
    """Section across the strap axis through the head, and along the channel."""
    if PUCK_ANGLE != 0.0:
        raise ValueError("The section views assume the cable runs along +x")
    cable = ((FOOT_X / 2 - 4.0, POCKET_FLOOR_Z + CABLE_DIAMETER / 2), CABLE_DIAMETER / 2,
             "#e27030")
    across = section_segments(vertices, 0, PAD_OFFSET[0])
    along = section_segments(vertices, 1, PAD_OFFSET[1])

    canvas = Image.new("RGB", (1600, 760), "#e9eef0")
    draw_section(canvas, across, [], (24, 24, 660, 712),
                 "ACROSS  ·  THROUGH THE HEAD, 6 O'CLOCK LEFT")
    draw_section(canvas, along, [cable], (708, 24, 868, 712),
                 "ALONG THE CHANNEL  ·  POCKET, BOOT AND EXIT")
    canvas.save(DIRECTORY / "sections.png", optimize=True)


def camera(viewer):
    """Screen axes (right, up, toward viewer) for a viewer at the given direction."""
    toward = np.asarray(viewer, dtype=np.float64)
    toward /= np.linalg.norm(toward)
    right = np.array([-toward[1], toward[0], 0.0])
    right /= np.linalg.norm(right)
    return right, np.cross(toward, right), toward


def main():
    vertices, normals = read_binary_stl(DIRECTORY / "dock.stl")
    dock = [with_color(vertices, normals, PART_COLOR)]
    flat = vertices.reshape(-1, 3)
    size = flat.max(axis=0) - flat.min(axis=0)
    coupon_vertices, coupon_normals = read_binary_stl(DIRECTORY / "coupon.stl")
    coupon = [with_color(coupon_vertices, coupon_normals, PART_COLOR)]

    views = Image.new("RGB", (1600, 1010), "#e9eef0")
    draw_scene(views, dock, (24, 24, 1000, 600), (1, 0, 0), (0, 1, 0), (0, 0, 1),
               f"TOP  ·  {size[0]:.0f} x {size[1]:.0f} mm")
    draw_scene(views, dock, (24, 648, 1000, 338), (1, 0, 0), (0, 0, 1), (0, -1, 0),
               f"FRONT  ·  {size[0]:.0f} x {size[2]:.0f} mm")
    draw_scene(views, dock, (1048, 24, 528, 470), (0, 1, 0), (0, 0, 1), (1, 0, 0),
               f"SIDE  ·  {size[1]:.0f} x {size[2]:.0f} mm")
    draw_scene(views, coupon, (1048, 518, 528, 468), *camera((0.45, -0.60, 0.66)),
               "COUPON  ·  POCKET AND CHANNEL")
    views.save(DIRECTORY / "views.png", optimize=True)
    render_sections(vertices)

    oblique = camera((0.45, -0.60, 0.66))
    preview = Image.new("RGB", (1600, 950), "#e9eef0")
    draw_scene(preview, dock, (25, 25, 1550, 900), *oblique,
               "CMF WATCH 3 PRO  ·  CHARGING DOCK", padding=90)
    preview.save(DIRECTORY / "preview.png", optimize=True)

    scene = dock + charger_stand_in() + watch_stand_in()
    usage = Image.new("RGB", (1600, 1100), "#e9eef0")
    draw_scene(usage, scene, (24, 24, 1552, 640), *oblique,
               "IN USE  ·  WATCH FACE UP, STRAPS OVER THE ENDS")
    draw_scene(usage, scene, (24, 688, 764, 388), (1, 0, 0), (0, 0, 1), (0, -1, 0),
               "IN USE  ·  FRONT")
    draw_scene(usage, scene, (812, 688, 764, 388), (0, 1, 0), (0, 0, 1), (1, 0, 0),
               "IN USE  ·  SIDE")
    usage.save(DIRECTORY / "usage.png", optimize=True)


if __name__ == "__main__":
    main()
