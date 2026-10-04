"""Render the catalogue, cap and part previews from the CAD models.

The images are deterministic: a fixed orthographic camera, a software
z-buffer and Pillow, with no GPU or windowing system.
"""

from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cap
import head
import toppers


DIRECTORY = Path(__file__).resolve().parent
IMAGES = DIRECTORY / "images"
BACKGROUND = (236, 240, 242)
SUPERSAMPLE = 2
LIGHT = np.array([-0.35, -0.55, 0.76])
LIGHT /= np.linalg.norm(LIGHT)
PALETTE = [(244, 178, 190), (250, 214, 165), (190, 222, 196), (178, 206, 236),
           (214, 196, 238), (247, 232, 170), (232, 190, 168), (200, 226, 232)]
HEAD_COLOUR = (226, 229, 232)
SCREEN_COLOUR = (34, 37, 42)
FACE_COLOUR = (245, 247, 250)


@dataclass
class Mesh:
    triangles: np.ndarray          # (n, 3, 3)
    colour: tuple[int, int, int]


def tessellate(shape: cq.Shape, colour: tuple[int, int, int],
               tolerance: float = 0.08) -> Mesh:
    vertices, faces = shape.tessellate(tolerance, 0.3)
    points = np.array([v.toTuple() for v in vertices], dtype=np.float64)
    triangles = np.round(points[np.array(faces, dtype=np.int64)], 6) + 0.0
    # The mesher's triangle order varies between runs. Rotating each triangle
    # to start at its smallest vertex and sorting the triangles keeps the
    # rasterisation, and therefore the images, reproducible.
    first = np.array([min(range(3), key=lambda i: tuple(t[i])) for t in triangles])
    order = (np.arange(3)[None, :] + first[:, None]) % 3
    triangles = np.take_along_axis(triangles, order[:, :, None], axis=1)
    keys = triangles.reshape(len(triangles), 9)
    return Mesh(triangles[np.lexsort(keys.T[::-1])], colour)


def head_proxy() -> list[Mesh]:
    """Simplified StackChan head and base for context, not a printable part."""
    shell = head.envelope(0.0, holes=False)
    for side in (-1, 1):
        for y in head.SIDE_HOLE_Y:
            shell = shell.cut(cq.Solid.makeCylinder(
                2.4, 2.0, cq.Vector(side * 27.5, y, head.SIDE_HOLE_Z),
                cq.Vector(-side, 0, 0)))
    screen = cq.Solid.makeBox(46, 0.6, 36, cq.Vector(-23, head.CORE_FRONT - 0.5, -45))
    eyes = [cq.Solid.makeCylinder(2.2, 0.6, cq.Vector(x, head.CORE_FRONT - 0.6, -24),
                                  cq.Vector(0, 1, 0)) for x in (-11, 11)]
    mouth = cq.Solid.makeBox(12, 0.6, 1.6, cq.Vector(-6, head.CORE_FRONT - 0.7, -34))
    neck = cq.Solid.makeBox(40, 40, 8, cq.Vector(-20, 4, -62))
    base = cq.Solid.makeCylinder(25, 8.5, cq.Vector(0, 16, -70.5))
    return [tessellate(shell, HEAD_COLOUR, 0.15), tessellate(screen, SCREEN_COLOUR),
            *[tessellate(e, FACE_COLOUR) for e in eyes], tessellate(mouth, FACE_COLOUR),
            tessellate(neck, (178, 182, 188), 0.2), tessellate(base, (120, 124, 130), 0.2)]


