"""Render the generated binary STLs into orthographic views and a preview.

The STLs are stored in print orientation. They are turned back into the use
orientation of generate.py (x along the wall, y toward the user, z up,
panel top edge at z=0, panel back face at y=0) and shown on a wall with
schematic L-shaped hooks. usage.png adds simplified stand-ins for the headset,
the controllers and the trackers, built from boxes, ellipsoids and tori; they
show the intended placement, not the product shapes.
"""

from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont


DIRECTORY = Path(__file__).resolve().parent
LIGHT = np.array([-0.30, 0.55, 0.78])
LIGHT /= np.linalg.norm(LIGHT)
PART_COLOR = (213, 227, 231)
WALL_COLOR = (236, 230, 220)
HOOK_COLOR = (120, 128, 134)

# Must match generate.py.
HOOK_SPACING = 160.0
SLOT_TOP = -24.0
SLOT_WIDTHS = (8.0, 14.0)
# Schematic hook: 6 mm square shank and an up-turned tip.
HOOK_SIZE = 6.0
HOOK_SHANK = 10.0
HOOK_TIP = 12.0
# Must match generate.py: arm top, controller and tracker pegs.
ARM_TOP = -70.0
CONTROLLER_PEG_X = (-55.0, 55.0)
CONTROLLER_PEG_TOP = -63.0
TRACKER_PEG_X = (-88.0, -44.0, 0.0, 44.0, 88.0)
TRACKER_PEG_TOP = -200.0
PEG_SLOPE = np.tan(np.radians(12.0))
PANEL_THICKNESS = 6.0
DEVICE_COLOR = (64, 69, 76)
VISOR_COLOR = (238, 240, 242)
STRAP_COLOR = (96, 102, 110)
WALL_THICKNESS = 12.0
WALL_MARGIN = 60.0
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

    use = turn(vertices) + np.array([-width / 2, 0.0, 0.0])
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
            if sign < 0:
                p = p[::-1]
            normal = sign * a / np.linalg.norm(a)
            if np.dot(np.cross(p[1] - p[0], p[2] - p[0]), normal) < 0:
                p = p[::-1]
            triangles += [[p[0], p[1], p[2]], [p[0], p[2], p[3]]]
            normals += [normal, normal]
    return np.array(triangles), np.array(normals), np.array(color)


