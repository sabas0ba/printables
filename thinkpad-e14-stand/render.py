"""Render the stand STL into views, a preview, and both uses with a notebook proxy."""

import importlib.util
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from generate import (LENGTH, NOTEBOOK_DEPTH, NOTEBOOK_MAX_THICKNESS,
                      NOTEBOOK_WIDTH, BASE_HALF_THICKNESS, frame_point)


DIRECTORY = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "stl_renderer", DIRECTORY.parent / "mi-vacuum-cleaner-mini" / "render.py"
)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

STAND_COLOR = (213, 227, 231)
NOTEBOOK_COLOR = (92, 96, 104)
DISPLAY_THICKNESS = 6.0
HINGE_ANGLE = 170.0     # illustration only; the display tilt follows the hinge


def reclined_prism(section):
    """Extrude a polygon in the reclined (u, w) frame over the notebook width."""
    x0 = (LENGTH - NOTEBOOK_WIDTH) / 2
    ring = [frame_point(u, w) for u, w in section]
    near = [np.array([x0, y, z]) for y, z in ring]
    far = [np.array([x0 + NOTEBOOK_WIDTH, y, z]) for y, z in ring]
    triangles = []
    count = len(ring)
    for i in range(1, count - 1):
        triangles += [(near[0], near[i + 1], near[i]), (far[0], far[i], far[i + 1])]
    for i in range(count):
        j = (i + 1) % count
        triangles += [(near[i], near[j], far[j]), (near[i], far[j], far[i])]
    vertices = np.array(triangles)
    normals = np.cross(vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    return vertices, normals


def rectangle(u0, u1, w0, w1):
    return [(u0, w0), (u1, w0), (u1, w1), (u0, w1)]


def closed_notebook():
    return [reclined_prism(rectangle(0.0, NOTEBOOK_MAX_THICKNESS, 0.0, NOTEBOOK_DEPTH))]


def open_notebook():
    """Base half in the slot; the display folds toward the user by 180 - hinge."""
    fold = math.radians(180.0 - HINGE_ANGLE)
    along = np.array([math.sin(fold), math.cos(fold)])
    across = np.array([math.cos(fold), -math.sin(fold)])
    hinge = np.array([0.0, NOTEBOOK_DEPTH])
    display = [hinge, hinge + across * DISPLAY_THICKNESS,
               hinge + across * DISPLAY_THICKNESS + along * NOTEBOOK_DEPTH,
               hinge + along * NOTEBOOK_DEPTH]
    return [reclined_prism(rectangle(0.0, BASE_HALF_THICKNESS, 0.0, NOTEBOOK_DEPTH)),
            reclined_prism([tuple(point) for point in display])]


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
        brightness = float(np.clip(0.68 + 0.28 * abs(np.dot(normal, renderer.LIGHT)),
                                   0.39, 0.96))
        current[visible] = z[visible]
        pixels[min_y:max_y + 1, min_x:max_x + 1][visible] = (color * brightness).astype(np.uint8)
    image.paste(Image.fromarray(pixels))
    ImageDraw.Draw(image).text((x0 + 22, y0 + 16), label, fill="#25333c",
                               font=renderer.font(21))


def front_camera(viewer):
    """Screen axes (right, up, toward viewer) for a viewer on the user side."""
    toward = np.asarray(viewer, dtype=np.float64)
    toward /= np.linalg.norm(toward)
    right = np.array([-toward[1], toward[0], 0.0])
    right /= np.linalg.norm(right)
    return right, np.cross(toward, right), toward


def with_color(meshes, color):
    return [(vertices, normals, np.array(color, dtype=np.float64))
            for vertices, normals in meshes]


def main():
    vertices, normals = renderer.read_binary_stl(DIRECTORY / "stand.stl")
    stand = with_color([(vertices, normals)], STAND_COLOR)
    box = vertices.reshape(-1, 3)
    size = box.max(axis=0) - box.min(axis=0)

    views = Image.new("RGB", (1600, 1010), "#e9eef0")
    draw_scene(views, stand, (24, 24, 1000, 600), (1, 0, 0), (0, 1, 0), (0, 0, 1),
               f"TOP  ·  {size[0]:.0f} x {size[1]:.0f} mm")
    draw_scene(views, stand, (24, 648, 1000, 338), (1, 0, 0), (0, 0, 1), (0, -1, 0),
               f"FRONT  ·  {size[0]:.0f} x {size[2]:.0f} mm")
    draw_scene(views, stand, (1048, 24, 528, 962), (0, 1, 0), (0, 0, 1), (1, 0, 0),
               f"SIDE  ·  {size[1]:.0f} x {size[2]:.0f} mm")
    views.save(DIRECTORY / "views.png", optimize=True)

    camera = front_camera((0.45, -0.60, 0.66))
    preview = Image.new("RGB", (1600, 950), "#e9eef0")
    draw_scene(preview, stand, (25, 25, 1550, 900), *camera,
               "THINKPAD E14  ·  STAND", padding=90)
    preview.save(DIRECTORY / "preview.png", optimize=True)

    side = ((0, 1, 0), (0, 0, 1), (1, 0, 0))
    usage = Image.new("RGB", (1600, 1100), "#e9eef0")
    for column, (label, notebook) in enumerate((("CLOSED  ·  STORAGE", closed_notebook()),
                                                ("OPEN  ·  DISPLAY ONLY", open_notebook()))):
        scene = stand + with_color(notebook, NOTEBOOK_COLOR)
        draw_scene(usage, scene, (24 + column * 788, 24, 764, 520), *camera, label)
        draw_scene(usage, scene, (24 + column * 788, 568, 764, 508), *side,
                   label + "  ·  SIDE")
    usage.save(DIRECTORY / "usage.png", optimize=True)


if __name__ == "__main__":
    main()
