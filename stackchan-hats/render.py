"""Render the catalogue, cap and part previews from the CAD models.

The images are deterministic: a fixed orthographic camera, a software
z-buffer and Pillow, with no GPU or windowing system.
"""

from dataclasses import dataclass
import json
from pathlib import Path

import cadquery as cq
from OCP.OSD import OSD_ThreadPool
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cap
import drapes
import head
import integral
import shells
import toppers


# Parallel booleans and meshing in OCC can split faces differently from run
# to run. One worker thread keeps the outputs byte-for-byte reproducible.
OSD_ThreadPool.DefaultPool_s(1)

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
    """Simplified StackChan head for context, not a printable part."""
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
    return [tessellate(shell, HEAD_COLOUR, 0.15), tessellate(screen, SCREEN_COLOUR),
            *[tessellate(e, FACE_COLOUR) for e in eyes], tessellate(mouth, FACE_COLOUR)]


def body_proxy() -> list[Mesh]:
    """Body below the head and the base, from the measured bands and profile."""
    z0, _, y0, y1, half = head.BODY_BANDS[0]
    neck = cq.Solid.makeBox(2 * half, y1 - y0, -head.HEAD_HEIGHT - z0,
                            cq.Vector(-half, y0, z0))
    top = head.BASE_PROFILE[1][1]
    base = (cq.Workplane("XY", origin=(0, head.YAW_AXIS_Y + 4.75, head.DESK))
            .sketch().rect(48.0, 56.0).vertices().fillet(8.0).finalize()
            .extrude(top - head.DESK).val())
    return [tessellate(neck, (178, 182, 188), 0.2), tessellate(base, (120, 124, 130), 0.2)]


def pitched(meshes: list[Mesh], degrees: float) -> list[Mesh]:
    """Rotate head-fixed meshes about the pitch axis."""
    result = []
    for mesh in meshes:
        flat = head.pitch(mesh.triangles.reshape(-1, 3), degrees)
        result.append(Mesh(flat.reshape(mesh.triangles.shape), mesh.colour))
    return result


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


SMALL_ROWS = ("front", "rear")
LARGE_KEYS = ("palm-tree",)         # front-row sets too tall for the catalogue grid
SHELL_COLOURS = {
    "shell-house": (232, 190, 168), "shell-house-roof": (176, 84, 64),
    "shell-tofu": (246, 244, 236),
    "shell-pudding": (247, 222, 150), "shell-norimaki": (96, 104, 96),
    "shell-sakuramochi": (244, 190, 204), "shell-omurice": (248, 214, 110),
    "shell-onigiri-triangle": (244, 244, 240), "shell-onigiri-round": (244, 244, 240),
    "shell-shumai": (240, 226, 196), "shell-bread": (240, 212, 160),
}
# Preview colour of the raised front details; the parts print in one colour.
RELIEF_COLOURS = {
    "shell-house": (150, 96, 80), "shell-house-roof": (120, 56, 44),
    "shell-tofu": (120, 72, 40),
    "shell-pudding": (150, 90, 40), "shell-norimaki": (60, 66, 60),
    "shell-sakuramochi": (120, 170, 110), "shell-omurice": (210, 60, 50),
    "shell-onigiri-triangle": (52, 60, 56), "shell-onigiri-round": (52, 60, 56),
    "shell-bread": (196, 140, 80),
}
DRAPE_COLOURS = {
    "drape-soy-sauce": (92, 54, 34), "drape-caramel": (164, 96, 40),
    "drape-nori-band": (46, 54, 48), "drape-nori-wrap": (46, 54, 48),
    "drape-sakura-leaf": (122, 168, 98), "drape-crust": (196, 128, 66),
}
# Toppings shown with a drape, and their colours.
DRAPE_TOPPINGS = {"drape-soy-sauce": "yakumi", "drape-caramel": "cherry",
                  "drape-nori-band": "umeboshi"}
TOPPING_COLOURS = {"yakumi": (214, 200, 120), "cherry": (198, 40, 52),
                   "umeboshi": (186, 52, 64)}
ROOF_KEY = "shell-house-roof"
RELIEF_SHIFT = cq.Vector(0, -0.05, 0)   # in front of the coincident shell faces


