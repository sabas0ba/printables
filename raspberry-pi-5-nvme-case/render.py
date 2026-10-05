"""Render the case parts and the reference assembly from the exported STL files."""

import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import generate
from generate import LID, WALL_TOP


DIRECTORY = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "stl_renderer", DIRECTORY.parent / "mi-vacuum-cleaner-mini" / "render.py"
)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

CASE = (213, 227, 231)
LID_COLOR = (226, 221, 205)
BOARD = (122, 168, 120)
SECTION_Y = 27.0
LIGHT = np.array([0.25, -0.35, 0.90]) / np.linalg.norm([0.25, -0.35, 0.90])


def mesh(name, color, offset=(0.0, 0.0, 0.0)):
    vertices, normals = renderer.read_binary_stl(DIRECTORY / name)
    colors = np.tile(np.array(color, dtype=np.float64), (len(vertices), 1))
    return vertices + np.array(offset), normals, colors


def lid_in_place(color=LID_COLOR, lift=0.0):
    """The lid STL is upside down for printing; flip it back over the tray."""
    vertices, normals, colors = mesh("lid.stl", color)
    flip = np.array([1.0, -1.0, -1.0])
    vertices = vertices * flip + np.array([0.0, 0.0, WALL_TOP + LID + lift])
    return vertices, normals * flip, colors


def combine(parts):
    return tuple(np.concatenate([part[i] for part in parts]) for i in range(3))


def draw_view(image, parts, region, u, v, depth, label, padding=36):
    """Z-buffered flat-shaded projection with one color per triangle."""
    vertices, normals, colors = combine(parts)
    x0, y0, width, height = region
    u, v, depth = (np.asarray(a, dtype=np.float64) / np.linalg.norm(a) for a in (u, v, depth))
    projected = np.stack([vertices @ u, vertices @ v], axis=-1)
    lo, hi = projected.min(axis=(0, 1)), projected.max(axis=(0, 1))
    scale = min((width - 2 * padding) / (hi[0] - lo[0]),
                (height - 2 * padding - 24) / (hi[1] - lo[1]))
    points = (projected - (lo + hi) / 2) * scale
    points[..., 0] += x0 + width / 2
    points[..., 1] = y0 + height / 2 - points[..., 1] + 12
    depths = vertices @ depth
    near, far = depths.max(), depths.min()

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x0, y0, x0 + width, y0 + height), radius=18, fill="#ffffff")
    z_buffer = np.full((image.height, image.width), -np.inf)
    pixels = np.asarray(image).copy()
    for i, triangle in enumerate(points):
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
        # Depth cue: surfaces further from the viewer are darker.
        brightness *= 0.62 + 0.38 * (depths[i].mean() - far) / (near - far)
        current[visible] = z[visible]
        pixels[min_y:max_y + 1, min_x:max_x + 1][visible] = (colors[i] * brightness).astype(np.uint8)
    image.paste(Image.fromarray(pixels))
    ImageDraw.Draw(image).text((x0 + 20, y0 + 14), label, fill="#25333c", font=renderer.font(20))


def render_views():
    tray = mesh("tray.stl", CASE)
    lid = lid_in_place()
    canvas = Image.new("RGB", (1600, 1180), "#e9eef0")
    draw_view(canvas, [tray], (24, 24, 760, 520), (1, 0, 0), (0, 1, 0), (0, 0, 1),
              "TRAY TOP  ·  112.8 x 65.8 mm, screw-head cups")
    draw_view(canvas, [lid], (816, 24, 760, 520), (1, 0, 0), (0, 1, 0), (0, 0, 1),
              "LID TOP  ·  spring tongues: HAT corners and SSD end")
    draw_view(canvas, [tray], (24, 568, 760, 290), (1, 0, 0), (0, 0, 1), (0, -1, 0),
              "FRONT  ·  USB-C, 2x micro HDMI, hook windows")
    draw_view(canvas, [tray], (816, 568, 760, 290), (-1, 0, 0), (0, 0, 1), (0, 1, 0),
              "BACK  ·  vents, hook windows")
    draw_view(canvas, [tray], (24, 882, 760, 274), (0, 1, 0), (0, 0, 1), (1, 0, 0),
              "RIGHT  ·  USB/Ethernet portal, SSD ledge")
    draw_view(canvas, [tray], (816, 882, 760, 274), (0, -1, 0), (0, 0, 1), (-1, 0, 0),
              "LEFT  ·  power button, LED, microSD")
    canvas.save(DIRECTORY / "views.png", optimize=True)


def render_preview():
    tray = mesh("tray.stl", CASE)
    boards = mesh("reference-assembly.stl", BOARD)
    lid = lid_in_place(lift=28.0)
    canvas = Image.new("RGB", (1600, 1000), "#e9eef0")
    draw_view(canvas, [tray, boards, lid], (25, 25, 1550, 950),
              (0.78, -0.62, 0), (-0.37, -0.46, 0.81), (0.37, 0.47, 0.80),
              "RASPBERRY PI 5 + M.2 HAT+ + 2280 NVMe  ·  CASE (lid lifted)", padding=80)
    canvas.save(DIRECTORY / "preview.png", optimize=True)


def tessellate(shape, color):
    points, triangles = shape.tessellate(0.05, 0.2)
    points = np.array([point.toTuple() for point in points])
    vertices = points[np.array(triangles)]
    normals = np.cross(vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    keep = lengths[:, 0] > 1e-12
    colors = np.tile(np.array(color, dtype=np.float64), (keep.sum(), 1))
    return vertices[keep], normals[keep] / lengths[keep], colors


def render_section():
    """True section at the SSD centreline, seen from the front."""
    half = generate.box((-50, 150), (SECTION_Y, 100), (-10, 60))
    boards = [solid for name, solid, _ in generate.envelopes() if "plug" not in name]
    parts = [tessellate(generate.make_tray().intersect(half), CASE),
             tessellate(generate.make_lid().intersect(half), LID_COLOR)]
    parts += [tessellate(solid.intersect(half), BOARD) for solid in boards
              if solid.intersect(half).Volume() > 1e-6]
    canvas = Image.new("RGB", (1600, 640), "#e9eef0")
    draw_view(canvas, parts, (25, 25, 1550, 590), (1, 0, 0), (0, 0, 1), (0, -1, 0),
              f"SECTION y = {SECTION_Y} mm  ·  SSD end on ledge, lid tongue above", padding=60)
    canvas.save(DIRECTORY / "section.png", optimize=True)


if __name__ == "__main__":
    render_views()
    render_preview()
    render_section()
