"""Render the actual basket STL and a three-tier assembly."""

import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from generate import BASE_HEIGHT, STACK_PITCH, TRAY_Y, TRAY_Z


DIRECTORY = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "stl_renderer", DIRECTORY.parent / "mi-vacuum-cleaner-mini" / "render.py"
)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def main():
    vertices, normals = renderer.read_binary_stl(DIRECTORY / "rack.stl")
    views = Image.new("RGB", (1600, 1200), "#e9eef0")
    for region, u, v, depth, label in (
        ((24, 24, 960, 560), (1, 0, 0), (0, 1, 0), (0, 0, 1),
         "TOP | 220 x 140 mm"),
        ((24, 608, 960, 360), (1, 0, 0), (0, 0, 1), (0, -1, 0),
         "FRONT | 220 x 79.5 mm"),
        ((1008, 24, 568, 944), (0, 1, 0), (0, 0, 1), (1, 0, 0),
         "END | 140 x 79.5 mm"),
    ):
        renderer.draw_view(views, vertices, normals, region, u, v, depth, label)
    draw = ImageDraw.Draw(views)
    for index, line in enumerate((
        "Mesh: 4 x 4 mm openings / 2 mm ribs | Floor top: Z=5 | Rim top: Z=18",
        "Stack pitch: 75 mm | Peg: 6 x 6 x 4.5 mm | Socket: 6.8 x 6.8 x 5 mm",
        "Posts: 14 x 14 mm | Centers: X=+/-103, Y=+/-63 mm | Bottom air channels: 2 mm high",
        "3 tiers: 229.5 mm high | 4 tiers: 304.5 mm high | Prototype: not load-tested",
    )):
        draw.text((40, 994 + index * 46), line, fill="#25333c", font=renderer.font(23))
    views.save(DIRECTORY / "views.png", optimize=True)
    preview = Image.new("RGB", (1400, 1050), "#e9eef0")
    u, v, depth = (0.866, -0.5, 0), (0.25, 0.433, 0.866), (-0.433, -0.75, 0.5)
    renderer.draw_view(preview, vertices, normals, (24, 24, 1352, 1002), u, v, depth,
                       "STACKABLE CHILI BASKET | One printed part", padding=65)
    preview.save(DIRECTORY / "preview.png", optimize=True)
    assembly = Image.new("RGB", (1400, 1400), "#e9eef0")
    base_v, base_n = renderer.read_binary_stl(DIRECTORY / "base.stl")
    tray_v, tray_n = renderer.read_binary_stl(DIRECTORY / "drip-tray.stl")
    stacked = np.concatenate(
        [vertices + np.array([0, 0, BASE_HEIGHT + STACK_PITCH * i]) for i in range(3)]
        + [base_v, tray_v + np.array([0, TRAY_Y, TRAY_Z])])
    all_normals = np.concatenate([np.tile(normals, (3, 1)), base_n, tray_n])
    renderer.draw_view(assembly, stacked, all_normals,
                       (24, 24, 1352, 1352), u, v, depth,
                       "THREE TIERS + BASE + REMOVABLE DRIP TRAY", padding=70)
    assembly.save(DIRECTORY / "assembly.png", optimize=True)
    drawer = Image.new("RGB", (1400, 1100), "#e9eef0")
    pulled = np.concatenate([vertices + np.array([0, 0, BASE_HEIGHT]), base_v,
                             tray_v + np.array([0, TRAY_Y - 85, TRAY_Z])])
    renderer.draw_view(drawer, pulled, np.concatenate([normals, base_n, tray_n]),
                       (24, 24, 1352, 1052), u, v, depth,
                       "DRIP TRAY | Pull forward to empty | 23 mm air gap", padding=70)
    drawer.save(DIRECTORY / "drawer.png", optimize=True)
    accessory = Image.new("RGB", (1600, 1180), "#e9eef0")
    for mesh, face_normals, region, u2, v2, d2, label in (
        (base_v, base_n, (24, 24, 764, 480), (1, 0, 0), (0, 1, 0), (0, 0, 1),
         "BASE TOP | 244 x 164 mm"),
        (base_v, base_n, (24, 528, 764, 300), (1, 0, 0), (0, 0, 1), (0, -1, 0),
         "BASE FRONT | Height 42.5 mm"),
        (tray_v, tray_n, (812, 24, 764, 480), (1, 0, 0), (0, 1, 0), (0, 0, 1),
         "TRAY TOP | 228 x 168 mm incl. grip"),
        (tray_v, tray_n, (812, 528, 764, 300), (0, 1, 0), (0, 0, 1), (1, 0, 0),
         "TRAY END | Height 12 mm"),
    ):
        renderer.draw_view(accessory, mesh, face_normals, region, u2, v2, d2, label)
    draw = ImageDraw.Draw(accessory)
    for index, line in enumerate((
        "Base: basket seat Z=38 | Tray rails Z=3 | Inward supports: 45 degrees",
        "Tray body: 228 x 156 x 12 mm | Floor / walls: 2.4 mm | No drain holes",
        "Installed tray center Y=-2 | Basket bottom to tray rim: 23 mm",
        "3 tiers with base: 267.5 mm | 4 tiers with base: 342.5 mm",
        "Fit/withdrawal checked in CAD. Printed watertightness and load capacity untested.",
    )):
        draw.text((40, 868 + index * 48), line, fill="#25333c", font=renderer.font(23))
    accessory.save(DIRECTORY / "accessories.png", optimize=True)


if __name__ == "__main__":
    main()