def small_sets() -> list[toppers.TopperSet]:
    return [t for t in toppers.SETS
            if t.pieces[0].row in SMALL_ROWS and t.key not in LARGE_KEYS]


def large_sets() -> list[toppers.TopperSet]:
    return [t for t in toppers.SETS if t not in small_sets()]


def render_catalogue(proxy: list[Mesh], cap_solid: cq.Shape) -> None:
    columns, size = 5, 320
    rows = -(-len(small_sets()) // columns)
    canvas = Image.new("RGB", (columns * (size + 12) + 12, rows * (size + 12) + 12),
                       BACKGROUND)
    view = (0.42, -1.0, 0.32)
    cap_mesh = tessellate(cap_solid, PALETTE[0])
    right, up, _ = camera(view)
    # Shared bounds so that every tile has the same scale.
    corners = np.array([[x, y, z] for x in (-40, 40) for y in (-16, 50) for z in (-60, 44)])
    bounds = (np.array([corners @ right, corners @ up]).min(1),
              np.array([corners @ right, corners @ up]).max(1))
    for index, topper in enumerate(small_sets()):
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


def render_large(proxy: list[Mesh], cap_solid: cq.Shape) -> None:
    """Integral variants and the large plug-in sets, worn."""
    items: list[tuple[str, list[Mesh]]] = []
    for index, variant in enumerate(integral.VARIANTS):
        colour = PALETTE[(index + 2) % len(PALETTE)]
        items.append((variant.title, [tessellate(integral.build(variant), colour)]))
    large = large_sets()
    cap_mesh = tessellate(cap_solid, PALETTE[0])
    for index, topper in enumerate(large):
        colour = PALETTE[(index + 4) % len(PALETTE)]
        items.append((topper.title, worn_meshes(topper, colour, cap_mesh)))
    columns, size = 5, 360
    rows = -(-len(items) // columns)
    canvas = Image.new("RGB", (columns * (size + 12) + 12, rows * (size + 12) + 12),
                       BACKGROUND)
    view = (0.95, -0.8, 0.45)
    right, up, _ = camera(view)
    corners = np.array([[x, y, z] for x in (-80, 80) for y in (-20, 52)
                        for z in (-72, 60)])
    bounds = (np.array([corners @ right, corners @ up]).min(1),
              np.array([corners @ right, corners @ up]).max(1))
    for index, (title, meshes) in enumerate(items):
        x = 12 + (index % columns) * (size + 12)
        y = 12 + (index // columns) * (size + 12)
        draw(canvas, proxy + meshes, (x, y, size, size), view, title, bounds, 12)
    canvas.save(IMAGES / "large.png", optimize=True)


def render_shells(proxy: list[Mesh]) -> None:
    """Head-covering shells, worn, titled with their allowed look-up angle."""
    report = json.loads((DIRECTORY / "validation.json").read_text())
    columns, size = 5, 360
    rows = -(-len(shells.SHELLS) // columns)
    canvas = Image.new("RGB", (columns * (size + 12) + 12, rows * (size + 12) + 12),
                       BACKGROUND)
    view = (0.42, -1.0, 0.32)
    right, up, _ = camera(view)
    corners = np.array([[x, y, z] for x in (-50, 50) for y in (-16, 50)
                        for z in (-60, 52)])
    bounds = (np.array([corners @ right, corners @ up]).min(1),
              np.array([corners @ right, corners @ up]).max(1))
    for index, shell in enumerate(shells.SHELLS):
        meshes = [tessellate(shells.build(shell), SHELL_COLOURS[shell.key])]
        outline = shells.outline_face(shell.silhouette())
        cutters = shells.engravings(shell, outline)
        for relief in shells.reliefs(shell, outline):
            for cutter in cutters:
                relief = relief.cut(cutter)
            meshes.append(tessellate(relief.translate(RELIEF_SHIFT),
                                     RELIEF_COLOURS[shell.key]))
        angle = report[shell.key]["allowed_pitch_deg"]
        x = 12 + (index % columns) * (size + 12)
        y = 12 + (index // columns) * (size + 12)
        draw(canvas, proxy + meshes, (x, y, size, size), view,
             f"{shell.title}, up to {angle:.0f} deg", bounds, 12)
    canvas.save(IMAGES / "shells.png", optimize=True)


def render_drapes(proxy: list[Mesh]) -> None:
    """Food drapes on the head, with their toppings, and the house roof."""
    items: list[tuple[str, list[Mesh]]] = []
    by_key = {t.key: t for t in toppers.SETS}
    for drape in drapes.DRAPES:
        meshes = [tessellate(drapes.build(drape), DRAPE_COLOURS[drape.key])]
        topping = DRAPE_TOPPINGS.get(drape.key)
        if topping:
            meshes += [tessellate(full.moved(toppers.placement(piece)),
                                  TOPPING_COLOURS[topping])
                       for piece, full, _ in toppers.build_set(by_key[topping])]
        items.append((drape.title, meshes))
    roof = next(s for s in shells.SHELLS if s.key == ROOF_KEY)
    outline = shells.outline_face(roof.silhouette())
    meshes = [tessellate(shells.build(roof), SHELL_COLOURS[ROOF_KEY])]
    meshes += [tessellate(r.translate(RELIEF_SHIFT), RELIEF_COLOURS[ROOF_KEY])
               for r in shells.reliefs(roof, outline)]
    items.append((roof.title, meshes))
    columns, size = 4, 400
    rows = -(-len(items) // columns)
    canvas = Image.new("RGB", (columns * (size + 12) + 12, rows * (size + 12) + 12),
                       BACKGROUND)
    view = (0.55, -1.0, 0.3)
    right, up, _ = camera(view)
    corners = np.array([[x, y, z] for x in (-42, 42) for y in (-18, 50)
                        for z in (-60, 44)])
    bounds = (np.array([corners @ right, corners @ up]).min(1),
              np.array([corners @ right, corners @ up]).max(1))
    for index, (title, meshes) in enumerate(items):
        x = 12 + (index % columns) * (size + 12)
        y = 12 + (index // columns) * (size + 12)
        draw(canvas, proxy + meshes, (x, y, size, size), view, title, bounds, 12)
    canvas.save(IMAGES / "drapes.png", optimize=True)


def render_motion(head_meshes: list[Mesh], body: list[Mesh], cap_solid: cq.Shape) -> None:
    """Side views over the pitch range with large pieces worn."""
    colour = PALETTE[4]
    worn = [tessellate(cap_solid, colour)]
    for key in ("dragon-wings", "dragon-tail"):
        topper = next(t for t in toppers.SETS if t.key == key)
        worn += [tessellate(full.moved(toppers.placement(piece)), colour)
                 for piece, full, _ in toppers.build_set(topper)]
    angles = (0.0, 45.0, head.PITCH_RANGE_DEG[1])
    size = 420
    canvas = Image.new("RGB", (len(angles) * (size + 12) + 12, size + 24), BACKGROUND)
    view = (1.0, 0.0, 0.0)
    right, up, _ = camera(view)
    corners = np.array([[0, y, z] for y in (-60, 90) for z in (-75, 75)])
    bounds = (np.array([corners @ right, corners @ up]).min(1),
              np.array([corners @ right, corners @ up]).max(1))
    for index, angle in enumerate(angles):
        meshes = body + pitched(head_meshes + worn, angle)
        draw(canvas, meshes, (12 + index * (size + 12), 12, size, size), view,
             f"PITCH {angle:.0f} DEG", bounds, 12)
    canvas.save(IMAGES / "motion.png", optimize=True)


def main() -> None:
    IMAGES.mkdir(exist_ok=True)
    for stale in IMAGES.glob("*.png"):
        stale.unlink()
    head_meshes = head_proxy()
    body = body_proxy()
    proxy = head_meshes + body
    cap_solid = cap.make_cap()
    render_cap(proxy, cap_solid)
    render_parts()
    render_catalogue(proxy, cap_solid)
    render_large(proxy, cap_solid)
    render_shells(proxy)
    render_drapes(proxy)
    render_motion(head_meshes, body, cap_solid)


if __name__ == "__main__":
    main()