def camera(direction: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Orthographic basis looking from the given direction towards the origin."""
    towards_viewer = np.asarray(direction, dtype=np.float64)
    towards_viewer /= np.linalg.norm(towards_viewer)
    right = np.cross(np.array([0.0, 0.0, 1.0]), towards_viewer)
    if np.linalg.norm(right) < 1e-6:
        right = np.array([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(towards_viewer, right)
    return right, up, towards_viewer


def draw(image: Image.Image, meshes: list[Mesh], region: tuple[int, int, int, int],
         direction: tuple[float, float, float], label: str = "",
         bounds: tuple[np.ndarray, np.ndarray] | None = None, padding: int = 24) -> None:
    """Rasterise meshes into a rounded tile of the image."""
    x0, y0, width, height = region
    s = SUPERSAMPLE
    right, up, viewer = camera(direction)
    all_points = np.concatenate([m.triangles.reshape(-1, 3) for m in meshes])
    projected = np.stack([all_points @ right, all_points @ up], axis=-1)
    lo, hi = bounds if bounds is not None else (projected.min(0), projected.max(0))
    label_space = 30 if label else 0
    scale = min((width - 2 * padding) / (hi[0] - lo[0]),
                (height - 2 * padding - label_space) / (hi[1] - lo[1])) * s
    centre = (lo + hi) / 2
    w, h = width * s, height * s
    colour = np.zeros((h, w, 3), dtype=np.float64)
    colour[:] = (255, 255, 255)
    depth = np.full((h, w), -np.inf)
    for mesh in meshes:
        tri = mesh.triangles
        normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        length = np.linalg.norm(normal, axis=1)
        keep = length > 1e-12
        tri, normal = tri[keep], normal[keep] / length[keep, None]
        # Tessellation winding is not guaranteed; visibility relies on the
        # depth buffer and the normal is turned towards the viewer.
        normal = np.where((normal @ viewer)[:, None] < 0, -normal, normal)
        screen = np.stack([(tri @ right - centre[0]) * scale + w / 2,
                           h / 2 + label_space * s / 2 - (tri @ up - centre[1]) * scale],
                          axis=-1)
        z = tri @ viewer
        shade = np.clip(0.62 + 0.38 * (normal @ LIGHT), 0.35, 1.0)
        base = np.array(mesh.colour, dtype=np.float64)
        for i in range(len(tri)):
            a, b, c = screen[i]
            min_x = max(0, int(np.floor(min(a[0], b[0], c[0]))))
            max_x = min(w - 1, int(np.ceil(max(a[0], b[0], c[0]))))
            min_y = max(0, int(np.floor(min(a[1], b[1], c[1]))))
            max_y = min(h - 1, int(np.ceil(max(a[1], b[1], c[1]))))
            if min_x > max_x or min_y > max_y:
                continue
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) < 1e-12:
                continue
            yy, xx = np.mgrid[min_y:max_y + 1, min_x:max_x + 1]
            px, py = xx + 0.5, yy + 0.5
            wa = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / denominator
            wb = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / denominator
            wc = 1.0 - wa - wb
            inside = (wa >= -1e-9) & (wb >= -1e-9) & (wc >= -1e-9)
            zz = wa * z[i, 0] + wb * z[i, 1] + wc * z[i, 2]
            window = depth[min_y:max_y + 1, min_x:max_x + 1]
            visible = inside & (zz > window)
            if not visible.any():
                continue
            window[visible] = zz[visible]
            colour[min_y:max_y + 1, min_x:max_x + 1][visible] = base * shade[i]
    tile = Image.fromarray(colour.clip(0, 255).astype(np.uint8)).resize(
        (width, height), Image.Resampling.LANCZOS)
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), 16, fill=255)
    image.paste(tile, (x0, y0), mask)
    if label:
        ImageDraw.Draw(image).text((x0 + 16, y0 + 12), label, fill=(37, 51, 60),
                                   font=ImageFont.load_default(size=19))


def worn_meshes(topper: toppers.TopperSet, colour: tuple[int, int, int],
                cap_mesh: Mesh) -> list[Mesh]:
    meshes = [Mesh(cap_mesh.triangles, colour)]
    for piece, full, _ in toppers.build_set(topper):
        meshes.append(tessellate(full.moved(toppers.placement(piece)), colour))
    return meshes


def render_catalogue(proxy: list[Mesh], cap_solid: cq.Shape) -> None:
    columns, size = 5, 320
    rows = -(-len(toppers.SETS) // columns)
    canvas = Image.new("RGB", (columns * (size + 12) + 12, rows * (size + 12) + 12),
                       BACKGROUND)
    view = (0.42, -1.0, 0.32)
    cap_mesh = tessellate(cap_solid, PALETTE[0])
    right, up, _ = camera(view)
    # Shared bounds so that every tile has the same scale.
    corners = np.array([[x, y, z] for x in (-40, 40) for y in (-16, 50) for z in (-60, 44)])
    bounds = (np.array([corners @ right, corners @ up]).min(1),
              np.array([corners @ right, corners @ up]).max(1))
    for index, topper in enumerate(toppers.SETS):
        colour = PALETTE[index % len(PALETTE)]
        meshes = proxy + worn_meshes(topper, colour, cap_mesh)
        x = 12 + (index % columns) * (size + 12)
        y = 12 + (index // columns) * (size + 12)
        draw(canvas, meshes, (x, y, size, size), view, topper.title, bounds, 14)
    canvas.save(IMAGES / "catalogue.png", optimize=True)


def render_cap(proxy: list[Mesh], cap_solid: cq.Shape) -> None:
    canvas = Image.new("RGB", (1300, 440), BACKGROUND)
    worn = proxy + [tessellate(cap_solid, PALETTE[3])]
    draw(canvas, worn, (12, 12, 416, 416), (0.75, 0.9, 0.7), "WORN, REAR VIEW")
    printed = [tessellate(cap.to_print(cap_solid), PALETTE[3])]
    draw(canvas, printed, (442, 12, 416, 416), (0.6, -0.8, 0.9),
         "AS PRINTED, TOP ON BED")
    detail = [tessellate(cap_solid, PALETTE[3])]
    draw(canvas, detail, (872, 12, 416, 416), (-1.0, 0.25, -0.35),
         "INSIDE: DETENT AND FLEXURE")
    canvas.save(IMAGES / "cap.png", optimize=True)


def render_parts() -> None:
    columns, size = 5, 240
    rows = -(-len(toppers.SETS) // columns)
    canvas = Image.new("RGB", (columns * (size + 10) + 10, rows * (size + 10) + 10),
                       BACKGROUND)
    for index, topper in enumerate(toppers.SETS):
        colour = PALETTE[index % len(PALETTE)]
        meshes = [tessellate(full, colour) for _, full, _ in toppers.build_set(topper)]
        offset = 0.0
        laid = []
        for mesh in meshes:
            lo = mesh.triangles[..., 0].min()
            hi = mesh.triangles[..., 0].max()
            shifted = mesh.triangles.copy()
            shifted[..., 0] += offset - lo
            laid.append(Mesh(shifted, mesh.colour))
            offset += hi - lo + 4.0
        x = 10 + (index % columns) * (size + 10)
        y = 10 + (index // columns) * (size + 10)
        draw(canvas, laid, (x, y, size, size), (0.0, -0.35, 1.0), topper.title, None, 16)
    canvas.save(IMAGES / "parts.png", optimize=True)


def main() -> None:
    IMAGES.mkdir(exist_ok=True)
    proxy = head_proxy()
    cap_solid = cap.make_cap()
    render_cap(proxy, cap_solid)
    render_parts()
    render_catalogue(proxy, cap_solid)


if __name__ == "__main__":
    main()
