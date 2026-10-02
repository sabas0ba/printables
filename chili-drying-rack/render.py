"""Render the actual STL using the repository's existing software renderer."""

import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw


DIRECTORY = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "stl_renderer", DIRECTORY.parent / "mi-vacuum-cleaner-mini" / "render.py"
)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def main():
    vertices, normals = renderer.read_binary_stl(DIRECTORY / "rack.stl")
    views = Image.new("RGB", (1600, 1000), "#e9eef0")
    for region, u, v, depth, label in (
        ((24, 24, 1552, 430), (1, 0, 0), (0, 1, 0), (0, 0, 1),
         "TOP | 220 x 35 mm | 8 positions, pitch 27 mm"),
        ((24, 478, 1100, 250), (1, 0, 0), (0, 0, 1), (0, -1, 0),
         "FRONT | 220 x 5 mm"),
        ((1148, 478, 428, 250), (0, 1, 0), (0, 0, 1), (1, 0, 0),
         "END | 35 x 5 mm"),
    ):
        renderer.draw_view(views, vertices, normals, region, u, v, depth, label)
    draw = ImageDraw.Draw(views)
    for index, line in enumerate((
        "Cord slots: 2.2 mm | Top knot seats: diameter 6 mm, depth 1.5 mm",
        "Suspension: 4 holes, diameter 4 mm | Centers: X = +/-102, Y = +/-10.5 mm",
        "Outer corner radius: 3 mm | Top/bottom edge bevel: 0.35 mm | Units: mm",
        "Flat base down for printing. Knot seats up during use. Prototype: not load-tested.",
    )):
        draw.text((40, 774 + index * 46), line, fill="#25333c", font=renderer.font(23))
    views.save(DIRECTORY / "views.png", optimize=True)
    preview = Image.new("RGB", (1600, 800), "#e9eef0")
    renderer.draw_view(preview, vertices, normals, (24, 24, 1552, 752),
                       (0.94, -0.34, 0), (0.17, 0.47, 0.866),
                       (-0.294, -0.814, 0.5),
                       "CHILI DRYING RACK | 8 cords | 220 x 35 x 5 mm", padding=65)
    preview.save(DIRECTORY / "preview.png", optimize=True)


if __name__ == "__main__":
    main()