def parametric_mesh(point, normal, u_range, v_range, color, nu=36, nv=18):
    """Triangulate point(u, v) with analytic outward normals normal(u, v)."""
    us = np.linspace(*u_range, nu + 1)
    vs = np.linspace(*v_range, nv + 1)
    grid = np.array([[point(u, v) for v in vs] for u in us])
    triangles, normals = [], []
    for i in range(nu):
        for j in range(nv):
            a, b = grid[i, j], grid[i + 1, j]
            c, d = grid[i + 1, j + 1], grid[i, j + 1]
            n = np.asarray(normal((us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2))
            n = n / np.linalg.norm(n)
            triangles += [[a, b, c], [a, c, d]]
            normals += [n, n]
    return np.array(triangles), np.array(normals), np.array(color)


def ellipsoid(center, semi_axes, color, frame=np.eye(3)):
    center = np.asarray(center, dtype=np.float64)
    a, b, c = semi_axes
    e1, e2, e3 = frame

    def point(u, v):
        return center + a * np.cos(v) * np.cos(u) * e1 + b * np.cos(v) * np.sin(u) * e2 \
            + c * np.sin(v) * e3

    def normal(u, v):
        return np.cos(v) * np.cos(u) / a * e1 + np.cos(v) * np.sin(u) / b * e2 \
            + np.sin(v) / c * e3

    return parametric_mesh(point, normal, (0, 2 * np.pi), (-np.pi / 2, np.pi / 2), color)


def torus(center, major, minor, color):
    """Ring in the x-z plane, parallel to the wall."""
    center = np.asarray(center, dtype=np.float64)
    e1, e2, n = np.eye(3)[0], np.eye(3)[2], np.eye(3)[1]

    def radial(u):
        return np.cos(u) * e1 + np.sin(u) * e2

    def point(u, v):
        return center + (major + minor * np.cos(v)) * radial(u) + minor * np.sin(v) * n

    def normal(u, v):
        return np.cos(v) * radial(u) + np.sin(v) * n

    return parametric_mesh(point, normal, (0, 2 * np.pi), (0, 2 * np.pi), color, 48, 12)


def strap(start, end, width, thickness, across, color):
    """Flat band from start to end; across is the direction of its width."""
    start, end = np.asarray(start, dtype=np.float64), np.asarray(end, dtype=np.float64)
    along = (end - start) / 2
    across = np.asarray(across, dtype=np.float64)
    across = across - np.dot(across, along) / np.dot(along, along) * along
    across = across / np.linalg.norm(across)
    through = np.cross(along, across)
    through = through / np.linalg.norm(through)
    return oriented_box((start + end) / 2,
                        (along, across * width / 2, through * thickness / 2), color)


def headset_stand_in(x_offset):
    """Battery pack on the arm, side straps and the visor leaning on the rib.

    The visor is 195 mm wide (PICO 4 Enterprise specification); the strap
    run from the battery pack to the visor is assumed to be 150 mm.
    """
    x = x_offset
    battery = ellipsoid((x, 38.0, ARM_TOP + 18.0), (45.0, 20.0, 18.0), DEVICE_COLOR)
    visor = oriented_box((x, 71.0, -250.0),
                         ((97.5, 0, 0), (0, 49.0, 0), (0, 0, 50.0)), VISOR_COLOR)
    meshes = [battery, visor]
    for side in (-1.0, 1.0):
        meshes.append(strap((x + side * 40.0, 38.0, ARM_TOP + 14.0),
                            (x + side * 88.0, 60.0, -200.0),
                            30.0, 4.0, (0, 1, 0), STRAP_COLOR))
    return meshes


def controller_stand_ins(x_offset):
    """Tracking ring hanging on each peg, grip below; 134.7 mm tall in total."""
    meshes = []
    ring_y = 30.0
    peg_top = CONTROLLER_PEG_TOP + (ring_y - PANEL_THICKNESS) * PEG_SLOPE
    major, minor = 32.0, 4.5
    for x_peg in CONTROLLER_PEG_X:
        x = x_offset + x_peg
        ring_z = peg_top - (major - minor)
        meshes.append(torus((x, ring_y, ring_z), major, minor, DEVICE_COLOR))
        top = ring_z + major + minor
        grip_semi = (134.7 - (top - (ring_z - major))) / 2 + 10.0
        grip_z = top - 134.7 + grip_semi
        meshes.append(ellipsoid((x, ring_y + 4.0, grip_z), (20.0, 22.0, grip_semi),
                                DEVICE_COLOR))
    return meshes


def tracker_stand_ins(x_offset):
    """Strap loop over each peg and an assumed 38 x 38 x 14 mm tracker below."""
    meshes = []
    for x_peg in TRACKER_PEG_X:
        x = x_offset + x_peg
        top = TRACKER_PEG_TOP + (18.0 - PANEL_THICKNESS) * PEG_SLOPE + 1.0
        meshes.append(oriented_box((x, 18.0, top), ((8.0, 0, 0), (0, 8.0, 0), (0, 0, 1.0)),
                                   STRAP_COLOR))
        for side in (-1.0, 1.0):
            meshes.append(oriented_box((x + side * 7.0, 18.0, top - 13.0),
                                       ((1.0, 0, 0), (0, 8.0, 0), (0, 0, 13.0)),
                                       STRAP_COLOR))
        meshes.append(oriented_box((x, 18.0, top - 26.0 - 19.0),
                                   ((19.0, 0, 0), (0, 7.0, 0), (0, 0, 19.0)),
                                   DEVICE_COLOR))
    return meshes


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


def wall_mesh(x0, x1, z0, z1):
    triangles, normals = box_mesh(x0, x1, -WALL_THICKNESS, 0.0, z0, z1)
    return triangles, normals, np.array(WALL_COLOR)


def hook_meshes(x_offset):
    """Two hooks resting at the top of the slots, as in use."""
    meshes = []
    for x_slot, slot_width in zip((-HOOK_SPACING / 2, HOOK_SPACING / 2), SLOT_WIDTHS):
        x0 = x_offset + x_slot - slot_width / 2
        x1 = x0 + HOOK_SIZE
        z1 = SLOT_TOP
        z0 = z1 - HOOK_SIZE
        for box in (box_mesh(x0, x1, 0.0, HOOK_SHANK, z0, z1),
                    box_mesh(x0, x1, HOOK_SHANK - HOOK_SIZE, HOOK_SHANK, z1, z1 + HOOK_TIP)):
            meshes.append((box[0], box[1], np.array(HOOK_COLOR)))
    return meshes


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
        wall_mesh(left_center - left_width / 2 - WALL_MARGIN,
                  right_center + right_width / 2 + WALL_MARGIN,
                  headset[0][..., 2].min() - WALL_MARGIN, WALL_MARGIN),
        *hook_meshes(left_center), *hook_meshes(right_center),
    ]
    canvas = Image.new("RGB", (1600, 1000), "#e9eef0")
    draw_view(canvas, meshes, (25, 25, 1550, 950), *oblique((-0.45, 0.80, 0.50)),
              "PICO 4  ·  WALL HANGERS", padding=80)
    canvas.save(DIRECTORY / "preview.png", optimize=True)


def render_usage(headset, accessories):
    left_width, right_width = headset[2], accessories[2]
    left_center = -(right_width + MODULE_GAP) / 2
    right_center = (left_width + MODULE_GAP) / 2
    left = [part_mesh(headset[0], headset[1], left_center),
            *hook_meshes(left_center), *headset_stand_in(left_center)]
    right = [part_mesh(accessories[0], accessories[1], right_center),
             *hook_meshes(right_center), *controller_stand_ins(right_center),
             *tracker_stand_ins(right_center)]
    wall = wall_mesh(left_center - left_width / 2 - WALL_MARGIN,
                     right_center + right_width / 2 + WALL_MARGIN,
                     -300.0 - WALL_MARGIN, WALL_MARGIN)
    canvas = Image.new("RGB", (1600, 1560), "#e9eef0")
    draw_view(canvas, [*left, *right, wall], (25, 25, 1550, 950),
              *oblique((-0.45, 0.80, 0.50)),
              "IN USE  ·  SIMPLIFIED STAND-INS FOR HEADSET, CONTROLLERS AND TRACKERS",
              padding=70)
    for column, (name, meshes) in enumerate((("HEADSET MODULE", left),
                                             ("ACCESSORY MODULE", right))):
        draw_view(canvas, meshes, (25 + column * 787, 1000, 763, 535),
                  (0, 1, 0), (0, 0, 1), (1, 0, 0), f"{name}  ·  SIDE", padding=36)
    canvas.save(DIRECTORY / "usage.png", optimize=True)


if __name__ == "__main__":
    loaded = {name: read_binary_stl(DIRECTORY / name)
              for name in ("headset.stl", "accessories.stl")}
    printed = [(v, n, np.array(PART_COLOR)) for v, n in loaded.values()]
    headset = to_use_orientation(*loaded["headset.stl"])
    accessories = to_use_orientation(*loaded["accessories.stl"])
    render_views(headset, accessories, printed)
    render_preview(headset, accessories)
    render_usage(headset, accessories)
