"""Render the generated binary STLs into orthographic views and a preview.

The STLs are stored in print orientation. They are turned back into the use
orientation of generate.py (x along the shelf edge, y toward the user, z up,
shelf top at z=0, panel back face at y=0) and shown on a shelf board.
"""

from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont


DIRECTORY = Path(__file__).resolve().parent
LIGHT = np.array([-0.30, 0.55, 0.78])
LIGHT /= np.linalg.norm(LIGHT)
PART_COLOR = (213, 227, 231)
SHELF_COLOR = (222, 196, 160)

# Use-orientation position of the print bed corner: the top of the clamp is
# at z=TOP_LEG_THICKNESS and the rear end of its top leg at y=-TOP_LEG_DEPTH.
TOP_LEG_THICKNESS = 5.0
TOP_LEG_DEPTH = 45.0
SHELF_THICKNESS = 20.0
SHELF_DEPTH = 120.0
MODULE_GAP = 40.0


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


def to_use_orientation(vertices, normals):
    """Inverse of generate.to_print_orientation, up to the x offset."""
    width = vertices[..., 2].max()

    def turn(points):
        return np.stack([points[..., 2], points[..., 1], -points[..., 0]], axis=-1)

    use = turn(vertices)
    use += np.array([-width / 2, -TOP_LEG_DEPTH, TOP_LEG_THICKNESS])
    return use, turn(normals), width


def box_mesh(x0, x1, y0, y1, z0, z1):
    corners = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
    quads = [((0, 1, 3, 2), (-1, 0, 0)), ((4, 6, 7, 5), (1, 0, 0)),
             ((0, 4, 5, 1), (0, -1, 0)), ((2, 3, 7, 6), (0, 1, 0)),
             ((0, 2, 6, 4), (0, 0, -1)), ((1, 5, 7, 3), (0, 0, 1))]
    triangles, normals = [], []
    for (a, b, c, d), normal in quads:
        triangles += [corners[[a, b, c]], corners[[a, c, d]]]
        normals += [normal, normal]
    return np.array(triangles, dtype=np.float64), np.array(normals, dtype=np.float64)


def font(size):
    return ImageFont.load_default(size=size)


def draw_view(image, meshes, region, u, v, depth, label, padding=42):
    """Draw (vertices, normals, color) meshes in an orthographic view."""
    x0, y0, width, height = region
    u = np.asarray(u, dtype=np.float64) / np.linalg.norm(u)
    v = np.asarray(v, dtype=np.float64) / np.linalg.norm(v)
    depth = np.asarray(depth, dtype=np.float64) / np.linalg.norm(depth)

    vertices = np.concatenate([mesh[0] for mesh in meshes])
    normals = np.concatenate([mesh[1] for mesh in meshes])
    colors = np.concatenate([np.tile(mesh[2], (len(mesh[0]), 1)) for mesh in meshes])

    projected = np.stack([vertices @ u, vertices @ v], axis=-1)
    lo = projected.min(axis=(0, 1))
    hi = projected.max(axis=(0, 1))
    scale = min((width - 2 * padding) / (hi[0] - lo[0]),
                (height - 2 * padding - 24) / (hi[1] - lo[1]))
    center = (lo + hi) / 2
    points = (projected - center) * scale
    points[..., 0] += x0 + width / 2
    points[..., 1] = y0 + height / 2 - points[..., 1] + 12
    depths = vertices @ depth

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x0, y0, x0 + width, y0 + height),
                           radius=18, fill="#ffffff")
    z_buffer = np.full((image.height, image.width), -np.inf)
    pixels = np.asarray(image).copy()
    for i in range(len(vertices)):
        triangle = points[i]
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
        z = wa * depths[i, 0] + wb * depths[i, 1] + wc * depths[i, 2]
        current = z_buffer[min_y:max_y + 1, min_x:max_x + 1]
        visible = (wa >= 0) & (wb >= 0) & (wc >= 0) & (z > current)
        if not np.any(visible):
            continue
        brightness = float(np.clip(0.68 + 0.28 * np.dot(normals[i], LIGHT), 0.39, 0.96))
        current[visible] = z[visible]
        pixels[min_y:max_y + 1, min_x:max_x + 1][visible] = (colors[i] * brightness).astype(np.uint8)
    image.paste(Image.fromarray(pixels))
    draw = ImageDraw.Draw(image)
    draw.text((x0 + 22, y0 + 16), label, fill="#25333c", font=font(21))


