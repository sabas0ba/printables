"""Render the generated binary STL into three orthographic views and a preview."""

from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont


DIRECTORY = Path(__file__).resolve().parent
STL = DIRECTORY / "holder.stl"
LIGHT = np.array([0.25, -0.35, 0.90])
LIGHT /= np.linalg.norm(LIGHT)


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


def draw_view(image, vertices, normals, region, u, v, depth, label, padding=42):
    x0, y0, width, height = region
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    depth = np.asarray(depth, dtype=np.float64)
    u /= np.linalg.norm(u)
    v /= np.linalg.norm(v)
    depth /= np.linalg.norm(depth)

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
        normal = normals[i]
        brightness = float(np.clip(0.68 + 0.28 * np.dot(normal, LIGHT), 0.39, 0.96))
        color = (int(213 * brightness), int(227 * brightness),
                 int(231 * brightness))
        current[visible] = z[visible]
        pixels[min_y:max_y + 1, min_x:max_x + 1][visible] = color
    image.paste(Image.fromarray(pixels))
    draw = ImageDraw.Draw(image)
    draw.text((x0 + 22, y0 + 16), label, fill="#25333c", font=font(21))


def render_views(vertices, normals):
    canvas = Image.new("RGB", (1600, 1010), "#e9eef0")
    draw_view(canvas, vertices, normals, (24, 24, 1120, 456),
              (1, 0, 0), (0, 1, 0), (0, 0, 1), "TOP  ·  281 x 68 mm")
    draw_view(canvas, vertices, normals, (24, 504, 1120, 480),
              (1, 0, 0), (0, 0, 1), (0, -1, 0), "SIDE  ·  281 x 45 mm")
    draw_view(canvas, vertices, normals, (1168, 24, 408, 960),
              (0, 1, 0), (0, 0, 1), (1, 0, 0), "END  ·  68 x 45 mm")
    canvas.save(DIRECTORY / "views.png", optimize=True)


def render_preview(vertices, normals):
    canvas = Image.new("RGB", (1600, 950), "#e9eef0")
    draw_view(canvas, vertices, normals, (25, 25, 1550, 900),
              (0.78, -0.62, 0), (-0.37, -0.46, 0.81),
              (0.37, 0.47, 0.80), "MI VACUUM CLEANER MINI  ·  HOLDER", padding=90)
    canvas.save(DIRECTORY / "preview.png", optimize=True)


if __name__ == "__main__":
    mesh, face_normals = read_binary_stl(STL)
    render_views(mesh, face_normals)
    render_preview(mesh, face_normals)
