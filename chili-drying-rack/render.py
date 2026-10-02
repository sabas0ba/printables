"""Render the actual basket STL and a three-tier assembly."""

import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from generate import STACK_PITCH


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
    stacked = np.concatenate([vertices + np.array([0, 0, STACK_PITCH * i])
                              for i in range(3)])
    renderer.draw_view(assembly, stacked, np.tile(normals, (3, 1)),
                       (24, 24, 1352, 1352), u, v, depth,
                       "THREE TIERS | Same part x 3 | No added hardware", padding=70)
    assembly.save(DIRECTORY / "assembly.png", optimize=True)


if __name__ == "__main__":
    main()