def part_mesh(vertices, normals, x_offset=0.0):
    return (vertices + np.array([x_offset, 0.0, 0.0]), normals, np.array(PART_COLOR))


def shelf_mesh(x0, x1):
    triangles, normals = box_mesh(x0, x1, -SHELF_DEPTH, 0.0, -SHELF_THICKNESS, 0.0)
    return triangles, normals, np.array(SHELF_COLOR)


def size_label(vertices, axes):
    sizes = vertices.max(axis=(0, 1)) - vertices.min(axis=(0, 1))
    return " x ".join(f"{sizes[a]:.0f}" for a in axes) + " mm"


def oblique(toward_viewer):
    """Screen right, screen up and the viewer direction for an oblique view."""
    toward_viewer = np.asarray(toward_viewer, dtype=np.float64)
    toward_viewer /= np.linalg.norm(toward_viewer)
    right = np.cross([0.0, 0.0, 1.0], toward_viewer)
    return right, np.cross(toward_viewer, right), toward_viewer


def render_views(headset, accessories, printed):
    canvas = Image.new("RGB", (1600, 1500), "#e9eef0")
    for column, (name, (vertices, normals, _)) in enumerate(
            (("HEADSET", headset), ("ACCESSORIES", accessories))):
        x = 24 + column * 788
        mesh = part_mesh(vertices, normals)
        draw_view(canvas, [mesh], (x, 24, 764, 700), (-1, 0, 0), (0, 0, 1), (0, 1, 0),
                  f"{name} FRONT  ·  {size_label(vertices, (0, 2))}")
        draw_view(canvas, [mesh], (x, 748, 370, 728), (0, 1, 0), (0, 0, 1), (1, 0, 0),
                  f"SIDE  ·  {size_label(vertices, (1, 2))}", padding=36)
        draw_view(canvas, [printed[column]], (x + 394, 748, 370, 728),
                  *oblique((0.55, -0.70, 0.45)),
                  f"PRINT  ·  {size_label(printed[column][0], (0, 1, 2))}", padding=36)
    canvas.save(DIRECTORY / "views.png", optimize=True)


def render_preview(headset, accessories):
    left_width, right_width = headset[2], accessories[2]
    left_center = -(right_width + MODULE_GAP) / 2
    right_center = (left_width + MODULE_GAP) / 2
    meshes = [
        part_mesh(headset[0], headset[1], left_center),
        part_mesh(accessories[0], accessories[1], right_center),
        shelf_mesh(left_center - left_width / 2 - 40, right_center + right_width / 2 + 40),
    ]
    canvas = Image.new("RGB", (1600, 1000), "#e9eef0")
    draw_view(canvas, meshes, (25, 25, 1550, 950), *oblique((-0.45, 0.80, 0.50)),
              "PICO 4  ·  SHELF-EDGE HANGERS", padding=80)
    canvas.save(DIRECTORY / "preview.png", optimize=True)


if __name__ == "__main__":
    loaded = {name: read_binary_stl(DIRECTORY / name)
              for name in ("headset.stl", "accessories.stl")}
    printed = [(v, n, np.array(PART_COLOR)) for v, n in loaded.values()]
    headset = to_use_orientation(*loaded["headset.stl"])
    accessories = to_use_orientation(*loaded["accessories.stl"])
    render_views(headset, accessories, printed)
    render_preview(headset, accessories)
